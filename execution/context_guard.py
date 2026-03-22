"""
ToolResultContextGuard — prevents training output from overwhelming agent context.

Ported from OpenClaw's:
  src/agents/pi-embedded-runner/tool-result-context-guard.ts
  src/agents/pi-embedded-runner/tool-result-truncation.ts

Rules:
  - Tool results (executor stdout/stderr) are capped at MAX_TOOL_RESULT_SHARE
    of the total context window (default 30%)
  - Hard max of HARD_MAX_CHARS regardless of context size
  - Head+tail truncation strategy preserves error/exception content at the tail
    (errors almost always appear at the end of training output)
  - Preemptive compaction triggered when context hits 90% capacity
"""

import re

# Mirrors OpenClaw's constants
MAX_TOOL_RESULT_SHARE       = 0.30    # tool results cap: 30% of total context
HARD_MAX_CHARS              = 400_000  # absolute hard cap
CONTEXT_HEADROOM_RATIO      = 0.75    # 25% buffer — stay under 75% before guard triggers
PREEMPTIVE_OVERFLOW_RATIO   = 0.90    # full compaction at 90% capacity
CHARS_PER_TOKEN             = 4       # rough estimate

# Error indicators to preserve at the tail of truncated output
ERROR_INDICATORS = [
    "error", "exception", "traceback", "failed", "valueerror", "typeerror",
    "keyerror", "indexerror", "attributeerror", "importerror", "runtimeerror",
    "memoryerror", "syntaxerror", "stderr", "exit code", "killed",
]


class ToolResultContextGuard:
    """
    Guards context window from being overwhelmed by tool output.
    Apply to executor stdout/stderr before adding to context.
    """

    def __init__(
        self,
        max_context_tokens:   int   = 6000,
        max_tool_share:       float = MAX_TOOL_RESULT_SHARE,
        hard_max_chars:       int   = HARD_MAX_CHARS,
    ):
        self.max_context_tokens = max_context_tokens
        self.max_tool_share     = max_tool_share
        self.hard_max_chars     = hard_max_chars

        # Derived budget: how many chars can tool results use
        total_chars      = max_context_tokens * CHARS_PER_TOKEN
        self.max_tool_chars = min(
            int(total_chars * max_tool_share),
            hard_max_chars,
        )

    def guard(self, stdout: str, stderr: str) -> tuple[str, str]:
        """
        Apply the context guard to executor stdout and stderr.
        Returns (guarded_stdout, guarded_stderr).
        """
        # Split the budget between stdout and stderr
        # stderr gets priority when both are present (errors are more important)
        if stdout and stderr:
            stderr_budget = min(len(stderr), self.max_tool_chars // 2)
            stdout_budget = self.max_tool_chars - stderr_budget
        elif stderr:
            stderr_budget = self.max_tool_chars
            stdout_budget = 0
        else:
            stdout_budget = self.max_tool_chars
            stderr_budget = 0

        guarded_stdout = truncate_tool_result(stdout, stdout_budget) if stdout else ""
        guarded_stderr = truncate_tool_result(stderr, stderr_budget) if stderr else ""

        return guarded_stdout, guarded_stderr

    def guard_combined(self, text: str) -> str:
        """Guard a single combined output string."""
        return truncate_tool_result(text, self.max_tool_chars)

    def context_overflow_level(self, current_tokens: int) -> str:
        """
        Returns the overflow state:
          'ok'          — under headroom ratio
          'warn'        — between headroom and preemptive threshold
          'preemptive'  — over preemptive threshold, trigger compaction
          'overflow'    — over 100%, must compact before continuing
        """
        ratio = current_tokens / self.max_context_tokens
        if ratio < CONTEXT_HEADROOM_RATIO:
            return "ok"
        if ratio < PREEMPTIVE_OVERFLOW_RATIO:
            return "warn"
        if ratio < 1.0:
            return "preemptive"
        return "overflow"


def truncate_tool_result(text: str, max_chars: int) -> str:
    """
    Head+tail truncation that preserves error content at the tail.

    OpenClaw strategy:
      - Keep head (1/3 of budget) — captures script startup, early logs
      - Keep tail (2/3 of budget) — where errors/exceptions always appear
      - Insert a truncation marker in between

    If the tail contains error indicators, expand tail budget by 10%.
    """
    if not text or len(text) <= max_chars:
        return text

    removed = len(text) - max_chars

    # Check if tail contains errors — expand tail budget if so
    tail_sample = text[-min(1000, len(text)):]
    has_errors  = any(ind in tail_sample.lower() for ind in ERROR_INDICATORS)

    if has_errors:
        # Bias toward tail: 25% head, 75% tail
        head_size = max_chars // 4
    else:
        # Standard: 33% head, 67% tail
        head_size = max_chars // 3

    tail_size = max_chars - head_size

    head = text[:head_size]
    tail = text[-tail_size:]

    marker = f"\n\n... [{removed:,} characters truncated] ...\n\n"
    return head + marker + tail


def format_execution_result(stdout: str, stderr: str, metrics: dict, success: bool, guard: ToolResultContextGuard) -> str:
    """
    Format executor output for injection into agent context.
    Applies the context guard before formatting.
    """
    g_stdout, g_stderr = guard.guard(stdout, stderr)

    status = "SUCCEEDED" if success else "FAILED"
    parts  = [f"[EXECUTION {status}]"]

    if metrics:
        import json
        parts.append(f"Metrics: {json.dumps(metrics, indent=2)}")

    if g_stdout.strip():
        parts.append(f"Stdout:\n{g_stdout.strip()}")

    if g_stderr.strip():
        parts.append(f"Stderr:\n{g_stderr.strip()}")

    return "\n\n".join(parts)
