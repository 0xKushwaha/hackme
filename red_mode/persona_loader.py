"""
Persona Loader — Red Mode
=========================
Loads persona .md files from the personas/ directory as system prompts.
Each .md file IS the system prompt for that persona agent.
"""
from __future__ import annotations

import json
from pathlib import Path

PERSONAS_DIR = Path(__file__).parent.parent / "personas"
INDEX_PATH   = PERSONAS_DIR / "personas_index.json"


def get_index() -> list[dict]:
    """Return the full personas index (all 20 personas with metadata)."""
    with open(INDEX_PATH, "r") as f:
        data = json.load(f)
    return data["personas"]


def load_persona(name: str) -> str:
    """
    Load a single persona's system prompt by handle name.
    e.g. load_persona("andrej_karpathy")
    """
    path = PERSONAS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_personas(names: list[str]) -> dict[str, str]:
    """
    Load multiple personas by handle name.
    Returns: {handle_name: system_prompt_text}
    """
    return {name: load_persona(name) for name in names}


def list_available() -> list[str]:
    """Return handles for all extracted personas."""
    idx = get_index()
    return [p["name"].lower().replace(" ", "_").replace("ç", "c").replace("ö", "o")
            for p in idx if p.get("status") == "extracted"]


def persona_display_name(handle: str) -> str:
    """Convert handle to display name. e.g. andrej_karpathy → Andrej Karpathy"""
    return handle.replace("_", " ").title()
