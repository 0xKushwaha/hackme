"""
ContextManager — structured history that replaces the plain-string log.

Key improvements over the old system:
- Pinned entries (e.g. dataset summary) are NEVER trimmed
- Each entry has metadata: agent name, role, timestamp
- Token-aware trimming drops non-pinned entries oldest-first
- Serializable to/from JSON for persistence across runs
- Can retrieve history by agent or role
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# Roles for tagging entries
ROLE_DATASET   = "dataset_context"   # initial dataset summary — pinned
ROLE_TASK      = "task_context"      # competition / user goal — pinned
ROLE_ANALYSIS  = "analysis"          # EDA, stats, skeptic output
ROLE_PLAN      = "plan"              # pragmatist, devil advocate
ROLE_CODE      = "code"              # generated Python scripts
ROLE_RESULT    = "result"            # execution output + metrics
ROLE_ERROR     = "error"             # failed execution details
ROLE_NARRATIVE = "narrative"         # storyteller final summary
ROLE_META      = "meta"              # orchestrator decisions, misc


MAX_CONTEXT_TOKENS = 6000   # ~24K chars before trimming kicks in
CHARS_PER_TOKEN    = 4


@dataclass
class ContextEntry:
    agent:     str
    role:      str
    content:   str
    pinned:    bool = False          # pinned entries survive trimming
    id:        str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str  = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    metadata:  dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ContextEntry":
        return cls(**d)

    def render(self) -> str:
        """Single-string representation used when building context for agents."""
        return f"[{self.agent.upper()} | {self.role}]\n{self.content}"

    def token_estimate(self) -> int:
        return len(self.content) // CHARS_PER_TOKEN


class ContextManager:
    """
    Maintains an ordered list of ContextEntry objects.
    Provides trimmed context strings for agent consumption.
    """

    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.entries: list[ContextEntry] = []
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------ #
    # Adding entries                                                       #
    # ------------------------------------------------------------------ #

    def add(
        self,
        agent:    str,
        role:     str,
        content:  str,
        pinned:   bool = False,
        metadata: dict = None,
    ) -> ContextEntry:
        entry = ContextEntry(
            agent=agent,
            role=role,
            content=content,
            pinned=pinned,
            metadata=metadata or {},
        )
        self.entries.append(entry)
        return entry

    MAX_DATASET_CHARS = 40_000   # hard cap — prevents huge datasets from blowing context

    def add_dataset_context(self, summary: str) -> ContextEntry:
        """Dataset summary is always pinned — it never gets trimmed."""
        if len(summary) > self.MAX_DATASET_CHARS:
            summary = summary[:self.MAX_DATASET_CHARS] + "\n... [dataset summary truncated]"
        return self.add("system", ROLE_DATASET, summary, pinned=True)

    def add_task_context(self, task_description: str) -> ContextEntry:
        """
        Pin the user's competition / task goal — always visible to every agent.
        Agents use this to tailor metric choice, evaluation strategy, and
        final recommendations to the actual objective.
        """
        content = (
            "COMPETITION / TASK GOAL\n"
            "=======================\n"
            f"{task_description.strip()}\n\n"
            "All agents must align their analysis, metric recommendations, and "
            "conclusions to this stated goal."
        )
        return self.add("user", ROLE_TASK, content, pinned=True)

    def add_code(self, code: str, attempt: int = 1) -> ContextEntry:
        return self.add(
            "code_writer", ROLE_CODE, code,
            metadata={"attempt": attempt},
        )

    def add_result(self, output: str, metrics: dict, success: bool, attempt: int = 1) -> ContextEntry:
        summary = (
            f"Training {'SUCCEEDED' if success else 'FAILED'} (attempt {attempt})\n"
            f"Metrics: {json.dumps(metrics, indent=2)}\n"
            f"Output:\n{output[:2000]}"   # cap raw output at 2K chars
        )
        return self.add(
            "executor", ROLE_RESULT if success else ROLE_ERROR,
            summary, metadata={"metrics": metrics, "success": success, "attempt": attempt},
        )

    # ------------------------------------------------------------------ #
    # Retrieving entries                                                   #
    # ------------------------------------------------------------------ #

    def get_by_agent(self, agent: str) -> list[ContextEntry]:
        return [e for e in self.entries if e.agent.lower() == agent.lower()]

    def get_by_role(self, role: str) -> list[ContextEntry]:
        return [e for e in self.entries if e.role == role]

    def last_result(self) -> Optional[ContextEntry]:
        results = self.get_by_role(ROLE_RESULT) + self.get_by_role(ROLE_ERROR)
        return results[-1] if results else None

    def last_metrics(self) -> Optional[dict]:
        r = self.last_result()
        return r.metadata.get("metrics") if r else None

    def last_code(self) -> Optional[str]:
        codes = self.get_by_role(ROLE_CODE)
        return codes[-1].content if codes else None

    def training_attempts(self) -> int:
        return len(self.get_by_role(ROLE_CODE))

    # ------------------------------------------------------------------ #
    # Building context string for agents                                  #
    # ------------------------------------------------------------------ #

    def _total_tokens(self, entries: list[ContextEntry]) -> int:
        return sum(e.token_estimate() for e in entries)

    def get_context_string(self) -> str:
        """
        Returns a trimmed context string for agent consumption.
        Pinned entries are always included.
        Non-pinned entries are included oldest-first until token budget is hit.
        """
        pinned     = [e for e in self.entries if e.pinned]
        non_pinned = [e for e in self.entries if not e.pinned]

        pinned_tokens = self._total_tokens(pinned)
        budget        = self.max_tokens - pinned_tokens

        # Fill budget with non-pinned, newest-last (drop oldest first)
        kept = []
        for entry in reversed(non_pinned):
            if self._total_tokens(kept) + entry.token_estimate() <= budget:
                kept.append(entry)
            else:
                break
        kept.reverse()   # restore chronological order

        all_entries = pinned + kept
        # Re-sort by insertion order (use entries list as reference)
        order = {e.id: i for i, e in enumerate(self.entries)}
        all_entries.sort(key=lambda e: order[e.id])

        return "\n\n".join(e.render() for e in all_entries)

    def get_slim_context_string(self, max_recent: int = 2) -> str:
        """
        Lightweight context for critique/planning agents that don't need the full log.
        Always includes all pinned entries (dataset summary, task goal).
        Only includes the most recent `max_recent` non-pinned entries.
        This significantly reduces prompt size and LLM latency for agents like
        Skeptic, Ethicist, Devil's Advocate, and Pragmatist.
        """
        pinned     = [e for e in self.entries if e.pinned]
        non_pinned = [e for e in self.entries if not e.pinned]
        recent     = non_pinned[-max_recent:] if non_pinned else []

        all_entries = pinned + recent
        order = {e.id: i for i, e in enumerate(self.entries)}
        all_entries.sort(key=lambda e: order[e.id])

        return "\n\n".join(e.render() for e in all_entries)

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump([e.to_dict() for e in self.entries], f, indent=2)

    def load(self, path: str):
        with open(path) as f:
            data = json.load(f)
        self.entries = [ContextEntry.from_dict(d) for d in data]

    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"  CONTEXT SUMMARY ({len(self.entries)} entries)")
        print(f"{'='*60}")
        for e in self.entries:
            pin = "📌" if e.pinned else "  "
            print(f"{pin} [{e.timestamp}] {e.agent.upper():20s} | {e.role:20s} | ~{e.token_estimate()} tokens")
