# Anki API boundaries and compatibility

## Scoped manual regeneration

Compared tags **25.02**, **26.08.1** and current main commit
`084221657115fdd6d138d26cbce51c006184724b` before choosing the extension points.
The [25.02 GUI hook declarations](https://github.com/ankitects/anki/blob/25.02/qt/tools/genhooks_gui.py)
and [current-main declarations](https://github.com/ankitects/anki/blob/084221657115fdd6d138d26cbce51c006184724b/qt/tools/genhooks_gui.py)
provide `editor_will_show_context_menu(editor_webview, menu)` and
`browser_menus_did_init(browser)`. The first argument is the webview; resolve its
`.editor`. The Browser action belongs in `browser.form.menu_Notes`; obtain IDs
through `browser.selected_notes()` and deduplicate again in the worker.

Both the [25.02 standard editor](https://github.com/ankitects/anki/blob/25.02/qt/aqt/editor.py)
and [26.08.1 standard editor](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/editor_legacy.py)
provide `call_after_note_saved(callback, keepFocus=True)`. It flushes current web
fields; standard-editor bridge saves queue public note operations. The explicit
`CollectionOp` queues behind them. `loadNoteKeepingFocus()` refreshes the live
output without switching notes; `run_in_background(initiator=editor)` prevents the
Browser's operation handler from unnecessarily resetting editor focus.

NewEditor exposes `nid`, not `.note`, but provides the save callback. The Browser
selected action uses that callback and then reads selected notes from the collection.
It does not depend on the experimental editor having standard-editor internals.
The current-note context action is for the standard editor only. The experimental
automatic-hook limitation below remains. Source inspection and backend tests do
not replace GUI validation; see [manual regeneration verification](manual-regeneration.md).

The following boundaries were checked against **26.08.1** and main commit
`5edc31694f07487266bb8c4725508f6c5f5c198d`. Versioned source references establish
the inspected API contract, not support for every future release. Follow
[testing](testing.md) for backend, offscreen Qt and actual-client validation.

## Hook selection

The public generated [Python hook definitions](https://github.com/ankitects/anki/blob/26.08.1/pylib/tools/genhooks.py)
declare `note_will_flush(note: Note)` and
`note_will_be_added(col: Collection, note: Note, deck_id: DeckId)`.
The former covers both additions and updates. The latter only covers additions and
is unnecessary here.

[`Note._to_backend_note()`](https://github.com/ankitects/anki/blob/26.08.1/pylib/anki/notes.py)
invokes `note_will_flush(self)` before constructing the backend note. It is also
used by note validation and cloze inspection, so callbacks must be idempotent and
must not save anything. `Note.col` is a weak proxy: compare equality with the active
collection, not object identity. This is covered by both adapter and real tests.

[`Collection`](https://github.com/ankitects/anki/blob/26.08.1/pylib/anki/collection.py)
routes `add_note`, `add_notes`, `update_note` and `update_notes` through that
serialization. Updating only the in-memory field therefore participates in the
caller's ordinary commit and undo. No post-save operation or monkey patch is needed
for those paths. `note.flush()` is deprecated and skips normal undo semantics.

For manual regeneration, `update_notes` uses undo by default. The first successful
batch's `undo_status().last_step` anchors `merge_undo_entries`; no custom undo entry
is needed. `add_custom_undo_entry` was inspected but not used, avoiding empty entries
when no notes change. Saving/resetting the collection explicitly is unnecessary.

## GUI, background work and progress

The [GUI hook definitions](https://github.com/ankitects/anki/blob/26.08.1/qt/tools/genhooks_gui.py)
include `editor_did_unfocus_field(changed, note, current_field_idx) -> bool` and
`editor_did_fire_typing_timer(note)`. These are narrower than note serialization and
are not used for persistence. Profile open/close hooks manage the session snapshot;
`editor_did_init(editor)` is used only for the experimental-editor diagnostic.

The [standard editor](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/editor_legacy.py)
and [note operations](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/operations/note.py)
use the Python collection path. Do not confuse the file's “legacy” name with use of
deprecated mutation APIs: it is still the normal editor alongside an experimental
replacement in this release.

[`CollectionOp`](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/operations/__init__.py)
serializes worker access to the collection and dispatches completion changes to
Anki's GUI/undo handling. Return `OpChanges` or an object with `.changes`.
BulkResult follows this contract, including cancellation/partial failure.
`QueryOp.with_progress` handles profile preparation separately.

[`ProgressUpdate`](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/progress.py)
provides `user_wants_abort`, `label`, `value`, `max` and `abort` to the main-thread
progress callback. The callback transfers cancellation to an Event and never sets
backend abort for a committing batch. Worker code does not call progress widgets.

Note discovery uses public `find_notes("mid:<numeric ID>")`. The
[search parser](https://github.com/ankitects/anki/blob/26.08.1/rslib/src/search/parser.rs)
distinguishes `mid:` (ID) from `note:` (name). A name search for the numeric ID would
incorrectly miss notes. The real-backend bulk tests exercise actual ID discovery.
No raw SQL or private backend mutation is used by the add-on.

## Experimental editor and backend-only paths

26.08.1 contains a separate [NewEditor](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/editor.py).
Its [Svelte editor](https://github.com/ankitects/anki/blob/26.08.1/ts/routes/editor/NoteEditor.svelte)
calls `updateNotes`/`addNote` over HTTP. The
[media server](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/mediasrv.py)
dispatches these directly to Rust rather than constructing Python Note objects.
Consequently neither Python note hook runs for that path.

The [main window](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/main.py)
selects between normal/experimental dialogs, and the
[browser](https://github.com/ankitects/anki/blob/26.08.1/qt/aqt/browser/browser.py)
also supports the experimental editor via an experiment flag/Shift override.
There is no supported whole-note precommit hook for this path in the inspected
definitions. A generic post-operation callback does not provide the changed note
IDs, so it is not a safe substitute for an atomic precommit update.

Automatic generation supports automatic refresh in the **standard editor and public Python
note APIs**. It warns when NewEditor is opened; use standard editing or explicit
bulk regeneration. It does not patch HTTP handlers, inject an editor save shim, or
silently perform a collection-wide scan on every change. Imports/sync and other
backend-only operations similarly require explicit regeneration as needed.

Before claiming universal editor support, obtain an upstream precommit hook or
approve a separately designed integration with the experimental editor. This is a
known compatibility boundary, not proof that the GUI was tested. A release smoke
test must cover standard editor creation/editing, GUI progress, reload settings,
profile switching and other installed add-ons' hook interactions.

## Structural operations

Rechecked current upstream main on 2026-09-08 at
`a389f004094c61b1645054cd722720caf6a6e38f`. The
[GUI hook definitions](https://github.com/ankitects/anki/blob/a389f004094c61b1645054cd722720caf6a6e38f/qt/tools/genhooks_gui.py)
still provide no supported experimental-editor whole-note precommit hook. Retain
the standard-editor automatic path and explicit regeneration; no monkey patch,
post-save scan or polling has been added.

Setup uses public
[ModelManager APIs](https://github.com/ankitects/anki/blob/26.08.1/pylib/anki/models.py):
`new_field`, `add_field`, `remove_field` (in-memory draft), and `update_dict`.
Anki supplies stable field/template IDs on roundtrip. The official 26.8.1 backend
also preserves custom field ownership metadata through update and undo/redo.
Collection-local settings use `get_config` and `set_config(..., undoable=True)`.
Structural changes, generated-data clearing and settings are grouped with
`add_custom_undo_entry`/`merge_undo_entries`, merging each batch promptly. Unlike
bulk regeneration, setup is an independently named structural action. Both return
an object with `.changes` for CollectionOp's normal view/undo updates.

`gui_hooks.operation_did_execute(changes, handler)` refreshes the small in-memory
configuration snapshot after changes/undo. It does not scan notes, mutate notes,
or substitute for a precommit hook. Before serialization, config is also refreshed
to follow sync. Real temporary-backend tests cover setup, canonical JSON expansion
into templates, cleanup of 3,100 notes, owned field deletion and undo, rollback,
and restoring configuration after undoing initial setup. Actual Qt/mobile checks
remain pending in the manual checklist.
