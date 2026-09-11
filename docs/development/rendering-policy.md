# Rendering policy for the future runtime

This is a contract for later runtime/card work, not an implementation. The version-1
database remains a faithful raw structural tree. Presentation projects that tree
without editing, flattening or dropping its source annotations in stored data.

## Hierarchy and dictionary meanings

- Unnamed groups are transparent layout containers, never blank component nodes.
  Traverse them in source order so visible descendants stay reachable from the
  nearest displayed ancestor. Preserve their layout context in the projection;
  a child's position is relative to its source siblings, not automatically the
  newly displayed ancestor. An unnamed leaf has no visible component to display.
- A node with `part` is a structural fragment, not an independent complete kanji.
  Keep `part` (and `number` where supplied) in raw data. Suppress an ordinary
  complete-component tile/gloss for the fragment itself; still traverse its
  descendants. Do not merge fragments solely by matching `char`: separate instances
  can exist and `number` can distinguish them. `partial=true` likewise must not
  imply a complete standalone component.
- Display the actual KanjiVG `char` for a variant. Resolve meanings using explicit
  `base`, otherwise `char`, against KANJIDIC2. Do not replace the displayed glyph
  with its base. Do not guess meanings from appearance or from a different occurrence.
- For normal component glosses, choose one or two useful KANJIDIC2 meanings in
  authoritative order after removing presentation boilerplate such as
  `radical (no. N)`. This is a display filter, not a database edit or a new meaning.
  If no useful meaning remains, omit the gloss. Do not broadly remove every meaning
  containing the word “radical”; define narrow patterns with renderer tests later.
- Keep the full meaning array for the main kanji available. Short component glosses
  must not replace the source meanings or limit the main kanji detail view.
- Unresolved labels can still have useful named descendants. Never discard a whole
  subtree because its parent's gloss is missing. CDP/IDS labels are identifiers,
  not ordinary single-character kanji tiles; do not synthesize a glyph for them.

## Radical highlighting

Ordinary highlighting uses only `radical="general"`, at any depth including the
root. Preserve other conventions in raw data but do not promote them to general.
If none is supplied, show no general-radical highlight. Retain source-node identity
while projecting: a radical on a hidden fragment/container must not be arbitrarily
assigned to each visible descendant as though they were complete radicals.

## Observed positions

Raw codes remain unchanged in the database. The card UI translates known codes to
plain labels, with positions interpreted relative to source siblings. The following
counts cover **all 6,702 supplied SVG glyphs**, including non-KANJIDIC2 glyphs.
They were measured from the archive; meanings follow the official
[KanjiVG SVG format documentation](https://kanjivg.tagaini.net/svg-format.html#position)
(consulted 2026-09-08). No position is required on every group.

| Raw code | Occurrences | Meaning / suggested UI label |
| --- | ---: | --- |
| `bottom` | 6,559 | Below sibling / Bottom |
| `top` | 6,550 | Above sibling / Top |
| `right` | 5,745 | Right of sibling / Right |
| `left` | 5,738 | Left of sibling / Left |
| `tare` | 419 | Covers above and left / Upper-left enclosure |
| `tarec` | 400 | Counterpart inside tare / Inside upper-left enclosure |
| `kamae` | 324 | Surrounding element / Enclosure |
| `nyoc` | 221 | Counterpart inside nyo / Inside lower-left enclosure |
| `nyo` | 221 | Extends left and below / Lower-left enclosure |
| `kamaec` | 20 | Counterpart of kamae / Inside enclosure |
| `⿵A` | 11 | Outer upper surround / Upper enclosure |
| `⿵B` | 6 | Inner lower section / Inside upper enclosure |
| `middle` | 5 | Central member of three, either axis / Middle |
| `⿶1` | 3 | Inner upper section / Inside lower enclosure |
| `⿶2` | 2 | Outer lower surround / Lower enclosure |

The source documentation cautions that `kamae` and `middle` are inconsistent;
labels must not imply exact geometry. `nyoc`, `tarec`, and `kamaec` denote counterpart
roles rather than fixed screen coordinates. Unknown future codes remain raw in the
database; the UI should omit an unrecognized position label rather than guess.

Examples: 建 uses 聿=`nyoc` and 廴=`nyo`. 階 includes unnamed positioned groups.
語 contains split 二 fragments beneath 五. These require projection, not rewriting
the database to resemble the UI.

The renderer implements this policy without changing the master or payload
schemas. See [renderer architecture](renderer-architecture.md) for the exact
concise labels, deterministic gloss rules, conservative via handling and collapse
behavior. Source audit counts and raw structure above remain unchanged.
