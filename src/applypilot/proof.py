"""Thin wrapper — real code lives in ~/Projects/LuckyDucky/proof.py"""
import sys
from pathlib import Path

_ld = Path.home() / "Projects" / "LuckyDucky"
if str(_ld) not in sys.path:
    sys.path.insert(0, str(_ld))

from proof import list_proofs, show_proof_list, show_proof_detail, show_proof_full  # noqa: F401, E402
