# Third-party data and licensing

Auto Kanji Breakdown uses KANJIDIC2 and KanjiVG. No endorsement is implied.
AGPL-3.0-or-later applies to original software, not these upstream datasets or their
documentation. Retain this notice and licenses/ when redistributing the package.

## KANJIDIC2

Compiled by **James William Breen** and the **Electronic Dictionary Research and
Development Group (EDRDG)**. Copyright remains with James William Breen and EDRDG.
Used in conformance with the [EDRDG General Dictionary Licence Statement](https://www.edrdg.org/edrdg/licence.html),
which applies **Creative Commons Attribution-ShareAlike 4.0 International**.

- [KANJIDIC project/documentation](https://www.edrdg.org/wiki/KANJIDIC_Project.html)
- [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Local copies: [EDRDG statement](licenses/EDRDG-licence.html),
  [project documentation](licenses/KANJIDIC-documentation.html),
  [full CC licence](licenses/CC-BY-SA-4.0.txt).

The supplied XML reports file version 4, database version 2026-253, created
2026-09-10. We select English meanings, Japanese on/kun readings, first stroke
count and frequency rank. Dictionary indices (including SKIP codes), non-Japanese
readings and other unused metadata are omitted. Derived dictionary content remains
subject to upstream terms; inclusion does not transfer ownership of upstream material.
Desktop source checks periodically download official upstream data and rebuild
locally in a background worker. Ordinary generation and review work offline; a
failed check retains the working database. Existing notes are refreshed only on
later edits or explicit regeneration. See docs/database-updates.md.

## KanjiVG

**KanjiVG**, by **Ulrich Apel and contributors**, is licensed under
[Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/).
The supplied SVG notices read Copyright (C) 2009/2010/2011 Ulrich Apel.

- [Project](https://kanjivg.tagaini.net/)
- [Repository/source releases](https://github.com/KanjiVG/kanjivg)
- Supplied release: `kanjivg-20250816-main.zip`.
- Local copies: [source copyright notice](licenses/KanjiVG-source-notice.txt),
  [project documentation](licenses/KanjiVG-documentation.html),
  [full CC licence](licenses/CC-BY-SA-3.0.txt).

We discard SVG geometry and presentation; preserve ordered structural groups and
original/base, radical, position and fragment annotations; and join canonical
glyphs to the KANJIDIC2 character set. Structural data remains subject to upstream
terms. AUTHORS retains the project attribution and link. No source data is edited.

## Derived database and attribution of changes

`generated/kanji_db.json` is a derived/compiled database assembled for Auto Kanji
Breakdown from both sources. The installed `data/kanji_db.json` contains identical
bytes. Its `sources` envelope records versions, filenames and SHA-256 hashes.
Compilation/transformation work: **Copyright 2026 Nik Dhanda**. This credit claims
no ownership of upstream material.

The combined adapted database is distributed under **CC BY-SA 4.0**, with upstream
attribution retained. CC BY-SA 3.0 section 4(b) permits an adaptation under a later
version with the same licence elements. This does not relicense the original
KanjiVG archive itself. Code and database have separate licences; AGPL-3.0-or-later does
not replace either source's terms. Generated note payloads contain extracts of
this same derived material.

The desktop package includes local licence/documentation copies. The synced
renderer provides one collapsed Sources panel per breakdown area with offline
attribution and official links. Payload provenance identifies its own snapshot;
legacy data says details are unavailable. Actual mobile access still requires
release smoke testing. No source-project endorsement is implied.
