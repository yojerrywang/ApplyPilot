"""Thin wrapper — real code lives in ~/Projects/LuckyDucky/bridge.py"""
import sys
from pathlib import Path

# Add LuckyDucky to path so imports work
_ld = Path.home() / "Projects" / "LuckyDucky"
if str(_ld) not in sys.path:
    sys.path.insert(0, str(_ld))

from bridge import ResumeMatcher, run_bridge, _resume_to_text  # noqa: F401, E402
