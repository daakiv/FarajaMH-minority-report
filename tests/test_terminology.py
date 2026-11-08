import csv
import json
import sqlite3

import pytest

from farajamh.terminology import Resolver, import_owl, import_rf2


def tsv(path, fields, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(fields.split())
        w.writerows(rows)
    return path


def rf2_files(tmp_path):
    # Entirely fabricated tiny Snapshot rows: not distributed SNOMED content.
    c = tsv(tmp_path / "Concept_Snapshot.txt", "id effectiveTime active moduleId definitionStatusId", [
        ["111111111111111111", "20260101", "1", "999", "0"], ["222222222222222222", "20260101", "0", "999", "0"]])
    d = tsv(tmp_path / "Description_Snapshot.txt", "id effectiveTime active moduleId conceptId languageCode typeId term caseSignificanceId", [
        ["1", "20260101", "1", "999", "111111111111111111", "en", "900000000000003001", "Fabricated pain (finding)", "0"],
        ["2", "20260101", "1", "999", "111111111111111111", "en", "900000000000013009", "Preferred fabricated pain", "0"],
        ["3", "20260101", "1", "999", "111111111111111111", "en", "900000000000013009", "Other dialect wording", "0"],
        ["4", "20260101", "1", "999", "222222222222222222", "en", "900000000000003001", "Inactive fabricated pain (finding)", "0"]])
    l = tsv(tmp_path / "Language_Snapshot.txt", "id effectiveTime active moduleId refsetId referencedComponentId acceptabilityId", [
        ["a", "20260101", "1", "999", "900000000000509007", "2", "900000000000548007"],
        ["b", "20260101", "1", "999", "other", "3", "900000000000548007"]])
    return c, d, l


def test_rf2_import_search_and_string_ids(cfg, tmp_path):
    c, d, l = rf2_files(tmp_path)
    path = tmp_path / "rf2.sqlite"
    meta = import_rf2(path, c, d, l, "http://snomed.info/sct/999", "20260101", "900000000000509007")
    assert meta["count"] == 2
    cfg["mode"] = "local"
    cfg["terminology"]["SNOMED_CT"].update(index=str(path), edition="http://snomed.info/sct/999", release="20260101")
    resolver = Resolver(cfg)
    result = resolver.search("SNOMED_CT", ["fabricated pain"])
    assert result["state"] == "HITS" and len(result["candidates"]) == 2
    item = resolver.verify("SNOMED_CT", "SNOMEDCT:111111111111111111")
    assert isinstance(item["sctid"], str) and item["label"] == "Preferred fabricated pain"
    assert item["fsn"] == "Fabricated pain (finding)" and item["module"] == "999"
    assert not resolver.verify("SNOMED_CT", "SNOMEDCT:222222222222222222")["active"]
    with pytest.raises(ValueError, match="Nonexistent"): resolver.verify("SNOMED_CT", "SNOMEDCT:9876")


def test_rf2_fixture_not_real_release(cfg, tmp_path):
    path = tmp_path / "rf2.sqlite"
    import_rf2(path, *rf2_files(tmp_path), "http://snomed.info/sct/999", "20260101", "900000000000509007", fixture=True)
    cfg["mode"] = "local"
    cfg["terminology"]["SNOMED_CT"].update(index=str(path), edition="http://snomed.info/sct/999", release="20260101")
    assert Resolver(cfg).search("SNOMED_CT", ["pain"])["state"] == "UNAVAILABLE"


def test_missing_language_refset_fails_atomic_import(tmp_path):
    path = tmp_path / "rf2.sqlite"
    with pytest.raises(ValueError, match="refset"):
        import_rf2(path, *rf2_files(tmp_path), "http://snomed.info/sct/999", "20260101", "missing")
    assert not path.exists() and not path.with_suffix(".importing").exists()


@pytest.mark.parametrize("resource", ["MFOEM", "MFOMD"])
def test_local_owl_index(cfg, tmp_path, resource):
    path = tmp_path / "ontology.ttl"
    release = "https://example.org/test/2026-01-01"
    path.write_text(f'''@prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    <https://example.org/test> a owl:Ontology; owl:versionIRI <{release}> .
    <http://purl.obolibrary.org/obo/{resource}_TEST1> a owl:Class; rdfs:label "Fabricated pain" .''')
    index = tmp_path / "owl.sqlite"
    import_owl(index, path, resource, release)
    cfg["mode"] = "local"
    cfg["terminology"][resource].update(index=str(index), release=release)
    result = Resolver(cfg).search(resource, ["pain"])
    assert result["state"] == "HITS" and result["candidates"][0]["id"] == resource + ":TEST1"
    cfg["terminology"][resource]["release"] = "different"
    assert Resolver(cfg).search(resource, ["pain"])["state"] == "UNAVAILABLE"


@pytest.mark.parametrize("resource", ["MFOEM", "MFOMD"])
def test_ols_queries_verified_by_term_endpoint(cfg, monkeypatch, resource):
    cfg["mode"] = "connected"
    cfg["terminology"][resource].update(adapter="ols", release="2026-01-01")
    seen = []
    iri = "http://purl.obolibrary.org/obo/" + resource + "_TEST"
    def fake(cfg, url):
        seen.append(url)
        if "/search?" in url: return {"response": {"docs": [{"iri": iri}]}}
        if "/terms/" in url: return {"iri": iri, "label": "Fabricated pain", "description": ["Test definition"], "is_obsolete": False}
        return {"config": {"version": "2026-01-01"}}
    monkeypatch.setattr("farajamh.terminology.network.request", fake)
    result = Resolver(cfg).search(resource, ["pain"])
    assert result["state"] == "HITS" and any("/terms/http%253A%252F%252F" in url for url in seen)


@pytest.mark.parametrize("resource,ancestors,domain", [
    ("SNOMED_CT", ["Clinical finding", "Mental disorder", "Disease"], "Clinical finding › disorder"),
    ("SNOMED_CT", ["Clinical finding", "Emotional state finding"], "Clinical finding"),
    ("MFOEM", ["process", "emotion process", "affective process"], "emotion"),
    ("MFOMD", ["process", "pathological mental process"], "symptom or sign"),
    ("MFOMD", ["process"], None),
])
def test_ols_domain_from_ancestors(cfg, monkeypatch, resource, ancestors, domain):
    cfg["mode"] = "connected"
    cfg["terminology"][resource].update(adapter="ols", release="test", experimental_lookup_only=True,
        ontology="snomed" if resource == "SNOMED_CT" else resource.lower(), endpoint="https://www.ebi.ac.uk/ols4/api")
    monkeypatch.setattr("farajamh.terminology._CACHE", {})
    iri = "http://snomed.info/id/123" if resource == "SNOMED_CT" else "http://purl.obolibrary.org/obo/" + resource + "_TEST"
    def fake(cfg, url):
        if "/search?" in url: return {"response": {"docs": [{"iri": iri}]}}
        if url.endswith("/hierarchicalAncestors?size=200"): return {"_embedded": {"terms": [{"label": a} for a in ancestors]}}
        if "/terms/" in url: return {"iri": iri, "label": "Test", "is_obsolete": False}
        return {"config": {"version": "test", "versionIri": "test"}}
    monkeypatch.setattr("farajamh.terminology.network.request", fake)
    assert Resolver(cfg).search(resource, ["unique-" + resource + str(domain)])["candidates"][0]["domain"] == domain


def test_ols_domain_failure_keeps_candidate(cfg, monkeypatch):
    cfg["mode"] = "connected"
    cfg["terminology"]["MFOEM"].update(adapter="ols", release="test")
    monkeypatch.setattr("farajamh.terminology._CACHE", {})
    iri = "http://purl.obolibrary.org/obo/MFOEM_TEST"
    def fake(cfg, url):
        if "/search?" in url: return {"response": {"docs": [{"iri": iri}]}}
        if "hierarchicalAncestors" in url or "/parents?" in url: raise TimeoutError("down")
        if "/terms/" in url: return {"iri": iri, "label": "Test", "is_obsolete": False}
        return {"config": {"version": "test"}}
    monkeypatch.setattr("farajamh.terminology.network.request", fake)
    result = Resolver(cfg).search("MFOEM", ["domain-failure"])
    assert result["state"] == "HITS" and result["candidates"][0]["domain"] is None and result["candidates"][0]["parents"] == []


def test_search_failure_distinct_from_no_results(cfg, monkeypatch):
    cfg["mode"] = "connected"
    cfg["terminology"]["MFOEM"].update(adapter="ols", release="test")
    def fake(cfg, url):
        if "/search?" in url: raise TimeoutError("credential-bearing exception must not be logged")
        return {"config": {"version": "test"}}
    monkeypatch.setattr("farajamh.terminology.network.request", fake)
    result = Resolver(cfg).search("MFOEM", ["pain"])
    assert result["state"] == "SEARCH_FAILED" and "credential" not in json.dumps(result)


def test_required_snomed_missing(cfg):
    cfg["mode"] = "local"
    result = Resolver(cfg).search("SNOMED_CT", ["pain"])
    assert result["state"] == "UNAVAILABLE" and result["blocking_prerequisite"]


def test_experimental_snomed_is_explicit_and_ids_verified(cfg, monkeypatch):
    cfg['mode']='connected'
    cfg['terminology']['SNOMED_CT'].update(adapter='ols',ontology='snomed',endpoint='https://www.ebi.ac.uk/ols4/api',release='test-release')
    resolver=Resolver(cfg)
    assert resolver.search('SNOMED_CT',['worry'])['state']=='UNAVAILABLE'
    cfg['terminology']['SNOMED_CT']['experimental_lookup_only']=True
    def fake(cfg,url):
        if '/search?' in url:return {'response':{'docs':[{'iri':'http://snomed.info/id/123'}]}}
        if '/terms/' in url:return {'iri':'http://snomed.info/id/123','label':'Test only','is_obsolete':False}
        return {'config':{'versionIri':'test-release'}}
    monkeypatch.setattr('farajamh.terminology.network.request',fake)
    result=Resolver(cfg).search('SNOMED_CT',['worry'])
    assert result['state']=='HITS'
    assert result['candidates'][0]['id']=='SNOMEDCT:123'
    assert result['candidates'][0]['experimental_lookup_only'] is True


def test_imported_namespace_not_returned_as_mfoem(cfg, monkeypatch):
    cfg['mode']='connected'
    cfg['terminology']['MFOEM'].update(adapter='ols',release='test')
    def fake(cfg,url):
        if '/search?' in url:return {'response':{'docs':[{'iri':'http://purl.obolibrary.org/obo/GO_123'}]}}
        return {'config':{'version':'test'}}
    monkeypatch.setattr('farajamh.terminology.network.request',fake)
    assert Resolver(cfg).search('MFOEM',['worry'])['state']=='NO_RESULTS'
