#!/usr/bin/env python3
"""Repo-checkout entry point for pil.export_html.

Delegates to the installed `pil` package when available, otherwise to the
repo's src/ layout. Keeps `bin/` working without a pip install.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from pil.export_html import main
except ImportError:
    sys.path.insert(0, os.path.join(_HERE, "..", "src"))
    from pil.export_html import main

if __name__ == "__main__":
    main()
