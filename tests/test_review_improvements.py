import copy
import threading
import time
import pytest
from conftest import curated
from test_guided_review import decision
from farajamh.jobs import ReviewJobs
from farajamh.pipeline import App
from farajamh.ranking import rank
from farajamh.terminology import Resolver


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
