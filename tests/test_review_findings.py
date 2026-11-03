import copy
import json
import pytest
from farajamh.models import validate_output, interpret
from farajamh.terminology import Resolver
from farajamh.ranking import rank
from farajamh.workflow import steps
from farajamh.pipeline import applicability
from farajamh.intake import prepare_case
from conftest import approved_mapping, adjudicated, curated


def test_cultural_note_id_is_not_an_evidence_id(app, sources, monkeypatch):
    d=app.run(sources[0]);output=copy.deepcopy(d['models'][0]['output'])
    output['hypotheses'][0]['cultural_notes']=[dict(id='CN1',text='Constructed note citing supplied text',reference='E1')]
    validate_output(output,sources[0])
    app.cfg['models']=app.cfg['models'][:1]
    monkeypatch.setattr('farajamh.models.call',lambda *args:(json.dumps(output),{'digest':'test'}))
    run=interpret(app.cfg,sources[0])[0]
    assert run['status']=='COMPLETED' and len(run['attempts'])==1
    output['hypotheses'][0]['cultural_notes'][0]['reference']='NOT-SUPPLIED'
    with pytest.raises(ValueError,match='Cultural note CN1: reference must name supplied evidence'):
        validate_output(output,sources[0])
    run=interpret(app.cfg,sources[0])[0]
    assert run['status']=='FAILED' and 'consistency validation' in run['failure_reason']
    assert 'schema' not in run['failure_reason']


def test_each_meaning_owns_queries_rank_and_coverage(cfg,monkeypatch):
    resolver=Resolver(cfg);calls=[]
    def search(resource,queries):
        calls.append((resource,queries))
        bodily=queries==['chest heaviness']
        candidates=[] if bodily and resource!='SNOMED_CT' else [dict(id='tight' if bodily else 'distress',label='Tight chest' if bodily else 'distress',lexical_score=1)]
        return dict(state='HITS' if candidates else 'NO_RESULTS',resource=resource,queries=queries,candidates=candidates,metadata={'release':'test'})
    monkeypatch.setattr(resolver,'search',search)
    meanings=[dict(id='body',meaning='chest heaviness',category='somatic',search_terms=['chest heaviness']),dict(id='emotion',meaning='distress about job loss',category='emotional',search_terms=['stress','distress'])]
    result=resolver.for_meanings(meanings)
    assert len(calls)==6 and all(q in (['chest heaviness'],['distress','stress']) for _,q in calls)
    assert result['MFOEM']['by_meaning']['body']['state']=='NO_RESULTS'
    assert result['MFOEM']['by_meaning']['emotion']['candidates'][0]['id']=='distress'
    body=result['SNOMED_CT']['by_meaning']['body']
    assert body['candidates'][0]['id']=='tight' and body['candidates'][0]['rank']==1
    assert body['ranking']['approved_meaning']=='chest heaviness [category: somatic]'
    assert 'distress' not in body['ranking']['approved_meaning']
    with pytest.raises(ValueError,match='one approved meaning'):
        rank(cfg,{},meanings)


def test_meaning_failure_is_not_hidden_by_other_hits(cfg,monkeypatch):
    resolver=Resolver(cfg)
    monkeypatch.setattr(resolver,'search',lambda resource,queries:dict(state='SEARCH_FAILED' if queries==['body'] else 'HITS',queries=queries,candidates=[],error='TimeoutError',metadata={}))
    result=resolver.for_meanings([dict(id='b',meaning='body',category='somatic',search_terms=['body']),dict(id='e',meaning='emotion',category='emotional',search_terms=['emotion'])])
    assert all(x['state']=='SEARCH_FAILED' for x in result.values())
    assert result['MFOEM']['by_meaning']['e']['state']=='HITS'


def test_cross_meaning_candidate_cannot_be_approved(app,sources):
    d,_=curated(app,sources[0]);resource=d['terminology']['MFOEM'];meaning_id=d['sense_links'][0]['meaning_id']
    resource['by_meaning'][meaning_id]['candidates']=[]
    resource['by_meaning'][meaning_id]['state']='NO_RESULTS'
    with app.store.transaction():app.store.save(d,d['version'])
    decision=dict(resource='MFOEM',action='approve',sense_id='FARAJA:test',candidate_id='FIXTURE:MFOEM-emotional-pain',predicate='skos:relatedMatch',rationale='Synthetic test',evidence_refs=['E1'])
    with pytest.raises(ValueError,match='not retrieved'):
        app.mapping(sources[0]['utterance_id'],decision,'token-demo_curator',d['version'])


def test_review_and_terminology_start_neutral(app,sources):
    d=app.run(sources[0]);chips=steps(d)
    assert [x['state'] for x in chips[5:]]==['neutral','neutral','neutral']
    assert chips[7]['detail']=='Case saved; decision pending'
    # An approved meaning with searches but no sign-off is not complete: terminology and record stay pending.
    d,_=adjudicated(app,sources[1]);chips=steps(d)
    assert [x['state'] for x in chips[5:]]==['ran','neutral','neutral']
    assert chips[7]['detail']=='Meaning saved; terminology 0 of 3 sources reviewed'
    d['terminology']['MFOMD']['state']='UNAVAILABLE'
    assert steps(d)[6]['state']=='attention'


def test_progress_resumes_at_next_unfinished_task(app,sources):
    from farajamh.workflow import progress
    from test_review_improvements import batch
    assert progress(app.run(sources[1]))['next_task']=='meaning'
    d,_=curated(app,sources[0])
    p=progress(d)
    assert p['next_task']=='terminology' and (p['sources_reviewed'],p['sources_total'])==(0,3)
    assert p['meanings'][0]['local_concept'] and p['meanings'][0]['sources']['MFOEM']['search']=='HITS'
    d=app.signoff('SYN01',batch(d),'token-demo_curator',d['version'])
    p=progress(d)
    assert p['next_task']=='done' and p['sources_reviewed']==3 and p['meanings'][0]['sources']['SNOMED_CT']['decision']=='approve'
    assert [x['state'] for x in steps(d)[6:]]==['ran','ran']


def test_recurrent_intake_and_local_applicability(cfg):
    source=prepare_case(dict(utterance_id='RECUR-01',original_text='Kila usiku, synthetic example.',expression_text='Kila usiku',language='sw',experiencer='self',assertion='affirmed',event_time='recurrent',synthetic=True),mode='connected',person={'roles':['reviewer']})
    assert source['qualifiers']['event_time']=='recurrent'
    assert applicability(source)['temporal_scope']=='recurrent'


def test_export_keeps_eligible_mapping_and_reports_experimental(app,sources,tmp_path,monkeypatch):
    from farajamh.exports import export_readiness,export_sssom
    d,_,_=approved_mapping(app,sources[0]);experimental=copy.deepcopy(d['mapping_reviews'][0]);experimental['decision'].update(resource='SNOMED_CT',candidate_id='FIXTURE:experimental-test')
    experimental['candidate']['experimental_lookup_only']=True;d['mapping_reviews'].append(experimental)
    with app.store.transaction():app.store.save(d,d['version'])
    readiness=export_readiness(app,d,app.identity('token-demo_curator'),True)
    assert not readiness['blockers'] and len(readiness['excluded_mappings'])==1
    result=export_sssom(app,tmp_path/'mixed','token-demo_curator',True)
    assert result['rows']==1 and result['excluded_mappings']==1
    assert 'FIXTURE:experimental-test' not in (tmp_path/'mixed'/'SIMULATED.mappings.sssom.tsv').read_text()
    assert json.loads((tmp_path/'mixed'/'excluded-mappings.json').read_text())[0]['resource']=='SNOMED_CT'
    d['terminology']['SNOMED_CT']['state']='UNAVAILABLE'
    with app.store.transaction():app.store.save(d,d['version'])
    with pytest.raises(ValueError,match='required terminology review incomplete'):
        export_sssom(app,tmp_path/'unavailable','token-demo_curator',True)


def test_failed_search_keeps_source_pending_even_when_deferred(app,sources):
    from farajamh.workflow import progress
    from test_review_improvements import batch
    d,_=curated(app,sources[0])
    d=app.signoff('SYN01',batch(d),'token-demo_curator',d['version'])
    d['terminology']['MFOMD']['state']='SEARCH_FAILED'
    for v in (d['terminology']['MFOMD'].get('by_meaning') or {}).values(): v['state']='SEARCH_FAILED'
    p=progress(d)
    assert p['next_task']=='terminology' and p['sources_reviewed']==2
