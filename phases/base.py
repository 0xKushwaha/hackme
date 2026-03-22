"""
BasePhase — abstract base for all pipeline phases.

Each phase is a self-contained unit with its own agent team.
Phases communicate through the shared Orchestrator context, so a phase
can read everything prior phases produced.

Key property: phases are independently re-runnable.
If you change the ModelDesignPhase logic you can re-run from that phase
without re-running DataUnderstandingPhase — the context already has the
EDA outputs from the earlier run.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PhaseResult:
    phase_name:  str
    success:     bool
    summary:     str
    outputs:     dict[str, Any]  = field(default_factory=dict)
    error:       Optional[str]   = None
    duration_s:  float           = 0.0
    run_id:      str             = field(default_factory=lambda: str(uuid.uuid4())[:12])


class BasePhase:
    """
    Abstract pipeline phase.

    Subclasses:
      - Set `name` (str) — used in logs
      - Set `REQUIRED_AGENTS` (list[str]) — validated before run
      - Implement `_run(**kwargs) -> PhaseResult`
    """

    name: str             = "base"
    REQUIRED_AGENTS: list = []

    def __init__(self, orchestrator):
        self.orch = orchestrator

    def run(self, **kwargs) -> PhaseResult:
        """Public entry point. Validates agents, times execution, catches crashes."""
        missing = [a for a in self.REQUIRED_AGENTS if a not in self.orch.agents]
        if missing:
            result = PhaseResult(
                phase_name=self.name,
                success=False,
                summary=f"Missing required agents: {missing}",
                error=f"Missing agents: {missing}",
            )
            print(f"\n[Phase:{self.name}] ❌ {result.error}")
            return result

        t0 = time.time()
        try:
            result = self._run(**kwargs)
        except Exception as exc:
            result = PhaseResult(
                phase_name=self.name,
                success=False,
                summary=f"Phase '{self.name}' crashed: {exc}",
                error=str(exc),
            )
            print(f"\n[Phase:{self.name}] ❌ Crashed: {exc}")

        result.duration_s = round(time.time() - t0, 2)
        status = "✅" if result.success else "❌"
        print(f"\n[Phase:{self.name}] {status} Completed in {result.duration_s}s")
        return result

    def _run(self, **kwargs) -> PhaseResult:
        raise NotImplementedError(f"Phase '{self.name}' must implement _run()")

    # ------------------------------------------------------------------ #
    # Helpers shared by all phases                                         #
    # ------------------------------------------------------------------ #

    def _last_output(self, agent: str) -> str:
        """Get the most recent context entry from a given agent."""
        for e in reversed(self.orch.context.entries):
            if e.agent == agent:
                return e.content
        return ""
