"""Refuse to rebuild the retracted metrics dashboard from dashboard_data.json."""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("generate_dashboard_html.py")), run_name="__main__")
