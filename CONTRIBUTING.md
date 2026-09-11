# Contributing

Thanks for helping make kanji breakdowns useful and reliable for Japanese learners.
Keep proposals focused, and discuss larger changes before implementing them.

## Report a bug or suggest an improvement

Use the issue forms when you have access to the repository. While it is private,
non-collaborators should use the maintainer's beta feedback channel.
Include the add-on version, Anki/OS versions, steps, expected and actual results,
and relevant sanitized Status & Diagnostics information. Mention other add-ons.
Use synthetic notes; never upload your collection, credentials or private study data.

For features, explain the learning problem and current workaround. Screenshots
are helpful for UI issues after checking them for private content.

## Report data or decomposition issues

Include the exact character, the displayed structure/meaning, what seems wrong and
a reliable reference. KANJIDIC2 is the dictionary authority and KanjiVG supplies
structure. Avoid manual semantic guesses or individual-kanji patches solely to
make a tree look nicer. Reproduce the issue before changing normalization.
No future decomposition algorithm is promised by this beta.

## Development

Read [contributor principles](docs/development/principles.md) and the [developer documentation index](docs/development/README.md).
Use a virtual environment and disposable Anki test collections. Runtime must remain
compatible with Python 3.9; no test tooling should ship to users.

The included generated database is sufficient to build an add-on:

```sh
python -m tools.build_addon
```

For full tests, acquire the unchanged upstream archives separately in ignored
`data_sources/`. Do not commit those archives, local environments, collection files,
recordings under artifacts/, caches or packaged .ankiaddon files. Never manually
edit generated database records. Follow [building the database](docs/development/building-database.md)
for reproducible regeneration and [releasing](docs/development/releasing.md) for dependencies.

```sh
python -m unittest discover -s tests -v
node tests/test_renderer.js
python -m tools.preview_renderer artifacts/preview.html
node tests/test_renderer_browser.js artifacts/preview.html artifacts/browser /path/to/chromium
```

Use the documented Python/Anki environments with real backends and PyQt; skipped
optional tests do not count as release verification. Playwright and Chromium are
development tools only. Create artifacts/ if needed, and set QT_QPA_PLATFORM=offscreen
for unattended Qt checks. Add tests for meaningful behavior and regressions.

## Pull requests and licensing

Explain the problem, resulting behavior and relevant tests. Include screenshots for
visual changes and compatibility/data considerations. Avoid unrelated rewrites.

Original software contributions are expected under **AGPL-3.0-or-later**. You must
have the right to contribute them. Preserve copyright/attribution and the separate
KANJIDIC2/KanjiVG/CC BY-SA data terms; do not relicense source datasets as software.
See [third-party notices](THIRD_PARTY_LICENSES.md). No new contributor agreement is
introduced here. Do not include secrets or personal notes in tests or commits.
