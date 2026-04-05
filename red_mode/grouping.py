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

# Matches: ## Champion: [andrej_karpathy] or ## Champion: [Andrej Karpathy]
_CHAMPION_RE = re.compile(
    r"##\s*Champion\s*:\s*\[([A-Za-z_\s]+?)\]",
    re.IGNORECASE,
)


def _fuzzy_match(raw: str, group_members: list[str]) -> Optional[str]:
    """Match a raw name string against group member handles."""
    raw_norm = raw.strip().lower().replace(" ", "_")
    # Exact match first
    for member in group_members:
        if raw_norm == member:
            return member
    # Substring match
    for member in group_members:
        if raw_norm in member or member in raw_norm:
            return member
    # Last name match (e.g. "karpathy" → "andrej_karpathy")
    for member in group_members:
        parts = member.split("_")
        if any(p in raw_norm for p in parts):
            return member
    return None


def elect_champion_from_election(
    election_output: str,
    group_members:   list[str],
) -> str:
    """
    Extract the champion from an election LLM output.

    The election prompt asks the LLM to output:
      ## Champion: [{exact_handle}]

    Strategy (in priority order):
      1. Parse the "## Champion: [name]" line.
      2. Fall back to mention frequency in the election output.
      3. Fall back to the first group member.
    """
    # 1. Explicit ## Champion: [name] marker
    m = _CHAMPION_RE.search(election_output)
    if m:
        matched = _fuzzy_match(m.group(1), group_members)
        if matched:
            return matched

    # 2. Mention frequency
    best, best_count = group_members[0], 0
    for member in group_members:
        display = member.replace("_", " ").lower()
        count   = election_output.lower().count(display)
        if count > best_count:
            best, best_count = member, count

    return best
