"""Optional integration tests against the real Anki Python/Rust backend.

All collections are temporary. No existing user profile or collection is opened.
"""
from pathlib import Path
import tempfile
import unittest

try:
    from anki.collection import Collection, OpChanges
    from anki import hooks
except ModuleNotFoundError as error:
    if error.name != 'anki':
        raise
    Collection = None

from src.akb.database import Database
from src.akb.config import parse_config
from src.akb.runtime import Runtime
from src.akb.payload import deserialize
from src.akb.bulk import regenerate
from src.akb.integration import Integration


@unittest.skipIf(Collection is None, 'Optional Anki backend is not installed')
class AnkiBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.col = Collection(str(Path(self.temp.name) / 'collection.anki2'))
        self.model = self.col.models.new('AKB test')
        for name in ('Text', 'Extra', 'Output'):
            self.col.models.add_field(self.model, self.col.models.new_field(name))
        template = self.col.models.new_template('Card')
        template['qfmt'], template['afmt'] = '{{Text}}', '{{Output}}'
        self.col.models.add_template(self.model, template)
        added = self.col.models.add_dict(self.model)
        self.model = self.col.models.get(added.id)
        self.runtime = Runtime(Database(Path(__file__).resolve().parents[1] / 'generated/kanji_db.json').load(),
                               parse_config({'version': 1, 'mappings': [{
                                   'enabled': True, 'notetype_id': self.model['id'],
                                   'source_fields': ['Text', 'Extra'], 'output_field': 'Output'}]}))
        self.adapter = Integration(None, 'test')
        self.adapter.runtime, self.adapter.collection = self.runtime, self.col
        hooks.note_will_flush.append(self.adapter.before_save)

    def tearDown(self):
        hooks.note_will_flush.remove(self.adapter.before_save)
        self.col.close()
        self.temp.cleanup()

    def note(self, text):
        note = self.col.new_note(self.model)
        note['Text'] = text
        self.col.add_note(note, 1)
        return note

    def test_creation_and_edit_are_saved_with_payload_and_undo(self):
        note = self.note('階𠮟')
        stored = self.col.get_note(note.id)
        self.assertEqual([e['char'] for e in deserialize(stored['Output'])['entries']], ['階', '𠮟'])
        original = stored['Output']
        stored['Text'] = '水'
        self.col.update_note(stored)
        self.assertEqual(deserialize(self.col.get_note(note.id)['Output'])['entries'][0]['char'], '水')
        self.col.undo()
        restored = self.col.get_note(note.id)
        self.assertEqual((restored['Text'], restored['Output']), ('階𠮟', original))
        self.col.redo()
        self.assertEqual(self.col.get_note(note.id)['Text'], '水')

    def test_clearing_and_backend_bulk_undo(self):
        notes = [self.note(c) for c in '階建語']
        # Simulate stale synced cache via a save while this add-on hook is suspended.
        with self.runtime.suspend_hook():
            for n in notes:
                n['Output'] = 'stale'
            self.col.update_notes(notes)
        result = regenerate(self.col, self.runtime, OpChanges(), batch_size=1)
        self.assertFalse(result.error)
        self.assertEqual(result.changed, 3)
        self.assertTrue(result.changes.note)
        self.col.undo()
        self.assertTrue(all(self.col.get_note(n.id)['Output'] == 'stale' for n in notes))
        self.col.redo()
        self.assertTrue(all(self.col.get_note(n.id)['Output'] != 'stale' for n in notes))
        n = self.col.get_note(notes[0].id)
        n['Text'] = 'abc'
        self.col.update_note(n)
        self.assertEqual(self.col.get_note(n.id)['Output'], '')

    def test_bulk_noop_preserves_undo_and_cancel_is_undoable(self):
        notes = [self.note(c) for c in '階建語']
        before = self.col.undo_status().last_step
        self.assertEqual(regenerate(self.col, self.runtime, OpChanges()).changed, 0)
        self.assertEqual(self.col.undo_status().last_step, before)
        with self.runtime.suspend_hook():
            for n in notes:
                n['Output'] = 'stale'
            self.col.update_notes(notes)
        calls = []
        def progress(done, total):
            calls.append(done)
        result = regenerate(self.col, self.runtime, OpChanges(), progress,
                            cancelled=lambda: bool(calls) and calls[-1] >= 2, batch_size=1)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.changed, 1)
        self.col.undo()
        self.assertTrue(all(self.col.get_note(n.id)['Output'] == 'stale' for n in notes))
