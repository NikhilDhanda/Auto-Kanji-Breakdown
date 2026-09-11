from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import re

from src.akb import templates
from src.akb.config import parse_config
from src.akb.setup import (KEY, FIELD_OWNER, Request, apply_plan, available_name,
                          plan_setup, proven_created, read_config, safe_payload)
from src.akb.cleanup import plan_cleanup
from src.akb.payload import serialize

try:
    from anki.collection import Collection
except ModuleNotFoundError:
    Collection = None

OWNER = 'a' * 32
PAYLOAD = serialize({'version': 1, 'entries': [{'char': '人', 'meanings': ['person']}]})


class MarkerTests(unittest.TestCase):
    def test_theme_allowlist_and_template_version(self):
        for theme in templates.THEMES:
            self.assertEqual(templates.parse_theme(theme), theme)
            block = templates.html_block('Output', OWNER, theme)
            self.assertIn(f'data-akb-theme="{theme}"', block)
            self.assertIn('renderer=6', block)
        for invalid in [None, [], 'unknown', '\" onclick=alert(1)']:
            self.assertEqual(templates.parse_theme(invalid), 'classic')
            with self.assertRaises(templates.IntegrationError):
                templates.html_block('Output', OWNER, invalid)
    def test_html_idempotence_outside_bytes_and_moved_block(self):
        block = templates.html_block('Generated', OWNER)
        before = ' \r\n{{Front}}<div>user</div>\n'
        value = templates.replace(before, OWNER, block)
        self.assertEqual(templates.replace(value, OWNER, block), value)
        moved = 'first\r\n' + block + '\nlast '
        self.assertEqual(templates.replace(moved, OWNER), 'first\r\n\nlast ')
        self.assertEqual(templates.replace(value, OWNER), before)
        self.assertIn('{{Generated}}', block)
        self.assertNotIn('fetch(', block)

    def test_version_upgrade_and_css(self):
        block = templates.css_block(OWNER)
        old = block.replace(f'renderer={templates.RENDERER_VERSION}', 'renderer=1')
        self.assertEqual(templates.status(old, OWNER, True), 'outdated')
        value = templates.replace('/* user */' + old, OWNER, block, True)
        self.assertEqual(templates.status(value, OWNER, True), 'current')
        self.assertEqual(templates.replace(value, OWNER, css=True), '/* user */')
        self.assertEqual(templates.status('', OWNER), 'not installed')

    def test_damage_duplicate_unknown_owner_and_unsafe_field(self):
        block = templates.html_block('Output', OWNER)
        for bad in [block + block, block.replace('AKB:END', 'AKB:BROKEN'), block.replace(OWNER, 'b' * 32)]:
            with self.assertRaises(templates.IntegrationError):
                templates.replace(bad, OWNER)
        for name in ['{{Text}}', '</script>', '#Text', 'text:Text']:
            with self.assertRaises(templates.IntegrationError):
                templates.html_block(name, OWNER)

    def test_config_versions_and_collision(self):
        row = dict(enabled=True, notetype_id=1, source_fields=['A', 'B'], output_field='C')
        self.assertEqual(parse_config({'version': 1, 'mappings': [row]}).mappings,
                         parse_config({'version': 2, 'mappings': [row]}).mappings)
        self.assertEqual(available_name({'flds': [{'name': 'Auto Kanji Breakdown'}, {'name': 'Auto Kanji Breakdown (2)'}]}),
                         'Auto Kanji Breakdown (3)')
        self.assertTrue(safe_payload(PAYLOAD))
        self.assertFalse(safe_payload('<b>my notes</b>'))
        self.assertFalse(safe_payload('{"version":1,"entries":[]}<script>'))


@unittest.skipIf(Collection is None, 'Optional Anki backend is not installed')
class SetupBackendTests(unittest.TestCase):
    def test_global_theme_updates_multiple_types_without_notes_and_undoes(self):
        from src.akb.setup import apply_theme
        self.setup(output='Output')
        other = self.col.models.copy(self.model())
        other['tmpls'][0]['afmt'] = '{{Text}}'
        other['css'] = ''
        self.col.models.update_dict(other)
        apply_plan(self.col, plan_setup(self.col, self.raw(), Request(other['id'], ('Text',), 'Output')))
        before = self.raw()
        note = list(self.col.get_note(self.note.id).fields)
        with patch.object(self.col, 'find_notes', side_effect=AssertionError('Theme must not scan notes')):
            self.assertFalse(apply_theme(self.col, 'matcha', before).error)
        self.assertEqual(self.raw()['default_theme'], 'matcha')
        for row in self.raw()['mappings']:
            self.assertEqual(row['theme'], 'matcha')
            model = self.col.models.get(row['notetype_id'])
            self.assertIn('data-akb-theme="matcha"', model['tmpls'][0]['afmt'])
        self.assertEqual(list(self.col.get_note(self.note.id).fields), note)
        self.col.undo()
        self.assertEqual(self.raw(), before)
        for row in before['mappings']:
            self.assertIn('data-akb-theme="classic"', self.col.models.get(row['notetype_id'])['tmpls'][0]['afmt'])

    def test_global_theme_rejects_damage_and_stale_config_before_writes(self):
        from src.akb.setup import apply_theme
        self.setup(output='Output')
        before = self.raw()
        with self.assertRaises(templates.IntegrationError):
            apply_theme(self.col, 'light', {})
        model = self.model()
        model['tmpls'][0]['afmt'] += '<!-- AKB:broken -->'
        self.col.models.update_dict(model)
        with self.assertRaises(templates.IntegrationError):
            apply_theme(self.col, 'light', before)
        self.assertEqual(self.raw(), before)

    def test_theme_default_without_mappings_and_new_setup(self):
        from src.akb.setup import apply_theme
        apply_theme(self.col, 'sakura', self.raw())
        self.assertEqual(self.setup(output='Output').row['theme'], 'sakura')

    def test_theme_only_change_preserves_notes_migrates_v1_and_cleans_up(self):
        from src.akb.setup_ui import recommend_regeneration
        self.setup(output='Output')
        self.fill('Output')
        before_note = self.col.get_note(self.note.id)
        before_fields = list(before_note.fields)
        model = self.model()
        model['tmpls'][0]['afmt'] = model['tmpls'][0]['afmt'].replace('renderer=6', 'renderer=1')
        model['css'] = model['css'].replace('renderer=6', 'renderer=1')
        self.col.models.update_dict(model)
        for theme in templates.THEMES:
            self.setup(output='Output', theme=theme)
            row = self.raw()['mappings'][0]
            self.assertEqual(row['theme'], theme)
            self.assertFalse(recommend_regeneration(row, row['source_fields'], 'Output', True))
            self.assertIn(f'data-akb-theme="{theme}"', self.model()['tmpls'][0]['afmt'])
            self.assertIn('renderer=6', self.model()['css'])
            self.assertEqual(list(self.col.get_note(self.note.id).fields), before_fields)
        # Omitting a theme on reconfiguration preserves the existing choice.
        self.setup(output='Output')
        self.assertEqual(self.raw()['mappings'][0]['theme'], templates.THEMES[-1])
        self.cleanup('renderer')
        self.assertNotIn('AKB:', self.model()['tmpls'][0]['afmt'])
        self.assertEqual(list(self.col.get_note(self.note.id).fields), before_fields)
        self.col.undo()
        self.assertIn(f'data-akb-theme="{templates.THEMES[-1]}"', self.model()['tmpls'][0]['afmt'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.col = Collection(str(Path(self.temp.name) / 'collection.anki2'))
        model = self.col.models.new('Setup test')
        for name in ('Text', 'Extra', 'Output', 'Auto Kanji Breakdown'):
            self.col.models.add_field(model, self.col.models.new_field(name))
        template = self.col.models.new_template('Card 1')
        template.update(qfmt='{{Text}}', afmt='{{FrontSide}}<hr>original back')
        self.col.models.add_template(model, template)
        self.mid = self.col.models.add_dict(model).id
        self.original = deepcopy(self.model())
        self.note = self.col.new_note(self.model())
        self.note['Text'] = '階建語'
        self.col.add_note(self.note, 1)
        self.cards = self.col.find_cards('')

    def tearDown(self):
        self.col.close()
        self.temp.cleanup()

    def model(self):
        return self.col.models.get(self.mid)

    def raw(self):
        return read_config(self.col)

    def setup(self, **kwargs):
        plan = plan_setup(self.col, self.raw(), Request(self.mid, ('Text', 'Extra'), **kwargs))
        result = apply_plan(self.col, plan)
        self.assertFalse(result.error)
        return plan

    def fill(self, name, value=PAYLOAD):
        note = self.col.get_note(self.note.id)
        note[name] = value
        self.col.update_note(note)

    def cleanup(self, mode, delete=False):
        plan = plan_cleanup(self.col, self.raw(), self.mid, mode, delete)
        result = apply_plan(self.col, plan)
        self.assertFalse(result.error)
        return plan

    def test_creation_ownership_default_back_and_single_undo(self):
        plan = self.setup()
        self.assertEqual(plan.row['output_field'], 'Auto Kanji Breakdown (2)')
        model = self.model()
        self.assertEqual(model['tmpls'][0]['qfmt'], self.original['tmpls'][0]['qfmt'])
        self.assertIn('AKB:START', model['tmpls'][0]['afmt'])
        field = model['flds'][-1]
        self.assertTrue(proven_created(self.raw()['mappings'][0], field))
        self.assertEqual(self.raw()['version'], 2)
        self.col.undo()
        self.assertEqual([f['name'] for f in self.model()['flds']], [f['name'] for f in self.original['flds']])
        self.assertIsNone(self.col.get_config(KEY))
        self.col.redo()
        self.assertEqual(self.col.find_cards(''), self.cards)

    def test_reconfigure_idempotent_front_back_preserves_other_content(self):
        self.setup(output='Output')
        before = self.model()
        self.setup(output='Output')
        self.assertEqual(self.model(), before)
        tid = before['tmpls'][0]['id']
        self.setup(output='Output', targets=((tid, 'qfmt'), (tid, 'afmt')))
        self.assertIn('AKB:START', self.model()['tmpls'][0]['qfmt'])
        self.cleanup('renderer')
        self.assertEqual(self.model()['tmpls'][0]['qfmt'], self.original['tmpls'][0]['qfmt'])
        self.assertEqual(self.model()['tmpls'][0]['afmt'], self.original['tmpls'][0]['afmt'])
        self.assertEqual(self.model()['css'], self.original['css'])
        self.assertTrue(self.raw()['mappings'][0]['enabled'])
        self.cleanup('renderer')

    def test_data_only_full_selected_field_preserved_and_undo(self):
        self.setup(output='Output')
        self.fill('Output')
        self.cleanup('data')
        self.assertEqual(self.col.get_note(self.note.id)['Output'], '')
        self.assertFalse(self.raw()['mappings'][0]['enabled'])
        self.assertIn('AKB:START', self.model()['tmpls'][0]['afmt'])
        self.col.undo()
        self.assertEqual(self.col.get_note(self.note.id)['Output'], PAYLOAD)
        self.assertTrue(self.raw()['mappings'][0]['enabled'])
        self.cleanup('full', True)
        self.assertIn('Output', [f['name'] for f in self.model()['flds']])
        self.assertEqual(self.col.find_cards(''), self.cards)
        self.cleanup('full', True)

    def test_delete_created_field_and_undo_restores_payload(self):
        name = self.setup().row['output_field']
        self.fill(name)
        self.cleanup('full', True)
        self.assertNotIn(name, [f['name'] for f in self.model()['flds']])
        self.assertEqual(self.col.find_cards(''), self.cards)
        self.col.undo()
        self.assertEqual(self.col.get_note(self.note.id)[name], PAYLOAD)
        self.assertTrue(proven_created(self.raw()['mappings'][0], self.model()['flds'][-1]))
        self.col.redo()
        self.cleanup('full', True)

    def test_suspicious_data_preserved_and_deletion_refused(self):
        name = self.setup().row['output_field']
        self.fill(name, 'handwritten content')
        with self.assertRaises(templates.IntegrationError):
            plan_cleanup(self.col, self.raw(), self.mid, 'full', True)
        plan = self.cleanup('full')
        self.assertEqual(plan.skipped, 1)
        self.assertEqual(self.col.get_note(self.note.id)[name], 'handwritten content')

    def test_user_template_reference_blocks_deletion(self):
        name = self.setup().row['output_field']
        model = self.model()
        model['tmpls'][0]['qfmt'] += '{{' + name + '}}'
        self.col.models.update_dict(model)
        with self.assertRaises(templates.IntegrationError):
            plan_cleanup(self.col, self.raw(), self.mid, 'full', True)

    def test_no_overwrite_existing_data_and_stale_preview(self):
        self.fill('Output', 'user content')
        with self.assertRaises(templates.IntegrationError):
            self.setup(output='Output')
        self.fill('Output', '')
        plan = plan_setup(self.col, self.raw(), Request(self.mid, ('Text',), 'Output'))
        self.fill('Output', PAYLOAD)
        with self.assertRaises(templates.IntegrationError):
            apply_plan(self.col, plan)
        self.assertNotIn('AKB:START', self.model()['tmpls'][0]['afmt'])

    def test_invalid_sources_and_target(self):
        for request in [Request(self.mid, (), 'Output'), Request(self.mid, ('Text',), 'Text'),
                        Request(self.mid, ('Gone',)), Request(self.mid, ('Text',), targets=((123, 'afmt'),))]:
            with self.assertRaises(templates.IntegrationError):
                plan_setup(self.col, self.raw(), request)

    def test_replaced_field_identity_refuses_cleanup(self):
        self.setup(output='Output')
        model = self.model()
        next(f for f in model['flds'] if f['name'] == 'Output')['id'] = 987654321
        self.col.models.update_dict(model)
        with self.assertRaises(templates.IntegrationError):
            plan_cleanup(self.col, self.raw(), self.mid, 'data')

    def test_legacy_migration_preserves_other_mapping(self):
        legacy = {'version': 1, 'mappings': [{'enabled': False, 'notetype_id': 123, 'source_fields': ['A'], 'output_field': 'B'}]}
        plan = plan_setup(self.col, legacy, Request(self.mid, ('Text',), 'Output'))
        self.assertFalse(apply_plan(self.col, plan, legacy).error)
        self.assertEqual(self.raw()['mappings'][0], legacy['mappings'][0])

    def test_backend_template_expansion_keeps_json_html_safe(self):
        self.setup(output='Output')
        sensitive = serialize({'version': 1, 'entries': [{'char': '人', 'meanings': ['</script><img onerror="bad()"> & {{Text}}']}]})
        self.fill('Output', sensitive)
        answer = self.col.get_card(self.cards[0]).answer()
        match = re.search(r'<script type="application/json" class="akb-data">(.*?)</script>', answer, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(match[1], sensitive)
        self.assertNotIn('<img onerror', answer)

    def test_failure_rolls_back_field_template_and_config(self):
        plan = plan_setup(self.col, self.raw(), Request(self.mid, ('Text',)))
        with patch.object(self.col, 'set_config', side_effect=RuntimeError('injected failure')):
            result = apply_plan(self.col, plan)
        self.assertTrue(result.error)
        self.assertEqual([f['name'] for f in self.model()['flds']], [f['name'] for f in self.original['flds']])
        self.assertEqual(self.model()['tmpls'][0]['afmt'], self.original['tmpls'][0]['afmt'])
        self.assertIsNone(self.col.get_config(KEY))

    def test_large_cleanup_keeps_undo_anchor_across_more_than_30_batches(self):
        from anki.collection import AddNoteRequest
        self.setup(output='Output')
        requests = []
        for _ in range(3100):
            note = self.col.new_note(self.model())
            note['Text'], note['Output'] = '人', PAYLOAD
            requests.append(AddNoteRequest(note=note, deck_id=1))
        self.col.add_notes(requests)
        self.cleanup('data')
        self.assertEqual(self.col.get_note(requests[0].note.id)['Output'], '')
        self.assertEqual(self.col.get_note(requests[-1].note.id)['Output'], '')
        self.col.undo()
        self.assertEqual(self.col.get_note(requests[0].note.id)['Output'], PAYLOAD)
        self.assertEqual(self.col.get_note(requests[-1].note.id)['Output'], PAYLOAD)

    def test_runtime_tracks_undo_and_rejects_replaced_output(self):
        from src.akb.integration import Integration
        from src.akb.runtime import Runtime
        from src.akb.database import Database
        from src.akb.config import Config, validate_mapping
        adapter = Integration(None, 'test')
        adapter.runtime = Runtime(Database(Path(__file__).resolve().parents[1] / 'generated/kanji_db.json').load(), Config())
        adapter.collection = self.col
        adapter.sync_config()
        self.setup(output='Output')
        adapter.sync_config()
        mapping = adapter.runtime.mappings[self.mid]
        self.col.undo()
        adapter.sync_config()
        self.assertEqual(adapter.runtime.mappings, {})
        self.col.redo()
        adapter.sync_config()
        self.assertIn(self.mid, adapter.runtime.mappings)
        replaced = deepcopy(self.model())
        next(f for f in replaced['flds'] if f['name'] == 'Output')['id'] = -999
        self.assertIsNotNone(validate_mapping(mapping, replaced))

    def test_setup_generation_preference_roundtrips_and_undo_restores_it(self):
        self.setup(output='Output', generate_existing=False)
        self.assertFalse(self.raw()['mappings'][0]['generate_existing'])
        self.setup(output='Output', generate_existing=True)
        self.assertTrue(self.raw()['mappings'][0]['generate_existing'])
        self.col.undo()
        self.assertFalse(self.raw()['mappings'][0]['generate_existing'])
        # Non-UI callers do not silently reset a saved preference.
        self.setup(output='Output')
        self.assertFalse(self.raw()['mappings'][0]['generate_existing'])

    def test_setup_preview_count_and_words_match_request(self):
        from src.akb.setup_ui import review_summary
        plan = plan_setup(self.col, self.raw(), Request(self.mid, ('Text',), enabled=False))
        self.assertEqual(plan.notes, 1)
        text = review_summary(plan, False)
        self.assertIn('Japanese fields:\n• Text', text)
        self.assertIn('Card 1: Back', text)
        self.assertIn('Automatic updates are off', text)
        self.assertIn('Existing notes will not be generated now', text)


    def test_cleanup_result_counts_confirmed_commits_and_fields(self):
        plan = self.setup()
        name = plan.row['output_field']
        self.fill(name)
        result = apply_plan(self.col, plan_cleanup(self.col, self.raw(), self.mid, 'full', True))
        self.assertFalse(result.error)
        self.assertEqual(result.cleanup.notes_cleared, 1)
        self.assertEqual(result.cleanup.templates_removed, 1)
        self.assertEqual(result.cleanup.deleted, (name,))
        self.assertNotIn(name, [f['name'] for f in self.model()['flds']])
        repeat = apply_plan(self.col, plan_cleanup(self.col, self.raw(), self.mid, 'full'))
        self.assertEqual(repeat.cleanup.notes_cleared, 0)
        self.assertEqual(repeat.cleanup.templates_removed, 0)
        self.assertFalse(repeat.changed)

    def test_cleanup_data_and_renderer_results_preserve_fields(self):
        self.setup(output='Output')
        self.fill('Output')
        display = apply_plan(self.col, plan_cleanup(self.col, self.raw(), self.mid, 'renderer'))
        self.assertEqual(display.cleanup.notes_cleared, 0)
        self.assertEqual(display.cleanup.templates_removed, 1)
        self.assertEqual(self.col.get_note(self.note.id)['Output'], PAYLOAD)
        data = apply_plan(self.col, plan_cleanup(self.col, self.raw(), self.mid, 'data'))
        self.assertEqual(data.cleanup.notes_cleared, 1)
        self.assertEqual(data.cleanup.templates_removed, 0)
        self.assertIn(('Output', 'not_created'), data.cleanup.retained)
        self.assertIn('Output', [f['name'] for f in self.model()['flds']])
