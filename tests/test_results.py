"""User summaries use committed facts and preserve no-op/partial distinctions."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
from src.akb.results import CleanupResult, cleanup_text, regeneration_text, notify
from src.akb.bulk import BulkResult


class ResultTests(unittest.TestCase):
    def test_cleanup_modes_fields_and_actual_counts(self):
        full = CleanupResult('full', notes_cleared=2014, templates_removed=2,
                             deleted=('Auto Kanji Breakdown',))
        text = cleanup_text(full, 'removed')
        for phrase in ('2,014 breakdowns removed.', '2 card templates',
                       'The "Auto Kanji Breakdown" field was deleted.',
                       'Automatic data update files were removed.', 'review history were not deleted'):
            self.assertIn(phrase, text)
        text = cleanup_text(CleanupResult('renderer', templates_removed=1))
        self.assertIn('1 card template.', text)
        self.assertIn('Generated breakdown data was kept.', text)
        text = cleanup_text(CleanupResult('data', notes_cleared=1,
                            retained=(('Output', 'not_created'),)))
        self.assertIn('1 breakdown removed.', text)
        self.assertIn('Your card templates were kept.', text)
        self.assertIn('not created by Auto Kanji Breakdown', text)
        self.assertNotIn('field was deleted', text)
        for reason, wording in [('not_requested', 'deletion was not selected'),
                                ('unverified', 'could not be verified')]:
            self.assertIn(wording, cleanup_text(CleanupResult('full', retained=(('Output', reason),))))

    def test_noop_protection_and_file_failures_are_honest(self):
        self.assertTrue(cleanup_text(CleanupResult('full')).startswith('Nothing to clean up'))
        text = cleanup_text(CleanupResult('full', protected=1), 'failed')
        self.assertIn('unsupported field content that was preserved', text)
        self.assertIn('could not be removed', text)
        self.assertNotIn('files were removed.', text)
        self.assertIn('could not be reloaded', cleanup_text(CleanupResult('full'), 'removed_reload_failed'))

    def test_regeneration_counts_protected_cancellation_and_setup(self):
        result = BulkResult(None, total=21, changed=18, unchanged=2, skipped=1, protected=1)
        text = regeneration_text(result)
        for phrase in ('18 notes updated.', '2 notes were already up to date.',
                       '1 note was skipped because the breakdown field contained unsupported content.'):
            self.assertIn(phrase, text)
        result = BulkResult(None, total=10, changed=1, cancelled=True, pending=2)
        text = regeneration_text(result)
        self.assertTrue(text.startswith('Regeneration cancelled'))
        self.assertIn('1 note updated before cancellation.', text)
        self.assertIn('2 notes were not saved.', text)
        text = regeneration_text(BulkResult(None, total=2, changed=1, unchanged=1), setup=True)
        self.assertTrue(text.startswith('Setup complete'))
        self.assertIn('1 note was already up to date.', text)
        self.assertIn('Future desktop edits', text)
        self.assertNotIn('now have kanji', text)  # An update can also clear an empty-source note.

    def test_noop_and_failed_runs_do_not_claim_success(self):
        self.assertIn('Breakdowns already up to date', regeneration_text(BulkResult(None, total=2, unchanged=2)))
        self.assertIn('No notes to regenerate', regeneration_text(BulkResult(None)))
        for result in (BulkResult(None, failed=1), BulkResult(None, skipped=1),
                       BulkResult(None, diagnostics=['invalid settings'])):
            self.assertNotIn('already up to date', regeneration_text(result))

    def test_notifications_are_plain_or_escaped_and_simple_success_nonmodal(self):
        utils = SimpleNamespace(tooltip=Mock(), showInfo=Mock())
        with patch.dict('sys.modules', {'aqt.utils': utils}):
            notify('Setup complete', None)
            utils.tooltip.assert_called_once_with('Setup complete', parent=None)
            utils.showInfo.assert_not_called()
            notify('The "<Field>" field was deleted.', None, detailed=True)
            utils.showInfo.assert_called_once_with('The "<Field>" field was deleted.', parent=None, textFormat='plain')
            notify('<Field>', None)
            self.assertEqual(utils.tooltip.call_args.args[0], '&lt;Field&gt;')

    def test_file_removal_callback_reports_completed_state_only(self):
        from src.akb.update_service import UpdateService
        from src.akb import update_service
        class Query:
            def __init__(self, parent, op, success): self.op, self.success = op, success
            def failure(self, callback): self.failed = callback; return self
            def without_collection(self): return self
            def run_in_background(self):
                try: value = self.op(None)
                except Exception as error: self.failed(error)
                else: self.success(value)
        for exists, clear_error, load_error, expected in (
                (True, False, False, 'removed'), (False, False, False, 'absent'),
                (True, True, False, 'failed'), (True, False, True, 'removed_reload_failed')):
            store, database, finished = Mock(), Mock(), Mock()
            store.root.exists.return_value = exists
            if clear_error: store.clear.side_effect = ValueError('protected')
            if load_error: database.load.side_effect = ValueError('unavailable')
            adapter = SimpleNamespace(mw=None, running=False, loading=False, runtime=None)
            service = UpdateService(adapter)
            with patch.dict('sys.modules', {'aqt.operations': SimpleNamespace(QueryOp=Query)}), \
                    patch.object(update_service, 'Store', return_value=store), \
                    patch.object(update_service, 'Database', return_value=database):
                service.remove_files(finished)
            finished.assert_called_once_with(expected)
            self.assertFalse(service.busy)
