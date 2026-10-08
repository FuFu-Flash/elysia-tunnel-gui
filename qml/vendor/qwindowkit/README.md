# QWindowKit example caption controls

This directory vendors the QML example caption button from [QWindowKit](https://github.com/stdware/qwindowkit) at commit `7416119514962562e1e3ed131f2a5f4e1d9e7426`, together with the four window-control SVGs in `assets/window-controls`. The upstream native C++ framework is not included.

The original files are used under the Apache License 2.0. See `LICENSE` and `provenance.json` for the full license, pinned source URLs and original file hashes. Changes made for Elysia Tunnel must be identified in the modified files.

`ElysiaWindowButton.qml` extends the unchanged upstream `QWKButton` with theme,
focus, tooltip, translation and ripple handling. The source SVGs remain unchanged;
96 px transparent ink/white PNG variants in `assets/window-controls` are rendered
at build time by `packaging/rasterize_window_icons.py`. This avoids an SVG image plugin
or an additional render effect at runtime while retaining the upstream geometry.
