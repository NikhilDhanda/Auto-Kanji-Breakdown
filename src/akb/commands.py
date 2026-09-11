"""Explicit regeneration at editor/Browser scope through supported GUI hooks."""

LABEL = 'Regenerate Kanji Breakdown'


def feedback(message, parent):
    from aqt.utils import tooltip
    tooltip(message, parent=parent)


def ready(adapter, parent):
    if adapter.runtime is None or adapter.loading or adapter.running:
        feedback('Kanji Breakdown is busy or not loaded. Check Status & Diagnostics.', parent)
        return False
    if adapter.collection != adapter.mw.col:
        feedback('The active collection changed. Reload Kanji Breakdown settings.', parent)
        return False
    adapter.sync_config()
    return True


def editor_menu(adapter, webview, menu):
    from aqt.qt import qconnect
    editor = webview.editor
    # The experimental editor has a different UI and no legacy context hook.
    if not hasattr(editor, 'loadNoteKeepingFocus'):
        return
    action = menu.addAction(LABEL)
    qconnect(action.triggered, lambda _checked=False: current_note(adapter, editor))


def browser_menu(adapter, browser):
    from aqt.qt import qconnect
    if getattr(browser, '_akb_regenerate_action', None) is not None:
        return
    action = browser.form.menu_Notes.addAction(LABEL)
    browser._akb_regenerate_action = action
    qconnect(action.triggered, lambda _checked=False: selected_notes(adapter, browser))


def current_note(adapter, editor):
    parent = editor.widget
    if not ready(adapter, parent):
        return
    note = editor.note
    if note is None or note.col != adapter.collection:
        feedback('No current note is available.', parent)
        return
    problem = adapter.runtime.check(note, manual=True)
    if problem:
        feedback(problem, parent)
        return
    output_before = note[adapter.runtime.mappings[note.mid].output_field]
    generation = adapter.generation
    adapter.running = True  # prevent duplicate commands during the async flush

    def saved():
        if generation != adapter.generation:
            return
        adapter.running = False
        if editor.note is not note:
            feedback('The current note changed. Run regeneration again.', parent)
            return
        if not ready(adapter, parent):
            return
        runtime = adapter.runtime
        problem = runtime.check(note, manual=True)
        if problem:
            feedback(problem, parent)
            return
        if editor.addMode:
            # An unsaved Add draft must never be inserted as a side effect.
            try:
                result = runtime.refresh(note, manual=True)
                if result.changed:
                    editor.loadNoteKeepingFocus()
                feedback(result.diagnostic or ('1 note updated.' if result.changed
                                              else 'Breakdowns already up to date. No notes needed updating.'), parent)
            except Exception:
                feedback('Could not regenerate this draft. Its output was preserved.', parent)
            return

        output = runtime.mappings[note.mid].output_field
        changed_during_save = note[output] != output_before
        snapshot = [(name, note[name]) for name in note.keys() if name != output]

        def done(result):
            # Do not replace subsequent edits or switch the editor to an old note.
            if (not result.failed and not result.skipped and not result.error and
                    editor.note is note and generation == adapter.generation and
                    snapshot == [(name, note[name]) for name in note.keys() if name != output]):
                try:
                    stored = adapter.collection.get_note(note.id)
                    if list(stored.keys()) == list(note.keys()):
                        note[output] = stored[output]
                        editor.loadNoteKeepingFocus()
                except Exception:
                    feedback('Regeneration finished, but the editor could not refresh. Reopen the note.', parent)
                    return
            message = result.error or (result.diagnostics[0] if result.diagnostics else '')
            if result.failed and not message:
                message = 'Could not regenerate this note. Its output was preserved.'
            if result.cancelled:
                from .results import regeneration_text
                message = regeneration_text(result)
            feedback(message or ('1 note updated.' if result.changed or changed_during_save else
                                 'Breakdowns already up to date. No notes needed updating.'), parent)

        # Queued after Anki's editor save. The normal hook normally already did
        # the work; this becomes a no-op without a second write/undo entry.
        adapter.bulk(note_ids=(note.id,), parent=parent, finished=done, initiator=editor)

    try:
        editor.call_after_note_saved(saved, keepFocus=True)
    except Exception:
        adapter.running = False
        feedback('Could not save current editor contents. Regeneration was not started.', parent)


def selected_notes(adapter, browser):
    if not ready(adapter, browser):
        return
    ids = tuple(dict.fromkeys(browser.selected_notes()))
    if not ids:
        feedback('Select one or more notes to regenerate.', browser)
        return
    generation = adapter.generation
    current = getattr(browser.editor, 'note', None)
    if current is not None and current.mid in adapter.runtime.mappings:
        problem = adapter.runtime.check(current, manual=True)
        if problem:
            feedback('Resolve the current editor before regenerating the selection: ' + problem, browser)
            return
    adapter.running = True

    def saved():
        if generation != adapter.generation:
            return
        adapter.running = False
        if not ready(adapter, browser):
            return
        adapter.bulk(note_ids=ids, parent=browser)

    try:
        # Include current Browser editor edits before reading selected notes.
        browser.editor.call_after_note_saved(saved, keepFocus=True)
    except Exception:
        adapter.running = False
        feedback('Could not save Browser editor contents. Regeneration was not started.', browser)
