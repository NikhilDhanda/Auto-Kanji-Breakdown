# Frequently asked questions

## Does this modify my Japanese text?

No. It reads the fields you choose and writes generated information to a separate
breakdown field. Do not put handwritten content in that dedicated field.

## Does this affect scheduling or review history?

No. Generation and cleanup do not delete notes, cards, scheduling or review history.

## Does it work with existing decks?

Yes. Configure the note types they use and generate breakdowns for existing notes.
You choose the field names and card sides; no special deck is required.

## Does it work with Yomitan?

Yomitan can create notes through AnkiConnect with automatic breakdowns on desktop. Configure
the matching note type and Japanese fields first. [Prerequisites and limits](yomitan.md)

## Does it work on AnkiMobile?

You can review synced breakdowns in AnkiMobile, including offline. Generate them
on desktop first; mobile does not generate new breakdowns.

## Does it work on AnkiDroid?

You can review synced breakdowns in AnkiDroid, including offline. After editing
Japanese text on mobile, sync back to desktop and regenerate. See [mobile use](mobile.md).

## Does it work offline?

Generation uses local kanji data. Existing breakdowns work offline after syncing.
Downloading newer source data needs internet access.

## Does it send my cards anywhere?

Auto Kanji Breakdown does not upload notes or study data and has no analytics or
telemetry. Normal Anki sync and Yomitan/AnkiConnect are separate applications/workflows.

## What happens when the kanji database updates?

A validated update becomes available for future generation. If updating fails, the
working data remains available. [Data updates](database-updates.md)

## Do existing cards update automatically after a database refresh?

No bulk rewrite happens merely because data changed. Later desktop edits or manual
regeneration use the new data. Use Regenerate Breakdowns for older configured notes.

## What happens if I edit a card on mobile?

After editing its Japanese text, sync back to desktop, regenerate the affected note,
then sync again. Mobile does not run the desktop generator.

## Can I change themes later?

Yes. Choose a theme in Settings and press its Apply button. It does not regenerate
your notes. [Themes](themes.md)

## Can I remove the add-on safely?

Use Cleanup first if you want the generated display/data removed, then uninstall.
Optional field deletion has safeguards. [Cleanup modes and limits](cleanup.md)

## Where does the kanji information come from?

KANJIDIC2 supplies dictionary information; KanjiVG supplies structure. Open the
bottom-right ⓘ for offline credits and snapshot details. [Attribution](ATTRIBUTION.md)

## Why does a particular decomposition look unusual?

The structure is derived from open-source KanjiVG data. Its technically valid
branches may be more detailed than a learner expects. The add-on does not invent
meanings or a different tree when information is missing.

## How do I report a bad decomposition?

Share the character, a sanitized screenshot or branch description, what you expected
and a reliable reference if available. Do not include private study material.
[Reporting data issues](../CONTRIBUTING.md)
