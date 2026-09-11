# Data attribution and provenance

Auto Kanji Breakdown uses **KANJIDIC2**, compiled by James William Breen and the
Electronic Dictionary Research and Development Group (EDRDG), and **KanjiVG**,
by Ulrich Apel and contributors. No endorsement is implied.

[THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md) is the complete distribution
notice, included with local licence/documentation copies. Original code is
AGPL-3.0-or-later; upstream and derived data retain their separate CC terms.
Compilation/transformation: Copyright 2026 Nik Dhanda, without claiming upstream ownership.

| Input | Version | Licence | SHA-256 |
| --- | --- | --- | --- |
| `data_sources/kanjidic2.xml.gz` | File 4; database 2026-253; created 2026-09-10 | CC BY-SA 4.0 / EDRDG statement | `1b71bf842d53bbf7f490baa13f9d236de81e37f97b6fdd9170946b74ead5a6bc` |
| `data_sources/kanjivg-20250816-main.zip` | 2025-08-16 | CC BY-SA 3.0 | `69a2944ec1183086fdee5ba9c1f48bc306b867480a95b2f337f3203bf50689a3` |

`generated/kanji_db.json` is the combined derived database, distributed under
CC BY-SA 4.0 with upstream attribution retained. Its `sources` envelope preserves
provenance; the add-on bundles identical bytes at `data/kanji_db.json`.

KANJIDIC2 transformations select English meanings, on/kun readings, first stroke
count and frequency; omit indexing metadata including SKIP. KanjiVG transformations
discard SVG geometry/presentation, preserve ordered structure and annotations, and
join canonical glyphs to KANJIDIC2 entries. Sources are never modified.
See [schema](development/database-schema.md), [upstream notices](../THIRD_PARTY_LICENSES.md),
and [releasing](development/releasing.md).

The approved beta baseline was refreshed on 2026-09-10 from the exact verified
official input bytes. Master SHA-256: `cf90012dabe9f61a452ba790f63a72948fe3c090eee43a8d4287bba41cab6a04`.
The sidecar records actual retrieval on 2026-09-10 and HTTP validators.
See [reproducible database build](development/building-database.md).

Software contributions remain AGPL-3.0-or-later; this does not relicense upstream
data. Provide corresponding source/build instructions with distribution. The
28-day desktop source-check interval is project policy, not a universal legal
deadline. Preserve notices for offline desktop and synced mobile access.
