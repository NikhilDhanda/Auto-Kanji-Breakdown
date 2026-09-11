"""Conservative cleanup: canonical payloads only; ownership never follows a name."""
from copy import deepcopy

from . import templates
from .setup import Plan, Request, SIDES, inspect_notes, proven_created, row_for, safe_payload


def managed_fields(model, row):
    fields = []
    sources = row.get('source_fields', [])
    for field in model['flds']:
        records = [r for r in row.get('fields', []) if r.get('name') == field['name']]
        selected = field['name'] == row.get('output_field')
        if not records and not selected:
            continue
        if field['name'] in sources:
            raise templates.IntegrationError('A managed output is now a source field. Resolve configuration before cleanup.')
        if records and not any(r.get('id') == field.get('id') for r in records):
            raise templates.IntegrationError('A field was replaced under the same name. Cleanup cannot prove its identity.')
        fields.append(field)
    return fields


def plan_cleanup(col, raw, mid, mode='full', delete_field=False):
    if mode not in ('renderer', 'data', 'full') or (delete_field and mode != 'full'):
        raise templates.IntegrationError('Choose a supported cleanup mode.')
    before = col.models.get(mid)
    row = row_for(raw, mid)
    if not before or not row:
        raise templates.IntegrationError('Configured note type no longer exists. No notes or fields were changed.')
    model = deepcopy(before)
    owner = row.get('owner')
    if mode in ('renderer', 'full'):
        for t in model['tmpls']:
            for side in SIDES:
                t[side] = templates.replace(t[side], owner)
        model['css'] = templates.replace(model['css'], owner, css=True)
        row.update(templates=[], css=False)
    fields = managed_fields(model, row) if mode in ('data', 'full') else []
    digest, count, affected, suspicious = inspect_notes(col, mid, [f['name'] for f in fields])
    deleted = []
    if delete_field:
        for field in fields:
            if not proven_created(row, field):
                continue
            _, _, _, bad = inspect_notes(col, mid, [field['name']])
            if bad:
                raise templates.IntegrationError('An owned field contains non-generated content. Clear breakdown data without deleting the field.')
            # Conservative: any reference outside the removed blocks is enough
            # to stop deletion, including custom/filtered/cloze/browser formats.
            if any(field['name'] in t.get(key, '') for t in model['tmpls']
                   for key in ('qfmt', 'afmt', 'bqfmt', 'bafmt')):
                raise templates.IntegrationError('An owned field is referenced outside the Auto Kanji Breakdown display. Leave the field in place.')
            col.models.remove_field(model, field)
            deleted.append(field['name'])
    if mode in ('data', 'full'):
        row['enabled'] = False
    summary = (f"Note type: {model['name']}\nAction: {dict(renderer='Remove visual breakdown only', data='Clear breakdown data', full='Full cleanup')[mode]}\n"
               f"Generated fields: {', '.join(f['name'] for f in fields) or 'none'}\n"
               f"Approximately {affected} of {count} notes contain generated data to clear.\n"
               f"Notes with non-generated content to preserve: {suspicious}\n"
               f"Fields to delete: {', '.join(deleted) or 'none'}\n"
               + ('Automatic generation will be disabled.\n' if mode != 'renderer' else 'Automatic generation remains unchanged.\n')
               + ('Deleting a field changes the note type. Card references outside Auto Kanji Breakdown are checked; notes, cards and scheduling are retained.\n' if deleted else '')
               + 'User template content and user-created fields are preserved. This action can be undone.')
    return Plan(Request(mid, tuple(row.get('source_fields', [])), row.get('output_field')),
                deepcopy(before), deepcopy(raw), model, row, digest, count, affected, suspicious, summary, mode, delete_field)


def clear_fields(col, plan, committed=lambda: None):
    names = [f['name'] for f in managed_fields(plan.before_model, plan.row)]
    pending = []
    cleared = 0
    for nid in sorted(col.find_notes(f'mid:{plan.request.mid}')):
        note = col.get_note(nid)
        changed = False
        for name in names:
            if note[name] and safe_payload(note[name]):
                note[name] = ''
                changed = True
        if changed:
            pending.append(note)
        if len(pending) >= 100:
            col.update_notes(pending)
            committed()
            cleared += len(pending)
            pending.clear()
    if pending:
        col.update_notes(pending)
        committed()
        cleared += len(pending)
    return cleared
