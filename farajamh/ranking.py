"""Optional local semantic ranking; similarity is not mapping confidence."""
import math
from . import network
from .common import digest, require


def cosine(a,b):
    require(len(a)==len(b) and len(a)>0, 'Embedding dimensions differ')
    denominator=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else 0.0


def rank(cfg, results, meanings):
    require(len(meanings)==1, 'Rank one approved meaning at a time')
    settings=cfg.get('retrieval',{}).get('ranking',{})
    context='\n'.join(h['meaning']+' [category: '+h['category']+']' for h in meanings)
    candidates=[c for result in results.values() for c in result['candidates']]
    info={'method':'lexical fallback','approved_meaning':context,'notice':'Similarity is not confidence, approval or proof of a semantic gap.'}
    if settings and context and candidates:
        try:
            endpoint=settings['endpoint'].rstrip('/')
            model=settings['model']
            tags=network.request(cfg,endpoint+'/api/tags')
            installed=next((m for m in tags['models'] if m.get('name')==model),None)
            require(installed and not installed.get('remote_host'),'Local embedding model required')
            texts=[context]+[c['label']+' — '+(' '.join(c.get('definition') or []) if isinstance(c.get('definition'),list) else (c.get('definition') or '')) for c in candidates]
            vectors=[]
            for offset in range(0,len(texts),16):
                batch=texts[offset:offset+16]
                reply=network.request(cfg,endpoint+'/api/embed',{'model':model,'input':batch,'truncate':True,'keep_alive':0})
                require(len(reply['embeddings'])==len(batch),'Missing embeddings')
                vectors.extend(reply['embeddings'])
            scores=[cosine(vectors[0],v) for v in vectors[1:]]
            require(all(math.isfinite(s) for s in scores),'Invalid similarity')
            for candidate,score in zip(candidates,scores):candidate['semantic_similarity']=score
            info.update(method='local embedding cosine',model=model,model_digest=installed['digest'],input_hash=digest(texts))
        except Exception as exc:
            info['error']=type(exc).__name__
    for result in results.values():
        result['ranking']={**info, 'meaning_id':meanings[0].get('id')} if result['candidates'] else {'method':'not applicable', 'notice':'No candidates to rank', 'meaning_id':meanings[0].get('id')}
        result['candidates'].sort(key=lambda c:(bool(c.get('exact_label')), c.get('semantic_similarity',c.get('lexical_score',0))),reverse=True)
        for position,c in enumerate(result['candidates'],1):c['rank']=position
    return results
