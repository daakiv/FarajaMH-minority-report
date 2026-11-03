import json
from pathlib import Path

from farajamh.common import validate
from farajamh.models import validate_output

PACK = Path(__file__).resolve().parents[1] / 'pilot/workshop-dummy'


def read(name):
    return json.loads((PACK / name).read_text())


def sources():
    return [json.loads(line) for line in (PACK / 'utterances.jsonl').read_text().splitlines()]


def test_workshop_inputs_and_mock_responses_validate():
    manifest = read('manifest.json')
    validate('manifest', manifest)
    inputs = sources()
    assert manifest['count'] == len(inputs) == 16
    responses = read('model_responses.json')
    for source in inputs:
        validate('source', source)
        assert source['synthetic'] is True
        assert source['source_type'] == 'constructed-text'
        for outputs in responses[source['utterance_id']].values():
            for output in outputs:
                validate_output(output, source)


def test_workshop_pack_keeps_reference_separate_from_synthetic_meanings():
    reference = read('workshop-reference.json')
    assert len(reference['rows']) == 48
    assert {r['source_row'] for r in reference['rows']} == set(range(2, 50))
    codes = read('category-reference.json')['families']
    assert next(c for c in codes if c['code'] == 'Ob')['primary_category'] is None
    assert next(c for c in codes if c['code'] == 'Cs')['slide_code'] == 'Cx'
    assert next(c for c in codes if c['code'] == 'R')['role'] == 'separate_safety_flag'
    dictionary = read('dictionary.json')
    assert dictionary['curator_approved'] is False
    assert all(e['synthetic'] and e['approval_status'] == 'SIMULATED_NOT_APPROVED'
               and e['external_mapping'] is None for e in dictionary['entries'])
    cases = read('cases.json')['cases']
    assert all(c['category_code'] != 'R' and not c['interpretation_validated'] for c in cases)
    assert sum(c['dictionary_entry_id'] is None for c in cases) == 2
    assert any(c['risk_flag'] == 'flagged' and c['scenario'] == 'agreement' for c in cases)


def test_workshop_fixture_models_run_without_approving_cases(app):
    app.cfg['fixtures'] = str(PACK / 'model_responses.json')
    for source in sources():
        dossier = app.run(source)
        assert all(run['status'] == 'COMPLETED' for run in dossier['models'])
        assert dossier['adjudication'] is None
        assert dossier['mapping_reviews'] == []
        assert dossier['provenance']['synthetic'] is True
        assert all(run['provenance']['reference_versions'] == [] for run in dossier['models'])
