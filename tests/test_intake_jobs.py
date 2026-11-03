import copy
import json
import threading
import time
import pytest
from farajamh.intake import prepare_case, IntakeError
from farajamh.jobs import Runs, model_availability
from farajamh.pipeline import App
from farajamh import models

TEXT = 'Kabla ya mkutano na bosi, nasikia moyo inadunda, roho inaenda mbio.'
EXPR = 'moyo inadunda, roho inaenda mbio'
PERSON = {'id':'tester','roles':['reviewer']}


def fields(**changes):
    return dict(utterance_id='KISWA-LIVE-05', original_text=TEXT, expression_text=EXPR,
        language='sw', experiencer='self', assertion='affirmed', event_time='unknown', synthetic=True, **changes)


def prepare(data):
    return prepare_case(data, mode='connected', person=PERSON)

@pytest.mark.parametrize('field,value', [('utterance_id','bad id'),('synthetic',False),('synthetic',1),('language','bad'),('assertion','bad'),('experiencer','bad'),('event_time','bad'),('expression_text','not in text')])
def test_invalid_field(field,value):
    data=fields();data[field]=value
    with pytest.raises(IntakeError) as exc: prepare(data)
    assert exc.value.field==field


def test_span_context_languages():
    s=prepare(fields(conversation_context='Invented meeting context'))
    assert s['expression_span']==dict(start=34,end=66,text=EXPR)
    assert s['evidence'][1]['id']=='E2'
    for language,text,expr,span in [('en','Before the meeting with my boss, my heart was pounding and racing.','my heart was pounding and racing',(33,65)),('mul','Kabla ya meeting na boss, nasikia heart inadunda, roho inaenda mbio.','heart inadunda, roho inaenda mbio',(34,67))]:
        data=fields();data.update(language=language,original_text=text,expression_text=expr)
        s=prepare(data);assert s['language']==language
        assert (s['expression_span']['start'],s['expression_span']['end'])==span
    data=fields();data.update(original_text='😀 é '+EXPR,expression_text=EXPR)
    assert prepare(data)['expression_span']['start']==4


def test_repeats_and_gates():
    data=fields();data['original_text']=EXPR+' '+EXPR
    with pytest.raises(IntakeError,match='occurrence'):prepare(data)
    data['occurrence']=2
    assert prepare(data)['expression_span']['start']==len(EXPR)+1
    with pytest.raises(IntakeError,match='fixture'):prepare_case(fields(),mode='fixture',person=PERSON)
    with pytest.raises(IntakeError,match='Reviewer'):prepare_case(fields(),mode='connected',person={'roles':[]})
    with pytest.raises(IntakeError,match='already'):prepare_case(fields(),mode='connected',person=PERSON,exists=lambda uid:True)
    data=fields();data['conversation_context']='Contact person@example.com'
    with pytest.raises(IntakeError,match='identifier') as exc:prepare(data)
    assert exc.value.field=='conversation_context'


def test_background_reserved_and_own_connection(cfg,monkeypatch):
    cfg['mode']='connected';started=threading.Event();finish=threading.Event();calls=[]
    def run(self,source,progress,actor):
        calls.append(threading.get_ident());started.set();finish.wait(5)
        progress({'stage':'record_saved','version':1})
    monkeypatch.setattr(App,'run',run)
    app=App(cfg);jobs=Runs(cfg)
    try:
        with pytest.raises(IntakeError):jobs.start(app,{**fields(),'synthetic':False},PERSON)
        assert not calls
        jobs.start(app,fields(),PERSON);assert started.wait(2)
        with pytest.raises(IntakeError,match='already'):jobs.start(app,fields(),PERSON)
        assert app.store.all()==[] # main connection remains usable while worker waits
        assert jobs.get('KISWA-LIVE-05',PERSON)['state']=='RUNNING'
        assert calls[0]!=threading.get_ident()
        assert jobs.get('missing',PERSON)['state']=='INTERRUPTED'
    finally:finish.set();jobs.pool.shutdown();app.store.db.close()


def test_mode_guard_precedes_lookup(app,sources,monkeypatch):
    d=app.run(sources[0]);app.cfg['mode']='connected'
    with pytest.raises(ValueError,match='environment'):app.check_mode(d)
    with pytest.raises(ValueError,match='environment'):app.run(sources[1])
    assert app.store.get(d['source']['utterance_id'])['version']==1


def test_structured_format(cfg,sources,monkeypatch):
    cfg['mode']='connected';model=dict(id='test',provider='ollama',endpoint='http://127.0.0.1:11434',model='test:1',settings={});requests=[]
    def request(cfg,url,data=None):
        requests.append((url,data))
        return {'models':[{'name':'test:1','digest':'digest'}]} if url.endswith('tags') else {'model':'test:1','message':{'content':'{}'}}
    monkeypatch.setattr(models.network,'request',request)
    models.call(cfg,model,[],sources[0],0)
    assert requests[-1][1]['format']['required']
    cfg['models']=[model];cfg['retrieval']={'ranking':{'model':'embed:1','endpoint':model['endpoint']}}
    rows=model_availability(cfg)
    assert [x['state'] for x in rows]==['installed','missing']
    assert rows[1]['command']=='ollama pull embed:1'

@pytest.mark.parametrize('raw,reason',[('not-json','not valid JSON'),('{"source":{}}','returned its input'),('{}','output schema')])
def test_failure_metrics(cfg,sources,monkeypatch,raw,reason):
    cfg['models']=cfg['models'][:1];events=[]
    monkeypatch.setattr(models,'call',lambda *args:(raw,{'digest':'x'}))
    run=models.interpret(cfg,sources[0],events.append)[0]
    assert reason in run['failure_reason']
    assert run['runtime_seconds']>=0 and run['provenance']['digest']=='x'
    assert [e['stage'] for e in events]==['model_started','model_finished']
    assert 'raw' not in str(events)


def test_progress_saved_actor(app,sources):
    events=[]
    d=app.run(sources[0],progress=events.append,actor='test-reviewer')
    stages=[e['stage'] for e in events]
    assert stages[0]=='input_checked' and stages[-1]=='record_saved'
    assert stages.index('dictionary')>max(i for i,x in enumerate(stages) if x=='model_finished')
    assert stages.index('comparison')>stages.index('dictionary')
    assert any(e['actor']=='test-reviewer' and e['action']=='CASE_ENTERED' for e in app.store.audit())


def test_export_screen_and_export_share_blocker(app,sources,tmp_path):
    from conftest import adjudicated
    from farajamh.exports import export_readiness, export_sssom
    d,_=adjudicated(app,sources[0])
    d['terminology']['MFOEM']['state']='UNAVAILABLE'
    with app.store.transaction():app.store.save(d,d['version'])
    person=app.identity('token-demo_curator','terminology')
    readiness=export_readiness(app,d,person,demonstration=True)
    assert 'MFOEM: required terminology review incomplete — the source was unavailable; rerun the search' in readiness['blockers']
    with pytest.raises(ValueError,match='MFOEM: required terminology review incomplete'):
        export_sssom(app,tmp_path/'export','token-demo_curator',True)


def test_http_intake_does_not_block_queue(cfg,monkeypatch):
    import urllib.request
    from farajamh.webapp import server
    cfg['mode']='connected';cfg['identities']={'test':dict(roles=['reviewer'],token_env='TEMP_PILOT_AUTH',simulated=False)}
    monkeypatch.setenv('TEMP_PILOT_AUTH','temporary-test-token')
    started=threading.Event();finish=threading.Event()
    def run(self,source,progress,actor):
        started.set();finish.wait(5);progress({'stage':'record_saved','version':1})
    monkeypatch.setattr(App,'run',run)
    http=server(cfg,0);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    def request(path,body=None):
        data=json.dumps(body).encode() if body else None
        req=urllib.request.Request(f'http://127.0.0.1:{http.server_port}'+path,data=data,headers={'Authorization':'Bearer temporary-test-token','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=2) as response:return json.load(response)
    try:
        assert request('/api/intake',fields())['id']=='KISWA-LIVE-05'
        assert started.wait(2)
        assert request('/api/queue')['items']==[]
        assert request('/api/run/KISWA-LIVE-05')['state']=='RUNNING'
    finally:
        finish.set();http.shutdown();http.server_close();thread.join()
