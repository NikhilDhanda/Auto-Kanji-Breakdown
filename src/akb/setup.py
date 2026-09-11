"""Collection-local setup plans. Preview is read-only; apply rechecks its snapshot."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional
import hashlib
import json
import uuid

from .config import parse_config
from .payload import safe_payload
from . import templates
from .setup_ui import setup_summary
from .results import CleanupResult

KEY = 'auto_kanji_breakdown'
FIELD_OWNER = 'akb_owner'
SIDES = ('qfmt', 'afmt')


def read_config(col, legacy=None):
    raw = col.get_config(KEY)
    if raw is None:
        raw = legacy if isinstance(legacy, dict) else {'version': 1, 'mappings': []}
    if not isinstance(raw, dict) or raw.get('version') not in (1, 2) or not isinstance(raw.get('mappings'), list):
        raise templates.IntegrationError('Unsupported configuration. Restore valid settings before setup.')
    result = deepcopy(raw)
    result.pop('auto_data_updates', None)  # Desktop-only preference, never collection state.
    return result


def row_for(raw, mid):
    rows = [r for r in raw['mappings'] if isinstance(r, dict) and r.get('notetype_id') == mid]
    if len(rows) > 1:
        raise templates.IntegrationError('Duplicate settings for this note type. Resolve them before continuing.')
    return deepcopy(rows[0]) if rows else {}


def field_record(row, field):
    return next((r for r in row.get('fields', []) if r.get('id') == field.get('id')
                 and r.get('name') == field['name']), None)


def proven_created(row, field):
    record = field_record(row, field)
    return bool(record and record.get('created') is True and record.get('token') == row.get('owner')
                and field.get(FIELD_OWNER) == row.get('owner') and row.get('owner'))


def available_name(model):
    names = {f['name'] for f in model['flds']}
    name, number = 'Auto Kanji Breakdown', 2
    while name in names:
        name = f'Auto Kanji Breakdown ({number})'
        number += 1
    return name


@dataclass(frozen=True)
class Request:
    mid: int
    sources: tuple[str, ...]
    output: Optional[str] = None  # None explicitly requests a new dedicated field.
    targets: Optional[tuple[tuple[int, str], ...]] = None  # stable template IDs
    enabled: bool = True
    generate_existing: Optional[bool] = None  # Setup preference; never used by runtime.
    theme: Optional[str] = None  # Synced template appearance, never note payload data.


@dataclass
class Plan:
    request: Request
    before_model: dict
    before_config: dict
    model: dict
    row: dict
    digest: str
    notes: int
    affected: int
    skipped: int
    summary: str
    mode: str = 'setup'
    delete_field: bool = False


def inspect_notes(col, mid, fields):
    digest = hashlib.sha256()
    affected = skipped = 0
    ids = col.find_notes(f'mid:{mid}')
    for nid in sorted(ids):
        note = col.get_note(nid)
        values = [note[name] for name in fields]
        digest.update(json.dumps([nid, values], ensure_ascii=False).encode('utf-8'))
        affected += any(v and safe_payload(v) for v in values)
        skipped += any(v and not safe_payload(v) for v in values)
    return digest.hexdigest(), len(ids), affected, skipped


def plan_setup(col, raw, request, owner=None):
    before = col.models.get(request.mid)
    if not before:
        raise templates.IntegrationError('Note type no longer exists.')
    model = deepcopy(before)
    row = row_for(raw, request.mid)
    owner = row.get('owner') or owner or uuid.uuid4().hex
    output = request.output or available_name(model)
    draft = dict(enabled=request.enabled, notetype_id=request.mid, notetype_name=model['name'],
                 source_fields=list(request.sources), output_field=output)
    # Validate disabled mappings as well: they may later be enabled.
    checked = parse_config({'version': 2, 'mappings': [dict(draft, enabled=True)]})
    names = [f['name'] for f in model['flds']]
    if not checked.mappings or any(n not in names for n in request.sources) or len(names) != len(set(names)):
        raise templates.IntegrationError('Choose distinct existing source fields and a separate output field.')
    if request.output and request.output not in names:
        raise templates.IntegrationError('Selected output field no longer exists.')
    targets = request.targets if request.targets is not None else tuple((t['id'], 'afmt') for t in model['tmpls'])
    valid = {(t['id'], side) for t in model['tmpls'] for side in SIDES}
    if len(set(targets)) != len(targets) or any(t not in valid for t in targets):
        raise templates.IntegrationError('A selected template or side no longer exists.')
    theme = request.theme if request.theme is not None else templates.parse_theme(row.get('theme', raw.get('default_theme')))
    block = templates.html_block(output, owner, theme)
    for template in model['tmpls']:
        for side in SIDES:
            template[side] = templates.replace(template[side], owner, block if (template['id'], side) in targets else None)
    model['css'] = templates.replace(model['css'], owner, templates.css_block(owner) if targets else None, True)
    fields = row.get('fields', [])
    if request.output:
        field = next(f for f in model['flds'] if f['name'] == output)
        if field.get(FIELD_OWNER) and not proven_created(row, field):
            raise templates.IntegrationError('Output field has ownership metadata that does not match this setup.')
        if not field_record(row, field):
            fields.append({'name': output, 'id': field['id'], 'created': False})
    row.update(draft, owner=owner, fields=fields,
               templates=[{'id': tid, 'side': side} for tid, side in targets],
               css=bool(targets), renderer_version=templates.RENDERER_VERSION, theme=theme)
    if request.generate_existing is not None:
        row['generate_existing'] = request.generate_existing
    digest, count, affected, suspicious = inspect_notes(col, request.mid, [output] if request.output else [])
    if suspicious:
        raise templates.IntegrationError(f'{suspicious} notes contain non-generated output content. Choose a new dedicated field to preserve it.')
    summary = setup_summary(model, request.sources, output, targets, request.enabled,
                            count, create=request.output is None)
    summary += '\nAppearance: ' + templates.THEME_LABELS[theme]
    return Plan(request, deepcopy(before), deepcopy(raw), model, row, digest, count, affected, 0, summary)


def new_config(raw, row):
    result = deepcopy(raw)
    result['version'] = 2
    result['mappings'] = [r for r in raw['mappings'] if not isinstance(r, dict) or r.get('notetype_id') != row['notetype_id']]
    result['mappings'].append(row)
    return result


@dataclass
class Applied:
    changes: object
    error: str = ''
    cleanup: Optional[CleanupResult] = None
    changed: bool = False


def apply_theme(col, theme, expected, legacy=None):
    """Update existing owned displays together; never inspect or regenerate notes."""
    from anki.collection import OpChanges
    if theme not in templates.THEMES:
        raise templates.IntegrationError('Choose a supported appearance theme.')
    raw = read_config(col, legacy)
    if raw != expected:
        raise templates.IntegrationError('Settings changed. Reopen setup before applying the theme.')
    updated = deepcopy(raw)
    updated['default_theme'] = theme
    models = []
    seen = set()
    for row in updated['mappings']:
        if not isinstance(row, dict) or row.get('notetype_id') in seen:
            raise templates.IntegrationError('Invalid or duplicate note type settings. Restore valid settings first.')
        seen.add(row.get('notetype_id'))
        row['theme'] = theme
        model = col.models.get(row.get('notetype_id', 0))
        if not model:
            continue
        before = deepcopy(model)
        model = deepcopy(model)
        installed = False
        for card in model['tmpls']:
            for side in SIDES:
                if templates.status(card[side], row.get('owner')) != 'not installed':
                    card[side] = templates.replace(card[side], row.get('owner'),
                        templates.html_block(row.get('output_field'), row.get('owner'), theme))
                    installed = True
        if installed:
            model['css'] = templates.replace(model['css'], row.get('owner'), templates.css_block(row.get('owner')), True)
            row['renderer_version'] = templates.RENDERER_VERSION
        if model != before:
            models.append(model)
    if updated == raw and not models:
        return Applied(OpChanges())
    anchor = col.add_custom_undo_entry('Auto Kanji Breakdown theme')
    try:
        for model in models:
            col.models.update_dict(model)
            col.merge_undo_entries(anchor)
        col.set_config(KEY, updated, undoable=True)
        return Applied(col.merge_undo_entries(anchor))
    except Exception:
        col.merge_undo_entries(anchor)
        return Applied(col.undo().changes, 'Theme update failed and was rolled back.')


def apply_plan(col, plan, legacy=None, runtime=None):
    from contextlib import nullcontext
    from anki.collection import OpChanges
    from .cleanup import plan_cleanup, clear_fields, managed_fields
    raw = read_config(col, legacy)
    if raw != plan.before_config or col.models.get(plan.request.mid) != plan.before_model:
        raise templates.IntegrationError('Settings or note type changed since preview. Preview again.')
    fresh = (plan_setup(col, raw, plan.request, plan.row['owner']) if plan.mode == 'setup'
             else plan_cleanup(col, raw, plan.request.mid, plan.mode, plan.delete_field))
    if fresh.digest != plan.digest:
        raise templates.IntegrationError('Note content changed since preview. Preview again.')
    model, row = deepcopy(fresh.model), deepcopy(fresh.row)
    if fresh.mode == 'setup' and fresh.request.output is None:
        field = col.models.new_field(row['output_field'])
        field[FIELD_OWNER] = row['owner']
        col.models.add_field(model, field)
    config = new_config(raw, row)
    details = None
    if fresh.mode != 'setup':
        old_fields = managed_fields(fresh.before_model, fresh.row) if fresh.mode != 'renderer' else []
        remaining = {f['name'] for f in model['flds']}
        deleted = tuple(f['name'] for f in old_fields if f['name'] not in remaining)
        retained = []
        for f in old_fields:
            if f['name'] in remaining:
                record = field_record(fresh.row, f)
                reason = ('not_created' if record and record.get('created') is False else
                          'unverified' if not proven_created(fresh.row, f) else
                          'not_requested' if not fresh.delete_field else '')
                retained.append((f['name'], reason))
        details = CleanupResult(fresh.mode,
            templates_removed=sum(any(t[side] != old[side] for side in SIDES)
                for t, old in zip(model['tmpls'], fresh.before_model['tmpls'])),
            styling_removed=model['css'] != fresh.before_model['css'], deleted=deleted,
            retained=tuple(retained), protected=fresh.skipped, settings_changed=config != raw)
    if model == fresh.before_model and config == raw and not fresh.affected:
        return Applied(OpChanges(), cleanup=details)
    anchor = col.add_custom_undo_entry('Auto Kanji Breakdown ' + fresh.mode)
    try:
        with runtime.suspend_hook() if runtime else nullcontext():
            if fresh.mode in ('data', 'full'):
                details.notes_cleared = clear_fields(col, fresh, lambda: col.merge_undo_entries(anchor))
            if model != fresh.before_model:
                col.models.update_dict(model)
                col.merge_undo_entries(anchor)
            if fresh.mode == 'setup' and fresh.request.output is None:
                saved = col.models.get(row['notetype_id'])
                field = next(f for f in saved['flds'] if f['name'] == row['output_field'])
                row['fields'].append({'name': field['name'], 'id': field['id'], 'created': True, 'token': row['owner']})
                config = new_config(raw, row)
            col.set_config(KEY, config, undoable=True)
            return Applied(col.merge_undo_entries(anchor), cleanup=details, changed=bool(model != fresh.before_model or config != raw or (details and details.notes_cleared)))
    except Exception:
        # The CollectionOp holds the collection lock; no user operation can be
        # interleaved with this action. Roll back only our grouped public operations.
        col.merge_undo_entries(anchor)
        return Applied(col.undo().changes, 'Setup/cleanup failed and was rolled back. No requested changes were kept.')
