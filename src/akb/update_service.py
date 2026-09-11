"""Main-thread Anki coordination around the collection-independent updater."""
from copy import deepcopy
import time
from .data_store import Store, provenance
from .database import Database, Entries
from .updater import Updater, enabled

HELP = ('About once a month, Auto Kanji Breakdown checks the official KANJIDIC2 and '
        'KanjiVG sources for updated kanji data. Updates happen in the background. '
        'The bundled database continues to work normally without an internet connection. '
        'No usage data, notes or study information are sent. Only desktop Anki performs these checks.')


class UpdateService:
    def __init__(self, adapter):
        self.adapter = adapter
        self.busy = False
        self.pending = None
        self.last_result = ''

    def set_enabled(self, checked):
        raw = deepcopy(self.adapter.legacy_config())
        if not isinstance(raw, dict):
            raw = {'version': 1, 'mappings': []}
        raw['auto_data_updates'] = bool(checked)
        self.adapter.mw.addonManager.writeConfig(self.adapter.addon_name, raw)

    def adopt(self):
        adapter = self.adapter
        if self.pending and not adapter.running and not adapter.loading and adapter.runtime:
            database = self.pending
            adapter.runtime.entries = database.load()  # Already populated in the worker.
            adapter.database = database
            self.pending = None

    def start(self, manual=False):
        adapter = self.adapter
        if self.busy or (not manual and (adapter.database_path is not None or not enabled(adapter.legacy_config()))):
            return
        from aqt.operations import QueryOp
        generation = adapter.generation
        self.busy = True

        def work(_col):
            result = Updater().run(manual)
            if result['status'] == 'updated':
                database = Database()
                database.manifest = result['manifest']
                database.origin = 'Updated'
                database._entries = Entries(result['data']['entries'])
                database._entries.provenance = provenance(result['manifest'])
                result['database'] = database
            return result

        def done(result):
            self.busy = False
            self.last_result = result['status']
            if result['status'] == 'updated':
                self.pending = result['database']
                self.adopt()
                if generation != adapter.generation:
                    return  # The global data snapshot is safe; suppress stale-profile UI.
                from aqt.utils import tooltip
                tooltip('Kanji data updated. New and edited notes will use the latest data. '
                        'Use Regenerate Breakdowns to refresh existing breakdowns.', parent=adapter.mw)

        def failed(_error):
            self.busy = False
            self.last_result = 'failed'
        QueryOp(parent=adapter.mw, op=work, success=done).failure(failed).without_collection().run_in_background()

    def diagnostics(self):
        store = Store()
        data, meta, origin = store.load()
        state = store.read_json('update_state.json')
        if not isinstance(state, dict):
            state = {'last_failure': 'Invalid saved update state'}
        def date(value):
            try:
                return time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(float(value))) if value else 'Never'
            except (ValueError, TypeError, OverflowError):
                return 'Unavailable'
        return '\n'.join([
            'Kanji database: ' + ('Last update failed; ' + origin if state.get('last_failure') else origin),
            'Database build/retrieval: ' + str(meta.get('retrieved') or 'Bundled snapshot'),
            'KANJIDIC2 snapshot: ' + str(meta['sources']['kanjidic2'].get('snapshot')),
            'KanjiVG release: ' + str(meta['sources']['kanjivg'].get('release')),
            'Database SHA-256: ' + meta['sha256'],
            'KANJIDIC2 SHA-256: ' + meta['sources']['kanjidic2']['sha256'],
            'KanjiVG SHA-256: ' + meta['sources']['kanjivg']['sha256'],
            'Last attempted check: ' + date(state.get('last_attempt')),
            'Last successful check: ' + date(state.get('last_success')),
            'Last successful update: ' + date(state.get('last_update')),
            'Last failure category: ' + str(state.get('last_failure') or 'None'),
            'Last failure stage: ' + str(state.get('failure_stage') or 'None'),
            'Last HTTP failure status: ' + str(state.get('failure_http_status') or 'None'),
            'Session update result: ' + (self.last_result or 'No check completed'),
            'Previously generated notes may use older snapshots. Use Regenerate Breakdowns to refresh them.'])

    def remove_files(self, finished=None):
        if self.busy:
            if finished:
                finished('failed')
            return
        from aqt.operations import QueryOp
        from .updater import _JOB
        self.busy = True
        removal = ['failed']
        def work(_col):
            if not _JOB.acquire(blocking=False):
                raise ValueError('Update still running')
            try:
                store = Store()
                existed = store.root.exists()
                store.clear()
                removal[0] = 'removed_reload_failed' if existed else 'absent_reload_failed'
                database = Database()
                database.load()
                return database, 'removed' if existed else 'absent'
            finally:
                _JOB.release()
        def done(outcome):
            database, state = outcome
            self.busy = False
            self.pending = database
            self.adopt()
            if finished:
                finished(state)
        def failed(_error):
            self.busy = False
            self.last_result = 'cleanup failed'
            if finished:
                finished(removal[0])
        QueryOp(parent=self.adapter.mw, op=work, success=done).failure(failed).without_collection().run_in_background()
