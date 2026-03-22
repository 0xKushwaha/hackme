"""
AgentRegistry — lifecycle tracking and spawn limits for agent runs.

Ported from OpenClaw's:
  src/agents/subagent-registry.ts
  src/agents/subagent-spawn.ts

Tracks every agent invocation with full lifecycle metadata:
  created → started → ended (success | failure | timeout | cancelled)

Enforces:
  MAX_CONCURRENT  — max parallel agents running at once (default 5)
  MAX_DEPTH       — max nesting depth for spawned subagents (default 10)
  ARCHIVE_TTL     — how long completed runs stay in registry (60 min)

The registry persists to disk for crash recovery and can reconcile
orphaned runs on restore.
"""

import json
import os
import uuid
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


MAX_CONCURRENT = 5
MAX_DEPTH      = 10
ARCHIVE_TTL    = 3600   # 60 minutes

OUTCOME_SUCCESS   = "success"
OUTCOME_FAILURE   = "failure"
OUTCOME_TIMEOUT   = "timeout"
OUTCOME_CANCELLED = "cancelled"


@dataclass
class AgentRun:
    run_id:       str
    agent_name:   str
    task:         str
    depth:        int   = 0
    parent_run_id: Optional[str] = None

    created_at:   str   = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at:   Optional[str] = None
    ended_at:     Optional[str] = None

    outcome:      Optional[str] = None    # success | failure | timeout | cancelled
    error_type:   Optional[str] = None
    runtime_ms:   Optional[int] = None

    def start(self):
        self.started_at = datetime.now().isoformat(timespec="seconds")

    def end(self, outcome: str, error_type: str = None, runtime_ms: int = None):
        self.ended_at   = datetime.now().isoformat(timespec="seconds")
        self.outcome    = outcome
        self.error_type = error_type
        self.runtime_ms = runtime_ms

    def is_active(self) -> bool:
        return self.ended_at is None

    def is_archived(self) -> bool:
        if not self.ended_at:
            return False
        ended = datetime.fromisoformat(self.ended_at)
        age_s = (datetime.now() - ended).total_seconds()
        return age_s > ARCHIVE_TTL

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentRun":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class AgentRegistry:
    """
    Thread-safe registry tracking all agent runs in the current session.
    Optionally persists to disk for crash recovery.
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT,
        max_depth:      int = MAX_DEPTH,
        persist_path:   Optional[str] = None,
    ):
        self.max_concurrent = max_concurrent
        self.max_depth      = max_depth
        self.persist_path   = persist_path
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.Lock()

        if persist_path and os.path.exists(persist_path):
            self._load()

    # ------------------------------------------------------------------ #
    # Spawn validation                                                     #
    # ------------------------------------------------------------------ #

    def can_spawn(self, depth: int = 0) -> tuple[bool, str]:
        """
        Check if a new agent can be spawned.
        Returns (allowed, reason_if_denied).
        """
        with self._lock:
            if depth > self.max_depth:
                return False, f"Max spawn depth ({self.max_depth}) exceeded."

            active = sum(1 for r in self._runs.values() if r.is_active())
            if active >= self.max_concurrent:
                return False, f"Max concurrent agents ({self.max_concurrent}) reached. {active} active."

        return True, ""

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def register(
        self,
        agent_name:    str,
        task:          str,
        depth:         int           = 0,
        parent_run_id: Optional[str] = None,
        run_id:        Optional[str] = None,
    ) -> AgentRun:
        run = AgentRun(
            run_id        = run_id or str(uuid.uuid4())[:12],
            agent_name    = agent_name,
            task          = task[:200],
            depth         = depth,
            parent_run_id = parent_run_id,
        )
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def start(self, run_id: str):
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id].start()

    def complete(self, run_id: str, outcome: str, error_type: str = None, runtime_ms: int = None):
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id].end(outcome, error_type, runtime_ms)
        self._sweep()
        self._save()

    def cancel(self, run_id: str):
        self.complete(run_id, OUTCOME_CANCELLED)

    # ------------------------------------------------------------------ #
    # Queries                                                              #
    # ------------------------------------------------------------------ #

    def get(self, run_id: str) -> Optional[AgentRun]:
        return self._runs.get(run_id)

    def active_runs(self) -> list[AgentRun]:
        with self._lock:
            return [r for r in self._runs.values() if r.is_active()]

    def recent_runs(self, limit: int = 20) -> list[AgentRun]:
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
        return runs[:limit]

    def children_of(self, parent_run_id: str) -> list[AgentRun]:
        with self._lock:
            return [r for r in self._runs.values() if r.parent_run_id == parent_run_id]

    # ------------------------------------------------------------------ #
    # Persistence and cleanup                                              #
    # ------------------------------------------------------------------ #

    def _sweep(self):
        """Remove archived (TTL-expired) runs."""
        with self._lock:
            to_remove = [rid for rid, r in self._runs.items() if r.is_archived()]
            for rid in to_remove:
                del self._runs[rid]

    def _save(self):
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            with open(self.persist_path, "w") as f:
                json.dump([r.to_dict() for r in self._runs.values()], f, indent=2)
        except Exception:
            pass

    def _load(self):
        try:
            with open(self.persist_path) as f:
                data = json.load(f)
            for d in data:
                run = AgentRun.from_dict(d)
                # Reconcile orphaned runs (were active when process crashed)
                if run.is_active():
                    run.end(OUTCOME_CANCELLED, error_type="crash_recovery")
                self._runs[run.run_id] = run
        except Exception:
            pass

    def print_summary(self):
        runs    = self.recent_runs(50)
        active  = [r for r in runs if r.is_active()]
        done    = [r for r in runs if not r.is_active()]

        print(f"\n[AgentRegistry] {len(active)} active, {len(done)} completed")
        for r in active:
            print(f"  ACTIVE  {r.run_id} | {r.agent_name:20s} | depth={r.depth}")
        for r in done[-10:]:
            icon = "✅" if r.outcome == OUTCOME_SUCCESS else "❌"
            ms   = f"{r.runtime_ms}ms" if r.runtime_ms else "?"
            print(f"  {icon} {r.run_id} | {r.agent_name:20s} | {r.outcome:10s} | {ms}")
