"""The only Qt/Anki adapter: lifecycle, background preparation and Tools actions."""
from threading import Event, Lock
import logging

from .bulk import regenerate
from .config import parse_config, validate_mapping
from .database import Database
from .runtime import Runtime
from .setup import KEY, read_config

logger = logging.getLogger(__name__)


class Integration:
    def __init__(self, mw, addon_name, database_path=None):
        self.mw = mw
        self.addon_name = addon_name
        self.database_path = database_path
        from .update_service import UpdateService
        self.updates = UpdateService(self)
        self.database = None
        self.runtime = None
        self.collection = None
        self.generation = 0
        self.warned = set()
        self.loading = False
        self.running = False
        self.fallback_mappings = None

    def diagnostic(self, message):
        if message in self.warned:
            return
        self.warned.add(message)
        from aqt.utils import showWarning
        self.mw.taskman.run_on_main(lambda: showWarning('Auto Kanji Breakdown: ' + message, parent=self.mw))

    def before_save(self, note):
        self.updates.adopt()
        runtime = self.runtime
        if runtime is None or note.col != self.collection:
            return
        try:
            self.sync_config()
            result = runtime.before_save(note)
            if result.diagnostic:
                self.diagnostic(result.diagnostic)
        except Exception as error:
            logger.error('Automatic generation failed (%s)', type(error).__name__)
            self.diagnostic('Could not generate this note. The destination was preserved; check configuration and reload the database.')

    def close(self):
        self.updates.pending = None
        self.generation += 1
        self.runtime = self.collection = self.database = None
        self.fallback_mappings = None
        self.warned.clear()
        self.loading = False
        self.running = False

    def editor_opened(self, editor):
        from aqt import editor as editor_module
        # Older supported Anki releases have only the standard Editor class.
        experimental = getattr(editor_module, 'NewEditor', None)
        if experimental is not None and isinstance(editor, experimental):
            self.diagnostic('The experimental Svelte editor bypasses Python note hooks. Use the standard editor for automatic updates, or run Regenerate after editing.')

    def legacy_config(self):
        return self.mw.addonManager.getConfig(self.addon_name)

    def sync_config(self, _changes=None, _handler=None):
        self.updates.adopt()
        # Collection config participates in undo and sync. Refresh only the tiny
        # mapping, keeping the loaded database and hook-suspension context intact.
        if self.runtime is not None and self.collection is not None:
            if self.fallback_mappings is None:
                self.fallback_mappings = dict(self.runtime.mappings)
            raw = self.collection.get_config(KEY)
            self.runtime.mappings = ({m.notetype_id: m for m in parse_config(raw).mappings}
                                     if raw is not None else dict(self.fallback_mappings))

    def prepare(self):
        from aqt.operations import QueryOp
        if self.loading or self.running or self.mw.col is None:
            return
        self.loading = True
        self.runtime = None
        self.collection = self.mw.col
        self.generation += 1
        generation = self.generation
        self.warned.clear()
        legacy = self.legacy_config()
        self.fallback_mappings = {m.notetype_id: m for m in parse_config(legacy).mappings}
        self.database = self.database or Database(self.database_path)
        database = self.database

        def work(col):
            config = parse_config(read_config(col, legacy))
            messages = list(config.diagnostics)
            for mapping in config.mappings:
                problem = validate_mapping(mapping, col.models.get(mapping.notetype_id))
                if problem:
                    messages.append(f'Note type {mapping.notetype_id}: {problem}')
            return Runtime(database.load(), config), messages

        def success(value):
            if generation != self.generation:
                return
            self.loading = False
            self.runtime, messages = value
            self.updates.adopt()
            self.updates.start()
            for message in messages:
                self.diagnostic(message)

        def failure(error):
            if generation == self.generation:
                self.loading = False
                self.diagnostic('Database/configuration could not be loaded. Automatic updates are disabled. Check the database and reload settings.')

        QueryOp(parent=self.mw, op=work, success=success).failure(failure).with_progress(
            'Loading Auto Kanji Breakdown'
        ).run_in_background()

    def bulk(self, mid=None, *, note_ids=None, parent=None, finished=None, initiator=None):
        from anki.collection import OpChanges
        from aqt.operations import CollectionOp
        from aqt.utils import showInfo
        runtime = self.runtime
        if runtime is None or self.running or self.loading:
            self.diagnostic('Runtime is not ready. Reload settings after checking the database.')
            return
        self.updates.adopt()
        runtime = self.runtime
        self.sync_config()
        hook_runtime = runtime
        if mid is not None:
            from .config import Config
            runtime = Runtime(runtime.entries, Config(tuple(m for m in runtime.mappings.values() if m.notetype_id == mid)))
        self.running = True
        cancel = Event()
        lock = Lock()
        state = [0, 0]
        parent = parent or self.mw
        generation = self.generation

        def progress(done, total):
            with lock:
                state[:] = [done, total]

        def update(_backend_progress, ui):
            if ui.user_wants_abort:
                cancel.set()
            with lock:
                done, total = state
            ui.label = f'Auto Kanji Breakdown: {done}/{total} notes (Esc to stop)'
            ui.value, ui.max = done, total
            # Never ask the backend to interrupt a committing batch. Cancellation
            # is cooperative between notes/batches via the thread-safe Event.

        def success(result):
            if generation != self.generation:
                return
            self.running = False
            self.updates.adopt()
            if finished:
                finished(result)
                return
            from .results import regeneration_notice
            regeneration_notice(result, parent)

        def failure(error):
            if generation != self.generation:
                return
            self.running = False
            self.diagnostic('Bulk regeneration could not start. No further updates were attempted.')

        def work(col):
            if col != self.collection or generation != self.generation:
                raise RuntimeError('Collection changed before regeneration')
            # Initial regeneration may use a filtered runtime; suspend the actual
            # installed hook too, avoiding duplicate generation during serialization.
            with hook_runtime.suspend_hook():
                return regenerate(col, runtime, OpChanges(), progress, cancel.is_set, note_ids=note_ids)

        CollectionOp(parent=parent, op=work).with_backend_progress(update).success(success).failure(failure).run_in_background(initiator=initiator)


def install(addon_name, database_path=None):
    from anki import hooks
    from aqt import mw, gui_hooks
    from aqt.qt import QAction, qconnect
    from .dialogs import open_dialog, show_status, show_guide
    from .commands import editor_menu, browser_menu
    from .about import show_about
    if mw is None:
        return
    if getattr(mw, '_akb_integration', None) is not None:
        return
    adapter = Integration(mw, addon_name, database_path)
    mw._akb_integration = adapter
    hooks.note_will_flush.append(adapter.before_save)
    gui_hooks.profile_did_open.append(adapter.prepare)
    gui_hooks.profile_will_close.append(adapter.close)
    gui_hooks.editor_did_init.append(adapter.editor_opened)
    gui_hooks.operation_did_execute.append(adapter.sync_config)
    gui_hooks.editor_will_show_context_menu.append(lambda webview, menu: editor_menu(adapter, webview, menu))
    gui_hooks.browser_menus_did_init.append(lambda browser: browser_menu(adapter, browser))
    menu = mw.form.menuTools.addMenu('Auto Kanji Breakdown')
    for label, callback in [('Settings', lambda: open_dialog(adapter)),
                            ('Regenerate Breakdowns...', lambda: adapter.bulk()),
                            ('Cleanup...', lambda: open_dialog(adapter, cleanup=True)),
                            (None, None),
                            ('Help && Guide', lambda: show_guide(adapter)),
                            ('Status && Diagnostics', lambda: show_status(adapter)),
                            ('About', lambda: show_about(adapter.mw))]:
        if label is None:
            menu.addSeparator()
            continue
        # Qt uses && to display a literal ampersand rather than a mnemonic.
        action = QAction(label, mw)
        qconnect(action.triggered, callback)
        menu.addAction(action)
    if mw.col is not None:
        adapter.prepare()
    return adapter
