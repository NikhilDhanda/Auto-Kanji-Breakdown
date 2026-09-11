"""Offline evidence for reviewing unresolved components; never modifies sources."""
from collections import Counter, defaultdict
import json
import unicodedata

from tools import build_database as builder


def category(value):
    if value.startswith('CDP-'):
        return 'CDP/IDS-style identifiers'
    if any(0x2FF0 <= ord(c) <= 0x2FFF for c in value):
        return 'CDP/IDS-style identifiers'
    if len(value) == 1:
        name = unicodedata.name(value, '')
        if name.startswith('CJK STROKE '):
            return 'CJK stroke symbols'
        if name.startswith(('HIRAGANA LETTER ', 'KATAKANA LETTER ')):
            return 'Kana'
        if name.startswith('CJK UNIFIED IDEOGRAPH-'):
            return 'Non-KANJIDIC2 ideographs'
    return 'Other structural/source labels'


def audit(entries, structures):
    """Audit retained nodes, searching all source glyphs for mapping evidence."""
    mappings = defaultdict(set)
    occurrences = defaultdict(list)
    positions = Counter()
    for char, tree in sorted(structures.items()):
        for node in builder.walk(tree):
            if 'base' in node and 'char' in node:
                mappings[node['char']].add(node['base'])
            if 'position' in node:
                positions[node['position']] += 1

        def visit(node, path):
            key = node.get('base', node.get('char'))
            if key is not None and key not in entries:
                occurrences[key].append({
                    'kanji': char, 'file': f'kanji/{ord(char):05x}.svg',
                    'path': path, 'char': node.get('char'),
                    'explicit_base': node.get('base'),
                })
            for index, child in enumerate(node.get('children', [])):
                visit(child, f'{path}.children[{index}]')

        if char in entries:
            visit(tree, 'structure')

    forms = ('NFC', 'NFD', 'NFKC', 'NFKD')
    # Reverse indexing also detects a dictionary compatibility character that
    # normalizes to the unresolved character, not just forward normalization.
    normalized_dictionary = {form: defaultdict(list) for form in forms}
    for char in sorted(entries):
        for form in forms:
            normalized_dictionary[form][unicodedata.normalize(form, char)].append(char)
    rows = {}
    totals = defaultdict(lambda: {'distinct': 0, 'occurrences': 0})
    for key, locations in sorted(occurrences.items()):
        kind = category(key)
        totals[kind]['distinct'] += 1
        totals[kind]['occurrences'] += len(locations)
        normalizations = {form: unicodedata.normalize(form, key) for form in forms}
        rows[key] = {
            'category': kind, 'count': len(locations),
            'codepoints': ' '.join(f'U+{ord(c):04X}' for c in key),
            'normalizations': normalizations,
            'normalization_matches': {form: normalized_dictionary[form].get(value, [])
                                      for form, value in normalizations.items()},
            'originals_elsewhere': sorted(mappings[key]),
            'occurrences': locations,
        }
    return {'unicode_version': unicodedata.unidata_version,
            'distinct': len(rows), 'occurrences': sum(r['count'] for r in rows.values()),
            'categories': dict(totals), 'positions_all_glyphs': dict(sorted(positions.items())),
            'values': rows}


def main():
    db, _ = builder.build(builder.default_source('kanjidic2.xml.gz'),
                          builder.default_source('kanjivg-20250816-main.zip'))
    structures, _ = builder.parse_kanjivg(builder.default_source('kanjivg-20250816-main.zip'))
    print(json.dumps(audit(db['entries'], structures), ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
