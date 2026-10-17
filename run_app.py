"""PyInstaller entry point for the native desktop application."""

import os
import sys

if getattr(sys, "frozen", False):
    # Apps launched from Finder may not inherit the shell's locale environment.
    os.environ.setdefault("LANG", "en_US.UTF-8")

from app.__main__ import main

if __name__ == "__main__":
    main()
