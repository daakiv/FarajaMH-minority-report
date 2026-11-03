"""Isolated synthetic pilot: never opens configured runtime storage."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from farajamh.common import config
from farajamh.intake import prepare_case
from farajamh.models import interpret
from farajamh.webapp import server

ROOT=Path(__file__).resolve().parents[1]
TEXTS=[
 ('E1','sw','Mawazo ya deni, ya watoto, ya kazi. Yananijaa kichwani','Yananijaa kichwani'),
 ('KISWA-LIVE-05','sw','Kabla ya mkutano na bosi, nasikia moyo inadunda, roho inaenda mbio.','moyo inadunda, roho inaenda mbio'),
 ('KISWA-LIVE-06','en','Before the meeting with my boss, my heart was pounding and racing.','my heart was pounding and racing'),
 ('KISWA-LIVE-07','mul','Kabla ya meeting na boss, nasikia heart inadunda, roho inaenda mbio.','heart inadunda, roho inaenda mbio')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['baseline','serve']);args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='faraja-now-pilot-'))
    cfg=config(ROOT/'config.live-test.yaml');cfg['storage']=str(folder/'pilot.sqlite')
    os.environ['FARAJA_DAVID_TOKEN']='isolated-pilot-token'
    (folder/'pack.json').write_text(json.dumps([dict(utterance_id=uid,language=lang,original_text=text,expression_text=expr,experiencer='self',assertion='affirmed',event_time='unknown',synthetic=True) for uid,lang,text,expr in TEXTS]))
    print('Temporary pilot directory:',folder,flush=True)
    if args.action=='serve':
        print('Isolated server http://127.0.0.1:8876/',flush=True)
        server(cfg,8876).serve_forever();return
    spec=importlib.util.spec_from_file_location('farajamh.baseline_models','/tmp/faraja_baseline_models.py');baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    results=[]
    person={'id':'pilot','roles':['reviewer']}
    pack=json.loads((folder/'pack.json').read_text())
    for data in pack[:2]:
        source=prepare_case(data,mode=cfg['mode'],person=person)
        for label,fn in [('before',baseline.interpret),('after',interpret)]:
            runs=fn(cfg,source)
            row={'id':data['utterance_id'],'format':label,'models':[{'model':r['configuration_id'],'status':r['status'],'seconds':round(r['runtime_seconds'],2),'digest':r['provenance'].get('digest'),'failure':r.get('failure_reason') or (r['attempts'][-1].get('validation_error','').splitlines() or [''])[0]} for r in runs]}
            results.append(row);(folder/'measurements.json').write_text(json.dumps(results,indent=2));print(json.dumps(row),flush=True)
    (ROOT/'docs'/'NOW_MODEL_MEASUREMENTS.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
