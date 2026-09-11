import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import weakref
import sys

from src.akb.database import Database, DatabaseError
from src.akb.config import parse_config
from src.akb.extractor import extract, plain_text
from src.akb.payload import build_payload, serialize, deserialize, components
from src.akb.runtime import Runtime
from src.akb.bulk import regenerate
from src.akb.integration import Integration

ROOT = Path(__file__).resolve().parents[1]


def configuration(mid=1, **overrides):
    row = dict(enabled=True, notetype_id=mid, notetype_name='Japanese',
               source_fields=['Text', 'Extra'], output_field='Output')
    row.update(overrides)
    return {'version': 1, 'mappings': [row]}


class Note:
    def __init__(self, text='階', extra='', output='', mid=1):
        self.mid = mid
        self.data = {'Text': text, 'Extra': extra, 'Output': output}
        self.model = {'id': mid, 'name': 'Japanese', 'flds': [{'name': n} for n in self.data]}
        self.writes = 0

    def note_type(self):
        return self.model

    def keys(self):
        return list(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.writes += 1


def all_nodes(node):
    yield node
    for child in node.get('children', []):
        yield from all_nodes(child)


class RuntimeFixture:
    @classmethod
    def setUpClass(cls):
        cls.entries = Database(ROOT / 'generated/kanji_db.json').load()

    def runtime(self, **kwargs):
        return Runtime(self.entries, parse_config(configuration(**kwargs)))


class RuntimeTests(RuntimeFixture, unittest.TestCase):
    def test_database_loads_once(self):
        db = Database(ROOT / 'generated/kanji_db.json')
        with patch.object(Path, 'read_bytes', wraps=db.path.read_bytes) as read:
            first = db.load()
            self.assertIs(first, db.load())
            self.assertEqual(read.call_count, 1)
        self.assertIn('𠮟', first)

    def test_database_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'db.json'
            with self.assertRaises(DatabaseError):
                Database(p).load()
            for data in ['{', '[]', '{"schema_version":2}', '{"schema_version":true}',
                         '{"schema_version":1,"generated":true,"sources":{},"entries":{}}']:
                p.write_text(data)
                with self.assertRaises(DatabaseError):
                    Database(p).load()

    def test_corrupt_record_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'db.json'
            p.write_text(json.dumps({'schema_version': 1, 'generated': True, 'sources': {},
                                    'entries': {'人': {'meanings': None}}}))
            with self.assertRaises(DatabaseError):
                Database(p).load()

    def test_config_multiple_and_disabled(self):
        raw = configuration()
        raw['mappings'] += configuration(mid=2)['mappings'] + configuration(mid=3, enabled=False)['mappings']
        parsed = parse_config(raw)
        self.assertEqual([m.notetype_id for m in parsed.mappings], [1, 2])
        self.assertFalse(parsed.diagnostics)

    def test_invalid_config(self):
        for raw in [None, [], {}, {'version': 2}, {'version': True}, {'version': 1, 'mappings': {}}]:
            result = parse_config(raw)
            self.assertFalse(result.mappings)
            self.assertTrue(result.diagnostics)
        for changes in [dict(notetype_id=True), dict(enabled='yes'), dict(source_fields=[]),
                        dict(source_fields=['Text', 'Text']), dict(output_field='Text'),
                        dict(source_fields=[{}]), dict(output_field='')]:
            self.assertTrue(parse_config(configuration(**changes)).diagnostics)

    def test_missing_automatic_preference_migrates_on_but_explicit_off_stays_off(self):
        for version in (1, 2):
            raw = configuration()
            raw['version'] = version
            del raw['mappings'][0]['enabled']
            before = copy.deepcopy(raw)
            self.assertEqual(len(parse_config(raw).mappings), 1)
            self.assertEqual(raw, before)
            raw['mappings'][0]['enabled'] = False
            self.assertFalse(parse_config(raw).mappings)
            for invalid in (None, 0, 'true'):
                raw['mappings'][0]['enabled'] = invalid
                self.assertTrue(parse_config(raw).diagnostics)

    def test_duplicate_mapping_disables_all_competitors(self):
        raw = configuration()
        raw['mappings'] *= 2
        self.assertFalse(parse_config(raw).mappings)

    def test_html_and_entities(self):
        text = '<div>階<br>建</div><p>&#x8a9e; &amp; 水</p><img alt="人" src="人.png">'
        self.assertEqual(extract([text], self.entries), list('階建語水'))
        self.assertIn('&', plain_text(text))
        self.assertEqual(extract(['[sound:人.mp3]<script>水</script><style>建</style>語'], self.entries), ['語'])

    def test_ruby(self):
        self.assertEqual(extract(['<ruby>階<rp>(</rp><rt>建<em>語</em></rt><rp>)</rp></ruby>水'], self.entries), ['階', '水'])

    def test_order_dedup_and_supplementary(self):
        self.assertEqual(extract(['水階水𠮟', '建階語'], self.entries), list('水階𠮟建語'))
        note = Note('水階', '建水')
        self.runtime(source_fields=['Extra', 'Text']).refresh(note)
        self.assertEqual([r['char'] for r in deserialize(note['Output'])['entries']], list('建水階'))

    def test_realistic_payload_size_and_repetition(self):
        from tools.inspect_payloads import inspect
        report = inspect()
        self.assertEqual(report['one_kanji']['payload'], report['repeated']['payload'])
        self.assertEqual(report['one_kanji']['utf8_bytes'], report['repeated']['utf8_bytes'])
        self.assertEqual(report['sentence']['chars'], list('新図書館階段上日本語読'))
        for case in report.values():
            self.assertEqual(case['utf8_bytes'], len(serialize(case['payload']).encode('utf-8')))

    def test_generation_failure_preserves_destination(self):
        note = Note(output='keep')
        with patch('src.akb.runtime.build_payload', side_effect=ValueError('broken')):
            with self.assertRaises(ValueError):
                self.runtime().refresh(note)
        self.assertEqual(note['Output'], 'keep')
        self.assertEqual(note.writes, 0)

    def test_payload_roundtrip_determinism_and_compact_provenance(self):
        p = build_payload(list('階建階'), self.entries)
        text = serialize(p)
        self.assertEqual(text, serialize(build_payload(list('階建'), self.entries)))
        self.assertEqual(deserialize(text), p)
        self.assertEqual(p['version'], 1)
        self.assertEqual(set(p), {'version', 'entries', 'provenance'})
        self.assertEqual(set(p['provenance']), {'kd', 'vg', 'db'})
        self.assertNotIn('sources', text)

    def test_markup_safe_json(self):
        p = {'version': 1, 'entries': [{'char': '人', 'meanings': ['</script><img onerror="bad"> &copy;']}]}
        text = serialize(p)
        self.assertNotIn('<', text)
        self.assertNotIn('&', text)
        self.assertEqual(deserialize(text), p)

    def test_missing_frequency_and_structure(self):
        p = build_payload(['𠮟', '㐆'], self.entries)['entries']
        self.assertNotIn('frequency', p[0])
        self.assertNotIn('children', p[1])
        self.assertEqual(p[1]['meanings'], self.entries['㐆']['meanings'])

    def test_base_lookup(self):
        p = build_payload(['階'], self.entries)['entries'][0]
        left = p['children'][0]
        self.assertEqual((left['char'], left['base']), ('⻖', '阜'))
        self.assertEqual(left['meanings'], self.entries['阜']['meanings'])
        self.assertEqual(left['radical'], 'general')

    def test_transparent_groups_keep_layout_context(self):
        node = {'position': 'top', 'children': [{'char': '人', 'position': 'left'}]}
        visible = components(node, self.entries)
        self.assertEqual(visible[0]['char'], '人')
        self.assertEqual(visible[0]['position'], 'left')
        self.assertEqual(visible[0]['via'], [{'position': 'top'}])

    def test_fragment_suppression_and_hidden_radical(self):
        node = {'char': '二', 'part': '1', 'radical': 'general', 'children': [{'char': '一'}]}
        visible = components(node, self.entries)
        self.assertEqual([v['char'] for v in visible], ['一'])
        self.assertNotIn('radical', visible[0])
        self.assertEqual(visible[0]['via'][0]['radical'], 'general')
        self.assertEqual(components({'char': '二', 'part': '2'}, self.entries), [])
        self.assertEqual(components({'char': '二', 'partial': True}, self.entries), [])

    def test_source_structure_unchanged_and_no_blank_nodes(self):
        before = copy.deepcopy(self.entries['語'])
        p = build_payload(['語', '階'], self.entries)
        self.assertEqual(before, self.entries['語'])
        for record in p['entries']:
            for n in all_nodes(record):
                self.assertTrue(n['char'])
                self.assertNotIn('part', n)
        chars = [n['char'] for n in all_nodes(p['entries'][0])]
        self.assertIn('五', chars)
        self.assertNotIn('二', chars)

    def test_root_and_deep_radical(self):
        for char in '人水':
            self.assertEqual(build_payload([char], self.entries)['entries'][0]['radical'], 'general')
        record = build_payload(['㐬'], self.entries)['entries'][0]
        self.assertTrue(any(n['char'] == '亠' and n.get('radical') == 'general' for n in all_nodes(record)))
        self.assertNotIn('radical', components({'char': '人', 'radical': 'nelson'}, self.entries)[0])

    def test_no_unresolved_meaning_invented(self):
        self.assertNotIn('meanings', components({'char': '匕', 'base': 'ヒ'}, self.entries)[0])
        self.assertEqual(components({'char': 'CDP-8BB0', 'children': [{'char': '人'}]}, self.entries)[0]['char'], '人')

    def test_updates_noop_clearing_and_output_edit(self):
        note = Note()
        runtime = self.runtime()
        self.assertTrue(runtime.before_save(note).changed)
        first = note['Output']
        self.assertFalse(runtime.before_save(note).changed)
        self.assertEqual(note.writes, 1)
        note.data['Text'] = '建'
        self.assertTrue(runtime.before_save(note).changed)
        self.assertNotEqual(first, note['Output'])
        note.data['Output'] = 'manual edit'
        self.assertTrue(runtime.before_save(note).changed)
        note.data['Text'] = 'abc'
        self.assertTrue(runtime.before_save(note).changed)
        self.assertEqual(note['Output'], '')

    def test_unrelated_and_invalid_fields_untouched(self):
        for note in [Note(mid=2), Note()]:
            if note.mid == 1:
                note.model['flds'][-1]['name'] = 'Renamed'
            old = copy.deepcopy(note.data)
            self.assertFalse(self.runtime().refresh(note).changed)
            self.assertEqual(old, note.data)

    def test_note_type_rename_keeps_id_and_field_reorder_is_safe(self):
        note = Note()
        note.model['name'] = 'Renamed'
        self.assertTrue(self.runtime().refresh(note).changed)
        note.model['flds'].reverse()
        note.data['Output'] = 'preserve'
        self.assertTrue(self.runtime().refresh(note).diagnostic)
        self.assertEqual(note['Output'], 'preserve')

    def test_suspend_only_hook(self):
        note = Note()
        runtime = self.runtime()
        with runtime.suspend_hook():
            self.assertFalse(runtime.before_save(note).changed)
            self.assertTrue(runtime.refresh(note).changed)
        note.data['Text'] = '水'
        self.assertTrue(runtime.before_save(note).changed)

    def test_adapter_weak_collection_reference_and_other_collection(self):
        class Collection:
            def get_config(self, key):
                return None
        col = Collection()
        adapter = Integration(None, 'test')
        adapter.collection, adapter.runtime = col, self.runtime()
        note = Note()
        note.col = weakref.proxy(col)
        adapter.before_save(note)
        self.assertTrue(note['Output'])
        other = Note()
        other.col = Collection()
        adapter.before_save(other)
        self.assertFalse(other['Output'])

    def test_profile_close_discards_pending_load(self):
        jobs = []
        class Query:
            def __init__(self, parent, op, success):
                self.op, self.success = op, success
            def failure(self, callback):
                return self
            def with_progress(self, label):
                return self
            def run_in_background(self):
                jobs.append(self)
        col = SimpleNamespace(models=SimpleNamespace(get=lambda mid: Note().model), get_config=lambda key: None)
        mw = SimpleNamespace(col=col, addonManager=SimpleNamespace(getConfig=lambda name: configuration()))
        adapter = Integration(mw, 'test', ROOT / 'generated/kanji_db.json')
        with patch.dict(sys.modules, {'aqt.operations': SimpleNamespace(QueryOp=Query)}):
            adapter.prepare()
            self.assertIsNone(adapter.runtime)
            adapter.close()
            jobs[0].success(jobs[0].op(col))
            self.assertIsNone(adapter.runtime)
            adapter.prepare()
            jobs[1].success(jobs[1].op(col))
            self.assertIsNotNone(adapter.runtime)
            self.assertIs(adapter.collection, col)


class CollectionStub:
    """Persist copies and undo snapshots, so tests check actual field outcomes."""
    def __init__(self, notes, runtime):
        self.notes = {i: copy.deepcopy(n) for i, n in enumerate(notes)}
        self.runtime = runtime
        self.history = []
        self.models = SimpleNamespace(get=lambda mid: next((n.model for n in self.notes.values() if n.mid == mid), None))
        self.batches = []
        self.fail_batch = None

    def find_notes(self, query):
        if not query.startswith('mid:'):
            raise ValueError('Expected numeric note-type query')
        return [i for i, note in self.notes.items() if note.mid == int(query[4:])]

    def get_note(self, nid):
        note = copy.deepcopy(self.notes[nid])
        note.id = nid
        return note

    def update_notes(self, notes):
        if len(self.batches) == self.fail_batch:
            raise RuntimeError('simulated backend failure')
        self.history.append(copy.deepcopy(self.notes))
        self.batches.append([n.id for n in notes])
        for n in notes:
            self.runtime.before_save(n)
            self.notes[n.id] = copy.deepcopy(n)
        return {'note': True}

    def undo_status(self):
        return SimpleNamespace(last_step=1)

    def merge_undo_entries(self, target):
        self.history = self.history[:target]
        return {'note': True}

    def undo(self):
        self.notes = self.history.pop()


class BulkTests(RuntimeFixture, unittest.TestCase):
    def test_bulk_changed_only_one_undo(self):
        runtime = self.runtime()
        unchanged = Note('水')
        runtime.refresh(unchanged)
        col = CollectionStub([Note(), unchanged, Note('建'), Note(mid=2)], runtime)
        before = copy.deepcopy(col.notes)
        result = regenerate(col, runtime, {}, batch_size=1)
        self.assertEqual((result.scanned, result.changed), (3, 2))
        self.assertEqual(col.batches, [[0], [2]])
        self.assertEqual(len(col.history), 1)
        self.assertEqual(col.notes[3].data, before[3].data)
        col.undo()
        self.assertEqual([n.data for n in col.notes.values()], [n.data for n in before.values()])

    def test_cancel_keeps_committed_batches_undoable(self):
        runtime = self.runtime()
        col = CollectionStub([Note(), Note('水'), Note('建')], runtime)
        result = regenerate(col, runtime, {}, cancelled=lambda: len(col.batches) == 1, batch_size=1)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.changed, 1)
        self.assertFalse(col.notes[1]['Output'])
        col.undo()
        self.assertFalse(col.notes[0]['Output'])

    def test_cancel_before_write_and_failure(self):
        runtime = self.runtime()
        col = CollectionStub([Note()], runtime)
        result = regenerate(col, runtime, {}, cancelled=lambda: True)
        self.assertTrue(result.cancelled)
        self.assertFalse(col.history)
        col = CollectionStub([Note(), Note('水')], runtime)
        col.fail_batch = 1
        result = regenerate(col, runtime, {}, batch_size=1)
        self.assertTrue(result.error)
        self.assertEqual(result.changed, 1)
        col.undo()
        self.assertFalse(col.notes[0]['Output'])

    def test_bulk_no_changes_no_undo(self):
        runtime = self.runtime()
        col = CollectionStub([Note('abc')], runtime)
        result = regenerate(col, runtime, {})
        self.assertEqual(result.changed, 0)
        self.assertFalse(col.history)
