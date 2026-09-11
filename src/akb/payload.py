"""A self-contained projection, serialized once as HTML-safe JSON text."""
import copy
import json


def components(node, entries):
    children = [visible for child in node.get('children', []) for visible in components(child, entries)]
    char = node.get('char')
    hidden = not char or len(char) != 1 or 'part' in node or node.get('partial') is True
    if hidden:
        # Preserve source-layout boundaries on promoted children, without assigning
        # the hidden parent's position or radical to the child itself.
        context = {k: node[k] for k in ('position', 'part', 'number') if k in node}
        if node.get('radical') == 'general':
            context['radical'] = 'general'
        if context:
            for child in children:
                child['via'] = [context.copy(), *child.get('via', [])]
        return children
    result = {'char': char}
    base = node.get('base', char)
    if base != char:
        result['base'] = base
    meanings = entries.get(base, {}).get('meanings', [])
    if meanings:
        result['meanings'] = list(meanings)
    for key in ('position', 'phon'):
        if key in node:
            result[key] = node[key]
    if node.get('variant'):
        result['variant'] = True
    if node.get('radical') == 'general':
        result['radical'] = 'general'
    if children:
        result['children'] = children
    return [result]


def build_payload(chars, entries):
    records = []
    for char in dict.fromkeys(chars):
        source = entries[char]
        record = {'char': char, 'meanings': list(source['meanings']),
                  'readings': copy.deepcopy(source['readings'])}
        for key in ('strokes', 'frequency'):
            if key in source:
                record[key] = source[key]
        tree = source.get('structure')
        if tree:
            if tree.get('radical') == 'general':
                record['radical'] = 'general'
            children = [v for child in tree.get('children', []) for v in components(child, entries)]
            if children:
                record['children'] = children
        records.append(record)
    result = {'version': 1, 'entries': records}
    if getattr(entries, 'provenance', None):
        result['provenance'] = dict(entries.provenance)
    return result


def serialize(payload):
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    # Fields are HTML. Escape markup delimiters as JSON escapes, not HTML entities.
    # JSON.parse(field.textContent) recovers the original strings on any client.
    for char, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e')]:
        value = value.replace(char, escaped)
    return value


def deserialize(value):
    data = json.loads(value)
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('Unsupported payload version')
    if not isinstance(data.get('entries'), list):
        raise ValueError('Invalid payload entries')
    return data


def safe_payload(value):
    """Recognize empty/canonical generated data before explicit manual replacement."""
    if not value:
        return True
    try:
        data = deserialize(value)
        return serialize(data) == value and all(isinstance(n, dict) and isinstance(n.get('char'), str)
                                                and len(n['char']) == 1 for n in data['entries'])
    except (ValueError, TypeError):
        return False
