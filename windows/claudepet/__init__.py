"""ClaudePet for Windows — a pixel cat that reacts to Claude Code and Claude Desktop.

Windows port of the macOS app in ../Sources/ClaudePet. The product logic (state
machine, event protocol, transcript tailing) is a faithful port; only the shell
(window, tray, IPC, file watching, autostart) is reimplemented for Windows.
"""

__version__ = "1.0.0"
