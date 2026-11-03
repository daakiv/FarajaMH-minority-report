"""Shared synthetic intake; offsets are Unicode code points, end exclusive."""
import re
from .common import now, scan_identifiers, validate

LANGUAGES = ('sw', 'en', 'mul', 'sw-x-sheng', 'sw-KE', 'sw-TZ', 'und')

class IntakeError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def prepare_case(fields, *, mode, person, exists=lambda uid: False):
    def check(ok, field, message):
        if not ok:
            raise IntakeError(field, message)
    check(mode != 'fixture', 'mode', 'New expressions require config.live-test.yaml; fixture intake is disabled.')
    check('reviewer' in person.get('roles', []), 'identity', 'Reviewer role required.')
    check(isinstance(fields, dict), 'intake', 'Supply an intake object.')
    uid = fields.get('utterance_id', '')
    check(isinstance(uid, str) and re.fullmatch(r'[A-Za-z0-9_-]+', uid), 'utterance_id', 'Use letters, numbers, underscores or hyphens for the record ID.')
    check(not exists(uid), 'utterance_id', 'This record ID already exists or is running.')
    check(fields.get('synthetic') is True, 'synthetic', 'Confirm that this is invented, synthetic data.')
    text, expression = fields.get('original_text'), fields.get('expression_text')
    check(isinstance(text, str) and bool(text.strip()), 'original_text', 'Enter the original utterance.')
    check(isinstance(expression, str) and bool(expression.strip()), 'expression_text', 'Copy the exact expression from the utterance.')
    starts = [i for i in range(len(text)) if text.startswith(expression, i)]
    check(bool(starts), 'expression_text', 'The expression must match the original utterance exactly.')
    occurrence = fields.get('occurrence')
    if occurrence is None and len(starts) == 1:
        occurrence = 1
    check(type(occurrence) is int and 1 <= occurrence <= len(starts), 'occurrence', 'Choose which occurrence of the expression to use.')
    language = fields.get('language')
    check(language in LANGUAGES, 'language', 'Choose a supported language code.')
    for key, allowed in {'experiencer': ('self', 'other', 'unknown'), 'assertion': ('affirmed', 'negated', 'uncertain', 'unknown'), 'event_time': ('present', 'past', 'future', 'recurrent', 'unknown')}.items():
        check(fields.get(key) in allowed, key, 'Choose a valid ' + key.replace('_', ' ') + '.')
    context, setting = fields.get('conversation_context', ''), fields.get('setting', '')
    for key, value in [('conversation_context', context), ('setting', setting)]:
        check(isinstance(value, str), key, 'Enter text for ' + key.replace('_', ' ') + '.')
    start = starts[occurrence - 1]
    source = dict(schema_version='1.0', utterance_id=uid, synthetic=True, original_text=text,
        language=language, language_spans=[], source_type='synthetic test', speaker_role='synthetic speaker',
        speaker_ref='SYN-person', region_variety=None, conversation=context or 'Context not supplied',
        expression_span={'start': start, 'end': start + len(expression), 'text': expression},
        qualifiers={'experiencer': fields['experiencer'], 'assertion': fields['assertion'], 'attribution': 'unknown',
            'event_time': fields['event_time'], 'utterance_time': now(), 'setting': setting or 'unknown'},
        evidence=[{'id': 'E1', 'text': text, 'reference': 'Synthetic utterance supplied at intake'}])
    if context.strip():
        source['evidence'].append({'id': 'E2', 'text': context, 'reference': 'Synthetic conversation context supplied at intake'})
    for field, value in fields.items():
        try:
            scan_identifiers(value)
        except ValueError:
            raise IntakeError(field, 'Possible identifier detected. Use invented data without contact details.') from None
    validate('source', source)
    return source


# The review screen's fields, accepted from a CSV or JSONL file so a whole test pack can run unattended.
INTAKE_FIELDS = ('utterance_id', 'original_text', 'expression_text', 'occurrence', 'language', 'experiencer',
    'assertion', 'event_time', 'setting', 'conversation_context', 'synthetic')
VERBATIM = ('original_text', 'expression_text', 'conversation_context')


def read_rows(path):
    import csv
    import json
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = [dict(row) for row in csv.DictReader(stream)]
    else:
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    cleaned = []
    for row in rows:
        row = {k: (v.strip() if isinstance(v, str) and k not in VERBATIM else v) for k, v in row.items()}
        if isinstance(row.get('synthetic'), str):
            row['synthetic'] = row['synthetic'].casefold() in ('true', 'yes', 'y', '1')
        occurrence = row.get('occurrence')
        if occurrence in ('', None):
            row['occurrence'] = None
        elif isinstance(occurrence, str) and occurrence.isdigit():
            row['occurrence'] = int(occurrence)
        for key in ('setting', 'conversation_context'):
            row[key] = row.get(key) or ''
        cleaned.append(row)
    return cleaned


def run_file(app, path, token):
    """Check every row with the same rules as the review screen; run none unless all pass."""
    person = app.identity(token, 'reviewer')
    app.check_mode()
    rows = read_rows(path)
    if not rows:
        raise IntakeError('file', 'The file has no cases.')
    existing = {row[0] for row in app.store.db.execute('SELECT id FROM sources')}
    seen, refused, sources = set(), [], []
    for number, row in enumerate(rows, 1):
        try:
            unknown = sorted(set(row) - set(INTAKE_FIELDS))
            if unknown:
                raise IntakeError(unknown[0], 'Unknown column ' + unknown[0] + '; use ' + ', '.join(INTAKE_FIELDS) + '.')
            source = prepare_case(row, mode=app.cfg['mode'], person=person, exists=lambda uid: uid in existing or uid in seen)
            seen.add(source['utterance_id'])
            sources.append(source)
        except IntakeError as exc:
            refused.append(f'case {number} ({row.get("utterance_id", "no ID")}) {exc.field}: {exc}')
    if refused:
        raise IntakeError('file', 'No cases were run. Fix these and try again: ' + ' | '.join(refused))
    results = []
    for source in sources:
        d = app.run(source, actor=person['id'])
        results.append({'utterance_id': source['utterance_id'], 'version': d['version'], 'state': d['state'],
            'comparison': d['comparison']['state'], 'usable_readings': d['comparison']['counts']['voting']})
    return {'count': len(results), 'results': results}
