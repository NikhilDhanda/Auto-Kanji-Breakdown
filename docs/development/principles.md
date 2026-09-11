# Contributor principles

Build a focused kanji breakdown tool, not a general dictionary. Prefer simple,
predictable behavior and standard-library or Anki APIs over new dependencies.
Prioritize data correctness, user safety, compatibility and licensing before
performance, convenience or visual polish. Discuss unrelated features separately.

## Data and rendering

KANJIDIC2 supplies meanings/readings/strokes/frequency; KanjiVG supplies structure.
Respect original/base mappings and distinct radical conventions, including nested
and root radicals. Never guess meanings, missing frequency or visual decomposition.
Use database membership for supplementary-plane coverage. Preserve raw source
structure and source provenance. Do not manually edit archives or generated records.
The deterministic shared builder is used by tooling and the optional desktop updater;
normal note processing never parses source archives. Keep the bundled database
available for a clean checkout and offline fallback.

Keep versioned structured payloads through the full pipeline. Never parse English
labels as a protocol or embed raw JSON in HTML attributes. Escape serialized data,
use textContent for source strings and scope CSS to owned renderer containers.
Hide unavailable optional data; preserve full main meanings and reachable descendants.
Schema changes require coordinated builder, validator, loader, renderer, tests and
documentation changes. See [rendering policy](rendering-policy.md).

## Collection safety and compatibility

Support arbitrary note types and fields. Validate configuration and field identity
before writing; finish generation before assigning output. Preserve unrelated data.
Respect owned template/field boundaries and cleanup refusal checks. Do not bypass
public APIs with raw SQL, legacy note.flush or explicit collection saves.
Use supported hooks with verified signatures, Anki collection operations and undo.
Keep expensive work off the GUI thread, cache validated lookups and provide useful
progress/cancellation for bulk work. Avoid post-save rescans, duplicate writes and
hidden background services. Runtime must support Python 3.9.

Normal generation/review stays local; the optional official-source updater is the
only network feature. Never upload note contents or add telemetry, advertising,
tracking or external services without an explicit project decision. Logs must not
expose private content. Surface understandable errors and report partial work honestly.

## Testing and distribution

Use disposable collections and synthetic examples. Add meaningful regression tests
for data merging, original mappings, radicals, supplementary kanji, absent data,
serialization, invalid configuration, hooks, ownership, undo and cancellation.
Do not weaken compatibility guards just to pass tests. Keep tests/build tools public,
but exclude archives, environments, caches, personal files and tests from packages.
Build deterministically and preserve all attribution and separate software/data
licences. Review clean install, upgrade, edits, regeneration, cleanup and malformed
inputs before release. See [testing](testing.md) and [releasing](releasing.md).

Keep code readable and changes focused. Update user and developer documentation
when behavior changes; essential knowledge must not depend on local agent instructions.
