# Yomitan and AnkiConnect

If Yomitan creates a note through AnkiConnect using a note type configured in Auto
Kanji Breakdown, its breakdown can be generated automatically on desktop.

## Before mining a card

- Set up Yomitan and AnkiConnect so they can already create your Anki notes.
- Keep desktop Anki and the required add-ons running for that workflow.
- In **Tools > Auto Kanji Breakdown > Settings**, configure the same note type
  Yomitan uses, and select the Japanese fields that it fills.
- Leave **Automatically keep breakdowns updated** enabled and choose a display side.

When that workflow creates a matching note, its breakdown can be generated on
desktop. Sync normally to review it on mobile. Mobile does not run the generator.

## If a mined note has no breakdown

Check the note type, selected Japanese fields and automatic-update switch. Then
try **Regenerate Kanji Breakdown** on the note in the desktop editor. Some import,
backend-edit or third-party paths can bypass automatic generation.

Third-party integrations can vary by version or workflow. If a mined note does not
receive a breakdown, regenerate it from the desktop editor and check the configured
note type and fields. Include both add-on versions and a non-private example when
reporting an issue. Never share credentials or an AnkiConnect API key.
[Troubleshooting](troubleshooting.md)
