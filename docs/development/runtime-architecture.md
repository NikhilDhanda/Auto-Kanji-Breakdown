# Runtime architecture

The `src/` directory supplies the packaged add-on root. Its `__init__.py` installs the thin
Anki adapter when imported by Anki; `src/akb/` transformation modules can also be
imported in ordinary Python. Setup, portable rendering and cleanup are separate modules;
see [renderer architecture](renderer-architecture.md). See [releasing](releasing.md) for the offline package builder.

## Data flow and modules

`database.py` loads the generated JSON; `config.py` parses mappings; `extractor.py`
recovers source text; `payload.py` resolves dictionary data and projects structural
trees; `runtime.py` computes and compares the destination before assigning it.
`integration.py` and `dialogs.py` adapt Qt/Anki. Setup/cleanup use public collection
operations; the transformation modules remain independent of Qt. `bulk.py` is
independently testable and reused for optional initial regeneration.

The installed fallback is `data/kanji_db.json` with its sidecar manifest. A valid
selected `user_files/akb_updates` database takes precedence. `Database(path)` and `install(addon_name, database_path=path)`
accept an explicit path. Development tools/tests inject `generated/kanji_db.json`.
No duplicate database is committed. The release builder stages the canonical
artifact at `data/kanji_db.json`; copying only `src/` into Anki without staging data
will produce an understandable load error. Use disposable profiles for development.

## Session preparation and diagnostics

The profile-open hook starts a progress-blocked `QueryOp` to read/validate the
database off the GUI thread, validate configured note types, and create a runtime
snapshot. The hook never reads files or reparses the master database. Successful
loads are cached for that profile session; profile close releases the data. Failure
disables automatic updates and surfaces a diagnostic. The loader validates the
envelope, schema version, nonempty entries mapping, dictionary value types and trees.

Use **Tools → Auto Kanji Breakdown → Settings** for collection-local
version-2 settings. Version-1 add-on JSON settings remain the fallback until setup.
**Status & Diagnostics → Reload database and settings** reapplies settings. It reuses
the loaded database; restart/switch profiles to load a replaced database. Nothing
rewrites existing notes on configuration reload: edit/save notes or use Regenerate.
Empty mappings are the conservative default. Invalid mappings are skipped with
diagnostics; independent valid mappings still work. Diagnostics are deduplicated
per load and marshalled to the main thread; logs contain error classes, not private
note contents. Only the optional desktop source-data updater makes network requests. It starts
after preparation in a collection-independent worker; it never blocks generation
or review. See [database updates](../database-updates.md) for adoption and privacy.

## Automatic updates and undo/sync

The sole mutation lifecycle hook is `anki.hooks.note_will_flush(note)`, which adjusts
the in-memory destination before Anki serializes new/updated notes. There is no
second save, recursion, custom undo entry, explicit collection save or reset. The
original operation commits source and cache together with normal Anki modification
and sync tracking. Repeated serializations are idempotent. Note validation/preview
can also serialize a note; that only updates the in-memory cache, never saves it.

Mappings are selected by note-type ID and exact fields. Unrelated types remain
untouched. Removed/renamed fields or stale note name/index layouts prevent writes.
Generation completes before assigning the destination. Identical bytes cause no
assignment; no supported characters produces an empty destination, clearing stale
data. The destination is wholly machine-owned, including preexisting manual text
once that output mapping is explicitly enabled. It must be a dedicated field.

Backend-only changes such as imports, sync, find/replace, and the experimental
Svelte editor can bypass Python note hooks. They are not automatically intercepted.
Use current-note, Browser selected-note or global regeneration after those operations.
See [manual regeneration](manual-regeneration.md) for scope, editor-save ordering,
ownership checks and undo. Other clients can display synced
payloads but cannot regenerate edits without this desktop runtime. The adapter warns
when the experimental editor is opened; use Anki's standard editor for automatic
updates. See [API investigation](anki-api.md) for this material compatibility limit.

## Bulk regeneration

**Tools → Auto Kanji Breakdown → Regenerate Breakdowns...** runs a `CollectionOp`. All discovery,
lookups, generation, and writes execute in its serialized collection worker.
Validated IDs use `find_notes("mid:<id>")`; no raw SQL. IDs are deduplicated and
ordered; notes are read in batches of 100. Only changed notes reach `update_notes`.
The ID list is held in memory, but only one batch's note objects/payloads is retained.

The first successful batch supplies the undo anchor via `undo_status().last_step`.
Subsequent batches merge into it using `merge_undo_entries`. This gives one undo
step (Anki's standard update-note label) without creating an empty undo entry for a
no-op. Serialization during the worker suppresses this runtime's automatic hook
through a context-local guard, avoiding duplicate work. Other add-ons still run.

Progress uses `CollectionOp.with_backend_progress`: its main-thread callback reads
small locked counters and sets a thread-safe cancellation Event when Esc/close is
requested. The worker checks between notes/batches. It does not abort an in-flight
backend commit. Discovery and a current backend call can delay cancellation.
Cancelling discards the pending batch and preserves completed batches as one
undoable operation. Errors report the number committed and retain completed undoable
work rather than claiming a whole-run transaction. A backend/undo-system failure
may leave separately undoable batches; no automatic rollback of unrelated work is
attempted. `CollectionOp` receives the changes object even after partial completion
so Anki updates views/undo actions normally.

## Source text normalization

HTMLParser decodes entities once, ignores markup attributes and comments, inserts
boundaries for br/div/p/li/tr, and skips script/style/template content. Ruby base
text remains; rt/rp annotations are excluded, including nested formatting. Anki
`[sound:filename]` references are removed so Japanese media filenames are not mined.
Image alt/src attributes do not contribute characters. Plain field text and entities
representing kanji do. Unsupported characters are ignored by database membership;
Python Unicode iteration naturally supports supplementary planes. Unique characters
follow first appearance across source fields in configured order.

This is text recovery, not browser layout: CSS-hidden spans are not interpreted,
Anki cloze hint syntax is not specially stripped, and malformed unclosed annotation
tags conservatively suppress remaining text. No Unicode semantic normalization,
translation, kana conversion or reading punctuation changes are performed.

## Verification

`python -m unittest discover -s tests -v` runs all standard-library tests; optional
real-backend tests skip when `anki` is unavailable. In a separate test environment,
install `anki==26.8.1` and run the same command to exercise temporary collections.
This is a development test dependency only. No tests open a user's collection or
require network access. `python -m tools.inspect_payloads` reports sizes and full
sample payloads. See [testing](testing.md) for verification procedures.


## Completion feedback

results.py formats committed outcomes, never preview estimates. Routine success
and no-op use tooltips; protected content, cancellation and partial failure use
plain-text dialogs. Escape user field names in HTML tooltips. Cleanup counts
successfully changed templates once even when both sides changed, and distinguishes
user-owned, unverified and intentionally retained fields. Safety failures still
refuse/roll back rather than becoming success. File-removal feedback waits for its
callback and distinguishes absent/removed files, failure and fallback reload failure.
Setup without an initial run explicitly says existing notes were not regenerated.
