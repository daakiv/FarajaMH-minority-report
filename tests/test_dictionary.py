from farajamh.dictionary import evidence
from farajamh.common import ROOT


def test_dictionary_evidence_is_unapproved_and_has_provenance(cfg):
    cfg['dictionary']={'path':str(ROOT.parent/'pilot/workshop-dummy/dictionary.json')}
    result=evidence(cfg,{'original_text':'kichwa imejaa ngori'})
    assert result['state']=='CANDIDATES'
    assert result['sha256'] and result['version'].startswith('master-')
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


def test_entries_added_in_the_workbook_are_in_the_dictionary(cfg):
    # DUMMY_DICT_17-34 were added to the master workbook; tools/sync_workshop_dictionary.py copies them into the JSON.
    cfg['dictionary']={'path':str(ROOT.parent/'pilot/workshop-dummy/dictionary.json')}
    result=evidence(cfg,{'original_text':'Ninasikia sauti nikilalala','expression_span':{'text':'Ninasikia sauti '}})
    assert [e['id'] for e in result['entries']]==['DUMMY_DICT_29'] and result['entries'][0]['match_type']=='exact expression'


def test_every_entry_says_where_it_came_from(cfg):
    import json
    library=json.loads((ROOT.parent/'pilot/workshop-dummy/dictionary.json').read_text())
    assert library['source_workbook']=='FarajaMH_Workshop_master_Pack.xlsx'
    for e in library['entries']:
        assert e['origin'] in {'Workshop Proposal','Test wording','System proposal'} and e['status'] in {'Proposed','Validated','Rejected'}
        assert e['from_case'] in {'Kisumu','Naivasha','Morogoro'} if e['origin']=='Workshop Proposal' else e['from_case']
