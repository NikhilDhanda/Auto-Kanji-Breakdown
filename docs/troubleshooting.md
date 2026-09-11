# Troubleshooting

Start with **Tools > Auto Kanji Breakdown > Status & Diagnostics**. It shows the
loaded kanji data and configuration issues. **Help & Guide** has the common commands.

## There is no breakdown on my card

Check that Settings uses the note's actual note type, the correct Japanese fields
and the intended card side. For existing notes, run regeneration if you skipped it
during setup. A note with no supported kanji has no breakdown to show.

## It did not update after an edit

Enable **Automatically keep breakdowns updated** for the note type. Use the standard
desktop editor or regenerate explicitly after imports, some third-party edits or
mobile edits. The experimental Svelte editor can bypass automatic generation.

## A field is missing, protected or renamed

Reopen Settings and review the selected fields. Do not overwrite unrelated text in
a breakdown field. Choose a new dedicated field if the existing one contains your
own content. Cleanup can refuse field deletion when safety checks fail.

## My theme or Sources panel still looks old

Use theme **Apply** in Settings, then sync. Regenerating notes updates their
information; it does not update the card display code.

## A data update failed or I am offline

The add-on retains working data and has a bundled fallback. Check Status & Diagnostics
for details; use **Check for database updates now** when online if needed. There is
no need to delete your notes or run cleanup to retry a source check.

## Scrolling is less smooth with many branches open

Try closing branches you do not need. If scrolling stays slow, include your
Anki/OS versions, theme and a small non-private example when reporting it.

## A decomposition looks unusual

KanjiVG describes structure, which can expose unfamiliar fragments. Missing meanings
are not guessed. Report the character, shown branches, expected result and any
reliable source. See [contributing](../CONTRIBUTING.md).

## Compatibility and reporting

Use desktop Anki with Python 3.9 or newer. macOS and Linux desktop testing is
limited, and third-party integrations can vary by version or workflow.
See [compatibility](../README.md#compatibility).

Report the add-on version from About, Anki/OS versions, reproduction steps and
sanitized Status & Diagnostics text. Mention other add-ons involved. Use a
non-private example rather than a collection export or unreviewed screenshot.
See [reporting an issue](../CONTRIBUTING.md#report-a-bug-or-suggest-an-improvement).
