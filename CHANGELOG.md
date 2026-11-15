# Changelog

## 1.0.0

- New desktop app built on CustomTkinter: visual gradient editor with draggable stops, preset gallery (plus user presets), angle / radial / reverse, solid background, live preview, zoom.
- New GUI-free engine shared by the app, the CLI and the library, so preview and export can no longer diverge.
- Arbitrary angles, radial mode, cell-ratio correction; sRGB / linear / OKLab blending.
- Exports: ANSI truecolor / 256 / 16, Discord, HTML, SVG, PNG. New `ansifadegen` command-line tool.
- Fixes: colours are rounded instead of truncated; input that already contains ANSI codes is cleaned; wide characters and tabs use their real column width; blanks are no longer given colour codes (smaller output).
- Colours accept `#rgb`, `#rrggbb`, names and `R,G,B`; more built-in names.
- Preview of very large texts is much faster (a 300×80 text went from ~4.5 s to ~0.1 s).
- Test suite (pytest, including GUI tests) and CI.
