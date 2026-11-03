"""Versioned dictionary evidence, never a model vote or automatic approval."""
import json
import re
from .common import file_hash, resolve


def features(text):
    # Explicit, inspectable test rules, not a general Kiswahili stemmer.
    variants={"kichwani":"kichwa", "imejaa":"jaa", "yamejaa":"jaa", "yananijaa":"jaa", "kinajaa":"jaa"}
    return {variants.get(w,w) for w in re.findall(r"\w+",text.casefold())} - {"ya","na","wa","kwa","ni","la"}


def evidence(cfg, source):
    path = cfg.get('dictionary', {}).get('path')
    if not path:
        return {'state':'NOT_CONFIGURED','entries':[]}
    path = resolve(cfg, path)
    library = json.loads(path.read_text())
    expression=source.get('expression_span',{}).get('text',source['original_text'])
    tokens = features(expression)
    matches = []
    for entry in library['entries']:
        words = features(entry['expression'])
        shared = sorted(tokens & words)
        exact = expression.strip().casefold() == entry['expression'].strip().casefold()
        if exact or len(shared) >= 2:
            matches.append({**entry,'matched_words':shared,'match_type':'exact expression' if exact else 'multiple normalized features; not verified equivalence'})
    return {'state':'CANDIDATES' if matches else 'NO_MATCH','version':library['version'],
        'matching_version':'phrase-features-2', 'query_expression':expression, 'sha256':file_hash(path),'synthetic':library.get('synthetic'),
        'curator_approved':library.get('curator_approved',False),'entries':matches,
        'notice':'Dictionary evidence is not a vote. Lexical overlap does not establish contextual fit.'}
