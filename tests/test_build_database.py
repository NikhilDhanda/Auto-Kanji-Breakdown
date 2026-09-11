import copy
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from tools import build_database as b
from tools import audit_components as audit


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kd = b.default_source('kanjidic2.xml.gz')
        cls.vg = b.default_source('kanjivg-20250816-main.zip')
        cls.before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (cls.kd, cls.vg)]
        cls.db, cls.stats = b.build(cls.kd, cls.vg)
        cls.entries = cls.db['entries']

    def test_dictionary_values_match_source(self):
        root = ET.fromstring(gzip.decompress(self.kd.read_bytes()))
        self.assertEqual(set(self.entries), {c.findtext('literal') for c in root.findall('character')})
        for c in root.findall('character'):
            entry = self.entries[c.findtext('literal')]
            self.assertEqual(entry['meanings'], [m.text for m in c.findall('reading_meaning/rmgroup/meaning')
                                                if m.get('m_lang', 'en') == 'en'])
            for kind, target in [('ja_on', 'on'), ('ja_kun', 'kun')]:
                self.assertEqual(entry['readings'][target], [r.text for r in c.findall('reading_meaning/rmgroup/reading')
                                                           if r.get('r_type') == kind])
        self.assertIn('かた.る', self.entries['語']['readings']['kun'])

    def test_dictionary_optional_and_language_fields(self):
        xml = b'''<kanjidic2><header><file_version>4</file_version></header>
        <character><literal>A</literal><misc><stroke_count>3</stroke_count><stroke_count>4</stroke_count></misc>
        <reading_meaning><rmgroup><meaning>first</meaning><meaning m_lang="fr">non</meaning>
        <meaning m_lang="en">second</meaning><reading r_type="ja_kun">a.b</reading>
        <reading r_type="pinyin">excluded</reading></rmgroup></reading_meaning></character></kanjidic2>'''
        entries, _, stats = b.parse_kanjidic(xml)
        self.assertEqual(entries['A'], {'strokes': 3, 'meanings': ['first', 'second'],
                                       'readings': {'on': [], 'kun': ['a.b']}})
        self.assertEqual(stats['alternative_stroke_counts'], 1)

    def test_nested_structure_and_split_parts(self):
        tree = self.entries['語']['structure']
        self.assertEqual([c['char'] for c in tree['children']], ['言', '吾'])
        right = tree['children'][1]
        self.assertEqual(right['phon'], '吾')
        self.assertEqual([c['part'] for c in right['children'][0]['children']], ['1', '2'])
        with zipfile.ZipFile(self.vg) as z:
            self.assertEqual(b.parse_svg(z.read('kanji/08a9e.svg'), '語'), tree)

    def test_original_meanings(self):
        nodes = [n for e in self.entries.values() if 'structure' in e for n in b.walk(e['structure'])]
        for displayed, base in [('亻', '人'), ('氵', '水'), ('忄', '心'), ('⻖', '阜')]:
            matches = [n for n in nodes if n.get('char') == displayed and n.get('base') == base]
            self.assertTrue(matches)
            for node in matches:
                self.assertEqual(b.component_meanings(node, self.entries), self.entries[base]['meanings'])
        self.assertEqual(b.component_meanings({'char': '人', 'base': 'absent'}, self.entries), [])
        self.assertEqual(b.component_meanings({}, self.entries), [])

    def test_radicals_at_all_depths(self):
        for char in ['人', '水']:
            self.assertEqual(self.entries[char]['structure']['radical'], 'general')
        self.assertEqual(self.entries['階']['structure']['children'][0]['radical'], 'general')
        deep = [n for e in self.entries.values() if 'structure' in e
                for child in e['structure'].get('children', [])
                for grandchild in child.get('children', []) for n in b.walk(grandchild) if 'radical' in n]
        self.assertTrue(deep)
        self.assertEqual(self.entries['㐬']['structure']['children'][0]['children'][0],
                         {'char': '亠', 'radical': 'general'})
        types = {n['radical'] for e in self.entries.values() if 'structure' in e
                 for n in b.walk(e['structure']) if 'radical' in n}
        self.assertTrue({'general', 'tradit', 'nelson', 'jis'} <= types)

    def test_missing_structure_frequency_and_supplementary(self):
        missing = [e for e in self.entries.values() if 'structure' not in e]
        self.assertTrue(missing)
        self.assertTrue(any(e['meanings'] for e in missing))
        self.assertTrue(any('frequency' not in e for e in self.entries.values()))
        self.assertIn('𠮟', self.entries)
        self.assertTrue(self.entries['𠮟']['meanings'])
        self.assertEqual(self.stats['supplementary_characters'], sum(ord(c) > 65535 for c in self.entries))

    def test_unnamed_groups_retained(self):
        nodes = list(b.walk(self.entries['階']['structure']))
        self.assertTrue(any('char' not in n and n.get('position') == 'left' for n in nodes))
        self.assertTrue(any(n.get('position') == 'nyoc' for n in b.walk(self.entries['建']['structure'])))

    def test_determinism_roundtrip_and_source_integrity(self):
        second, stats = b.build(self.kd, self.vg)
        self.assertEqual(b.encode(self.db), b.encode(second))
        self.assertEqual(self.stats, stats)
        self.assertEqual(json.loads(b.encode(self.db)), self.db)
        self.assertIn('𠮟'.encode(), b.encode(self.db))
        self.assertEqual(self.before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.kd, self.vg)])
        self.assertEqual(self.stats['output_bytes'], len(b.encode(self.db)))

    def test_schema_rejects_corruption(self):
        b.validate(self.db)
        for mutate in [lambda d: d.update(schema_version=2),
                       lambda d: d['entries']['人'].update(frequency=None),
                       lambda d: d['entries']['人']['structure'].update(radical=True),
                       lambda d: d['entries']['人']['structure'].update(children=[None]),
                       lambda d: d['entries']['人'].update(meanings=['']),
                       lambda d: d['entries']['人'].update(components=[])]:
            bad = copy.deepcopy(self.db)
            mutate(bad)
            with self.assertRaises(ValueError):
                b.validate(bad)

    def test_malformed_and_duplicate_sources(self):
        with self.assertRaises(ValueError):
            b.parse_kanjidic(b'<kanjidic2><header/><character><literal>A</literal></character><character><literal>A</literal></character></kanjidic2>')
        with self.assertRaises(ET.ParseError):
            b.parse_svg(b'<broken', '人')
        with zipfile.ZipFile(self.vg) as z:
            with self.assertRaises(ValueError):
                b.parse_svg(z.read('kanji/04eba.svg'), '水')

    def test_merge_does_not_mutate_inputs(self):
        entries = {'人': {'meanings': ['person'], 'readings': {'on': [], 'kun': []}}}
        trees = {'人': {'char': '人', 'radical': 'general'}}
        result = b.merge(entries, trees)
        result['人']['structure']['char'] = '水'
        self.assertNotIn('structure', entries['人'])
        self.assertEqual(trees['人']['char'], '人')

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            b.write_atomic(path, b'old')
            b.write_atomic(path, b'new')
            self.assertEqual(path.read_bytes(), b'new')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_cli_rejects_source_overwrite(self):
        result = subprocess.run([sys.executable, str(b.ROOT / 'tools/build_database.py'),
                                 '--output', str(self.kd)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'must not overwrite', result.stderr)
        self.assertEqual(hashlib.sha256(self.kd.read_bytes()).hexdigest(), self.before[0])

    def test_source_layout_has_no_root_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'kanjidic2.xml.gz').write_bytes(b'root-only fixture')
            with patch.object(b, 'ROOT', root):
                source = b.default_source('kanjidic2.xml.gz')
                self.assertEqual(source, root / 'data_sources/kanjidic2.xml.gz')
                self.assertFalse(source.exists())

    def test_audit_accounts_for_every_unresolved_occurrence(self):
        structures, _ = b.parse_kanjivg(self.vg)
        report = audit.audit(self.entries, structures)
        self.assertEqual({k: r['count'] for k, r in report['values'].items()},
                         self.stats['unresolved_bases'])
        self.assertEqual(report['occurrences'], self.stats['unresolved_components'])
        self.assertEqual(sum(c['distinct'] for c in report['categories'].values()), report['distinct'])
        for key, row in report['values'].items():
            for occurrence in row['occurrences']:
                self.assertEqual(occurrence['explicit_base'] or occurrence['char'], key)
        # These labels must not silently acquire meanings through visual guesses.
        for key in ['㇒', 'マ', '龰', 'CDP-8BB0']:
            self.assertEqual(b.component_meanings({'char': key}, self.entries), [])
        self.assertEqual(b.component_meanings({'char': '匕', 'base': 'ヒ'}, self.entries), [])

    def test_audit_finds_normalization_and_original_candidates(self):
        entries = {'A': {}, '人': {}, '神': {}}
        structures = {'A': {'char': 'A', 'children': [{'char': 'Ａ'}, {'char': '神'}, {'char': '亻'}]},
                      'B': {'char': 'B', 'children': [{'char': '亻', 'base': '人'}]}}
        report = audit.audit(entries, structures)
        self.assertEqual(report['values']['Ａ']['normalization_matches']['NFKC'], ['A'])
        self.assertEqual(report['values']['神']['normalization_matches']['NFKC'], ['神'])
        self.assertEqual(report['values']['亻']['originals_elsewhere'], ['人'])
        self.assertNotIn('B', report['values'])

    def test_audit_categories(self):
        for value, expected in [('㇒', 'CJK stroke symbols'), ('CDP-8BB0', 'CDP/IDS-style identifiers'),
                                ('⿱日隹', 'CDP/IDS-style identifiers'), ('つ', 'Kana'),
                                ('龰', 'Non-KANJIDIC2 ideographs'), ('⺄', 'Other structural/source labels')]:
            self.assertEqual(audit.category(value), expected)


if __name__ == '__main__':
    unittest.main()
