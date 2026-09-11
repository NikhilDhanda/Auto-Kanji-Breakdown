# Kanji data updates

Auto Kanji Breakdown includes kanji data so it works without a download during
normal generation or review. Optional desktop updates keep that information current.

## Automatic checks

**Automatically keep kanji data up to date** is on by default. About once a month,
desktop Anki can check the official KANJIDIC2 and KanjiVG sources in the background.
Turn the option off in Settings or Status & Diagnostics if you prefer.

The add-on does not upload your notes or study information. It has no analytics,
telemetry or account requirement. Source downloads are separate from normal Anki
sync. It is offline-friendly, not an add-on that never connects to the internet.

If a download or validation fails, working data is retained. Ordinary offline or
no-change checks do not interrupt you with a modal dialog.

## Check now

Open **Tools > Auto Kanji Breakdown > Status & Diagnostics** and choose
**Check for database updates now**. This runs a manual check even when automatic
checks are off. Reopen Status to see the latest outcome and source dates.

## What changes on my cards?

An update supplies data for new notes, later desktop edits and manual regeneration.
It does **not** automatically rewrite all existing breakdowns. If you want older
notes refreshed, use the [regeneration commands](usage.md). Then sync normally.

The card's **ⓘ** panel shows the source versions used for that particular breakdown.
Older breakdowns may not contain snapshot details; the panel says so honestly.

Downloaded data is local to the desktop installation. Normal add-on upgrades
preserve it, but do not rely on it surviving uninstall. [Full cleanup](cleanup.md)
can remove it explicitly, with no filesystem undo.

[Technical update architecture](development/database-update-architecture.md) · [Data attribution](ATTRIBUTION.md)
