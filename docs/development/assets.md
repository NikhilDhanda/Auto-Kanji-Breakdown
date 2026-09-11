# Documentation assets

Only reviewed documentation visuals belong here. Keep raw recordings, browser-test
captures and one-off scripts local. Use synthetic examples, avoid private study
content/account details, inspect every frame and check identifying metadata.
Preserve data attribution on pages displaying dictionary/structure previews.

| Asset | Content and provenance |
| --- | --- |
| breakdown-expanded.png | Browser preview of synthetic 磨 in Blue, from tools/preview_renderer.py. Not a device capture. |
| setup.png | Original maintainer PNG of desktop Settings, with an existing Core 2000 configuration. Field names are illustrative; Matcha and the existing output field are saved choices. No note contents or account details are shown. |
| mobile.jpg | Original maintainer JPEG of expanded 喝采 on mobile. Exact client, OS, package version and offline state were not supplied. |
| themes.gif | Eight labelled browser previews of collapsed synthetic 日常生活, three seconds each. Not device captures. |

## Reproducing the theme animation

Use the current database with Database, extract, build_payload and serialize,
then html_block and css_block from src/akb/templates.py, as in the preview tool.
Render 日常生活 in each THEME_LABELS palette without opening components. Add a
small neutral theme label outside the renderer, wait for local fonts, and capture
the 600 × 636 preview in headless Edge/Chromium with Playwright. Assemble frames
with Pillow, 3,000 ms per frame, loop 0 and disposal 2. These are development tools,
not package dependencies. No collection or runtime modification is needed.

Order: Light, Dark, Blue, Brown, Matcha, Matcha Dark, Sakura, Sakura Dark.
The included animation is 207,630 bytes, generated 2026-09-11. All eight frames
were reviewed. Keep intermediate captures/scripts outside the public candidate.

## Future recordings

A short desktop Anki interaction GIF could replace the static hero. Use a disposable
profile and synthetic card, begin collapsed, expand one branch and return to the
start. A setup recording can show field selection, recommended defaults, Back,
Review changes and Apply. Record package hash, client/OS and date. Do not embed
planned assets until they exist or describe browser previews as real device tests.

[Data attribution](../ATTRIBUTION.md) · [Third-party notices](../../THIRD_PARTY_LICENSES.md)
