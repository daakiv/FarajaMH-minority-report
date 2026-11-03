from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from time import monotonic
from threading import Lock, local
import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS

from . import network
from .ranking import rank
from .common import RESOURCES, canonical, digest, file_hash, now, require, resolve


def curie(iri: str) -> str:
    match = re.fullmatch(r"https?://purl.obolibrary.org/obo/([A-Za-z][A-Za-z0-9]*)_(.+)", iri)
    require(match, "Entity lacks supported OBO identifier; preserve unresolved, do not invent CURIE")
    return match[1] + ":" + match[2]


# Process-wide cache of public lookup responses, keyed by source, pinned release and query.
# Only search results and per-candidate details gathered during a search are cached; the
# verification that precedes an approval always calls the source again.
_CACHE: dict = {}
_CACHE_LOCK = Lock()
CACHE_SECONDS = 12 * 3600
CACHE_MAX_ENTRIES = 5000


# Domain = first listed ancestor found in the candidate's OLS hierarchy. Order matters: more specific first.
DOMAINS = {
    # SNOMED CT: its own top-level hierarchy names; disorders are a sub-branch of Clinical finding.
    "SNOMED_CT": [("Disease", "Clinical finding › disorder"), ("Clinical finding", "Clinical finding"),
        ("Situation with explicit context", "Situation with explicit context"), ("Procedure", "Procedure"),
        ("Observable entity", "Observable entity"), ("Event", "Event"), ("Social context", "Social context"),
        ("Staging and scales", "Staging and scales"), ("Qualifier value", "Qualifier value"), ("Body structure", "Body structure"),
        ("Substance", "Substance"), ("Physical object", "Physical object"),
        ("Environment or geographical location", "Environment or geographical location"), ("Record artifact", "Record artifact")],
    "MFOEM": [("emotion process", "emotion"), ("subjective affective feeling", "feeling"), ("appraisal process", "appraisal"),
        ("affective process", "affective process")],
    "MFOMD": [("mental disorder", "mental disorder"), ("pathological mental process", "symptom or sign"),
        ("disease course", "disease course")],
}


def cached(key, produce):
    """Return (value, cache_used). Values are copied so callers cannot alter the cache."""
    started = monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and started - hit[0] < CACHE_SECONDS:
            return deepcopy(hit[1]), True
    value = produce()
    with _CACHE_LOCK:
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.clear()
        _CACHE[key] = (monotonic(), deepcopy(value))
    return value, False


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


def lexical(query: str, text: str) -> float:
    a, b = set(re.findall(r"\w+", query.casefold())), set(re.findall(r"\w+", text.casefold()))
    return len(a & b) / len(a | b) if a | b else 0.0


def create_index(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    initialize_index(db)
    return db


def initialize_index(db):
    db.executescript('''CREATE TABLE meta(body TEXT);
        CREATE TABLE terms(id TEXT PRIMARY KEY, body TEXT);
        CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, text);''')


def search_ids(db, query):
    tokens = re.findall(r"\w+", query)
    if not tokens:
        return []
    match = " OR ".join('"' + t + '"' for t in tokens)
    return [row[0] for row in db.execute(
        "SELECT id FROM search WHERE search MATCH ? ORDER BY rank LIMIT 10", (match,))]


def put(db, term):
    db.execute("INSERT INTO terms VALUES(?,?)", (term["id"], canonical(term)))
    db.execute("INSERT INTO search VALUES(?,?)", (term["id"], " ".join([term["label"], term.get("fsn") or "", *term.get("synonyms", [])])))


def read_tsv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def import_rf2(destination: Path, concepts: Path, descriptions: Path, language: Path,
               edition: str, release: str, refset: str, fixture: bool = False) -> dict:
    require(re.fullmatch(r"\d{8}", release), "RF2 release must be YYYYMMDD")
    datetime.strptime(release, "%Y%m%d")
    require(edition.startswith("http://snomed.info/sct/") or fixture, "Provide SNOMED edition URI")
    require(all("Snapshot" in p.name for p in (concepts, descriptions, language)) or fixture, "Import Snapshot files only")
    require(not destination.exists(), "Index already exists: import to a new path/version, then update config")
    # Build transactionally into a temporary sibling, publish only a complete index.
    temporary = destination.with_suffix(".importing")
    require(not temporary.exists(), "Previous incomplete import exists; inspect/remove it before retry")
    db = create_index(temporary)
    try:
        db.executescript('''CREATE TABLE concepts(id TEXT PRIMARY KEY, active TEXT, module TEXT, effective TEXT);
            CREATE TABLE descriptions(id TEXT PRIMARY KEY, concept TEXT, active TEXT, type TEXT, term TEXT, lang TEXT);
            CREATE TABLE language(id TEXT PRIMARY KEY, description TEXT, acceptability TEXT);
            CREATE INDEX desc_concept ON descriptions(concept);
            CREATE INDEX lang_description ON language(description);''')
        for row in read_tsv(concepts):
            require(row["id"].isdigit() and row["active"] in ("0", "1"), "Invalid RF2 concept row")
            require(row["effectiveTime"] and row["effectiveTime"] <= release, "RF2 row newer than declared release or unpublished")
            db.execute("INSERT INTO concepts VALUES(?,?,?,?)", (row["id"], row["active"], row["moduleId"], row["effectiveTime"]))
        for row in read_tsv(descriptions):
            require(row["effectiveTime"] and row["effectiveTime"] <= release, "RF2 row newer than declared release or unpublished")
            db.execute("INSERT INTO descriptions VALUES(?,?,?,?,?,?)", (row["id"], row["conceptId"], row["active"], row["typeId"], row["term"], row["languageCode"]))
        for row in read_tsv(language):
            require(row["effectiveTime"] and row["effectiveTime"] <= release, "RF2 row newer than declared release or unpublished")
            if row["refsetId"] == refset and row["active"] == "1":
                db.execute("INSERT INTO language VALUES(?,?,?)", (row["id"], row["referencedComponentId"], row["acceptabilityId"]))
        require(db.execute("SELECT COUNT(*) FROM language").fetchone()[0], "Selected language refset absent/empty")
        for cid, active, module, effective in db.execute("SELECT * FROM concepts"):
            ds = list(db.execute("SELECT id,type,term,lang FROM descriptions WHERE concept=? AND active='1'", (cid,)))
            fsns = [d[2] for d in ds if d[1] == "900000000000003001"]
            preferred = [d[2] for d in ds if d[1] == "900000000000013009" and db.execute(
                "SELECT 1 FROM language WHERE description=? AND acceptability='900000000000548007'", (d[0],)).fetchone()]
            accepted = [d[2] for d in ds if db.execute("SELECT 1 FROM language WHERE description=?", (d[0],)).fetchone()]
            put(db, {"id": "SNOMEDCT:" + cid, "sctid": cid, "iri": "http://snomed.info/id/" + cid,
                "label": preferred[0] if preferred else (fsns[0] if fsns else "[No active description]"),
                "preferred_terms": preferred, "fsn": fsns[0] if fsns else None, "synonyms": accepted,
                "definition": None, "active": active == "1", "module": module, "effective_time": effective,
                "language_refset": refset, "edition": edition, "release": release, "fixture": fixture,
                "term_selection_note": "Selected language-refset preferred synonym; FSN fallback explicitly recorded"})
        meta = {"resource": "SNOMED_CT", "release": release, "edition": edition, "language_refset": refset,
            "fixture": fixture, "imported_at": now(), "source_hashes": {p.name: file_hash(p) for p in (concepts, descriptions, language)},
            "count": db.execute("SELECT COUNT(*) FROM terms").fetchone()[0]}
        db.execute("INSERT INTO meta VALUES(?)", (canonical(meta),))
        db.commit()
    except BaseException:
        db.close()
        temporary.unlink(missing_ok=True)
        raise
    db.close()
    temporary.rename(destination)
    return meta


def import_owl(destination: Path, source: Path, resource: str, release: str) -> dict:
    require(resource in ("MFOEM", "MFOMD"), "OWL importer only for MFOEM/MFOMD")
    require(not destination.exists(), "Import release into a new index")
    # RDF/XML or Turtle only; no remote imports, JSON-LD contexts or ontology reasoning.
    text = source.read_text()
    require("<!ENTITY" not in text and "<!DOCTYPE" not in text, "External XML entities forbidden")
    g = Graph().parse(data=text, format="turtle" if source.suffix == ".ttl" else "xml")
    versions = sorted(str(v) for v in g.objects(None, OWL.versionIRI))
    require(release in versions, "Release must equal a declared owl:versionIRI")
    temporary = destination.with_suffix(".importing")
    require(not temporary.exists(), "Incomplete import exists")
    db = create_index(temporary)
    try:
        for entity in sorted(set(g.subjects(RDF.type, OWL.Class)), key=str):
            if not isinstance(entity, URIRef):
                continue
            labels = list(g.objects(entity, RDFS.label))
            if not labels:
                continue
            identifier = curie(str(entity))
            label = next((str(x) for x in labels if x.language in ("en", None)), str(labels[0]))
            definition = next(g.objects(entity, URIRef("http://purl.obolibrary.org/obo/IAO_0000115")), None)
            synonyms = [str(x) for p in (SKOS.altLabel, URIRef("http://www.geneontology.org/formats/oboInOwl#hasExactSynonym")) for x in g.objects(entity, p)]
            deprecated = any(str(x).lower() in ("true", "1") for x in g.objects(entity, OWL.deprecated))
            put(db, {"id": identifier, "iri": str(entity), "label": label, "definition": str(definition) if definition else None,
                "synonyms": synonyms, "active": not deprecated, "release": release, "fixture": False})
        meta = {"resource": resource, "release": release, "source_sha256": file_hash(source), "fixture": False,
            "count": db.execute("SELECT COUNT(*) FROM terms").fetchone()[0], "imports_followed": False, "imported_at": now()}
        require(meta["count"], "No labeled OWL classes indexed")
        db.execute("INSERT INTO meta VALUES(?)", (canonical(meta),))
        db.commit()
    except BaseException:
        db.close()
        temporary.unlink(missing_ok=True)
        raise
    db.close()
    temporary.rename(destination)
    return meta


class Resolver:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._metadata_cache = {}
        self.progress = None
        self._verify_pool = None
        self._context = local()
        self.fixture_catalogue = json.loads((Path(__file__).parent / "resources/fictional_terminology.json").read_text()) if cfg["mode"] == "fixture" else None

    def emit(self, event):
        if self.progress:
            self.progress({**event, "meaning_id":getattr(self._context, "meaning_id", None)})

    def metadata(self, resource: str) -> dict:
        settings = self.cfg["terminology"][resource]
        if self.cfg["mode"] == "fixture":
            return {"resource": resource, "release": self.fixture_catalogue["release"], "fixture": True,
                "catalogue_sha256": digest(self.fixture_catalogue), "search_method": "SQLite FTS5 labels and synonyms",
                "count": len(self.fixture_catalogue["resources"][resource])}
        require(settings["enabled"], "Required resource disabled")
        if settings["adapter"] == "ols":
            require(resource != "SNOMED_CT" or settings.get("experimental_lookup_only") is True, "SNOMED OLS requires explicit experimental lookup configuration")
            if resource in self._metadata_cache:
                return self._metadata_cache[resource]
            result = network.request(self.cfg, settings["endpoint"] + "/ontologies/" + settings["ontology"])
            actual = result.get("config", {}).get("version") or result.get("config", {}).get("versionIri")
            require(actual and actual == settings["release"], "OLS release unavailable or changed; pin actual version")
            meta = {"resource": resource, "release": actual, "fixture": False,
                "endpoint": settings["endpoint"], "experimental_lookup_only": settings.get("experimental_lookup_only", False)}
            self._metadata_cache[resource] = meta
            return meta
        path = resolve(self.cfg, settings["index"])
        require(path.is_file(), "REQUIRED_RESOURCE_UNAVAILABLE")
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            meta = json.loads(db.execute("SELECT body FROM meta").fetchone()[0])
        require(meta["resource"] == resource and meta["release"] == settings["release"], "Resource/release mismatch")
        require(not meta["fixture"], "Fixture index cannot verify a real release")
        if resource == "SNOMED_CT":
            require(meta["edition"] == settings["edition"] and meta["language_refset"] == settings["language_refset"], "SNOMED edition/language refset mismatch")
        return meta

    def verify(self, resource: str, identifier: str, iri: str | None = None) -> dict:
        meta = self.metadata(resource)
        settings = self.cfg["terminology"][resource]
        if self.cfg["mode"] == "fixture":
            term = next((t for t in self.fixture_catalogue["resources"][resource] if t["id"] == identifier), None)
            require(term, "Nonexistent fixture identifier")
            term_iri = "https://example.org/farajamh/fictional-term/" + identifier.split(":")[1]
            require(iri is None or iri == term_iri, "Identifier/IRI mismatch")
            return {**term, "iri": term_iri, "active": True, "release": meta["release"], "fixture": True}
        if settings["adapter"] == "ols":
            require(iri and self.identifier(resource, iri) == identifier, "Identifier/IRI mismatch")
            url = settings["endpoint"] + "/ontologies/" + settings["ontology"] + "/terms/" + quote(quote(iri, safe=""), safe="")
            term = network.request(self.cfg, url)
            require(term.get("iri") == iri, "OLS returned a different entity")
            return {"id": identifier, "iri": iri, "label": term["label"], "definition": term.get("description"),
                "active": not term.get("is_obsolete", False), "release": meta["release"], "fixture": False,
                "experimental_lookup_only": meta.get("experimental_lookup_only", False)}
        with sqlite3.connect(f"file:{resolve(self.cfg, settings['index'])}?mode=ro", uri=True) as db:
            row = db.execute("SELECT body FROM terms WHERE id=?", (identifier,)).fetchone()
        require(row, "Nonexistent identifier")
        return json.loads(row[0])

    def domain(self, resource: str, iri: str) -> str | None:
        settings = self.cfg["terminology"][resource]
        url = settings["endpoint"] + "/ontologies/" + settings["ontology"] + "/terms/" + quote(quote(iri, safe=""), safe="")
        try:
            ancestors = network.request(self.cfg, url + "/hierarchicalAncestors?size=200")
        except Exception:
            return None  # Display aid only; a failed lookup must not fail the search.
        labels = {t.get("label") for t in ancestors.get("_embedded", {}).get("terms", [])}
        return next((name for label, name in DOMAINS.get(resource, []) if label in labels), None)

    def identifier(self, resource, iri):
        if resource == "SNOMED_CT":
            match = re.fullmatch(r"http://snomed.info/id/(\d+)", iri)
            require(match, "Unsupported SNOMED identifier")
            return "SNOMEDCT:" + match[1]
        identifier = curie(iri)
        require(identifier.startswith(resource + ":"), "Imported entity belongs to another ontology")
        return identifier

    def search(self, resource: str, queries: list[str]) -> dict:
        result = {"resource": resource, "queries": queries, "timestamp": now(), "candidates": [], "state": "UNAVAILABLE"}
        try:
            result["metadata"] = self.metadata(resource)
        except Exception as exc:
            result["error"] = type(exc).__name__
            result["blocking_prerequisite"] = "Required resource/release unavailable; complete terminology review prohibited"
            return result
        try:
            candidates = {}
            settings = self.cfg["terminology"][resource]
            for query in queries:
                started = monotonic()
                if self.progress: self.emit({"stage":"search_started", "resource":resource, "query":query})
                if self.cfg["mode"] == "fixture":
                    with sqlite3.connect(":memory:") as db:
                        initialize_index(db)
                        for term in self.fixture_catalogue["resources"][resource]:
                            put(db, term)
                        identifiers = search_ids(db, query)
                        tokens = re.findall(r"\w+", query)
                        match = " OR ".join('"' + t + '"' for t in tokens)
                        total = db.execute("SELECT COUNT(*) FROM search WHERE search MATCH ?", (match,)).fetchone()[0] if tokens else 0
                        result.setdefault("search_coverage", []).append({"query":query,"returned":len(identifiers),"total_reported":total,"limit":10})
                    entries = [self.verify(resource, identifier) for identifier in identifiers]
                elif settings["adapter"] == "ols":
                    url = settings["endpoint"] + "/search?" + urlencode({"q": query, "ontology": settings["ontology"], "rows": settings.get("limit", 10), "type": "class"})
                    release = result["metadata"]["release"]
                    response, cache_used = cached(("search", resource, release, query, settings.get("limit", 10)),
                        lambda: network.request(self.cfg, url)["response"])
                    hits = response["docs"]
                    result.setdefault("search_coverage", []).append({"query":query,"returned":len(hits),"total_reported":response.get("numFound"),"limit":settings.get("limit",10),"cache_used":cache_used})
                    pending = []
                    reused = []
                    for hit in hits:
                        try:
                            identifier = self.identifier(resource, hit["iri"])
                        except ValueError:
                            continue
                        if identifier not in candidates:
                            pending.append((identifier, hit["iri"]))
                        else:
                            reused.append(dict(candidates[identifier]))
                    # Domain is looked up with search results only; pre-approval verification stays a single live call.
                    details = lambda pair: cached(("term", resource, release, pair[0]), lambda: {**self.verify(resource, *pair), "domain": self.domain(resource, pair[1])})[0]
                    if self._verify_pool is not None:
                        entries = list(self._verify_pool.map(details, pending)) + reused
                    else:
                        with ThreadPoolExecutor(max_workers=4) as verification_pool:
                            entries = list(verification_pool.map(details, pending)) + reused
                else:
                    with sqlite3.connect(f"file:{resolve(self.cfg, settings['index'])}?mode=ro", uri=True) as db:
                        identifiers = search_ids(db, query)
                        tokens = re.findall(r"\w+", query)
                        match = " OR ".join('"' + t + '"' for t in tokens)
                        total = db.execute("SELECT COUNT(*) FROM search WHERE search MATCH ?", (match,)).fetchone()[0] if tokens else 0
                        result.setdefault("search_coverage", []).append({"query":query,"returned":len(identifiers),"total_reported":total,"limit":10})
                    entries = [self.verify(resource, identifier) for identifier in identifiers]
                for candidate in entries:
                    previous = candidates.get(candidate["id"], {})
                    candidate["lexical_score"] = max(previous.get("lexical_score", 0), lexical(query, candidate["label"]))
                    candidate["matched_queries"] = list(dict.fromkeys(previous.get("matched_queries", []) + [query]))
                    candidate["exact_label"] = previous.get("exact_label", False) or candidate["label"].strip().casefold() == query.strip().casefold()
                    if resource == "SNOMED_CT":
                        tag = re.search(r"\(([^()]+)\)$", candidate.get("fsn") or candidate["label"])
                        candidate["semantic_tag"] = tag.group(1).casefold() if tag else None
                    candidate["query"] = query
                    candidate["mismatch_notes"] = ["Lexical retrieval only; contextual fit and predicate require human review"]
                    if not candidate["active"]:
                        candidate["mismatch_notes"].append("INACTIVE: approval prohibited")
                    candidates[candidate["id"]] = candidate
                if self.progress:
                    coverage = next((c for c in result.get("search_coverage", []) if c["query"] == query), {})
                    self.emit({"stage":"search_finished", "resource":resource, "query":query, "returned":coverage.get("returned",len(entries)), "total_reported":coverage.get("total_reported"), "seconds":round(monotonic()-started,2)})
            result["candidates"] = list(candidates.values())
            result["state"] = "HITS" if candidates else "NO_RESULTS"
        except Exception as exc:
            result["state"] = "SEARCH_FAILED"
            result["error"] = type(exc).__name__
        return result

    def all(self, queries: list[str]) -> dict:
        with ThreadPoolExecutor(max_workers=3) as pool:
            return dict(zip(RESOURCES, pool.map(lambda r: self.search(r, queries), RESOURCES)))

    def for_meanings(self, meanings, resources=RESOURCES):
        # Each accepted meaning owns its queries, candidate pool and ranking context.
        require(len({h["id"] for h in meanings}) == len(meanings), "Distinct meaning IDs required for retrieval")
        require(resources and set(resources) <= set(RESOURCES), "Unknown terminology source")
        resources = [r for r in RESOURCES if r in resources]
        results = {}
        # At most four independent meaning/source searches. Ranking stays serial
        # to avoid contention on the local embedding model. No SQLite writes here.
        tasks = [(h, r) for h in meanings for r in resources]
        def retrieve(task):
            h, resource = task
            self._context.meaning_id = h["id"]
            return h["id"], resource, self.search(resource, sorted(set(h["search_terms"])))
        pools = {h["id"]: {} for h in meanings}
        with ThreadPoolExecutor(max_workers=4) as verification_pool:
            self._verify_pool = verification_pool
            try:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    for meaning_id, resource, lookup in pool.map(retrieve, tasks):
                        pools[meaning_id][resource] = lookup
            finally:
                self._verify_pool = None
        for meaning in meanings:
            if self.progress: self.emit({"stage":"ranking", "meaning_id":meaning["id"]})
            ranked = rank(self.cfg, pools[meaning["id"]], [meaning])
            for resource, lookup in ranked.items():
                root = results.setdefault(resource, {"resource": resource, "queries": [], "candidates": [],
                    "by_meaning": {}, "timestamp": now(), "ranking": {"method": "per meaning", "notice": "See each meaning's own ranking."}})
                root["by_meaning"][meaning["id"]] = {**lookup, "meaning_id": meaning["id"], "meaning": meaning["meaning"]}
        for root in results.values():
            lookups = list(root["by_meaning"].values())
            states = {x["state"] for x in lookups}
            root["state"] = ("UNAVAILABLE" if "UNAVAILABLE" in states else "SEARCH_FAILED" if "SEARCH_FAILED" in states else
                "HITS" if "HITS" in states else "NO_RESULTS")
            root["queries"] = sorted({q for x in lookups for q in x["queries"]})
            root["metadata"] = next((x["metadata"] for x in lookups if x.get("metadata")), {})
            # Compatibility index for stored mapping references; never use this union as a ranked list.
            unique = {}
            for lookup in lookups:
                for candidate in lookup["candidates"]:
                    unique.setdefault(candidate["id"], candidate)
            root["candidates"] = list(unique.values())
        return results
