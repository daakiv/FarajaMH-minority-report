import pytest
from farajamh.ranking import rank
from farajamh.common import validate,CATEGORY_FAMILIES


def test_ranking_uses_meaning_and_preserves_all_candidates(cfg, monkeypatch):
    cfg['retrieval']={'ranking':{'endpoint':'http://127.0.0.1:11434','model':'test'}}
    calls=[]
    def request(cfg,url,payload=None):
        if url.endswith('/api/tags'):return {'models':[{'name':'test','digest':'pinned'}]}
        calls.append(payload['input'])
        return {'embeddings':[[1,0],[0,1],[1,0]]}
    monkeypatch.setattr('farajamh.ranking.network.request',request)
    results={'MFOEM':{'candidates':[{'id':'bad','label':'bacteria'},{'id':'good','label':'worry'}]}}
    rank(cfg,results,[{'meaning':'thoughts about debt','category':'cognitive'}])
    assert calls[0][0]=='thoughts about debt [category: cognitive]'
    assert [c['id'] for c in results['MFOEM']['candidates']]==['good','bad']
    assert results['MFOEM']['ranking']['model_digest']=='pinned'


def test_bad_span_rejected_before_models(app,sources,monkeypatch):
    s=sources[0].copy();s['expression_span']={'start':0,'end':2,'text':'wrong'}
    monkeypatch.setattr('farajamh.pipeline.interpret',lambda *a:pytest.fail('No model call allowed'))
    with pytest.raises(ValueError,match='Expression span'):app.run(s)


def test_every_reviewer_category_is_allowed_for_models():
    import json
    from farajamh.common import ROOT
    model=json.loads((ROOT/'schemas/model_output.json').read_text())
    categories=model['properties']['hypotheses']['items']['properties']['category']['enum']
    assert set(categories)=={v[1] for v in CATEGORY_FAMILIES.values()}


def test_ranking_failure_is_explicit_and_retains_candidates(cfg, monkeypatch):
    cfg['retrieval']={'ranking':{'endpoint':'http://127.0.0.1:11434','model':'missing'}}
    monkeypatch.setattr('farajamh.ranking.network.request',lambda *a: {'models':[]})
    results={'MFOEM':{'candidates':[{'id':'one','label':'worry','lexical_score':0.5}]}}
    rank(cfg,results,[{'meaning':'worry','category':'emotional'}])
    assert results['MFOEM']['ranking']['method']=='lexical fallback'
    assert results['MFOEM']['ranking']['error']=='ValueError'
    assert len(results['MFOEM']['candidates'])==1


def test_expression_is_separate_with_parent_preserved(app,sources,monkeypatch):
    parent=app.run(sources[0]); text=parent['source']['original_text']
    monkeypatch.setattr('farajamh.pipeline.interpret',lambda *a:parent['models'])
    child=app.run_expression('SYN01',{'utterance_id':'SYN01-E1','start':0,'end':len(text),'text':text},'token-demo_ke',parent['version'])
    assert child['source']['original_text']==text
    assert child['source']['expression_span']['text']==text
    assert child['source']['parent_utterance_id']=='SYN01'
    assert child['state']=='AWAITING_REVIEW'
    assert app.store.get('SYN01')==parent
