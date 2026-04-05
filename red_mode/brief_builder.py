"""
Brief Builder — Red Mode
========================
Compresses pipeline output (or a raw dataset scan) into a structured
analysis brief that all persona agents will debate.

Two modes:
  1. pipeline_result  — uses agent_results from a completed Phase 1 run
  2. dataset_only     — scans the dataset directly (standalone mode)
"""
from __future__ import annotations

import json
import os
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────
# Mode 1: From Phase 1 pipeline result
# ─────────────────────────────────────────────────────────────────────

AGENT_ORDER = [
    "explorer", "skeptic", "statistician", "ethicist",
    "feature_engineer", "pragmatist", "devil_advocate",
    "optimizer", "architect",
]

AGENT_LABELS = {
    "explorer":         "Data Explorer",
    "skeptic":          "Skeptic",
    "statistician":     "Statistician",
    "ethicist":         "Ethicist",
    "feature_engineer": "Feature Engineer",
    "pragmatist":       "Pragmatist",
    "devil_advocate":   "Devil's Advocate",
    "optimizer":        "Optimizer",
    "architect":        "Architect",
}


def _truncate(text: str, max_chars: int = 1400) -> str:
    if len(text) <= max_chars:
        return text
    # Take the LAST max_chars — agent outputs front-load methodology and
    # put the actual insights, findings, and recommendations at the end.
    return "…" + text[-max_chars:].lstrip()


def build_brief_from_result(pipeline_result: dict, task_description: str = "") -> str:
    """
    Build a ~2000-token analysis brief from a completed Phase 1 run result.
    Truncates each agent's output so the full brief fits in context.
    """
    agent_results: dict = pipeline_result.get("agent_results", {})

    sections: list[str] = []

    if task_description:
        sections.append(f"## Task\n{task_description}")

    for key in AGENT_ORDER:
        if key not in agent_results:
            continue
        label = AGENT_LABELS.get(key, key.replace("_", " ").title())
        content = _truncate(agent_results[key], max_chars=1400)
        sections.append(f"## {label} Analysis\n{content}")

    if not sections:
        # Fallback: try context entries
        entries = pipeline_result.get("entries", [])
        for entry in entries[-10:]:
            sections.append(f"## {entry.get('agent','?').title()}\n{_truncate(entry.get('content',''), 500)}")

    brief = "\n\n---\n\n".join(sections)
    brief = f"# Analysis Brief\n\n{brief}"
    return brief


# ─────────────────────────────────────────────────────────────────────
# Mode 2: From dataset only (standalone — no Phase 1 needed)
# ─────────────────────────────────────────────────────────────────────

def build_brief_from_dataset(dataset_path: str, task_description: str = "") -> str:
    """
    Build a brief directly from a dataset without running Phase 1.
    Uses DatasetDiscovery to scan and profile the dataset.
    """
    from phases.discovery import DatasetDiscovery

    disc    = DatasetDiscovery()
    profile = disc.scan(dataset_path)
    summary = disc.format_profile(profile)

    lines = ["# Analysis Brief (Dataset Scan)\n"]

    if task_description:
        lines.append(f"## Task\n{task_description}\n")

    lines.append(f"## Dataset Profile\n{_truncate(summary, 2000)}")

    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Load result from disk (by run_id)
# ─────────────────────────────────────────────────────────────────────

def load_result_from_disk(run_id: str, exp_dir: str = "experiments") -> dict | None:
    path = Path(exp_dir) / "results" / f"{run_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None
