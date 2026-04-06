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

    @staticmethod
    def resolve_primary_file(path: str) -> str:
        """
        If path is a directory, returns the path to the largest tabular file
        found recursively within it. If path is already a file, returns it unchanged.

        Raises ValueError if no tabular files are found.
        """
        from pathlib import Path

        p = Path(path)
        if p.is_file():
            return path

        tabular_exts = {
            ".csv", ".tsv", ".parquet", ".feather",
            ".json", ".jsonl", ".xlsx", ".xls", ".h5", ".hdf5",
        }
        candidates = [
            f for f in p.rglob("*")
            if f.is_file() and f.suffix.lower() in tabular_exts
        ]
        if not candidates:
            raise ValueError(f"No tabular files found in directory: {path}")
        # Pick the largest — usually the primary training set
        primary = max(candidates, key=lambda f: f.stat().st_size)
        return str(primary)

    @staticmethod
    def load_dataframe(path: str, max_rows: int = None):
        """
        Robust tabular file loader shared by all phases.

        Accepts a file path OR a directory — if a directory is given, the
        largest tabular file found recursively inside it is loaded.

        Uses Path.suffix for reliable extension detection and explicit
        engine/format arguments to prevent pyarrow from treating CSV
        files as parquet (triggered by chromadb's pyarrow initialization).

        Args:
            path:     Absolute path to a tabular file or dataset directory.
            max_rows: If set, only this many rows are loaded (faster, less RAM).

        Returns:
            pd.DataFrame, or raises on unrecognised format.
        """
        import pandas as pd
        from pathlib import Path

        # Resolve directory → primary file
        path = BasePhase.resolve_primary_file(path)
        ext = Path(path).suffix.lower()

        if ext == ".csv":
            return pd.read_csv(path, engine="c", nrows=max_rows)

        if ext == ".tsv":
            return pd.read_csv(path, sep="\t", engine="c", nrows=max_rows)

        if ext in (".parquet",):
            # Explicit pyarrow engine — never let pandas auto-detect
            try:
                import pyarrow.parquet as pq
                pf = pq.ParquetFile(path)
                if max_rows:
                    batch = next(pf.iter_batches(batch_size=max_rows))
                    return batch.to_pandas()
                return pf.read().to_pandas()
            except Exception:
                # Fallback: pandas with explicit engine
                df = pd.read_parquet(path, engine="pyarrow")
                return df.head(max_rows) if max_rows else df

        if ext == ".feather":
            df = pd.read_feather(path)
            return df.head(max_rows) if max_rows else df

        if ext in (".xlsx", ".xls"):
            return pd.read_excel(path, nrows=max_rows)

        if ext in (".json",):
            try:
                df = pd.read_json(path, lines=True, nrows=max_rows)
            except Exception:
                df = pd.read_json(path)
                if max_rows:
                    df = df.head(max_rows)
            return df

        if ext == ".jsonl":
            rows = []
            with open(path) as f:
                for line in f:
                    rows.append(__import__("json").loads(line.strip()))
                    if max_rows and len(rows) >= max_rows:
                        break
            return pd.DataFrame(rows)

        if ext in (".h5", ".hdf5"):
            df = pd.read_hdf(path)
            return df.head(max_rows) if max_rows else df

        raise ValueError(f"Unsupported file extension: '{ext}' for path: {path}")
