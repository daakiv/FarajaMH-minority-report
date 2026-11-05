import copy
import csv
import io
import json
import threading
import urllib.error
import urllib.request
import zipfile
import time
import pytest
from conftest import approved_mapping, curated
from test_guided_review import decision
from farajamh import common
from farajamh.common import spelling_hints
from farajamh.exports import export_readiness, export_sssom
from farajamh.jobs import ReviewJobs
from farajamh.pipeline import App
from farajamh.ranking import rank
from farajamh.terminology import Resolver
from farajamh.webapp import server


def batch(d):
    return {'concept':None,'decisions':[dict(resource=r,action='approve',sense_id='FARAJA:test',candidate_id='FIXTURE:'+r+'-emotional-pain',predicate='skos:relatedMatch',rationale='The synthetic candidate expresses a related experience.',evidence_refs=['E1']) for r in ('MFOEM','MFOMD','SNOMED_CT')]}


def test_atomic_signoff_rolls_back_all_events_and_concept(app,sources):
    d,_=curated(app,sources[0]);payload=batch(d)
    concept=copy.deepcopy(app.store.senses()[0]);keys=['sense_id','meaning_id','source_label','english_gloss','definition','synonyms','cultural_applicability','example_refs','evidence_refs','owner','reuse_approved','applicability']
    payload['concept']={k:concept[k] for k in keys}
    payload['decisions'][2]['candidate_id']='NOT-RETRIEVED'
    before=app.store.audit()
    with pytest.raises(ValueError,match='not retrieved') as error:
        app.signoff('SYN01',payload,'token-demo_curator',d['version'])
    assert error.value.field=='signoff_SNOMED_CT'
    assert app.store.get('SYN01')['version']==d['version']
    assert app.store.audit()==before and app.store.senses()[0]['version']==1
    payload['decisions'][2]['candidate_id']='FIXTURE:SNOMED_CT-emotional-pain'
    result=app.signoff('SYN01',payload,'token-demo_curator',d['version'])
    assert len([x for x in result['mapping_reviews'] if not x['stale']])==3
    assert app.store.senses()[0]['version']==2
    assert sum(e['action']=='MAPPING_REVIEW' for e in app.store.audit())==3


def test_capped_search_cannot_be_a_gap(app,sources):
    d,_=curated(app,sources[0]);mid=d['sense_links'][0]['meaning_id']
    d['terminology']['MFOEM']['by_meaning'][mid]['search_coverage']=[dict(query='stress',returned=20,total_reported=286)]
    with app.store.transaction():app.store.save(d,d['version'])
    p=batch(d)['decisions'][0];p.update(action='gap',candidate_id=None,predicate=None)
    with pytest.raises(ValueError,match='Search incomplete'):app.mapping('SYN01',p,'token-demo_curator',d['version'])


def test_exact_label_ahead_of_similarity(cfg):
    results={'SNOMED_CT':{'candidates':[dict(id='score',label='Anxiety score',semantic_similarity=.99),dict(id='anxiety',label='Anxiety',semantic_similarity=.1,exact_label=True)]}}
    result=rank(cfg,results,[dict(id='a',meaning='anxiety',category='emotional')])
    assert result['SNOMED_CT']['candidates'][0]['id']=='anxiety'


def test_bounded_parallel_search_and_serial_ranking(cfg,monkeypatch):
    resolver=Resolver(cfg);lock=threading.Lock();active=0;peak=0
    def search(resource,queries):
        nonlocal active,peak
        with lock: active+=1;peak=max(peak,active)
        time.sleep(.04)
        with lock: active-=1
        return dict(resource=resource,queries=queries,state='NO_RESULTS',candidates=[])
    monkeypatch.setattr(resolver,'search',search)
    resolver.for_meanings([dict(id=str(i),meaning='test',category='emotional',search_terms=['anxiety']) for i in range(4)])
    assert 1<peak<=4


def test_background_progress_and_owner_isolation(app,cfg,sources,monkeypatch):
    d=app.run(sources[0]);started=threading.Event();finish=threading.Event()
    original=App.complete_review
    def slow(self,*args):
        self.resolver.progress(dict(stage='search_started',resource='MFOEM',query='pain'))
        started.set();finish.wait(4)
        return original(self,*args)
    monkeypatch.setattr(App,'complete_review',slow)
    jobs=ReviewJobs(cfg)
    try:
        body=dict(utterance_id='SYN01',version=d['version'],decision=decision(d))
        j=jobs.start(app,'complete_review',body,'token-demo_ke')
        assert started.wait(2)
        assert jobs.get(j['id'],app.identity('token-demo_ke'))['events'][0]['query']=='pain'
        with pytest.raises(ValueError,match='another reviewer'):jobs.get(j['id'],app.identity('token-demo_tz'))
        with pytest.raises(ValueError,match='already running'):jobs.start(app,'complete_review',body,'token-demo_ke')
        assert app.store.get('SYN01')['version']==1
        finish.set();jobs.pool.shutdown(wait=True)
        assert jobs.get(j['id'],app.identity('token-demo_ke'))['state']=='COMPLETED'
        assert 'token-demo_ke' not in str(jobs.jobs)
    finally:
        finish.set();jobs.pool.shutdown(wait=True)


def test_lookup_does_not_hold_write_lock_and_stale_result_rejected(app,cfg,sources,monkeypatch):
    d=app.run(sources[0]);original=app.resolver.for_meanings
    def lookup(meanings):
        other=App(cfg)
        try:
            with other.store.transaction():
                newer=other.store.get('SYN01');other.store.save(newer,newer['version'])
        finally:other.store.db.close()
        return original(meanings)
    monkeypatch.setattr(app.resolver,'for_meanings',lookup)
    with pytest.raises(ValueError,match='Stale version'):app.complete_review('SYN01',decision(d),'token-demo_ke',d['version'])
    assert app.store.get('SYN01')['adjudication'] is None


def test_spelling_hints_are_whole_word_and_keep_original():
    text='Naskia dunia ni ngumu, dunua yote. Dunuani'
    hints=spelling_hints(text)
    assert [(h['written'],h['suggested'],h['start'],h['end']) for h in hints]==[('Naskia','nasikia',0,6),('dunua','dunia',23,28)]
    assert text=='Naskia dunia ni ngumu, dunua yote. Dunuani'


def test_dossier_view_adds_hints_without_storing_them(app,cfg,sources,monkeypatch):
    monkeypatch.setitem(common.SPELLING_HINTS,'burning',dict(written='burning',suggested='burnin',note='test only'))
    d=app.run(sources[0]);http=server(cfg,0);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        request=urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/dossier/SYN01',headers={'Authorization':'Bearer token-demo_ke'})
        with urllib.request.urlopen(request) as response:view=json.load(response)
    finally:
        http.shutdown();http.server_close()
    assert view['spelling_hints']==[dict(written='burning',suggested='burnin',note='test only',start=12,end=19)]
    assert view['source']['original_text']=='My heart is burning'
    assert 'spelling_hints' not in app.store.get('SYN01') and app.store.get('SYN01')['version']==d['version']


def test_export_preview_rows_and_blocker_names_case(app,sources,tmp_path):
    d,_,payload=approved_mapping(app,sources[0])
    readiness=export_readiness(app,d,app.identity('token-demo_curator'),demonstration=True)
    assert readiness['mapping_rows']==[dict(subject_id='FARAJA:test',object_id=payload['candidate_id'],object_label=readiness['mapping_rows'][0]['object_label'],predicate_id='skos:relatedMatch',resource='MFOEM',lookup_only=False)]
    with app.store.transaction():
        d['terminology']['SNOMED_CT']['state']='UNAVAILABLE';app.store.save(d,d['version'])
    with pytest.raises(ValueError,match='^SYN01: '):export_sssom(app,tmp_path/'blocked','token-demo_curator',True)


def test_export_package_from_review_screen(app,cfg,sources):
    approved_mapping(app,sources[0]);http=server(cfg,0);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    def call(path,body=None,token='token-demo_curator'):
        request=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:return response.read()
    try:
        overview=json.loads(call('/api/exports'))
        assert overview['last_export'] is None and [(c['id'],c['status'],c['mapping_rows']) for c in overview['cases']]==[('SYN01','READY_FOR_FINAL_CHECK',1)]
        with pytest.raises(urllib.error.HTTPError):call('/api/background/export',{},'token-demo_tz')
        job=json.loads(call('/api/background/export',{}))
        for _ in range(100):
            job=json.loads(call('/api/review-job/'+job['id']))
            if job['state'] not in ('QUEUED','RUNNING'):break
            time.sleep(.05)
        assert job['state']=='COMPLETED' and job['export']['rows']==1,job
        package=job['export']['package']
        names=zipfile.ZipFile(io.BytesIO(call('/api/export-package/'+package+'.zip'))).namelist()
        assert {'SIMULATED.mappings.sssom.tsv','catalog.jsonld','excluded-mappings.json'}<={n.split('/',1)[1] for n in names}
        overview=json.loads(call('/api/exports'))
        assert overview['last_export']['package']==package and overview['cases'][0]['exported_version']==overview['cases'][0]['version']
        for bad in ('..%2F..%2Fconfig','20991231T000000Z'):
            with pytest.raises(urllib.error.HTTPError):call('/api/export-package/'+bad+'.zip')
    finally:
        http.shutdown();http.server_close()


def test_sssom_and_croissant_fields_for_single_reviewer(app,sources,tmp_path):
    approved_mapping(app,sources[0])
    first=export_sssom(app,tmp_path/'first','token-demo_curator',True);export_sssom(app,tmp_path/'second','token-demo_curator',True)
    text=(tmp_path/'first'/'SIMULATED.mappings.sssom.tsv').read_text()
    row=next(csv.DictReader(io.StringIO('\n'.join(l for l in text.splitlines() if not l.startswith('#'))),delimiter='\t'))
    assert 'reviewer_id' not in row and row['author_id']=='reviewer:demo_curator'
    assert row['object_source']=='FIXTURE:MFOEM' and row['comment']=='SIMULATED fit evidence'
    assert '# mapping_set_version: 1.0.1' in text and 'obo: http://purl.obolibrary.org/obo/' in text
    catalog=json.loads((tmp_path/'second'/'catalog.jsonld').read_text())
    assert catalog['version']=='1.0.2' and not catalog['@id'].startswith('file:') and catalog['creator']['name']
    fields={f['name']:f['description'] for r in catalog['recordSet'] for f in r['field']}
    assert fields['predicate_id'].startswith('SKOS relationship')
