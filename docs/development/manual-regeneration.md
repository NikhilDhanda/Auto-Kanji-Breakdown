# Manual regeneration

Implemented and verified on 2026-09-09. This adds scoped refresh commands without
changing rendering, payload format, setup settings or cleanup ownership rules.

## Four refresh paths

| Path | Location | Scope |
| --- | --- | --- |
| Automatic | Standard editor save | The note being saved |
| Current note | Right-click a standard editor field → **Regenerate Kanji Breakdown** | Current note, including an unsaved Add draft |
| Selected notes | Browser → **Notes → Regenerate Kanji Breakdown** | Selected note IDs, deduplicated across cards |
| Existing bulk | Tools → Auto Kanji Breakdown → **Regenerate Breakdowns** | All enabled configured mappings |

Manual regeneration recalculates from current source fields. It repairs stale
payloads after find/replace, imports, sync, experimental-editor edits or other paths
that bypass Python's automatic hook. It does not invent mappings or override
ownership. Unconfigured/disabled mappings, missing fields, stale layouts and invalid
field identities are skipped. Empty sources clear generated output; identical
payloads cause no extra collection write.

The two new commands also require empty or recognizable canonical version-1 output,
using the same content predicate as setup/cleanup. Malformed, handwritten or unknown
version output is preserved with a diagnostic. A valid older payload under version 1
can be rebuilt. This extra manual safeguard does not change the existing automatic
or global regeneration policy for an explicitly enabled dedicated output field.

## Editor contents and undo

The current-note command validates the live Python note before requesting
`editor.call_after_note_saved(callback, keepFocus=True)`, then revalidates after the
web fields have been flushed. Current source edits therefore reach the generation
path before a collection read. The standard editor queues its normal save, including
the existing automatic hook; the manual collection operation queues behind it.
Usually the save already generated the correct output and the explicit operation
is a no-op. Source and payload then share Anki's ordinary editor undo entry.

If the stored payload alone needs repair, the explicit changed-only update provides
one undo step. An unsaved Add draft is updated in memory and is never inserted as a
side effect; it gains collection undo only when the user adds it normally. The
command preserves focus through Anki's supported editor refresh and never closes
the editor. Delayed callbacks check profile generation and note identity; completion
copies only the output when the other live field values still match its snapshot.

The Browser snapshots the selection before flushing its active editor, then reads
selected notes in the collection worker. The active editor's normal source save may
be a separate undo step from a multi-note regeneration operation: these have different
scopes, and unrelated earlier undo entries are never blindly merged. A configured
standard-editor note with invalid/suspicious output blocks that flush with a message
to resolve it first. Other selected invalid notes are skipped independently.

## Shared worker and feedback

`Runtime.check()` handles validation and `Runtime.refresh()` remains the sole note
generation path. `commands.py` contains menu/save/feedback glue. `Integration.bulk()`
adapts the existing `bulk.regenerate()` worker to an explicit `note_ids` collection;
an empty selection never falls back to global discovery. Setup's canonical-output
predicate moved unchanged to `payload.safe_payload()` for reuse.

Saved-note work uses serialized `CollectionOp`, public `get_note`/`update_notes`,
100-note batches and the existing context-local automatic-hook guard. The first
successful batch anchors undo; later batches merge into it. No-op runs create no
undo entry. Per-note read/generation failures are counted and isolated. Commit or
undo failures stop the run; completed writes remain undoable, potentially as
separate batches if undo merging itself failed. No raw SQL, deprecated save APIs,
monkey patches, additional database loads or second generation engine are used.

Progress/cancellation use the existing locked counters and cancellation Event.
Cancellation discards the uncommitted batch and preserves committed work. It cannot
interrupt an in-flight backend commit. Current-note success uses a tooltip; selected
completion reports selected, examined, configured, changed, unchanged, skipped and
failed counts, with diagnostics and pending/discarded changes on cancellation.
“Configured” counts examined notes with an enabled mapping, including those later
skipped for invalid fields/output. “Changed” counts committed updates only.

## GUI verification boundary

The tests execute real collection/undo APIs but stub Qt scheduling and editor
callbacks. They do not claim a full Anki GUI smoke test or exact Python 3.9.18 /
Qt 6.6.2 / PyQt 6.6.1 execution. The [manual checklist](testing.md) covers
actual field flushing, focus, undo menus, cancellation and profile switching on
the user's Anki 25.02 environment and a current desktop version.

No new blocker for standard Anki 25.02 was found. The experimental editor still
bypasses automatic Python note hooks and lacks the standard context-menu extension.
Its Browser selected-note action uses the supported save callback without assuming
a `.note` attribute, but still requires GUI smoke verification. See the versioned
source references in the [API investigation](anki-api.md).


## Current result summaries

Result summaries preserve commit/undo behavior. BulkResult exposes a
protected-output subset of skipped notes in addition to existing committed,
unchanged, failed and pending counters. Successful runs use concise tooltips;
cancelled/partial runs use readable dialogs. A zero-change successful run says
Breakdowns already up to date; no matching notes and skipped/failed runs are not
misrepresented as success. Initial setup uses the same result formatter. Raw
per-note diagnostics remain in operation results; normal completion copy avoids
internal identifiers. See [testing](testing.md) for validation procedures.
