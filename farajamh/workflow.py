"""Status means recorded workflow progress, never clinical correctness."""
from .common import RESOURCES


TASK_LABELS = {"meaning": "Needs meaning review", "context": "Needs more context", "terminology": "Needs terminology review",
    "done": "Review complete", "closed": "Interpretation rejected"}


def progress(d):
    """What is recorded per meaning and source, and the next unfinished task. Export eligibility is separate."""
    state = d.get("state")
    a = d.get("adjudication") or {}
    meanings = a.get("decision", {}).get("meanings", []) if state == "ADJUDICATED" else []
    senses = {s["meaning_id"]: s["id"] for s in d.get("sense_links", []) if not s.get("stale")}
    latest = {}
    for m in d.get("mapping_reviews", []):
        if not m.get("stale"):
            latest[(m["decision"].get("sense_id"), m["decision"].get("resource"))] = m["decision"].get("action")
    rows, reviewed = [], 0
    for h in meanings:
        sense, sources = senses.get(h["id"]), {}
        for r in RESOURCES:
            root = d.get("terminology", {}).get(r) or {}
            lookup = (root.get("by_meaning") or {}).get(h["id"], root) if root else {}
            sources[r] = {"decision": latest.get((sense, r)) if sense else None, "search": lookup.get("state")}
            # A decision made while the search had failed (e.g. a deferral) is recorded but does not finish that source.
            reviewed += sources[r]["decision"] is not None and sources[r]["search"] in ("HITS", "NO_RESULTS")
        rows.append({"id": h["id"], "meaning": h.get("meaning"), "local_concept": sense, "sources": sources})
    total = len(meanings) * len(RESOURCES)
    task = ("meaning" if state in ("AWAITING_REVIEW", "AWAITING_ARBITRATION", "UNRESOLVED") else "context" if state == "NEEDS_CONTEXT"
        else "closed" if state == "REJECTED" else "terminology" if reviewed < total or any(not r["local_concept"] for r in rows) else "done")
    return {"next_task": task, "label": TASK_LABELS[task], "safety": a.get("decision", {}).get("risk_signal"),
        "meanings": rows, "sources_reviewed": reviewed, "sources_total": total}


def steps(d):
    def chip(name, target, state, detail=''):
        return dict(name=name, target=target, state=state, detail=detail)
    dictionary = d.get('dictionary_evidence')
    comparison = d.get('comparison', {})
    meaning = d.get('adjudication')
    lookups = d.get('terminology', {})
    done = progress(d)
    # Green only once every source has a recorded decision; searches alone are not sign-off.
    term_state = ('attention' if any(x.get('state') not in ('HITS', 'NO_RESULTS') for x in lookups.values()) else
        'ran' if done['sources_total'] and done['sources_reviewed'] == done['sources_total'] else 'neutral')
    summary = ' · '.join(r.replace('_CT', '')+' '+('not searched' if r not in lookups else
        str(len(lookups[r].get('candidates', [])))+' candidates' if lookups[r]['state']=='HITS' else
        'no results' if lookups[r]['state']=='NO_RESULTS' else 'unavailable') for r in RESOURCES)
    return [
        chip('Utterance', 'utteranceStep', 'ran'),
        chip('Expression', 'expressionSpan', 'ran' if d['source'].get('expression_span') else 'attention'),
        chip('Models', 'modelsStep', 'ran' if comparison.get('counts', {}).get('voting', 0)>=3 else 'attention'),
        chip('Dictionary', 'dictionaryStep', 'neutral' if not dictionary else 'ran' if dictionary['state'] in ('CANDIDATES', 'NO_MATCH') else 'attention'),
        chip('Compare and route', 'comparison', 'attention' if d.get('priority', {}).get('queue')=='PRIORITY' or comparison.get('escalation') else 'ran'),
        chip('Review: meaning and safety', 'meaningStep', 'neutral' if not meaning else 'ran' if d['state']=='ADJUDICATED' else 'attention'),
        chip('Terminology', 'termStep', term_state, summary),
        chip('Record', 'recordStep', 'ran' if done['next_task'] in ('done', 'closed') else 'neutral',
            'Case saved; decision pending' if not meaning else done['label'] if done['next_task'] != 'terminology'
            else f"Meaning saved; terminology {done['sources_reviewed']} of {done['sources_total']} sources reviewed"),
    ]
