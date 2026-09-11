# Testing and compatibility

This is a repeatable test procedure, not a record of completed GUI/mobile tests. Use a disposable
profile/collection with backups. Automated tests open temporary collections only.
Install the exact approved .ankiaddon and record its SHA-256. Do not substitute
a development source checkout for the package.
Do not interpret a browser preview as validation of a device WebView.

Record Anki/client version, OS, theme, result and any other installed add-ons.

## Setup and onboarding

Real Qt offscreen tests supplement, but do not complete, these actual Anki checks.
Use Anki 25.02 with Python 3.9 and a current version in disposable profiles.

- [ ] First Setup opens **How Auto Kanji Breakdown works** before the form.
  Continue opens Setup; dismiss/close is remembered and does not repeatedly show it.
- [ ] **Tools → Auto Kanji Breakdown → Help & Guide** opens the full guide.
  Cleanup and normal startup do not automatically show onboarding.
- [ ] All nine **?** buttons show local
  readable help without internet access; keyboard activation and closing work.
- [ ] At normal Windows scaling, 150% and 200%, tutorial/help/review text fits or
  scrolls, buttons remain reachable, and the form works on a smaller display.
- [ ] New mapping defaults: automatic updates on, existing-note generation on,
  backs on, fronts off, dedicated field selected. Explicitly choose Japanese fields.
- [ ] Existing disabled/front-only/no-display mappings retain their configuration.
  Unchanged reopening leaves existing-note regeneration off. Changing Japanese fields,
  their order, output, or enabling a disabled mapping checks it and shows Recommended.
  Reverting those changes returns it to off unless explicitly chosen by the user.
- [ ] An explicit regeneration checkbox choice survives subsequent edits and switching
  note types within the open dialog. Display-side-only changes do not recommend a run.
- [ ] Tutorial headings are bold and body text normal in light and dark Anki themes;
  dialog height remains unchanged. Recommended labels are clear without dominating.
- [ ] Missing database or disabled automatic updates visibly explains why existing
  generation is unavailable. Review accurately states that it will not run.
- [ ] Confirmation shows Japanese fields, display sides, generated field, enabled/
  disabled choices and background-counted notes in understandable language. Cancel
  changes nothing; Apply keeps existing stale-preview and undo behavior.
- [ ] The cross-device summary is visible but subordinate; help explains desktop
  generation versus synced offline review and how to refresh mobile source edits.
- [ ] The cleanup footer is easy to find; its explanation preserves user-created
  fields and requires proof before offering deletion of add-on-created fields.

## Scoped manual regeneration

Run these on Anki 25.02 / Python 3.9.18 / Qt 6.6.2 / PyQt 6.6.1 / Windows 10,
and a current desktop Anki build. Backend automation does not cover these GUI checks.

- [ ] Right-click a standard editor field and choose **Regenerate Kanji Breakdown**.
  Change おおきい to 大きい without leaving the field first. Output contains 大,
  current content/focus is retained, and undo restores source and payload together.
- [ ] Remove all kanji and regenerate: output clears. Repeat without edits: no new
  note write/undo step. Test both Browser editor and Edit Current windows.
- [ ] Use the action on an unsaved Add draft: output updates immediately, but no
  note is inserted until Add is pressed. Close/discard still works normally.
- [ ] Unconfigured, disabled, renamed/missing/replaced fields and suspicious output
  produce useful feedback without overwriting content. Fix Setup and retry.
- [ ] Browser **Notes → Regenerate Kanji Breakdown**: select one note, then several
  including duplicate cards and mixed configured/unconfigured types. Only selected
  configured notes change, once each; summary counts match. Test an empty selection.
- [ ] Leave unsaved source edits in the Browser editor before invoking the selected
  action. They save first; selected regeneration uses the resulting values. Confirm
  undo boundaries described in [manual regeneration](manual-regeneration.md).
- [ ] Select over 200 disposable notes, cancel partway, confirm only completed
  batches persist and undo together. Confirm the Browser remains responsive.
- [ ] Make backend-only source edits (find/replace or experimental editor), then
  regenerate the selection and verify repaired payloads. Experimental Browser
  editor need not expose the standard-editor context-menu action.
- [ ] Switch notes/profile while an editor-save callback is pending; no stale
  completion changes the new editor or disables subsequent regeneration.
- [ ] Routine current-note success uses a tooltip; selected completion reports
  updated/already-current counts; skipped, protected, failed or cancelled runs
  receive a readable detailed summary.

## Existing setup, runtime, rendering and cleanup

- [ ] Upgrade an intact renderer-1 setup with Review/Apply: owner and outside card
  content remain unchanged, renderer-6 blocks replace the old blocks once, and undo
  restores the old display. Regeneration alone does not upgrade templates.
- [ ] Choose Light, Dark, Blue, Brown, Matcha, Matcha Dark, Sakura and Sakura Dark in Appearance / Theme. Theme-only
  changes leave regeneration unchecked and payload bytes untouched. Sync the selected
  appearance and verify it on actual mobile clients, including offline.
- [ ] Expandable cards start collapsed. Click/tap the glyph, meaning and blank card
  areas; verify whole-card toggling, subtle hover/pressed feedback, keyboard Enter/
  Space, focus indication and no toggle while selecting text.
- [ ] Nested chevrons expand their own subtree without collapsing the main card.
  Full-reading and full-meaning buttons work independently and return to compact mode.
  Check 生, 息 and a fully opened 蹴 at 360–430px and larger system text settings.
- [ ] Structureless/root-radical entries show no fake children or structural chevrons.
  Check 人, 水, 生 and dictionary-only 㐆; long dictionary lists may still have +N.
- [ ] Frequency uses Freq #N and an accessible description, or is absent. General
  radicals keep labelled stars, raw position codes never appear, and 京 omits 10**16.
- [ ] Test all palettes in Anki light/night modes, keyboard navigation, touch, reduced
  motion and high DPI. Explicit themes should not change with night-mode classes.

- [ ] Clean packaged install: startup is responsive, no mappings/writes by
  default; missing/corrupt database has a useful diagnostic.
- [ ] First setup: arbitrary note type, two ordered sources, default back placement,
  dedicated field created; review summary matches actual change.
- [ ] Existing note type: human-owned colliding name produces a new suffixed field.
  Nonempty selected existing output is refused; empty selected output is preserved
  as user-owned. Sources and other fields remain byte-identical.
- [ ] Multiple note types: configure each independently; disable one, verify the
  other still updates. Select front/back combinations and multiple templates.
- [ ] Save a new standard-editor note containing 階建語人水𠮟㐆鬱; verify the payload,
  first-appearance order, supplementary characters and review rendering.
- [ ] Edit/remove source text, save, verify refresh/clear; undo restores source and
  generated payload together. A missing/renamed/replaced field skips safely.
- [ ] Optional initial regeneration affects only the selected type. Global
  regeneration covers enabled mappings, reports progress and cancellation; undo
  restores changed fields in one step. Test a large disposable collection.
- [ ] Desktop review in light/night modes: inspect all eight representative kanji
  and 新しい図書館の階段を上がり、日本語の本を読みました。
- [ ] Inspect ⻖ glyph/hill gloss, 聿 brush, 廴 long stride/stretching, translated
  position badges, general radicals, full main-meaning reveal, no empty frequency chips
  and no empty component buttons on 人, 水 or dictionary-only 㐆.
- [ ] Collapse/reopen main and nested branches by click, Tab/Enter/Space and touch.
  Review successive cards, flip repeatedly, test FrontSide plus explicit back block
  for duplicates and stale DOM. Verify existing template JS still works.
- [ ] Re-run setup: no duplicate HTML/JS/CSS. Move a whole block and update again;
  location and all outside formatting remain intact. Test outdated markers and
  intentional damaged/duplicate markers (refusal, no changes).
- [ ] Profile switching and config undo/redo: runtime follows collection-local
  mappings; legacy fallback behavior is restored after undoing first setup.
- [ ] Renderer-only cleanup leaves payloads and generation, removes only owned
  blocks, and preserves outside content. Undo restores integration.
- [ ] Data-only cleanup disables generation and clears valid payloads, preserving
  suspicious values and templates. Undo restores configuration and data.
- [ ] Full cleanup leaves selected user fields; optional deletion only removes
  proven created fields. Suspicious content/outside references block deletion.
  Notes, cards, review history and scheduling remain unchanged. Undo/redo restores
  owned field identity and payload; repeated cleanup is harmless.
- [ ] Experimental Svelte editor shows the limitation diagnostic; standard editor
  still works. Explicit Regenerate repairs payloads after experimental edits,
  imports, sync and other backend-only source changes. No polling/patching occurs.
- [ ] Sync to actual AnkiMobile: fonts, light/night modes, large readings, narrow
  screens, nested touch expansion and repeated flips/cards; then airplane-mode
  review without desktop/add-on/master database.
- [ ] Repeat on actual AnkiDroid, including night-mode class/lifecycle differences
  and offline review. Record supported app/WebView versions.
- [ ] Edit a source on mobile: confirm documented need for desktop regeneration;
  sync regenerated output back and verify no stale content.
- [ ] Disable/uninstall desktop Python: existing synced cards still render. Run
  cleanup before uninstall when removal is desired. Test integration with other
  installed add-ons in a separate disposable profile.

## Source updates and offline attribution

- [ ] Exact packaged build: default monthly source checks ON, saved OFF persists.
- [ ] Status manual check stays responsive during review; no modal for no change,
  offline or failed validation. Actual update produces a tooltip only.
- [ ] Corrupt/delete the selected downloaded DB in a disposable installation:
  startup loads bundled data. No personal collection is used for this test.
- [ ] Update succeeds; new/edited and manually regenerated notes use its snapshot.
  Untouched existing notes remain byte-identical until explicitly regenerated.
- [ ] Sources is once per area, collapsed initially, keyboard/touch accessible,
  readable in eight themes/narrow mobile screens and works in airplane mode.
- [ ] Old payload shows unavailable provenance; new payload shows actual date/tag.
  Sources interaction never collapses the kanji card. Check official links separately.
- [ ] Upgrade owned renderer 1/2 blocks with Setup or theme Apply; preserve outside
  templates/owners and legacy payloads. Verify undo restores prior integration.
- [ ] Full cleanup file option starts unchecked; only owned downloaded data is
  removed, unrelated user_files remains, automatic checks turn off. This filesystem
  step is not undone by collection undo. Renderer/data-only modes preserve downloads.
- [ ] Anki upgrade preserves downloaded user_files; uninstall behavior is documented
  without promising persistence. Reinstall runs with the bundled fallback if needed.
- [ ] AGPL software source/build instructions and separate CC/source notices are
  available to recipients. Record actual mobile/app versions and package hash.


## Automated checks and Python compatibility

Follow [release environments and commands](releasing.md#tests-and-dependencies).
Run the suite under actual Python 3.9 / Anki 25.02 and Python 3.10 / Anki 26.8.1,
with Qt installed. Record versions and skips; offscreen widgets and browser tests
are not proof of physical-device behavior. Full builder tests need source archives.

The static gate in tests/test_python39.py parses every shipped module with the 3.9
grammar, rejects evaluated/quoted PEP 604 unions and aliases, reviews imports/API
calls, and tests its own incompatible fixtures. Prefer typing.Optional/Union;
built-in generics are supported on 3.9. Real Qt bitwise flags are not type unions.
Review new stdlib APIs and run actual 3.9 execution; the static gate is conservative,
not a complete type-aware compatibility checker. Guard optional Anki APIs such as
NewEditor, absent on 25.02. Do not bundle development dependencies.

## Release coverage

Also verify Yomitan via AnkiConnect, recording both versions; uninstall/reinstall;
upgrade from the previous package without duplicate hooks; other add-on interactions;
expanded-card scrolling inside Anki; and corresponding source/licence availability.
Retain dated results and archive checksums outside the source tree. Current known
platform evidence and limitations are stated in the [README](../../README.md#compatibility).


## Documented compatibility evidence

Desktop use has been reported on Anki 25.02 / Windows 10, with Yomitan via
AnkiConnect and mobile review after sync. Automated collection/UI coverage includes
Python 3.9.13 / Anki 25.02 and Python 3.10.10 / Anki 26.8.1 with offscreen Qt.
Edge/Chromium tests cover eight themes, keyboard controls and simulated narrow/touch
layouts. These do not substitute for physical-client testing. Exact integration and
mobile app/OS versions, offline-device checks and exact-package clean-install results
remain to be recorded. macOS/Linux GUI coverage is not established.
