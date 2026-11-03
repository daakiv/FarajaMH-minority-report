"""Run the user-supplied synthetic example on installed local models, preserving raw responses."""
from pathlib import Path
import json
from farajamh.common import config, write_json
from farajamh.pipeline import App

root = Path(__file__).resolve().parents[1]
cfg = config(root / 'config.yaml')
cfg['mode'] = 'local'
cfg['network']['timeout_seconds'] = 600
cfg['models'] = [{'id': name, 'provider':'ollama', 'model':name,
    'endpoint':'http://127.0.0.1:11434','settings':{'temperature':0,'seed':42}}
    for name in ['gemma3:12b','qwen2.5:7b','llama3.1:8b']]
text = 'Mawazo ya deni, ya watoto, ya kazi. Yananijaa kichwani'
source = {'schema_version':'1.0','utterance_id':'KISWA-LIVE-04','synthetic':True,
    'original_text':text,'language':'sw','language_spans':[],
    'source_type':'user-supplied research test example','speaker_role':'synthetic speaker',
    'speaker_ref':'SYN-KISWA-04','region_variety':None,
    'conversation': 'Synthetic test using the supplied wording only. No additional conversation was supplied.',
    'qualifiers':{'experiencer':'self','assertion':'affirmed','attribution':'self','event_time':'unknown','utterance_time':'unknown','setting':'synthetic test'},
    'evidence':[{'id':'E1','text':text,'reference':'User-supplied test example, 2026-10-27'}]}
app = App(cfg)
try:
    print('Starting three local models; no dictionary exposed.',flush=True)
    d = app.run(source)
    write_json(root/'work/kiswa-live-test/dossier.json',d)
    print(json.dumps({'uid':source['utterance_id'],'version':d['version'],'models':[
        {'model':m['configuration_id'],'status':m['status'],'output':m['output']} for m in d['models']]},ensure_ascii=False),flush=True)
finally:
    app.store.db.close()
