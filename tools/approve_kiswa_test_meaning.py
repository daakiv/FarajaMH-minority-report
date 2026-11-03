"""Record David's explicit chat approval for this synthetic lookup, no mapping approval."""
import copy
from pathlib import Path
from farajamh.common import config, write_json
from farajamh.pipeline import App
root=Path(__file__).resolve().parents[1]
app=App(config(root/'config.live-test.yaml'))
d=app.store.get('KISWA-LIVE-04')
assert d['version']==1, 'This one-time approval has already run or the case changed'
h=copy.deepcopy(next(m['output']['hypotheses'][0] for m in d['models'] if m['output']))
h.update(id='reviewed-cognitive-1',meaning='feeling overwhelmed by recurring thoughts about debt, children and work',category='cognitive',search_terms=['worry','rumination','overwhelmed'],rationale='Reviewer-edited meaning explicitly approved by David in chat for this synthetic test; based on the supplied wording E1.',uncertainty='Interpretation for a synthetic test; cultural applicability and safety require separate review.',counterevidence=['Model translations contained errors; no diagnosis or physical symptom is established.'],cultural_notes=[])
h['semantic_frame']={'experience':'recurring thoughts and feeling overwhelmed','cause':'debt, children and work','cultural_reading':'not established'}
p={'decision':{'action':'approve','meanings':[h],'rationale':h['rationale'],'evidence_refs':['E1'],'risk_signal':'uncertain'},'annotations':{h['id']:{'family_code':'C','dap_categories':[]}},'safety_note':'Not assessed; pending separate reviewer assessment. Meaning approval is not safety clearance.','applicability_confirmed':True,'second_opinion_requested':False}
print('Running approved search terms against three OLS sources...',flush=True)
try:
 import os
 d=app.complete_review('KISWA-LIVE-04',p,os.environ['FARAJA_DAVID_TOKEN'],1)
 write_json(root/'work/kiswa-live-test/reviewed-dossier.json',d)
 print({r:{'state':v['state'],'candidates':[(c['id'],c['label']) for c in v['candidates']]} for r,v in d['terminology'].items()},flush=True)
finally: app.store.db.close()
