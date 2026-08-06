"""PyInstaller entry point.

`python -m claudepet` runs claudepet/__main__.py *as part of* the package, so its
relative imports resolve. PyInstaller instead executes the entry script as a
top-level module with no parent package, which makes those same relative imports
fail. This launcher gives it something to run that imports the package by name.
"""

from __future__ import annotations

import sys

from claudepet.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
