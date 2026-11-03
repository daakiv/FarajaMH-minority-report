"""Refresh the existing approval and create a separate expression-specific test; no new approval."""
import os,sqlite3
from pathlib import Path
from datetime import datetime
from farajamh.common import config,write_json
from farajamh.pipeline import App
root=Path(__file__).resolve().parents[1]
cfg=config(root/'config.live-test.yaml');cfg['network']['timeout_seconds']=600
app=App(cfg)
with sqlite3.connect(root/'work'/('before-retrieval-'+datetime.now().strftime('%Y%m%d%H%M%S')+'.sqlite')) as backup:app.store.db.backup(backup)
token=os.environ['FARAJA_DAVID_TOKEN']
try:
 d=app.store.get('KISWA-LIVE-04')
 print('Refreshing and ranking against unchanged approved meaning...',flush=True)
 d=app.refresh_terminology('KISWA-LIVE-04',{},token,d['version'])
 write_json(root/'work/kiswa-live-test/ranked-dossier.json',d)
 for r,v in d['terminology'].items():print(r,v['state'],len(v['candidates']),v.get('ranking'),[(c['id'],c['label'],c.get('semantic_similarity')) for c in v['candidates'][:5]],flush=True)
 text='Yananijaa kichwani';start=d['source']['original_text'].index(text)
 print('Creating separate expression occurrence with fresh model runs...',flush=True)
 child=app.run_expression('KISWA-LIVE-04',{'utterance_id':'KISWA-LIVE-04-E1','start':start,'end':start+len(text),'text':text},token,d['version'])
 write_json(root/'work/kiswa-live-test/expression-dossier.json',child)
 print('Expression created',child['state'],[(m['configuration_id'],m['status']) for m in child['models']],flush=True)
finally:app.store.db.close()
