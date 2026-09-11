# Hero showcase asset

`hero-grid.png`, created 2026-09-11, is the README hero.

| Position | Kanji | Theme |
| --- | --- | --- |
| Top left | 動 | Blue |
| Top right | 秘 | Matcha |
| Bottom left | 麻 | Sakura |
| Bottom right | 酔 | Brown |

Generated from the bundled database using Database, build_payload, serialize,
html_block and css_block, following tools/preview_renderer.py. Playwright with
headless Edge captured actual .akb-card elements at 2× pixel density after fonts
loaded and each main toggle was clicked once. Nested branches remain collapsed.
The documentation wrapper fixes equal panel widths/heights and a neutral surround;
no card typography, colors, content or renderer code was changed. Pillow places
the four captures on a 2×2 canvas with 24-pixel gutters and outer padding.
No AI generation or drawn UI was used. Intermediate files are local in
artifacts/hero-grid/. The finished PNG is the only new image distributed in docs.

The previous breakdown-expanded.png is retained as a useful deeper-tree example.
[Contributor asset guide](../development/assets.md) · [Attribution](../ATTRIBUTION.md)
