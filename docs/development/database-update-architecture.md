# Desktop source-data updates

The software version remains 0.9.0-beta.1. Normal generation and review work
offline. The explicitly approved background updater is the only runtime path
that downloads and parses upstream archives; it does not run during note lookup
or card rendering. Source parsing is shared with build tooling and confined to this update path.

## Shared implementation

`src/akb/build_data.py` owns parsing, merge semantics, deterministic encoding and
full database validation. `tools/build_database.py` is its development CLI.
There is no parallel dictionary implementation. Both support Python 3.9 and use
the standard library. Original/base mappings, raw structure, meanings, readings
and frequency semantics remain unchanged. Unknown structural attributes and
unexpected header fields fail closed rather than inventing interpretations.

`updater.py` receives only a Store, HTTP transport and clock. `update_service.py`
uses Anki's `QueryOp.without_collection()` to run it without a Collection object
or progress modal. Success callbacks return to the main thread. Updated entries
are adopted between active setup/regeneration operations. Note save, manual
generation and subsequent session preparation use the new immutable entry snapshot.
No updater calls a note mutation, collection scan, template update or bulk command.

## Scheduling and network

The desktop add-on preference `auto_data_updates` defaults to true when absent.
Explicit false is preserved. It is saved immediately by Setup or Status, outside
collection configuration, and does not sync. Changing it preserves mappings and
unrelated add-on settings. Disabling checks does not cancel an already running job.

After session database preparation, an enabled updater examines persisted state
in its worker. A successful check defers another automatic check for 28 days.
Failures retain the working database and allow retry in a later session after at
least 24 hours. Nothing polls continuously or requests the network every startup.
Status's **Check for database updates now** uses the same worker, bypassing time
and preference gates. An in-process lock prevents concurrent checks/cleanup.
Running multiple Anki processes against the same add-on directory is not supported.

Sources are fixed to:

- [Official KANJIDIC2 gzip](https://www.edrdg.org/kanjidic/kanjidic2.xml.gz).
- [Official KanjiVG releases API](https://api.github.com/repos/KanjiVG/kanjivg/releases?per_page=100).
  Among the returned releases choose the latest published stable release, ignoring
  drafts/prereleases, and require exactly `kanjivg-YYYYMMDD-main.zip` matching its tag.
  There is no fallback to all/stripped archives or maintainer-built databases.

ETag and Last-Modified validators are cached when present. Conditional requests
reuse only hash-verified cached bodies; a 304 without valid cached bytes fails.
Absent validators simply mean a normal download and SHA-256 comparison. Every
download, including release metadata, is hashed. Only changed source identities
cause a rebuild. A rolling gzip/header change can change identity even when most
dictionary entries remain identical.

HTTPS is mandatory. Initial URLs and redirects are limited to official EDRDG,
GitHub and GitHub release-asset hosts. Requests identify Auto Kanji Breakdown,
use a 15-second socket timeout and a 120-second streaming-body deadline. Limits:
KANJIDIC2 compressed 16 MiB, KanjiVG compressed 64 MiB, release JSON 4 MiB;
uncompressed XML 128 MiB; ZIP 30,000 entries/256 MiB total/2 MiB per member.
Current legitimate archives are about 1.5 MB and 12.6 MB. ZIP traversal, duplicate
members and symbolic links are rejected. Nothing is extracted or executed. XML
entity declarations, NUL encodings and excessive nesting/node counts are rejected;
external DTDs are never fetched. Temporary downloads are removed on completion/failure.

No note text, mappings, study history, identifiers, telemetry or analytics are sent.
Servers necessarily receive ordinary connection information such as IP address,
User-Agent and cache headers. Normal Anki sync is separate. Sources panel text is
offline; its external links use the network only if the user chooses to open them.

## Storage and atomic selection

```text
<installed add-on>/data/kanji_db.json          immutable bundled fallback
<installed add-on>/data/manifest.json          matching baseline manifest
<installed add-on>/user_files/akb_updates/
  owner.json                                 namespace ownership marker
  current.json                               atomic generation selection
  update_state.json                          check/failure/cache diagnostics
  database/<full DB SHA-256>/
    kanji_db.json
    manifest.json
  sources/<source or response SHA-256>         conditional HTTP body cache
```

Local update paths must stay in the owned namespace. Selected database files are
bounded to 64 MiB and metadata files to 256 KiB before reading.

The candidate must parse, pass full schema validation and coverage checks, and
match its manifest hash before staging. A loss of over 10% of dictionary entries
or 20% of structures is rejected for investigation. A complete pair is staged
in a new directory, then `current.json` is atomically replaced as the final commit
point. Before that point, any exception leaves the old selection unchanged.
This avoids exposing a half-written two-file pair. State is written first and
restored on a failed commit; a process crash may leave diagnostic state ahead of
the pointer, but the validated pointer remains authoritative. No collection undo
is involved. Atomic rename protects selection, not arbitrary hardware failure.

The next check removes obsolete known cache files/generation pairs; no backup
history is maintained. An interrupted candidate can remain until that check.
Unknown files are not pruned. Runtime prefers a hash/schema-validated selected
pair; absent, malformed, incomplete or incompatible updated data falls back to
the bundled pair. The bundled master is never overwritten by this updater.

Anki preserves `user_files` during add-on upgrades; it is excluded from the package.
Do not rely on it surviving add-on deletion/uninstallation. Full cleanup offers
an unchecked option to disable checks and remove only this marked namespace,
across all note types/profiles using that installation. Unrelated `user_files`
are preserved. This filesystem deletion is not undoable; collection cleanup
retains its existing undo and ownership rules. Other cleanup modes do not remove it.

## Provenance, diagnostics and existing notes

Manifest version 1 and builder compatibility 1 are independent of database schema
1, payload 1, collection config 2 and renderer 6. Manifests record full DB/source
hashes, KANJIDIC2 XML header snapshot, optional retrieval date/HTTP validators and
KanjiVG release. Retrieval date is not an official dictionary version. The refreshed baseline
was retrieved on 2026-09-10; unknown retrieval dates remain null.

Payload v1 gains optional `provenance: {kd, vg, db}` once per breakdown area:
XML snapshot date, stable release tag and first 12 DB hash characters. No full
hashes/legal documents are duplicated into notes. Legacy payloads remain valid.
New/edited/explicitly regenerated notes use current data. Updating the database
does not rewrite existing notes or cause a collection-wide sync.

The current renderer includes one collapsed **ⓘ** control per area, with inline offline
attribution, licence links and actual payload provenance. Legacy data gets an
explicit unavailable-details sentence. Keyboard Enter/Space, touch, propagation
isolation and all eight palettes are covered by browser tests. Reapply Settings or
use theme Apply to install renderer 6 into existing owned templates. Regeneration
alone does not update templates; source updates never do so automatically.

Status displays bundled/updated/failure state, snapshot/release, hashes, check and
update times, failed stage/HTTP status and session outcome. Reopen Status to refresh
the displayed diagnostic snapshot. No-change/offline/failure outcomes show no modal.
An actual successful update displays a tooltip explaining optional regeneration.

Future upstream format changes cannot be guaranteed compatible. A rejected build
must retain the working database until a reviewed software/parser update is available.

References: [Anki background operations](https://addon-docs.ankiweb.net/background-ops.html),
[Anki user_files configuration](https://addon-docs.ankiweb.net/addon-config.html).
