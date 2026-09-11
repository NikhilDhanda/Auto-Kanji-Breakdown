# Release process

The current candidate version is defined only in root `VERSION`. Examples below
use the initial beta candidate; update VERSION for later releases. Software version
is independent of master schema 1, payload 1, config 2 and renderer 6.

## Package and version

Run from the repository root:

```sh
python -m tools.build_addon
python -m tools.build_addon --output dist/repeat.ankiaddon
python -m tools.build_addon --validate dist/Auto-Kanji-Breakdown-0.9.0-beta.1.ankiaddon
```

`tools/build_addon.py` uses only the standard library and existing validators.
It reads the explicit `RUNTIME` and `LEGAL` allowlists, validates clean empty
configuration, checks common credential/path patterns, validates upstream notice
hashes, and runs both master/runtime database validators. Runtime byte content is
copied unchanged. Tests ensure the allowlist covers all current runtime source.
New runtime files require an intentional allowlist update.

The archive root contains `__init__.py`, `akb/`, `config.json`, generated
`manifest.json`, `VERSION`, `data/kanji_db.json`, `data/manifest.json`, LICENSE, AUTHORS,
THIRD_PARTY_LICENSES.md and licenses/. It never wraps them in `src/`.
The runtime default in `src/akb/database.py` resolves to that bundled data path.

Anki's [official sharing instructions](https://addon-docs.ankiweb.net/sharing.html)
require `package` and `name` for distribution outside AnkiWeb. The generated
manifest uses `package: auto_kanji_breakdown` and `name: Auto Kanji Breakdown`.
No speculative version field, timestamp, compatibility bound, or conflict ID is
invented. The release identifier is in VERSION and the filename. `meta.json` is
Anki-generated user metadata and is not shipped. `config.json` is the separate,
empty runtime fallback configuration.

ZIP entries are sorted, stored without compression, timestamped 1980-01-01, and
use fixed Unix regular-file permissions. No comments, extra fields or host paths
are stored. ZIP_STORED avoids zlib-version-dependent compressed output; this package
is small enough that the reproducibility benefit outweighs compression savings.
`.gitattributes` preserves checked-in bytes without newline conversion. All build
inputs are local. There is no runtime import/execution during assembly.

The temporary archive is validated before replacing the destination. Validation
rejects unexpected/missing/duplicate entries, checks CRCs and fixed metadata, and
compares every entry with intended inputs, including the master database. Secret
pattern checks supplement an explicit allowlist and human review; they are not a
guarantee that arbitrary text is free of sensitive content.

## Tests and dependencies

Use isolated development environments, never a personal collection. The development environment
may use Python 3.10+; release runtime checks also run under actual Python 3.9.
Known test combinations: `anki==25.2` with Python 3.9.13 and `anki==26.8.1` with
Python 3.10.10, plus PyQt6 6.6.1 / Qt 6.6.2 for offscreen widget tests.
Install these only in development environments; do not bundle their wheels.

```sh
python -m pip install anki==25.2 PyQt6==6.6.1 PyQt6-Qt6==6.6.2
python -m unittest discover -s tests -v
node tests/test_renderer.js
python -m tools.preview_renderer artifacts/preview.html
node tests/test_renderer_browser.js artifacts/preview.html artifacts/browser /path/to/chromium
```

For the second backend use anki==26.8.1 in its separate Python 3.10 environment.
Set QT_QPA_PLATFORM=offscreen for unattended widget tests. Browser tests use
Playwright (development only; `npm install --no-save playwright` in a separate
tooling directory) and Edge/Chromium. Record actual versions and skipped tests in
the release report. The Python suite includes database, packaging and 3.9 static
compatibility tests. Full source/database tests need the local upstream archives.

## Release sequence (manual publication)

1. Review the diff and Git candidate files, credentials, paths, screenshots and
   licences. Ensure ignored material is not tracked. Resolve the review gates in
   [release tests](testing.md).
2. Run all Python tests with real backends/Qt, JS tests and browser tests.
3. Check upstream data/licensing for each release. If needed acquire source
   archives separately, preserve their hashes, build twice and compare outputs.
   Do not silently substitute newer input for an old snapshot. If data is unchanged,
   revalidate the committed master without rewriting it.
4. Build twice, compare full archive SHA-256 values, validate the final archive and
   retain the printed inventory/checksums in release notes outside the package.
5. Install the exact archive in a clean disposable Anki profile. Verify startup,
   loader, package name, config defaults and no dependency on the source checkout.
6. Execute [release tests](testing.md).
   Include uninstall/reinstall and upgrading an existing private installation.
7. Once approved, manually commit and tag the reviewed source version. Nothing in
   the builder stages, commits, tags, pushes or contacts GitHub.
8. Manually create a GitHub Release and attach the approved `.ankiaddon` and its
   SHA-256. Release artifacts belong in Releases, never Git history.
9. Collect private/public beta feedback and resolve release blockers.
10. Later, upload the approved build to AnkiWeb after reviewing current limits and
    assigning the real AnkiWeb ID. AnkiWeb uses its own installation folder identity;
    do not invent a conflict ID. Test transition from the private package to that
    numeric ID so both copies cannot run simultaneously.

## Publication review gates

- Clean-profile installation of this exact archive has not yet been manually run.
- Preserve all source snapshots privately/off-Git for exact reproduction; the live
  EDRDG file is rolling and may not reproduce this historical database.
- Test the offline Sources panel on actual mobile clients after upgrading owned
  templates; retain desktop local notices and the separate AGPL/CC declarations.
  Confirm corresponding source/build instructions are available with distribution.
- Record exact mobile, Yomitan and AnkiConnect versions and offline tests.
- The reported expanded-card scrolling lag still needs testing inside Anki.
- Record confirmed user observations and unresolved platform limits in the README.
