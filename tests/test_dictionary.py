from farajamh.dictionary import evidence
from farajamh.common import ROOT


def test_dictionary_evidence_is_unapproved_and_has_provenance(cfg):
    cfg['dictionary']={'path':str(ROOT.parent/'pilot/workshop-dummy/dictionary.json')}
    result=evidence(cfg,{'original_text':'kichwa imejaa ngori'})
    assert result['state']=='CANDIDATES'
    assert result['sha256'] and result['version']=='dummy-0.1'
    assert result['curator_approved'] is False
    assert result['entries'][0]['meaning']=='persistent thoughts about tasks'
    assert evidence(cfg,{'original_text':'zzzzzzz'})['state']=='NO_MATCH'


def test_inflected_expression_matches_but_head_alone_does_not(cfg):
    cfg['dictionary']={'path':str(ROOT.parent/'pilot/workshop-dummy/dictionary.json')}
    source={'original_text':'Mawazo ya deni, ya watoto, ya kazi. Yananijaa kichwani',
            'expression_span':{'text':'Yananijaa kichwani'}}
    result=evidence(cfg,source)
    assert any(e['expression']=='kichwa imejaa ngori' for e in result['entries'])
    assert not any(e['expression']=='kichwa imejaa ngori' for e in evidence(cfg,{'original_text':'Kichwa kinawaka moto'})['entries'])
