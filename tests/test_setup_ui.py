"""Setup copy/default policy and optional real Qt widgets, without an Anki profile."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.akb import setup_ui as ui

MODEL = {'id': 1, 'name': 'Core 2000', 'flds': [{'name': 'Japanese'}, {'name': 'Output'}],
         'tmpls': [{'id': 10, 'name': 'Recognition'}]}


class PresentationTests(unittest.TestCase):
    def test_new_defaults(self):
        self.assertEqual(ui.defaults({}), {'enabled': True, 'initial': True, 'targets': None})

    def test_existing_choices_and_legacy_initial_off(self):
        row = {'enabled': False, 'templates': [], 'generate_existing': False}
        before = deepcopy(row)
        self.assertEqual(ui.defaults(row), {'enabled': False, 'initial': False, 'targets': set()})
        self.assertEqual(row, before)
        self.assertFalse(ui.defaults({'enabled': True})['initial'])
        self.assertFalse(ui.defaults(dict(row, generate_existing=True))['initial'])

    def test_generation_changes_recommend_rebuild_without_mutating_configuration(self):
        row = dict(enabled=True, source_fields=['A', 'B'], output_field='Out', generate_existing=True)
        before = deepcopy(row)
        self.assertFalse(ui.recommend_regeneration(row, ['A', 'B'], 'Out', True))
        self.assertTrue(ui.recommend_regeneration(row, ['B', 'A'], 'Out', True))
        self.assertTrue(ui.recommend_regeneration(row, ['A'], 'Out', True))
        self.assertTrue(ui.recommend_regeneration(row, ['A', 'B'], None, True))
        self.assertTrue(ui.recommend_regeneration(dict(row, enabled=False), ['A', 'B'], 'Out', True))
        self.assertEqual(row, before)

    def test_onboarding_state_keeps_settings(self):
        raw = {'version': 1, 'mappings': [{'enabled': False}], 'other': {'keep': 1}}
        before = deepcopy(raw)
        self.assertTrue(ui.needs_onboarding(raw))
        saved = ui.completed_onboarding(raw)
        self.assertFalse(ui.needs_onboarding(saved))
        self.assertEqual(raw, before)
        self.assertEqual(saved['mappings'], raw['mappings'])
        self.assertEqual(saved['other'], raw['other'])
        with self.assertRaises(ValueError):
            ui.completed_onboarding('invalid settings')

    def test_help_covers_major_options_and_safety(self):
        self.assertTrue(set(ui.LABELS).issubset(ui.HELP))
        self.assertTrue(all(ui.HELP[key].strip() for key in ui.LABELS))
        self.assertIn('never automatically deleted', ui.CLEANUP)
        self.assertIn('only offered for deletion when ownership can be proven', ui.CLEANUP)
        self.assertIn('Your Japanese source fields are not modified', ui.HELP['output'])
        self.assertIn('Each unique kanji is shown once', ui.HELP['sources'])
        self.assertIn('Recommended during first setup. This generates breakdowns for the notes you already have. '
                      'New notes and later desktop edits can be kept updated automatically.', ui.HELP['initial'])

    def test_mobile_review_is_distinct_from_generation(self):
        self.assertIn('cannot regenerate on the phone itself', ui.TUTORIAL)
        self.assertIn('then sync again', ui.TUTORIAL)
        self.assertIn('designed to work', ui.TUTORIAL)
        self.assertIn('internet connection', ui.TUTORIAL)
        self.assertIn('desktop Anki', ui.MOBILE)
        self.assertIn('including offline', ui.MOBILE)

    def test_preview_uses_plain_language_and_actual_choices(self):
        summary = ui.setup_summary(MODEL, ['Japanese'], 'Output', [(10, 'afmt')], True, 2007)
        plan = SimpleNamespace(summary=summary, notes=2007, request=SimpleNamespace(enabled=True))
        message = ui.review_summary(plan, True)
        for phrase in ['Ready to set up', 'Japanese fields:', 'Recognition: Back',
                       '✓ Keep breakdowns updated automatically', '2,007 existing notes']:
            self.assertIn(phrase, message)
        for phrase in ['Renderer:', 'payload', 'ownership', 'Initial regeneration:']:
            self.assertNotIn(phrase, message)
        self.assertIn('will not be generated now', ui.review_summary(plan, False))
        self.assertIn('load the database', ui.review_summary(plan, True, False))
        plan.request.enabled = False
        plan.summary = ui.setup_summary(MODEL, ['Japanese'], 'Output', [], False, 2007)
        disabled = ui.review_summary(plan, True)
        self.assertIn('Automatic updates are off', disabled)
        self.assertIn('will not be displayed', disabled)
        self.assertNotIn('✓', disabled)


try:
    from PyQt6 import QtCore, QtWidgets
except ImportError:
    QtWidgets = None


@unittest.skipIf(QtWidgets is None, 'Optional development PyQt6 is not installed')
class QtSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.raw = {'version': 1, 'mappings': []}
        self.parent = QtWidgets.QWidget()
        manager = SimpleNamespace(writeConfig=lambda name, raw: setattr(self, 'raw', raw))
        self.parent.addonManager = manager
        self.parent.col = SimpleNamespace(get_config=lambda key: None,
                                          models=SimpleNamespace(all=lambda: [MODEL], get=lambda mid: MODEL))
        self.adapter = SimpleNamespace(mw=self.parent, runtime=object(), running=False,
                                       loading=False, addon_name='test', legacy_config=lambda: deepcopy(self.raw))
        from src.akb.update_service import UpdateService
        self.adapter.updates = UpdateService(self.adapter)
        qt = SimpleNamespace(**{name: getattr(QtWidgets, name) for name in (
            'QCheckBox QComboBox QDialog QDialogButtonBox QFormLayout QHBoxLayout QLabel '
            'QListWidget QListWidgetItem QMessageBox QPushButton QScrollArea QTextEdit QVBoxLayout QWidget').split()})
        qt.Qt = QtCore.Qt
        qt.qconnect = lambda signal, callback: signal.connect(callback)
        class Query:
            def __init__(inner, parent, op, success):
                inner.op, inner.success = op, success
            def failure(inner, callback):
                return inner
            def with_progress(inner, label):
                return inner
            def run_in_background(inner):
                inner.success(inner.op(self.parent.col))
        modules = {'aqt.qt': qt, 'aqt.operations': SimpleNamespace(QueryOp=Query, CollectionOp=object),
                   'aqt.utils': SimpleNamespace(showInfo=lambda *a, **kw: None, showWarning=lambda *a, **kw: None)}
        self.modules = modules
        spec = importlib.util.spec_from_file_location('src.akb._ui_dialogs', Path(__file__).resolve().parents[1] / 'src/akb/dialogs.py')
        self.dialogs = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', modules):
            spec.loader.exec_module(self.dialogs)

    def tearDown(self):
        self.parent.close()
        self.parent.deleteLater()
        self.app.processEvents()

    def dialog(self, row=None):
        raw = {'version': 2, 'mappings': [row] if row else []}
        return self.dialogs.SetupDialog(self.adapter, raw, [MODEL])

    def test_widgets_apply_defaults_and_back_only(self):
        dialog = self.dialog()
        self.assertTrue(dialog.enabled.isChecked())
        self.assertTrue(dialog.initial.isChecked())
        self.assertIsNone(dialog.output.currentData())
        self.assertEqual([i.data(self.dialogs.ROLE) for i in self.dialogs.checked_items(dialog.targets)], [(10, 'afmt')])
        self.assertEqual(dialog.enabled.text(), ui.LABELS['enabled'])
        self.assertEqual(dialog.targets.currentItem().data(self.dialogs.ROLE), (10, 'afmt'))
        self.assertEqual([dialog.theme.itemText(i) for i in range(dialog.theme.count())],
                         ['Light', 'Dark', 'Blue', 'Brown', 'Matcha', 'Matcha Dark', 'Sakura', 'Sakura Dark'])
        self.assertEqual(dialog.theme.currentText(), 'Blue')
        self.assertEqual(dialog.theme.itemText(dialog.theme.findData('sakura')), 'Sakura Dark')

    def test_data_update_setting_is_immediate_preserves_mappings_and_saved_off(self):
        self.raw['other'] = 'keep'
        dialog = self.dialog()
        self.assertTrue(dialog.data_updates.isChecked())
        dialog.data_updates.click()
        self.assertFalse(self.raw['auto_data_updates'])
        self.assertEqual(self.raw['mappings'], [])
        self.assertEqual(self.raw['other'], 'keep')
        self.assertFalse(self.dialog().data_updates.isChecked())
        self.assertIn('No usage data, notes or study information are sent', ui.HELP['data_updates'])

    def test_status_manual_update_button_and_toggle(self):
        calls = []
        self.adapter.updates.start = lambda manual=False: calls.append(manual)
        self.adapter.updates.diagnostics = lambda: 'Kanji database: Bundled'
        def inspect(dialog):
            button = next(b for b in dialog.findChildren(QtWidgets.QPushButton)
                          if b.text() == 'Check for database updates now')
            button.click()
            check = next(b for b in dialog.findChildren(QtWidgets.QCheckBox)
                         if b.text() == ui.LABELS['data_updates'])
            self.assertTrue(check.isChecked())
            check.click()
            self.assertIn('Kanji database: Bundled', dialog.findChild(QtWidgets.QTextEdit).toPlainText())
            return 0
        with patch.object(QtWidgets.QDialog, 'exec', inspect):
            self.dialogs.show_status(self.adapter)
        self.assertEqual(calls, [True])
        self.assertFalse(self.raw['auto_data_updates'])

    def test_downloaded_database_cleanup_is_full_only_and_opt_in(self):
        row = dict(notetype_id=1, enabled=True)
        dialog = self.dialogs.SetupDialog(self.adapter, {'version':2,'mappings':[row]}, [MODEL], cleanup=True)
        self.assertFalse(dialog.remove_updates.isEnabled())
        self.assertFalse(dialog.remove_updates.isChecked())
        dialog.mode.setCurrentIndex(dialog.mode.findData('full'))
        self.assertTrue(dialog.remove_updates.isEnabled())
        self.assertFalse(dialog.remove_updates.isChecked())
        dialog.remove_updates.setChecked(True)
        dialog.mode.setCurrentIndex(dialog.mode.findData('data'))
        self.assertFalse(dialog.remove_updates.isChecked())

    def test_theme_apply_is_direct_and_does_not_review_pending_setup(self):
        dialog = self.dialog()
        dialog.theme.setCurrentIndex(dialog.theme.findData('matcha'))
        calls = []
        class Operation:
            def __init__(inner, parent, op):
                inner.op = op
            def success(inner, callback):
                inner.done = callback
                return inner
            def failure(inner, callback):
                return inner
            def run_in_background(inner):
                inner.done(inner.op(self.parent.col))
        self.adapter.sync_config = lambda: None
        feedback = Mock()
        self.modules['aqt.utils'].tooltip = feedback
        with patch.dict('sys.modules', self.modules), patch.object(self.dialogs, 'showInfo', side_effect=AssertionError('No modal')), patch.object(self.dialogs, 'CollectionOp', Operation), patch.object(
                self.dialogs, 'apply_theme', side_effect=lambda col, theme, raw, legacy: (
                    calls.append(theme) or SimpleNamespace(error=''))), patch.object(
                self.dialogs, 'text_dialog', side_effect=AssertionError('No review needed')):
            dialog.theme_apply.click()
        feedback.assert_called_once_with('Theme applied', parent=dialog)
        self.assertEqual(calls, ['matcha'])
        self.assertIsNone(dialog.output.currentData())
        self.assertEqual(self.dialogs.checked_items(dialog.sources), [])
        self.assertFalse(self.adapter.running)

    def test_widgets_restore_disabled_front_only_existing_mapping(self):
        row = dict(notetype_id=1, enabled=False, generate_existing=False, output_field='Output',
                   source_fields=['Japanese'], templates=[{'id': 10, 'side': 'qfmt'}])
        dialog = self.dialog(row)
        self.assertFalse(dialog.enabled.isChecked())
        self.assertFalse(dialog.initial.isChecked())
        self.assertEqual(dialog.output.currentData(), 'Output')
        self.assertEqual([i.data(self.dialogs.ROLE) for i in self.dialogs.checked_items(dialog.targets)], [(10, 'qfmt')])
        self.assertEqual(dialog.targets.currentItem().data(self.dialogs.ROLE), (10, 'qfmt'))

    def test_help_buttons_open_local_explanations(self):
        dialog = self.dialog()
        with patch.object(self.dialogs, 'text_dialog') as show:
            buttons = [b for b in dialog.findChildren(QtWidgets.QPushButton) if b.text() == '?']
            self.assertEqual(len(buttons), 9)
            for button in buttons:
                self.assertTrue(button.accessibleName().startswith('Help: '))
                button.click()
            self.assertEqual({call.args[2] for call in show.call_args_list}, set(ui.HELP.values()))

    def test_unavailable_initial_generation_explained_without_losing_choice(self):
        self.adapter.runtime = None
        dialog = self.dialog()
        self.assertTrue(dialog.initial.isChecked())
        self.assertFalse(dialog.initial.isEnabled())
        self.assertIn('load the database', dialog.initial_hint.text())
        self.adapter.runtime = object()
        dialog.update_initial()
        self.assertTrue(dialog.initial.isEnabled())
        dialog.enabled.setChecked(False)
        self.assertFalse(dialog.initial.isEnabled())
        self.assertIn('Turn on automatic updates', dialog.initial_hint.text())

    def test_first_tutorial_continue_then_reopen_without_repetition(self):
        with patch.object(self.dialogs, 'text_dialog', return_value=True) as tutorial, \
                patch.object(self.dialogs.SetupDialog, 'exec', return_value=0) as setup:
            self.dialogs.open_dialog(self.adapter)
            self.assertEqual(tutorial.call_count, 1)
            self.assertEqual(setup.call_count, 1)
            self.dialogs.open_dialog(self.adapter)
            self.assertEqual(tutorial.call_count, 1)
            self.assertEqual(setup.call_count, 2)
            self.dialogs.show_tutorial(self.adapter)
            self.assertEqual(tutorial.call_count, 2)

    def test_dismiss_tutorial_is_remembered_and_cleanup_does_not_onboard(self):
        with patch.object(self.dialogs, 'text_dialog', return_value=False) as tutorial, \
                patch.object(self.dialogs.SetupDialog, 'exec', return_value=0) as setup:
            self.dialogs.open_dialog(self.adapter, cleanup=True)
            self.assertEqual(tutorial.call_count, 0)
            self.dialogs.open_dialog(self.adapter)
            self.assertEqual(tutorial.call_count, 1)
            self.assertFalse(ui.needs_onboarding(self.raw))
            self.assertEqual(setup.call_count, 1)  # cleanup only; tutorial was dismissed
            self.dialogs.open_dialog(self.adapter)
            self.assertEqual(tutorial.call_count, 1)
            self.assertEqual(setup.call_count, 2)

    def test_native_confirmation_scrolls_plain_text_and_defaults_to_cancel(self):
        observed = []
        def inspect():
            dialog = self.app.activeModalWidget()
            view = dialog.findChild(QtWidgets.QTextEdit)
            buttons = dialog.findChild(QtWidgets.QDialogButtonBox)
            observed.append((view.toPlainText(), view.isReadOnly(),
                             buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).isDefault()))
            dialog.reject()
        QtCore.QTimer.singleShot(0, inspect)
        self.assertFalse(self.dialogs.text_dialog(self.parent, 'Review', '<Japanese field>\n' * 100, confirm=True))
        self.assertEqual(observed, [('<Japanese field>\n' * 100, True, True)])

    def test_tutorial_headings_bold_body_normal_in_light_and_dark_palettes(self):
        from PyQt6.QtGui import QColor, QPalette
        original_palette = self.app.palette()
        self.addCleanup(self.app.setPalette, original_palette)
        for dark in (False, True):
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Base, QColor('#222222' if dark else '#ffffff'))
            palette.setColor(QPalette.ColorRole.Text, QColor('#eeeeee' if dark else '#111111'))
            self.app.setPalette(palette)
            observed = []
            def inspect():
                dialog = self.app.activeModalWidget()
                view = dialog.findChild(QtWidgets.QTextEdit)
                doc = view.document()
                observed.append(([doc.find(h).charFormat().fontWeight() for h in ui.TUTORIAL_HEADINGS],
                                 doc.find('Select the fields where').charFormat().fontWeight(),
                                 view.palette().color(QPalette.ColorRole.Text)))
                dialog.accept()
            QtCore.QTimer.singleShot(0, inspect)
            self.dialogs.show_tutorial(self.adapter)
            self.assertEqual(observed[0][0], [700] * 5)
            self.assertLess(observed[0][1], 700)
            self.assertEqual(observed[0][2], palette.color(QPalette.ColorRole.Text))

    def configured_dialog(self, **kwargs):
        row = dict(notetype_id=1, enabled=True, generate_existing=True, output_field='Output',
                   source_fields=['Japanese'], templates=[{'id': 10, 'side': 'afmt'}])
        row.update(kwargs)
        return self.dialog(row)

    def test_unchanged_reopen_and_display_only_change_do_not_recommend_run(self):
        dialog = self.configured_dialog()
        self.assertFalse(dialog.initial.isChecked())
        self.assertEqual(dialog.theme.currentData(), 'classic')
        dialog.theme.setCurrentIndex(dialog.theme.findData('sakura'))
        self.assertFalse(dialog.initial.isChecked())
        self.assertTrue(dialog.initial_recommended.isHidden())
        dialog.targets.item(0).setCheckState(self.dialogs.CHECKED)
        self.assertFalse(dialog.initial.isChecked())

    def test_saved_theme_is_loaded_without_requesting_regeneration(self):
        dialog = self.configured_dialog(theme='matcha')
        self.assertEqual(dialog.theme.currentData(), 'matcha')
        self.assertFalse(dialog.initial.isChecked())

    def test_theme_only_preview_passes_choice_without_initial_regeneration(self):
        dialog = self.configured_dialog()
        self.parent.col.get_config = lambda key: deepcopy(dialog.raw)
        dialog.theme.setCurrentIndex(dialog.theme.findData('dark'))
        requests = []
        def plan(col, raw, request):
            requests.append(request)
            return SimpleNamespace(summary='Review', request=request, notes=3)
        with patch.object(self.dialogs, 'plan_setup', side_effect=plan), \
                patch.object(self.dialogs, 'text_dialog', return_value=True), \
                patch.object(dialog, 'apply') as apply:
            dialog.preview()
            self.assertEqual(requests[0].theme, 'dark')
            self.assertFalse(apply.call_args.args[1])

    def test_source_and_output_changes_recommend_until_explicit_choice(self):
        dialog = self.configured_dialog()
        dialog.sources.item(1).setCheckState(self.dialogs.CHECKED)
        self.assertTrue(dialog.initial.isChecked())
        self.assertFalse(dialog.initial_recommended.isHidden())
        dialog.sources.item(1).setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.assertFalse(dialog.initial.isChecked())
        dialog.output.setCurrentIndex(0)
        self.assertTrue(dialog.initial.isChecked())
        dialog.initial.click()  # Explicit OFF must survive more changes.
        dialog.sources.item(1).setCheckState(self.dialogs.CHECKED)
        dialog.enabled.setChecked(False)
        dialog.enabled.setChecked(True)
        self.assertFalse(dialog.initial.isChecked())

    def test_source_order_and_reenabling_recommend(self):
        dialog = self.configured_dialog(source_fields=['Japanese', 'Output'])
        self.assertFalse(dialog.initial.isChecked())
        dialog.sources.setCurrentRow(1)
        dialog.move_source(-1)
        self.assertTrue(dialog.initial.isChecked())
        dialog.move_source(1)
        self.assertFalse(dialog.initial.isChecked())
        disabled = self.configured_dialog(enabled=False)
        disabled.enabled.setChecked(True)
        self.assertTrue(disabled.initial.isChecked())

    def test_explicit_on_survives_reverting_inputs_and_note_type_switch(self):
        dialog = self.configured_dialog()
        dialog.initial.click()  # Explicit ON even with unchanged inputs.
        dialog.output.setCurrentIndex(0)
        dialog.output.setCurrentIndex(dialog.output.findData('Output'))
        self.assertTrue(dialog.initial.isChecked())
        second = deepcopy(MODEL)
        second['id'] = 2
        dialog.models.append(second)
        dialog.types.addItem('Second', 2)
        dialog.types.setCurrentIndex(1)
        dialog.initial.click()  # Explicit OFF for this new mapping.
        dialog.types.setCurrentIndex(0)
        self.assertTrue(dialog.initial.isChecked())
        dialog.types.setCurrentIndex(1)
        self.assertFalse(dialog.initial.isChecked())

    def test_reopen_preserves_saved_automatic_choice_and_missing_defaults_on(self):
        for value in (None, True, False):
            row = dict(notetype_id=1, source_fields=['Japanese'], output_field='Output')
            if value is not None:
                row['enabled'] = value
            before = deepcopy(row)
            for _ in range(2):
                dialog = self.dialog(row)
                self.assertEqual(dialog.enabled.isChecked(), value is not False)
                dialog.close()
            self.assertEqual(row, before)

    def test_about_is_local_canonical_and_external_link_requires_click(self):
        from src.akb import about
        opened = Mock()
        self.modules['aqt.utils'].openLink = opened
        def inspect(dialog):
            opened.assert_not_called()
            text = dialog.findChild(QtWidgets.QLabel).text()
            for expected in ('Version ' + about.local_text('VERSION').strip(),
                             'Created by Nik Dhanda', about.GITHUB, 'AGPL-3.0-or-later'):
                self.assertIn(expected, text)
            buttons = {b.text(): b for b in dialog.findChildren(QtWidgets.QPushButton)}
            with patch.object(about, 'show_licences') as licences:
                buttons['Sources & Licences'].click()
                licences.assert_called_once_with(dialog)
            opened.assert_not_called()
            buttons['GitHub'].click()
            return 0
        with patch.dict('sys.modules', self.modules), patch.object(QtWidgets.QDialog, 'exec', inspect):
            about.show_about(self.parent)
        opened.assert_called_once_with(about.GITHUB)

    def test_licences_are_packaged_plain_text_and_onboarding_credit_is_secondary(self):
        from src.akb import about
        def inspect_licences(dialog):
            choices = dialog.findChild(QtWidgets.QComboBox)
            view = dialog.findChild(QtWidgets.QTextEdit)
            self.assertTrue(view.isReadOnly())
            for i, (_, path) in enumerate(about.DOCUMENTS):
                choices.setCurrentIndex(i)
                self.assertEqual(view.toPlainText(), (about.ROOT / path).read_text(encoding='utf8'))
            return 0
        with patch.dict('sys.modules', self.modules), patch.object(QtWidgets.QDialog, 'exec', inspect_licences):
            about.show_licences(self.parent)
        def inspect_tutorial(dialog):
            label = next(l for l in dialog.findChildren(QtWidgets.QLabel) if l.text() == 'Created by Nik Dhanda')
            self.assertLessEqual(label.font().pointSizeF(), dialog.font().pointSizeF())
            self.assertLessEqual(dialog.height(), 480)
            return 0
        with patch.object(QtWidgets.QDialog, 'exec', inspect_tutorial):
            self.dialogs.show_tutorial(self.adapter)

    def test_guide_common_tasks_paths_and_bold_headings(self):
        self.assertNotIn('Common tasks', ui.TUTORIAL)
        self.assertIn('about once a month', ui.TUTORIAL)
        for path in ('Tools > Auto Kanji Breakdown > Settings',
                     'Tools > Auto Kanji Breakdown > Regenerate Breakdowns',
                     'Tools > Auto Kanji Breakdown > Status & Diagnostics',
                     'Tools > Auto Kanji Breakdown > Cleanup',
                     'Notes > Regenerate Kanji Breakdown'):
            self.assertIn(path, ui.GUIDE)
        self.assertIn('right-click a field', ui.GUIDE)
        self.assertIn('press Apply', ui.GUIDE)
        def inspect(dialog):
            doc = dialog.findChild(QtWidgets.QTextEdit).document()
            for heading in ui.GUIDE_HEADINGS:
                self.assertEqual(doc.find(heading).charFormat().fontWeight(), 700)
            self.assertLess(doc.find('While editing').charFormat().fontWeight(), 700)
            return 0
        with patch.object(QtWidgets.QDialog, 'exec', inspect):
            self.dialogs.show_guide(self.adapter)

    def test_tools_menu_labels_order_and_separator(self):
        from src.akb import integration
        from PyQt6.QtGui import QAction
        from types import ModuleType
        qt = self.modules['aqt.qt']
        qt.QAction = QAction
        self.parent.form = SimpleNamespace(menuTools=QtWidgets.QMenu())
        self.parent.col = None
        hooks = SimpleNamespace(note_will_flush=[])
        gui = SimpleNamespace(**{n: [] for n in ('profile_did_open profile_will_close '
            'editor_did_init operation_did_execute editor_will_show_context_menu browser_menus_did_init').split()})
        aqt = ModuleType('aqt'); aqt.mw = self.parent; aqt.gui_hooks = gui
        anki = ModuleType('anki'); anki.hooks = hooks
        modules = dict(self.modules, aqt=aqt, anki=anki)
        modules['src.akb.dialogs'] = self.dialogs
        with patch.dict('sys.modules', modules):
            integration.install('test')
        menu = self.parent.form.menuTools.actions()[0].menu()
        self.assertEqual([a.text() for a in menu.actions()], ['Settings',
            'Regenerate Breakdowns...', 'Cleanup...', '', 'Help && Guide',
            'Status && Diagnostics', 'About'])
        self.assertEqual([i for i,a in enumerate(menu.actions()) if a.isSeparator()], [3])

        from PyQt6.QtGui import QKeySequence
        visible = [a.text().replace('&&', '&') for a in menu.actions()]
        self.assertEqual(visible, ['Settings', 'Regenerate Breakdowns...', 'Cleanup...', '',
                                  'Help & Guide', 'Status & Diagnostics', 'About'])
        self.assertFalse(any('_' in text for text in visible))
        self.assertEqual([i for i,t in enumerate(visible) if t.endswith('...')], [1, 2])
        for action in menu.actions():
            self.assertTrue(QKeySequence.mnemonic(action.text()).isEmpty())

    def test_setup_completion_uses_actual_initial_result_or_no_generation_message(self):
        from src.akb.bulk import BulkResult
        from src.akb.setup import Applied
        from src.akb import results
        dialog = self.dialog()
        self.adapter.sync_config = lambda: None
        calls = []
        self.adapter.bulk = lambda mid, finished: (calls.append(mid), finished(BulkResult(None, total=2, changed=1, unchanged=1)))
        class Operation:
            def __init__(inner, parent, op): pass
            def success(inner, callback): inner.done = callback; return inner
            def failure(inner, callback): return inner
            def run_in_background(inner): inner.done(Applied(None, changed=True))
        plan = SimpleNamespace(request=SimpleNamespace(mid=1, enabled=True))
        with patch.object(self.dialogs, 'CollectionOp', Operation), patch.object(results, 'notify') as notice:
            dialog.apply(plan, True)
            self.assertEqual(calls, [1])
            self.assertIn('1 note updated.', notice.call_args.args[0])
            self.assertIn('1 note was already up to date.', notice.call_args.args[0])
            self.assertFalse(notice.call_args.kwargs['detailed'])
            dialog.apply(plan, False)
            self.assertEqual(calls, [1])
            self.assertIn('Existing notes were not regenerated.', notice.call_args.args[0])

    def test_cleanup_notice_waits_for_file_removal_result(self):
        from src.akb.setup import Applied
        from src.akb.results import CleanupResult
        from src.akb import results
        dialog = self.dialogs.SetupDialog(self.adapter, {'version':2,'mappings':[dict(notetype_id=1,enabled=True)]}, [MODEL], cleanup=True)
        dialog.mode.setCurrentIndex(dialog.mode.findData('full'))
        dialog.remove_updates.setChecked(True)
        self.adapter.sync_config = lambda: None
        callbacks = []
        self.adapter.updates.remove_files = lambda finished: callbacks.append(finished)
        class Operation:
            def __init__(inner, parent, op): pass
            def success(inner, callback): inner.done = callback; return inner
            def failure(inner, callback): return inner
            def run_in_background(inner): inner.done(Applied(None, cleanup=CleanupResult('full', notes_cleared=1), changed=True))
        with patch.object(self.dialogs, 'CollectionOp', Operation), patch.object(results, 'notify') as notice:
            dialog.apply(SimpleNamespace(), False)
            notice.assert_not_called()
            callbacks.pop()('removed')
            self.assertIn('1 breakdown removed.', notice.call_args.args[0])
            self.assertIn('Automatic data update files were removed.', notice.call_args.args[0])
            self.assertTrue(notice.call_args.kwargs['detailed'])
