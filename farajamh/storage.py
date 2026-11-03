from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .common import canonical, now, require


class Store:
    """SQLite transactions; immutable source and append-only revisions/events at application level."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT, version INTEGER, body TEXT NOT NULL,
            PRIMARY KEY(id,version), FOREIGN KEY(id) REFERENCES sources(id));
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, actor TEXT, action TEXT, entity TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS senses(id TEXT, version INTEGER, body TEXT,
            PRIMARY KEY(id,version));
        CREATE TABLE IF NOT EXISTS credentials(identity TEXT PRIMARY KEY, salt BLOB NOT NULL,
            hash BLOB NOT NULL, updated TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS immutable_source_update BEFORE UPDATE ON sources
            BEGIN SELECT RAISE(ABORT,'immutable source'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_source_delete BEFORE DELETE ON sources
            BEGIN SELECT RAISE(ABORT,'immutable source'); END;
        ''')
        for table in ("audit", "revisions", "senses"):
            for action in ("UPDATE", "DELETE"):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")

    @contextmanager
    def transaction(self):
        nested = self.db.in_transaction
        if nested:
            self.db.execute("SAVEPOINT nested_action")
        else:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("RELEASE nested_action" if nested else "COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK TO nested_action" if nested else "ROLLBACK")
            if nested: self.db.execute("RELEASE nested_action")
            raise

    def event(self, actor: str, action: str, entity: str, body: dict):
        self.db.execute("INSERT INTO audit(timestamp,actor,action,entity,body) VALUES(?,?,?,?,?)",
                        (now(), actor, action, entity, canonical(body)))

    def get(self, uid: str) -> dict:
        row = self.db.execute("SELECT body FROM revisions WHERE id=? ORDER BY version DESC LIMIT 1", (uid,)).fetchone()
        require(row is not None, "Unknown utterance")
        return json.loads(row[0])

    def save(self, dossier: dict, expected: int | None = None):
        uid = dossier["source"]["utterance_id"]
        row = self.db.execute("SELECT MAX(version) FROM revisions WHERE id=?", (uid,)).fetchone()
        version = row[0] or 0
        if expected is not None:
            require(expected == version, "Stale version: refresh the dossier")
        original = self.db.execute("SELECT body FROM sources WHERE id=?", (uid,)).fetchone()
        body = canonical(dossier["source"])
        if original:
            require(original[0] == body, "Original source/context immutable; use a new utterance ID with correction reference")
        else:
            self.db.execute("INSERT INTO sources VALUES(?,?)", (uid, body))
        dossier["version"] = version + 1
        self.db.execute("INSERT INTO revisions VALUES(?,?,?)", (uid, version + 1, canonical(dossier)))

    def all(self) -> list[dict]:
        return [self.get(r[0]) for r in self.db.execute("SELECT id FROM sources ORDER BY id")]

    def senses(self) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute('''SELECT s.body FROM senses s
            JOIN (SELECT id,MAX(version) v FROM senses GROUP BY id) x ON s.id=x.id AND s.version=x.v''')]

    def audit(self) -> list[dict]:
        return [dict(r) | {"body": json.loads(r["body"])} for r in self.db.execute("SELECT * FROM audit ORDER BY seq")]

    # Only a salted scrypt hash is stored; the token itself never reaches the database.
    SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}

    def set_credential(self, identity: str, token: str):
        require(len(token) >= 16, "Token must be at least 16 characters")
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(token.encode(), salt=salt, **self.SCRYPT)
        with self.transaction():
            self.db.execute("INSERT OR REPLACE INTO credentials VALUES(?,?,?,?)", (identity, salt, digest, now()))
            self.event(identity, "credential_set", identity, {"method": "scrypt"})

    def check_credential(self, identity: str, token: str) -> bool:
        row = self.db.execute("SELECT salt,hash FROM credentials WHERE identity=?", (identity,)).fetchone()
        if row is None: return False
        return hmac.compare_digest(hashlib.scrypt(token.encode(), salt=row["salt"], **self.SCRYPT), row["hash"])
