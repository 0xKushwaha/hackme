"""
Persona Grouping — Red Mode Tournament Architecture
=====================================================
Groups 20 personas into trait-based clusters for the hierarchical debate.

Stage A: Each group runs a panel debate (1 LLM call per group).
         The LLM role-plays all members and identifies the strongest position.
Stage B: One champion per group enters the cross-debate.

Groups are curated by expertise overlap — personas within a group share
enough background to have a productive internal debate, while groups
themselves cover maximally different perspectives.
"""
from __future__ import annotations

import re
from typing import Optional


# ── Trait-based groups (curated from personas_index.json expertise tags) ──

TRAIT_GROUPS: dict[str, dict] = {
    "theory": {
        "label": "Deep Learning Theory",
        "members": [
            "andrej_karpathy", "geoffrey_hinton", "yann_lecun",
            "francois_chollet", "sebastian_raschka",
        ],
    },
    "systems": {
        "label": "ML Systems & Infrastructure",
        "members": [
            "chip_huyen", "edward_yang", "matei_zaharia",
            "vicki_boykis", "tim_dettmers",
        ],
    },
    "applied": {
        "label": "Applied ML & Education",
        "members": [
            "andrew_ng", "jeremy_howard", "santiago_valdarrama",
            "jonas_mueller", "jay_alammar",
        ],
    },
    "strategy": {
        "label": "Strategy, Safety & Reliability",
        "members": [
            "sam_altman", "ethan_mollick", "chris_olah",
            "lilian_weng", "shreya_rajpal",
        ],
    },
}

# Flat lookup: persona_handle → group_key
_PERSONA_TO_GROUP: dict[str, str] = {}
for _gk, _gv in TRAIT_GROUPS.items():
    for _m in _gv["members"]:
        _PERSONA_TO_GROUP[_m] = _gk


def group_personas(names: list[str]) -> dict[str, list[str]]:
    """
    Assign selected persona names into trait groups.

    If fewer than 20 are selected, only groups with ≥1 member are returned.
    Unknown handles (not in TRAIT_GROUPS) go into a catch-all "misc" group.
    """
    groups: dict[str, list[str]] = {}

    for name in names:
        gk = _PERSONA_TO_GROUP.get(name, "misc")
        groups.setdefault(gk, []).append(name)

    return groups


def group_label(group_key: str) -> str:
    """Human-readable label for a group key."""
    meta = TRAIT_GROUPS.get(group_key)
    if meta:
        return meta["label"]
    return group_key.replace("_", " ").title()


# ── Champion election ─────────────────────────────────────────────────

_STRONGEST_RE = re.compile(
    r"STRONGEST\s+POSITION\s*:\s*\[?\s*([A-Za-z_\s]+?)\s*\]?$",
    re.IGNORECASE | re.MULTILINE,
)


def elect_champion(
    panel_output: str,
    group_members: list[str],
) -> str:
    """
    Extract the champion from a panel debate output.

    Strategy (in priority order):
      1. Parse the "STRONGEST POSITION: [name]" line the LLM was asked to emit.
      2. Fall back to the persona mentioned most often in the output.
      3. Fall back to the first member in the group.
    """
    # 1. Explicit marker
    m = _STRONGEST_RE.search(panel_output)
    if m:
        raw = m.group(1).strip().lower().replace(" ", "_")
        # Fuzzy match against group members
        for member in group_members:
            if raw in member or member in raw:
                return member

    # 2. Mention frequency — count how often each member's name appears
    #    outside of their own header section
    best, best_count = group_members[0], 0
    for member in group_members:
        display = member.replace("_", " ").lower()
        count = panel_output.lower().count(display)
        if count > best_count:
            best, best_count = member, count

    return best
