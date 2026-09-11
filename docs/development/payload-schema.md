# Generated note field schema v1

The canonical field value is compact deterministic JSON text:

```json
{"entries":[{"char":"人","frequency":5,"meanings":["person"],"radical":"general","readings":{"kun":["ひと","-り","-と"],"on":["ジン","ニン"]},"strokes":2}],"version":1}
```

An ordered entries array supplies first-appearance order without a redundant chars
array or map keys repeating each main character. `version` versions the payload,
independently of master database schema/version. Every entry is unique by char.
There is exactly one serialized representation, no labels protocol, HTML attribute,
human-readable fallback, script or styling. No supported kanji means **empty string**,
not an empty payload. `deserialize()` checks the envelope/version for development;
the future card renderer must validate untrusted synced field data before rendering.

Main records contain `char`, full `meanings`, and `readings.on/kun`, with original
KANJIDIC2 values. Optional `strokes`, `frequency`, root `radical="general"`, and
`children` are included only when available. The main structural root is implicit
in the main record; its character and meanings are not duplicated in a second tree.

Visible component nodes contain `char`, full resolved meanings when available,
`base` only when different from char, optional raw `position`, `variant: true`,
`phon`, `radical="general"`, and ordered `children`. Phon is a source phonetic label,
not an asserted reading; it is retained for later optional display. Other radical
conventions are excluded from ordinary display payloads, retained in the master.
No optional value is replaced with null, a dash or an English UI label.

Meanings are resolved through the occurrence's explicit base, otherwise char.
There is no fallback from an unresolved explicit base, guessed semantic mapping,
or additional dictionary record inclusion. Components need meanings, not duplicate
full readings/frequency/decomposition records. Repeated structural occurrences can
repeat short meaning arrays; their actual nested positions are distinct. The payload
contains only the source kanji and its displayed component tree. It needs no master
database, add-on or network to be consumed on another synced client.

## Structural projection

Unnamed, multi-character CDP/IDS, `part` and `partial=true` nodes are transparent.
Their descendants remain in source order under the nearest visible ancestor, and
their own complete-kanji tile/meaning is suppressed. Leaf fragments disappear.
The master tree, including all part metadata, is never modified. No synthetic
complete component is formed by combining equal fragment labels.

Promoted children optionally carry `via`, an ordered list of hidden-ancestor
contexts. Each context retains available `position`, `part`, `number` and general
`radical`; it is **not** a visible component. A child's own position remains relative
to its original siblings. A `via` radical is not the child's radical and must not
highlight the child as a complete radical. No empty context object is included.
For example a 人 under an unnamed top group can have `position:"left"` and
`via:[{"position":"top"}]`. This preserves the distinction without a blank node.
Hidden groups without context metadata leave no wrapper; spatial geometry is not
available or inferred. Hidden leaf radical fragments have no visible tile to highlight.

This follows [rendering policy](rendering-policy.md). Payload generation does not shorten glosses or remove
boilerplate: all available component meanings are retained for the renderer to
select useful glosses. Full main meanings
remain available independently.

## Serialization and field safety

Keys sort lexically, arrays preserve semantic order, separators are compact, and
there is no trailing newline. Japanese characters remain literal UTF-8. `<`, `>`
and `&` inside strings are encoded as JSON escapes `\u003c`, `\u003e`, `\u0026`,
so a dictionary string cannot become HTML or an HTML entity in Anki's field.
Quotes remain JSON quotes in text, never attribute delimiters. This single JSON
representation can be read with JSON.parse(container.textContent) by the future
renderer. Use DOM text APIs to display decoded strings; do not inject them as HTML.

The unrendered field displays JSON until a later renderer consumes it. It is a
machine-owned cache; users should not edit or format it in the rich-text editor.
Automatic refresh restores canonical bytes when the note next serializes through
the supported Python hook. Incoming sync preserves the received payload as normal
field data; the desktop hook is not a sync callback.


## Optional source provenance

Version 1 also accepts optional envelope metadata, once for the entire area:

```json
"provenance":{"kd":"2026-09-10","vg":"r20250816","db":"cf90012dabe9"}
```

`kd` is the actual KANJIDIC2 XML snapshot date, `vg` the KanjiVG stable release tag,
and `db` the first 12 database SHA-256 characters. Full hashes, manifests and legal
text are excluded. Legacy payloads without this property remain valid, safe to
regenerate and renderable. No existing notes are rewritten just to add provenance.
Renderer 3 uses this metadata in its offline Sources panel; unavailable legacy
metadata is explicitly labelled rather than inferred from the currently installed DB.
