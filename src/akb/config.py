"""Versioned configuration; IDs choose note types, exact names choose fields."""
from collections import Counter
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Mapping:
    notetype_id: int
    source_fields: tuple[str, ...]
    output_field: str
    notetype_name: str = ''
    output_id: Optional[int] = None
    owner: Optional[str] = None


@dataclass(frozen=True)
class Config:
    mappings: tuple[Mapping, ...] = ()
    diagnostics: tuple[str, ...] = ()


def parse_config(raw):
    if not isinstance(raw, dict) or type(raw.get('version')) is not int or raw['version'] not in (1, 2):
        return Config(diagnostics=('Configuration must have version 1 or 2; all mappings disabled.',))
    rows = raw.get('mappings')
    if not isinstance(rows, list):
        return Config(diagnostics=('Configuration mappings must be an array; all mappings disabled.',))
    ids = Counter(row.get('notetype_id') for row in rows if isinstance(row, dict)
                  and type(row.get('notetype_id')) is int)
    good, messages = [], []
    for index, row in enumerate(rows):
        label = f'Mapping {index + 1}'
        if not isinstance(row, dict):
            messages.append(f'{label}: expected an object; skipped.')
            continue
        mid, fields, output = row.get('notetype_id'), row.get('source_fields'), row.get('output_field')
        enabled = row.get('enabled', True)
        if type(enabled) is not bool:
            messages.append(f'{label}: enabled must be boolean; skipped.')
            continue
        if not enabled:
            continue
        if type(mid) is not int or mid <= 0 or ids[mid] != 1:
            messages.append(f'{label}: invalid or duplicate note type ID; skipped.')
            continue
        if (not isinstance(fields, list) or not fields or
                not all(isinstance(f, str) and f.strip() for f in fields) or
                len(set(fields)) != len(fields) or not isinstance(output, str) or
                not output.strip() or output in fields or
                not isinstance(row.get('notetype_name', ''), str)):
            messages.append(f'{label}: invalid fields or source/output overlap; skipped.')
            continue
        records = row.get('fields', [])
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            messages.append(f'{label}: invalid field identity records; skipped.')
            continue
        record = next((r for r in reversed(records) if r.get('name') == output), {})
        good.append(Mapping(mid, tuple(fields), output, row.get('notetype_name', ''),
                            record.get('id'), row.get('owner') if record.get('created') else None))
    return Config(tuple(good), tuple(messages))


def validate_mapping(mapping, notetype):
    if not notetype or notetype.get('id') != mapping.notetype_id:
        return 'Configured note type no longer exists.'
    names = [field['name'] for field in notetype['flds']]
    if len(names) != len(set(names)):
        return 'Note type has ambiguous field names.'
    if any(name not in names for name in (*mapping.source_fields, mapping.output_field)):
        return 'A configured field is missing or renamed; update the mapping.'
    output = next(f for f in notetype['flds'] if f['name'] == mapping.output_field)
    if ((mapping.output_id is not None and mapping.output_id != output.get('id')) or
            (mapping.owner is not None and mapping.owner != output.get('akb_owner'))):
        return 'Generated field identity changed; generation is disabled for this note type until setup is repaired.'
    return None
