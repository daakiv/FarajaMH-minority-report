"""Fresh synthetic verification; never opens existing runtime databases."""
import json
import os
from pathlib import Path
import tempfile
from farajamh.common import config
from farajamh.intake import prepare_case
from farajamh.pipeline import App
from farajamh.webapp import server

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=Path(tempfile.mkdtemp(prefix='faraja-review-fixes-'))
    cfg=config(ROOT/'config.live-test.yaml')
    cfg['storage']=str(folder/'test.sqlite')
    os.environ['FARAJA_DAVID_TOKEN']='isolated-pilot-token'
    app=App(cfg)
    source=prepare_case(dict(utterance_id='KISWA-LIVE-05',original_text='Kabla ya mkutano na bosi, nasikia moyo inadunda, roho inaenda mbio.',expression_text='moyo inadunda, roho inaenda mbio',language='sw',experiencer='self',assertion='affirmed',event_time='unknown',synthetic=True),mode=cfg['mode'],person=app.identity('isolated-pilot-token'))
    print('Fresh temporary test directory: '+str(folder),flush=True)
    d=app.run(source,progress=lambda event:print(json.dumps(event),flush=True),actor='david_local')
    summary={'models':[{'id':r['configuration_id'],'status':r['status'],'seconds':r['runtime_seconds'],'digest':r['provenance'].get('digest'),'failure':r.get('failure_reason'),'cultural_note_references':[(n['id'],n['reference']) for h in (r.get('output') or {}).get('hypotheses',[]) for n in h['cultural_notes']]} for r in d['models']],'comparison':d['comparison']['state'],'votes':d['comparison']['counts']['voting']}
    (ROOT/'docs/REVIEW_FIX_MODEL_CHECK.json').write_text(json.dumps(summary,indent=2))
    app.store.db.close()
    print('Updated test page: http://127.0.0.1:8877/ ; isolated-pilot-token',flush=True)
    server(cfg,8877).serve_forever()

if __name__=='__main__':main()
