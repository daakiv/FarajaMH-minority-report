"""Authenticated, process-local intake runs. A worker owns its SQLite connection."""
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
from . import network
from .intake import prepare_case, IntakeError
from .pipeline import App


def model_availability(cfg):
    rows, endpoints = [], {}
    models = [dict(m, profile=name) for name, p in cfg['model_profiles'].items() for m in p['models']]
    ranking = cfg.get('retrieval', {}).get('ranking', {})
    if ranking.get('model'):
        models.append(dict(ranking, id='ranking', provider='ollama', profile=None))
    for model in models:
        name, endpoint = model['model'], model.get('endpoint', '').rstrip('/')
        state = 'unavailable'
        if model['provider'] == 'ollama':
            if endpoint not in endpoints:
                try:
                    endpoints[endpoint] = network.request(cfg, endpoint + '/api/tags').get('models', [])
                except Exception:
                    endpoints[endpoint] = None
            installed = endpoints[endpoint]
            if installed is not None:
                state = 'installed' if any(name in (m.get('name'), m.get('model')) for m in installed) else 'missing'
        if model['provider'] == 'openai_compatible':
            # Only whether the key is present; the key itself never leaves the environment.
            state = 'hosted · key set' if os.environ.get(model['key_env']) else 'hosted · key missing (set ' + model['key_env'] + ')'
        rows.append({'id': model['id'], 'model': name, 'state': state, 'profile': model['profile'],
            'command': 'ollama pull ' + name if state == 'missing' else None})
    return rows


class Runs:
    def __init__(self, cfg):
        self.cfg, self.lock, self.jobs = cfg, Lock(), {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='faraja-intake')

    def start(self, app, fields, person):
        with self.lock:
            app.check_mode()
            fields = dict(fields)
            profile = fields.pop('model_profile', None) or self.cfg['model_profile']
            if profile not in self.cfg['model_profiles']:
                raise IntakeError('model_profile', 'Choose one of the configured model sets.')
            source = prepare_case(fields, mode=self.cfg['mode'], person=person,
                exists=lambda uid: uid in self.jobs or bool(app.store.db.execute('SELECT 1 FROM sources WHERE id=?', (uid,)).fetchone()))
            uid = source['utterance_id']
            self.jobs[uid] = {'id': uid, 'state': 'QUEUED', 'events': [], 'owner': person['id']}
            self.pool.submit(self.work, uid, source, person['id'], profile)
            return deepcopy(self.jobs[uid])

    def work(self, uid, source, actor, profile=None):
        app = None
        def emit(event):
            with self.lock:
                self.jobs[uid]['events'].append(event)
        try:
            with self.lock:
                self.jobs[uid]['state'] = 'RUNNING'
            app = App(self.cfg)
            app.run(source, progress=emit, actor=actor, profile=profile)
            with self.lock:
                self.jobs[uid]['state'] = 'COMPLETED'
        except Exception as exc:
            with self.lock:
                self.jobs[uid].update(state='FAILED', error='Run failed (' + type(exc).__name__ + '). No completed record was confirmed; check the server and use a new ID to retry.')
        finally:
            if app:
                app.store.db.close()

    def get(self, uid, person):
        with self.lock:
            if uid not in self.jobs:
                return {'id': uid, 'state': 'INTERRUPTED', 'events': [], 'error': 'Run status unavailable after restart. Check the queue before starting again.'}
            job = self.jobs[uid]
            if job['owner'] != person['id']:
                raise IntakeError('identity', 'This run belongs to another reviewer.')
            return deepcopy(job)

    def next_id(self, app):
        with self.lock:
            used = set(self.jobs) | {row[0] for row in app.store.db.execute('SELECT id FROM sources')}
            number = 1
            while f'KISWA-LIVE-{number:02d}' in used:
                number += 1
            return f'KISWA-LIVE-{number:02d}'


class ReviewJobs:
    """Background review operations; completion commits once, against expected version."""
    def __init__(self, cfg):
        self.cfg, self.lock, self.jobs = cfg, Lock(), {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='faraja-review')

    def start(self, app, operation, body, token):
        from uuid import uuid4
        from .common import require
        require(operation in ('complete_review', 'refresh_terminology', 'signoff'), 'Unknown background action')
        person = app.identity(token, 'reviewer' if operation == 'complete_review' else 'terminology')
        d = app.store.get(body['utterance_id'])
        app.check_mode(d)
        require(d['version'] == body['version'], 'Stale version: refresh the dossier')
        with self.lock:
            require(not any(j['utterance_id'] == body['utterance_id'] and j['state'] in ('QUEUED','RUNNING') for j in self.jobs.values()), 'An operation is already running for this case')
            jid = str(uuid4())
            self.jobs[jid] = dict(id=jid, utterance_id=body['utterance_id'], state='QUEUED', events=[], owner=person['id'])
            self.pool.submit(self.work, jid, operation, deepcopy(body), token)
            return deepcopy(self.jobs[jid])

    def work(self, jid, operation, body, token):
        from jsonschema import ValidationError
        app = None
        def emit(event):
            with self.lock:
                self.jobs[jid]['events'].append(event)
        try:
            with self.lock: self.jobs[jid]['state'] = 'RUNNING'
            app = App(self.cfg)
            app.resolver.progress = emit
            result = getattr(app, operation)(body['utterance_id'], body['decision'], token, body['version'])
            with self.lock:
                self.jobs[jid].update(state='COMPLETED', version=result['version'])
        except Exception as exc:
            field = getattr(exc, 'field', None)
            if isinstance(exc, ValidationError):
                field = '.'.join(str(x) for x in exc.absolute_path)
                error = exc.message[:500]
            else:
                error = str(exc)[:500] if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__
            with self.lock: self.jobs[jid].update(state='FAILED', error=error, field=field)
        finally:
            if app: app.store.db.close()
            # Tokens exist only on the running stack, never in job state or logs.

    def get(self, jid, person):
        with self.lock:
            job = self.jobs.get(jid)
            if not job:
                return dict(id=jid, state='INTERRUPTED', events=[], error='Status unavailable after restart. Reload the case to check its saved version before retrying.')
            if job['owner'] != person['id']:
                raise IntakeError('identity', 'This job belongs to another reviewer.')
            return deepcopy(job)
