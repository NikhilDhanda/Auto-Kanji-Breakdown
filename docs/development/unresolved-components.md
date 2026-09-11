# Unresolved component audit

Audited the supplied KANJIDIC2 2026-251 and KanjiVG 20250816 archives in
`data_sources/`. Recorded coverage: **459 occurrences, 70 distinct lookup
strings**. No resolver changes were warranted and no semantic mappings were added.
The 4,952 unnamed groups are counted separately, not as unresolved named components.

## Method and evidence

Run `python -m tools.audit_components` from the repository root to reproduce the
JSON evidence offline. It reparses the archives, enumerates every unresolved node
in retained KANJIDIC2 trees, records exact source file and zero-based child path,
and searches all 6,702 glyphs for explicit original mappings for each unresolved
value. It tests NFC, NFD, NFKC and NFKD in both directions against dictionary keys.
This run used Python's Unicode database **13.0.0**. Normalization candidates are
review evidence only; the builder never applies blanket compatibility normalization.

For every one of the 70 values:

- No matching KANJIDIC2 key exists.
- All four normalization forms leave the value unchanged, and none matches a
  normalized dictionary key (including reverse compatibility-character matches).
- No occurrence elsewhere in this KanjiVG archive supplies an original mapping
  from this lookup string to a dictionary character.

Explicit originals on the *actual nodes* were inspected too and are already
preserved and used. In particular, common 亻→人, 氵→水, 忄→心 and ⻖→阜 mappings
remain covered by regression tests. This does not assert that all unresolved labels
are semantically meaningless: many are useful components outside KANJIDIC2 coverage.
It establishes that they are not lost through an ignored supplied original or a
Unicode normalization equivalence. Descendant components can still resolve normally.

## Classification

Categories are exclusive for totals. “Potentially resolvable variants” is a
secondary review flag in the inventory, not an asserted mapping or extra category
added to the totals. These candidates remain unresolved because the available
sources do not justify conversion. Other labels consist of the radical symbol ⺄.

| Category | Distinct values | Occurrences |
| --- | ---: | ---: |
| CDP/IDS-style identifiers | 8 | 28 |
| CJK stroke symbols | 3 | 4 |
| Kana | 4 | 97 |
| Non-KANJIDIC2 ideographs | 54 | 329 |
| Other structural/source labels | 1 | 1 |

## Complete inventory

Every distinct unresolved string appears exactly once below. Examples are source
kanji, not proposed dictionary substitutes. The JSON audit includes **all** node
locations; this table lists up to three example kanji and the first node path.
CDP/IDS identifiers denote structures, stroke symbols denote strokes, kana denote
source shape/base labels, and the ideograph category contains actual Unicode
characters absent from this KANJIDIC2 release.

### CDP/IDS-style identifiers

| Value | Code point(s) | Count | Examples | First source node | Finding |
| --- | --- | ---: | --- | --- | --- |
| CDP-8BB0 | U+0043 U+0044 U+0050 U+002D U+0038 U+0042 U+0042 U+0030 | 6 | 從, 慫, 樅 | `kanji/05f9e.svg` / `structure.children[1]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| CDP-8BC4 | U+0043 U+0044 U+0050 U+002D U+0038 U+0042 U+0043 U+0034 | 5 | 原, 愿, 源 | `kanji/0539f.svg` / `structure.children[1]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| CDP-8BD0 | U+0043 U+0044 U+0050 U+002D U+0038 U+0042 U+0044 U+0030 | 11 | 傳, 囀, 團 | `kanji/050b3.svg` / `structure.children[1].children[0]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| CDP-8CB8 | U+0043 U+0044 U+0050 U+002D U+0038 U+0043 U+0042 U+0038 | 2 | 武 | `kanji/06b66.svg` / `structure.children[0]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| CDP-8DBA | U+0043 U+0044 U+0050 U+002D U+0038 U+0044 U+0042 U+0041 | 1 | 曦 | `kanji/066e6.svg` / `structure.children[1].children[1]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| ⿱日隹 | U+2FF1 U+65E5 U+96B9 | 1 | 暹 | `kanji/066b9.svg` / `structure.children[0]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| ⿱穴㒸 | U+2FF1 U+7A74 U+34B8 | 1 | 邃 | `kanji/09083.svg` / `structure.children[0]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |
| ⿵𠔼コ | U+2FF5 U+2053C U+30B3 | 1 | 爨 | `kanji/07228.svg` / `structure.children[0].children[1]` | Source structural identifier; use existing descendants, not an invented dictionary meaning. |

### CJK stroke symbols

| Value | Code point(s) | Count | Examples | First source node | Finding |
| --- | --- | ---: | --- | --- | --- |
| ㇁ | U+31C1 | 1 | 丞 | `kanji/04e1e.svg` / `structure.children[0].children[0].children[0]` | Stroke shape, not a dictionary kanji. |
| ㇆ | U+31C6 | 1 | 捌 | `kanji/0634c.svg` / `structure.children[1].children[0].children[1].children[0]` | Stroke shape, not a dictionary kanji. |
| ㇒ | U+31D2 | 2 | 澀 | `kanji/06f80.svg` / `structure.children[1].children[0].children[0].children[1]` | Stroke shape, not a dictionary kanji. |

### Kana

| Value | Code point(s) | Count | Examples | First source node | Finding |
| --- | --- | ---: | --- | --- | --- |
| つ | U+3064 | 29 | 労, 営, 図 | `kanji/052b4.svg` / `structure.children[0].children[0]` | Source explicitly uses this kana as original for ⺍; no dictionary meaning for that base. |
| コ | U+30B3 | 1 | 爨 | `kanji/07228.svg` / `structure.children[0].children[1].children[0]` | Kana shape in an IDS-like parent; no dictionary match. |
| ヒ | U+30D2 | 1 | 巓 | `kanji/05dd3.svg` / `structure.children[1].children[0].children[0].children[0]` | Source explicitly maps displayed 匕 to kana ヒ in 巓. Do not fall back to the displayed 匕 dictionary entry. |
| マ | U+30DE | 66 | 亂, 予, 令 | `kanji/04e82.svg` / `structure.children[0].children[0].children[1]` | Kana used as a structural shape; resemblance to a kanji is not semantic evidence. |

### Non-KANJIDIC2 ideographs

| Value | Code point(s) | Count | Examples | First source node | Finding |
| --- | --- | ---: | --- | --- | --- |
| 㐄 | U+3404 | 16 | 傑, 憐, 桀 | `kanji/05091.svg` / `structure.children[1].children[0].children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 㐫 | U+342B | 1 | 离 | `kanji/079bb.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㐭 | U+342D | 15 | 亶, 凛, 凜 | `kanji/04eb6.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㒸 | U+34B8 | 1 | 邃 | `kanji/09083.svg` / `structure.children[0].children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 㕚 | U+355A | 1 | 騷 | `kanji/09a37.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㕡 | U+3561 | 1 | 壑 | `kanji/058d1.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㡭 | U+386D | 2 | 斷, 繼 | `kanji/065b7.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㲋 | U+3C8B | 3 | 巉, 纔, 讒 | `kanji/05dc9.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 㳟 | U+3CDF | 4 | 暴, 曝, 瀑 | `kanji/066b4.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 䏍 | U+43CD | 6 | 態, 擺, 熊 | `kanji/0614b.svg` / `structure.children[0].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 䙳 | U+4673 | 1 | 樮 | `kanji/06a2e.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 䩗 | U+4A57 | 2 | 覇, 霸 | `kanji/08987.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 䩻 | U+4A7B | 1 | 羈 | `kanji/07f88.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 业 | U+4E1A | 27 | 並, 僕, 嘘 | `kanji/04e26.svg` / `structure.children[1]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 乡 | U+4E61 | 8 | 嚮, 壅, 擁 | `kanji/056ae.svg` / `structure.children[0].children[0].children[0]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 亚 | U+4E9A | 2 | 晋, 霊 | `kanji/0664b.svg` / `structure.children[0]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 亩 | U+4EA9 | 2 | 畆, 畝 | `kanji/07546.svg` / `structure.children[0]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 倠 | U+5020 | 3 | 膺, 軅, 雁 | `kanji/081ba.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 吅 | U+5405 | 2 | 単, 厳 | `kanji/05358.svg` / `structure.children[0]` | Explicit original for ⺍ in 単/厳; this base is absent from KANJIDIC2. |
| 堇 | U+5807 | 5 | 槿, 瑾, 覲 | `kanji/069ff.svg` / `structure.children[1]` | Useful named component (e.g. 槿), genuinely absent from this dictionary; do not substitute a containing kanji. |
| 夃 | U+5903 | 2 | 楹, 盈 | `kanji/06979.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 处 | U+5904 | 1 | 咎 | `kanji/0548e.svg` / `structure.children[0]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 夗 | U+5917 | 11 | 婉, 宛, 怨 | `kanji/05a49.svg` / `structure.children[1].children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 巂 | U+5DC2 | 1 | 攜 | `kanji/0651c.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 显 | U+663E | 1 | 顕 | `kanji/09855.svg` / `structure.children[0]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 歨 | U+6B68 | 1 | 徙 | `kanji/05f99.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 炏 | U+708F | 12 | 勞, 塋, 撈 | `kanji/052de.svg` / `structure.children[0].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 电 | U+7535 | 13 | 亀, 俺, 奄 | `kanji/04e80.svg` / `structure.children[1]` | Variant candidate: familiar simplified-looking form; Unicode normalization is not simplified/traditional conversion. No source original; no semantic substitution. |
| 遀 | U+9040 | 1 | 隨 | `kanji/096a8.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 駦 | U+99E6 | 1 | 騰 | `kanji/09a30.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 龰 | U+9FB0 | 46 | 促, 匙, 嚔 | `kanji/04fc3.svg` / `structure.children[1].children[1]` | Variant candidate: frequent foot-like component; no original or normalization mapping supplied. |
| 龶 | U+9FB6 | 44 | 倩, 債, 割 | `kanji/05029.svg` / `structure.children[1].children[0]` | Variant candidate: frequent component; no original or normalization mapping supplied. |
| 龷 | U+9FB7 | 3 | 戴, 横, 黄 | `kanji/06234.svg` / `structure.children[1].children[1].children[0]` | Variant candidate: component shape; no original or normalization mapping supplied. |
| 龹 | U+9FB9 | 1 | 騰 | `kanji/09a30.svg` / `structure.children[1].children[0]` | Variant candidate: component shape; no original or normalization mapping supplied. |
| 𠂇 | U+20087 | 1 | 友 | `kanji/053cb.svg` / `structure.children[0]` | Variant candidate: component in 友; no original or normalization mapping supplied. |
| 𠩺 | U+20A7A | 1 | 釐 | `kanji/091d0.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𠫯 | U+20AEF | 6 | 參, 慘, 滲 | `kanji/053c3.svg` / `structure.children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𡕰 | U+21570 | 1 | 鑁 | `kanji/09441.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𡰪 | U+21C2A | 19 | 僻, 劈, 壁 | `kanji/050fb.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𢆉 | U+22189 | 19 | 倖, 圉, 執 | `kanji/05016.svg` / `structure.children[1].children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𢆶 | U+221B6 | 10 | 斷, 濕, 繼 | `kanji/065b7.svg` / `structure.children[0].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𣬉 | U+23B09 | 3 | 篦, 蓖, 貔 | `kanji/07be6.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𣶒 | U+23D92 | 1 | 淵 | `kanji/06df5.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𤆍 | U+2418D | 1 | 爨 | `kanji/07228.svg` / `structure.children[1].children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𤍾 | U+2437E | 1 | 爨 | `kanji/07228.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𤕻 | U+2457B | 1 | 寤 | `kanji/05be4.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𤴡 | U+24D21 | 1 | 嚔 | `kanji/05694.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𥝢 | U+25762 | 2 | 藜, 黎 | `kanji/085dc.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𦍒 | U+26352 | 1 | 撻 | `kanji/064bb.svg` / `structure.children[1].children[0]` | Dictionary coverage gap; no original/normalization candidate. |
| 𦔮 | U+2652E | 1 | 輒 | `kanji/08f12.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𧘇 | U+27607 | 11 | 圜, 壌, 嬢 | `kanji/0571c.svg` / `structure.children[1].children[2]` | Variant candidate: clothing-like fragment; no original or normalization mapping supplied. |
| 𩾏 | U+29F8F | 1 | 鳳 | `kanji/09cf3.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𪪷 | U+2AAB7 | 1 | 彜 | `kanji/05f5c.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |
| 𬀷 | U+2C037 | 6 | 傷, 塲, 慯 | `kanji/050b7.svg` / `structure.children[1]` | Dictionary coverage gap; no original/normalization candidate. |

### Other structural/source labels

| Value | Code point(s) | Count | Examples | First source node | Finding |
| --- | --- | ---: | --- | --- | --- |
| ⺄ | U+2E84 | 1 | 虱 | `kanji/08671.svg` / `structure.children[0]` | Variant candidate: radical symbol; no local original or Unicode normalization link. Retain without guessed 乙 meaning. |

## Disposition

No counts were reduced artificially. In particular, do not map 龰 to 止, 龶 to 生,
⺄ to 乙, 𧘇 to 衣, or simplified-looking forms to a traditional kanji merely from
visual familiarity. Such choices would require additional authoritative mapping
information; they are not Unicode normalization operations established here.
巓's 匕→ヒ is an unusual explicit source annotation worth retaining for upstream
review, but overriding it with “spoon” would violate the supplied original.

Follow the
[rendering policy](rendering-policy.md) so unresolved/fragment/container nodes do
not obscure reachable descendants, and omit unavailable meanings. Any later
source-backed resolver change must include a targeted regression test and a new
before/after inventory; never edit the generated database by hand.
