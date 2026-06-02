"""Portföy state yükle/kaydet (JSON).

GERÇEK state (portfoy_state.json) gerçek lot+TL içerir → KİŞİSEL, git-ignore edilir.
Commit edilen yalnızca portfoy_state.example.json şablonudur (.env/.env.example deseni).
"""
from __future__ import annotations

import json
from pathlib import Path

from ballast.utils.config import ROOT_DIR

STATE_PATH = ROOT_DIR / "ballast" / "portfolio" / "portfoy_state.json"
EXAMPLE_PATH = ROOT_DIR / "ballast" / "portfolio" / "portfoy_state.example.json"


def load_state(path: Path = STATE_PATH) -> dict:
    """State JSON'u yükler. Gerçek state yoksa FileNotFoundError yükseltir."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    """State'i JSON olarak yazar (UTF-8, 2-boşluk girintili)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
