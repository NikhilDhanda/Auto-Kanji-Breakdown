"""Scoped regeneration: pure workers, adapter ordering, real temporary collections."""
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_runtime import RuntimeFixture, Note, CollectionStub
from src.akb.bulk import regenerate
from src.akb import commands
from src.akb.config import parse_config
from src.akb.database import Database
from src.akb.integration import Integration
from src.akb.payload import deserialize
from src.akb.runtime import Runtime

try:
    from anki.collection import Collection, OpChanges
    from anki import hooks
except ModuleNotFoundError:
    Collection = None


class SelectedTests(RuntimeFixture, unittest.TestCase):
    def test_selection_is_deduplicated_and_isolated(self):
        runtime = self.runtime()
        same = Note('水')
        runtime.refresh(same)
        col = CollectionStub([Note('大'), same, Note('建'), Note(mid=2)], runtime)
        result = regenerate(col, runtime, {}, note_ids=[0, 0, 1, 3], batch_size=1)
        self.assertEqual((result.total, result.scanned, result.processed, result.changed,
                          result.unchanged, result.skipped, result.failed), (3, 3, 2, 1, 1, 1, 0))
        self.assertEqual(col.batches, [[0]])
        self.assertFalse(col.notes[2]['Output'])
        col.undo()
        self.assertFalse(col.notes[0]['Output'])

    def test_protected_output_has_an_exact_result_count(self):
        runtime = self.runtime()
        note = Note('水')
        note['Output'] = '<b>Keep my text</b>'
        col = CollectionStub([note], runtime)
        result = regenerate(col, runtime, {}, note_ids=[0])
        self.assertEqual((result.changed, result.skipped, result.protected), (0, 1, 1))
        self.assertEqual(col.notes[0]['Output'], '<b>Keep my text</b>')

    def test_suspicious_content_missing_fields_and_unconfigured(self):
        runtime = self.runtime()
        suspicious = Note()
        suspicious['Output'] = '<b>my content</b>'
        for note in [suspicious, Note(mid=2)]:
            before = copy.deepcopy(note.data)
            self.assertTrue(runtime.refresh(note, manual=True).diagnostic)
            self.assertEqual(note.data, before)
        for name in ('Text', 'Output'):
            note = Note()
            note.model['flds'] = [f for f in note.model['flds'] if f['name'] != name]
            before = copy.deepcopy(note.data)
            self.assertTrue(runtime.refresh(note, manual=True).diagnostic)
            self.assertEqual(note.data, before)

    def test_empty_selection_does_not_fall_back_to_global(self):
        runtime = self.runtime()
        col = CollectionStub([Note()], runtime)
        result = regenerate(col, runtime, {}, note_ids=[])
        self.assertEqual(result.scanned, 0)
        self.assertFalse(col.batches)

    def test_cancel_discards_pending_and_committed_changes_undo(self):
        runtime = self.runtime()
        col = CollectionStub([Note(), Note('水'), Note('建')], runtime)
        progress = []
        result = regenerate(col, runtime, {}, note_ids=[0, 1, 2], batch_size=1,
                            progress=lambda done, total: progress.append(done),
                            cancelled=lambda: bool(progress) and progress[-1] >= 2)
        self.assertEqual((result.changed, result.pending, result.scanned), (1, 1, 2))
        self.assertTrue(result.cancelled)
        self.assertFalse(col.notes[1]['Output'])
        col.undo()
        self.assertFalse(col.notes[0]['Output'])

    def test_generation_failure_isolated_but_commit_failure_stops(self):
        runtime = self.runtime()
        col = CollectionStub([Note(), Note('水'), Note('建')], runtime)
        original = runtime.refresh
        def fail_one(note, **kwargs):
            if note.id == 1:
                raise ValueError('bad source')
            return original(note, **kwargs)
        with patch.object(runtime, 'refresh', side_effect=fail_one):
            result = regenerate(col, runtime, {}, note_ids=[0, 1, 2], batch_size=1)
        self.assertEqual((result.changed, result.failed), (2, 1))
        self.assertFalse(col.notes[1]['Output'])
        col = CollectionStub([Note(), Note('水'), Note('建')], runtime)
        col.fail_batch = 1
        result = regenerate(col, runtime, {}, note_ids=[0, 1, 2], batch_size=1)
        self.assertTrue(result.error)
        self.assertEqual(result.changed, 1)
        self.assertFalse(col.notes[2]['Output'])

    def test_missing_selected_note_does_not_stop_other_reads(self):
        runtime = self.runtime()
        col = CollectionStub([Note()], runtime)
        result = regenerate(col, runtime, {}, note_ids=[0, 999])
        self.assertEqual((result.changed, result.failed), (1, 1))


@unittest.skipIf(Collection is None, 'Optional Anki backend is not installed')
class ManualBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.col = Collection(str(Path(self.temp.name) / 'collection.anki2'))
        model = self.col.models.new('Manual test')
        for name in ('Text', 'Output'):
            self.col.models.add_field(model, self.col.models.new_field(name))
        template = self.col.models.new_template('Card')
        template.update(qfmt='{{Text}}', afmt='{{Output}}')
        self.col.models.add_template(model, template)
        self.model = self.col.models.get(self.col.models.add_dict(model).id)
        config = parse_config({'version': 1, 'mappings': [{'enabled': True,
                              'notetype_id': self.model['id'], 'source_fields': ['Text'], 'output_field': 'Output'}]})
        self.runtime = Runtime(Database(Path(__file__).resolve().parents[1] / 'generated/kanji_db.json').load(), config)
        self.adapter = Integration(SimpleNamespace(col=self.col), 'test')
        self.adapter.runtime, self.adapter.collection = self.runtime, self.col
        hooks.note_will_flush.append(self.adapter.before_save)
        self.messages, self.operations = [], []
        test = self
        class Operation:
            def __init__(self, parent, op):
                self.op = op
            def with_backend_progress(self, update):
                return self
            def success(self, callback):
                self.done = callback
                return self
            def failure(self, callback):
                self.fail = callback
                return self
            def run_in_background(self, initiator=None):
                test.operations.append(initiator)
                self.done(self.op(test.col))
        self.modules = patch.dict('sys.modules', {
            'aqt.operations': SimpleNamespace(CollectionOp=Operation),
            'aqt.utils': SimpleNamespace(tooltip=lambda message, **kwargs: self.messages.append(message),
                                        showInfo=lambda message, **kwargs: self.messages.append(message))})
        self.modules.start()

    def tearDown(self):
        self.modules.stop()
        hooks.note_will_flush.remove(self.adapter.before_save)
        self.col.close()
        self.temp.cleanup()

    def note(self, text, add=True):
        note = self.col.new_note(self.model)
        note['Text'] = text
        if add:
            self.col.add_note(note, 1)
        return note

    def editor(self, note, edited=None, add=False):
        editor = SimpleNamespace(widget=object(), note=note, addMode=add, loads=0, flushes=0)
        def load():
            editor.loads += 1
        def save(callback, keepFocus=False):
            self.assertTrue(keepFocus)
            editor.flushes += 1
            if edited is not None:
                note['Text'] = edited
                if not add:
                    self.col.update_note(note)
            callback()
        editor.loadNoteKeepingFocus = load
        editor.call_after_note_saved = save
        return editor

    def test_current_unsaved_edit_gains_kanji_and_undo_is_one_action(self):
        note = self.note('おおきい')
        editor = self.editor(note, '大きい')
        commands.current_note(self.adapter, editor)
        self.assertEqual(deserialize(self.col.get_note(note.id)['Output'])['entries'][0]['char'], '大')
        self.assertEqual(editor.flushes, 1)
        self.assertEqual(editor.loads, 1)
        self.assertEqual(self.operations, [editor])
        self.assertIn('updated', self.messages[-1])
        self.col.undo()
        restored = self.col.get_note(note.id)
        self.assertEqual((restored['Text'], restored['Output']), ('おおきい', ''))

    def test_current_loses_kanji_and_unchanged_has_no_extra_write(self):
        note = self.note('大きい')
        commands.current_note(self.adapter, self.editor(note, 'おおきい'))
        self.assertEqual(self.col.get_note(note.id)['Output'], '')
        anchor = self.col.undo_status().last_step
        commands.current_note(self.adapter, self.editor(note))
        self.assertEqual(self.col.undo_status().last_step, anchor)
        self.assertIn('already up to date', self.messages[-1])

    def test_new_draft_changes_in_memory_without_adding_note(self):
        note = self.note('おおきい', add=False)
        editor = self.editor(note, '大きい', add=True)
        commands.current_note(self.adapter, editor)
        self.assertEqual(deserialize(note['Output'])['entries'][0]['char'], '大')
        self.assertEqual(self.col.find_notes(''), [])
        self.assertEqual(self.operations, [])

    def test_current_suspicious_output_refused_before_editor_flush(self):
        note = self.note('大')
        note['Output'] = 'handwritten'
        editor = self.editor(note)
        commands.current_note(self.adapter, editor)
        self.assertEqual(editor.flushes, 0)
        self.assertEqual(note['Output'], 'handwritten')
        self.assertIn('preserved', self.messages[-1])

    def test_saved_payload_repair_and_selected_duplicates(self):
        notes = [self.note(c) for c in '大水建']
        with self.runtime.suspend_hook():
            for note in notes:
                note['Text'] = '語'
            self.col.update_notes(notes)
        browser = SimpleNamespace(editor=self.editor(notes[0]), selected_notes=lambda: [notes[0].id, notes[0].id, notes[1].id])
        commands.selected_notes(self.adapter, browser)
        self.assertTrue(all(deserialize(self.col.get_note(n.id)['Output'])['entries'][0]['char'] == '語' for n in notes[:2]))
        self.assertEqual(deserialize(self.col.get_note(notes[2].id)['Output'])['entries'][0]['char'], '建')
        self.assertIn('2 notes updated.', self.messages[-1])
        self.col.undo()
        self.assertEqual(deserialize(self.col.get_note(notes[0].id)['Output'])['entries'][0]['char'], '大')

    def test_current_saved_note_repairs_bypassed_hook(self):
        note = self.note('大')
        with self.runtime.suspend_hook():
            note['Text'] = '水'
            self.col.update_note(note)
        editor = self.editor(note)
        commands.current_note(self.adapter, editor)
        self.assertEqual(deserialize(note['Output'])['entries'][0]['char'], '水')
        self.assertIn('updated', self.messages[-1])

    def test_browser_single_selection_with_experimental_editor_interface(self):
        note = self.note('大')
        with self.runtime.suspend_hook():
            note['Text'] = '水'
            self.col.update_note(note)
        # NewEditor exposes nid and a supported save callback, but no .note.
        editor = SimpleNamespace(nid=note.id, call_after_note_saved=lambda callback, **kw: callback())
        browser = SimpleNamespace(editor=editor, selected_notes=lambda: [note.id])
        commands.selected_notes(self.adapter, browser)
        self.assertEqual(deserialize(self.col.get_note(note.id)['Output'])['entries'][0]['char'], '水')
        self.assertIn('1 note updated.', self.messages[-1])

    def test_current_unconfigured_does_not_flush(self):
        note = self.note('大')
        editor = self.editor(note)
        self.adapter.fallback_mappings = {}
        commands.current_note(self.adapter, editor)
        self.assertEqual(editor.flushes, 0)
        self.assertIn('not configured', self.messages[-1])

    def test_menus_use_webview_editor_and_browser_selection(self):
        actions = []
        class Menu:
            def addAction(self, label):
                self.label = label
                action = SimpleNamespace(triggered=object())
                actions.append(action)
                return action
        callbacks = []
        qt = SimpleNamespace(qconnect=lambda signal, callback: callbacks.append(callback))
        note = self.note('大')
        editor = self.editor(note)
        menu = Menu()
        browser = SimpleNamespace(form=SimpleNamespace(menu_Notes=menu), editor=editor,
                                  selected_notes=lambda: [note.id])
        with patch.dict('sys.modules', {'aqt.qt': qt}):
            commands.editor_menu(self.adapter, SimpleNamespace(editor=editor), menu)
            commands.browser_menu(self.adapter, browser)
            commands.browser_menu(self.adapter, browser)
        self.assertEqual(menu.label, 'Regenerate Kanji Breakdown')
        self.assertEqual(len(actions), 2)
        with patch.object(commands, 'current_note') as current, patch.object(commands, 'selected_notes') as selected:
            callbacks[0]()
            callbacks[1]()
            current.assert_called_once_with(self.adapter, editor)
            selected.assert_called_once_with(self.adapter, browser)

    def test_switch_note_while_waiting_does_not_regenerate_old_note(self):
        first, second = self.note('大'), self.note('水')
        editor = self.editor(first)
        callbacks = []
        editor.call_after_note_saved = lambda callback, **kwargs: callbacks.append(callback)
        commands.current_note(self.adapter, editor)
        editor.note = second
        callbacks[0]()
        self.assertEqual(self.operations, [])
        self.assertIn('current note changed', self.messages[-1])
