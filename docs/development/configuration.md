# Setup and configuration

Open **Tools → Auto Kanji Breakdown → Settings**. Select a note type,
check **Japanese fields** and arrange them with Move up/down. Keep “Create a new dedicated
field” for first setup, select card sides (backs by default), then review and apply.
Repeat for additional note types; configuring one preserves other mappings.

First setup opens a brief local tutorial; dismissing or continuing remembers it.
**Help & Guide** in the same submenu includes the short explanation plus common tasks with exact menu paths. Each major setup
option has a native **?** help button. A compact cross-device reminder and cleanup
link explain where to learn more without filling the form with technical details.

For a new mapping, **Automatically keep breakdowns updated** and **Generate
breakdowns for existing notes now** are on, backs are selected and fronts are off.
Japanese fields must still be selected explicitly. Existing mappings retain their
enabled flag, source order, output and selected sides, including an empty side list.
The existing-note checkbox starts off when reopening an unchanged configured type,
even if a previous setup generated its notes. Changing Japanese fields/order or the
generated field, or enabling a disabled mapping, recommends and checks regeneration.
Reverting those changes removes the recommendation. An explicit checkbox choice in
the open dialog takes precedence for that note type, including after switching types.
Display-side or theme changes alone do not recommend a run. Review shows the existing
note count collected by the existing background scan and clearly states which
options are off. See [testing](testing.md) for setup validation.

Setup never renames or deletes existing fields. New names are `Auto Kanji Breakdown`,
then `Auto Kanji Breakdown (2)`, etc. A colliding name is never implicitly adopted.
An explicitly selected pre-existing output is allowed only when every value is
empty or recognizable canonical version-1 payload JSON. Otherwise choose a new
field to preserve the content. Enabling a mapping authorizes future note saves and
regeneration to replace the entire dedicated output, including clearing it when
sources contain no supported kanji. Do not keep handwritten notes in that field.

The current-note and Browser selected-note **Regenerate Kanji Breakdown** commands
add a conservative content check: only empty or canonical version-1 generated
payloads may be replaced. Suspicious output is preserved with a diagnostic. Existing
automatic/global generation authorization and cleanup ownership rules are unchanged.
See [manual regeneration](manual-regeneration.md) for the four refresh paths.

Disabling generation preserves payloads and rendering. Changing sources/output does
not silently rebuild notes. **Generate breakdowns for existing notes now** uses the existing bulk
backend for only the configured note type, with a separate undo step. It is offered
when the database is loaded and automatic updates are enabled; Status includes a
reload action. If unavailable, a visible explanation and the confirmation explain
that existing notes will not be generated. The checkbox preference is retained.

Template integration is appended to selected sides. Updating setup replaces intact
owned blocks wherever moved and removes them from deselected sides. Outside bytes
are preserved exactly. Damaged, duplicate or unknown-owner markers stop changes.
Field names containing template delimiters/filter syntax are rejected.

**Appearance / Theme** offers **Light**, **Dark**, **Blue**, **Brown**, **Matcha**,
**Matcha Dark**, **Sakura**, and **Sakura Dark**, in that order.
Blue (formerly Classic) is the default for new and older unthemed mappings.
The previous Sakura palette is now labelled Sakura Dark. Saved identifiers
`classic` and `sakura` remain unchanged so existing colors are preserved;
the new palettes use `brown`, `matcha-dark`, and `sakura-light`. Existing
valid theme choices are restored. The **Apply** button beside the theme selector
immediately updates all configured Auto Kanji Breakdown displays in this collection
and saves the default for new setups. It does not apply pending field selections or
run regeneration, and the whole theme update can be undone in Anki. This controls
breakdown cards, not Anki's own application theme. The optional collection setting
`default_theme` stores this preference; no schema version change is required.
Applying a theme updates only the owned display
templates/styling and configuration, so existing generated notes need no rebuild.
The choice syncs in the card template and works without the desktop add-on at review
time. Run Setup/Review/Apply to update existing renderer blocks to version 6; normal
regeneration alone does not update templates. Ownership and cleanup checks remain
unchanged. See [renderer architecture](renderer-architecture.md).

## Configuration version 2

Master schema **1** and note payload version **1** are unchanged. Configuration
version **2** adds ownership and uses the collection configuration key
`auto_kanji_breakdown` through public `get_config`/`set_config`. It travels with the
collection, including sync, rather than depending on a profile name. Changes use
`undoable=True`, so resources and configuration undo together.

The add-on JSON settings remain a version-1 fallback until successful setup. After
migration the collection record is authoritative; use this dialog rather than the
add-on JSON editor. Legacy mapping values are never rewritten by onboarding;
only its UI completion flag is merged into the add-on settings. Undoing first setup
restores fallback behavior. Existing version-1 mappings survive migration and gain
identity records when explicitly configured.

Example (IDs/tokens are illustrative):

```json
{
  "version": 2,
  "mappings": [{
    "enabled": true,
    "notetype_id": 123456,
    "notetype_name": "Japanese",
    "source_fields": ["Expression", "Context"],
    "output_field": "Auto Kanji Breakdown",
    "owner": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "fields": [{
      "name": "Auto Kanji Breakdown",
      "id": -987654321,
      "created": true,
      "token": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }],
    "templates": [{"id": 456789, "side": "afmt"}],
    "css": true,
    "renderer_version": 6,
    "theme": "classic"
  }]
}
```

The owner is a random UUID hex token per configured note type. Every tracked field
has its stable Anki field ID and exact name. Created fields also carry the token in
the note-type field's `akb_owner` metadata. Selected existing fields have
`created: false` and are never automatically deleted. Historical outputs remain in
`fields` for cleanup; removed-resource records support repeated cleanup. The latest
record for a reused name supplies runtime identity. Ownership never follows a name
alone. Generation verifies output ID and, for created fields, the token.

`templates` records stable template IDs and `qfmt` (front)/`afmt` (back). `css` records
styling installation. Matching intact markers independently prove block ownership.
Browser-only templates are untouched. Status reports missing fields/templates and
marker problems. Names are display hints; note-type IDs remain authoritative.

The parser accepts versions 1 and 2: positive note-type ID, boolean enabled flag,
ordered unique nonempty sources and distinct output. Malformed mappings are skipped;
duplicate IDs disable competing writers. Unsupported envelopes disable all writers.
Fields resolve by exact name with identity checks where available. Missing/renamed
fields or stale Note layouts cause safe skipping. There is no profile/name remapping.

An optional boolean `generate_existing` in each mapping records the last applied setup
checkbox, not a standing request to run every time setup opens or a runtime setting.
The UI now derives the opening recommendation from current changes instead. The
record is written only by setup and follows its existing grouped
transaction/undo; callers that omit it preserve the previous value. Configuration
version remains 2. Automatic and manual generation ignore this presentation preference.
The independent add-on setting `ui_onboarding_completed: true` remembers tutorial
dismissal per installation, across profiles. It creates no collection undo entry
and does not modify collection settings, mappings, notes or templates.

## Cleanup

Use **Tools → Auto Kanji Breakdown → Cleanup**, select a configured type,
and preview one of these actions:

| Mode | Template/CSS | Payloads | Generation |
| --- | --- | --- | --- |
| Renderer only | Remove intact owned blocks | Keep | Unchanged |
| Clear generated data | Keep | Clear recognizable values | Disable |
| Full cleanup | Remove intact owned blocks | Clear recognizable values | Disable |

The preview reports approximate affected-note counts, suspicious-content counts,
and exact fields proposed for deletion. Noncanonical/malformed/handwritten values
are preserved and counted. A field replaced under the same name causes refusal;
missing fields are left alone. Source fields cannot be cleanup targets.

Full cleanup optionally offers deleting proven add-on-created fields, unchecked by
default. Name, ID, created flag, token and field metadata must match. Suspicious
content or a reference outside the owned template blocks (including browser,
filtered and cloze references) blocks deletion. Selected existing fields are always
retained. The preview warns that deletion changes note schema. No note/card/review
deletion API is used.

Planning/scanning runs off the GUI thread. Apply rechecks note type, configuration
and a digest of candidate note contents against the preview. Stale previews must
be regenerated. Public operations group changes into one undo entry; each clearing
batch is merged promptly so large jobs cannot evict the anchor. Setup/cleanup holds
the collection operation lock to completion and has no mid-commit cancel. Failures
before writes preserve everything; ordinary failures during this grouped operation
roll back its own changes. Catastrophic backend/undo failure still needs normal Anki
recovery/backups.

Uninstalling Python alone leaves synced rendering and payloads working. Run cleanup
before uninstalling to remove them. Mobile can display payloads offline; source
edits on mobile need desktop regeneration.


## Desktop database update setting

**Automatically keep kanji data up to date** is separate from automatic note
updates. It defaults ON when absent and preserves saved OFF. Setup and Status
save it immediately to installation-local add-on JSON as `auto_data_updates`;
it is not copied into collection config 2 and does not affect setup preview/undo.
Its ? help explains monthly official-source checks, offline fallback and no study
uploads. No mappings or unrelated settings are discarded.

**Status & Diagnostics → Check for database updates now** bypasses the interval,
using the same background updater even if automatic checks are off. Reopen Status
to refresh results. See [database updates](../database-updates.md) for 28-day scheduling,
24-hour failure backoff, storage, diagnostics and no automatic bulk regeneration.

Full cleanup optionally removes the marked `user_files/akb_updates` namespace and
disables data checks for this installation. It starts unchecked, is unavailable
in other cleanup modes, preserves unrelated user_files and is not filesystem-undoable.
Collection removal/undo semantics remain those described above. Do not assume
user_files survives add-on uninstallation; Anki preserves it during upgrades.

## About and feedback

Tools → Auto Kanji Breakdown → About shows the packaged
VERSION, author and software licence. Sources & Licences reads local packaged
attribution and licence texts offline. GitHub opens only when clicked.
The onboarding tutorial includes a small author credit without increasing its size.
Theme Apply reports “Theme applied” through a native non-modal Anki tooltip;
its existing undo operation is unchanged. Missing legacy automatic-generation
preferences default ON, while explicitly saved OFF remains OFF.


## Current UX wording

The menu order is Settings, Regenerate Breakdowns..., Cleanup..., a separator,
Help & Guide, Status & Diagnostics, About. The data field label is
"Breakdown data field". Nine ? controls cover automatic breakdowns, Japanese fields,
breakdown data field, card sides, theme, automatic kanji data updates, existing
notes, mobile use and cleanup. Obvious note-type selection and move buttons do not
receive extra help controls.

The first-run tutorial remains short with bold headings and a secondary author
credit, now briefly mentioning monthly data checks. The separate Help & Guide
adds setup, one-note/selected/global regeneration, theme Apply, update checks,
mobile syncing and cleanup tasks. About distinguishes the software licence from
data licensing. Theme Apply remains the non-modal "Theme applied" notification.

Beginner defaults are unchanged: automatic generation ON, existing-note generation
ON for a new mapping, backs ON, fronts OFF, classic palette (displayed as Blue).
Saved choices, including OFF and a collection default theme, are preserved.


## Completion feedback

Setup without an existing-note run reports Setup complete (or Settings already up
to date) and explicitly says existing notes were not regenerated. Initial runs
report committed updates and notes already current, never assuming every update
contains kanji: an update may correctly clear an empty-source note.

Cleanup reports committed note clears, removed card-template integrations, actual
field deletions and retained fields/reasons. It waits for optional local update
file removal before reporting its outcome. Missing files and removal/reload
failures remain distinct. Reference or identity checks that refuse deletion still
stop the operation with a warning; no silent keep-and-continue policy was added.
Routine success uses a tooltip. Cleanup details, protected content, cancellation
and partial results use a plain-text dialog. Theme remains simply Theme applied.
