"""
CodeExecutor — runs a generated Python script in a subprocess and captures results.

RETRY MECHANISM
===============
If the script fails with an ImportError / ModuleNotFoundError:
  1. LibraryInstallerAgent detects the missing package and pip-installs it
  2. The SAME script is re-executed immediately (no retry slot consumed)
  3. This inner auto-fix happens at most once per outer attempt

Outer retry (changing the code) is handled by the orchestrator training loop.
This layer only handles library gaps so the LLM doesn't have to write a new
script just because a package wasn't pre-installed.

Safety measures:
  - Timeout (default 5 min) kills the process if it hangs
  - Script runs with the current working directory set to work_dir
  - stdout/stderr captured — not streamed
"""

import os
import sys
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from .result_parser import parse, ParsedResult, ERROR_IMPORT
from agents.installer_agent import LibraryInstallerAgent


DEFAULT_TIMEOUT = 300   # seconds


@dataclass
class ExecutionResult:
    success:      bool
    metrics:      dict  = field(default_factory=dict)
    stdout:       str   = ""
    stderr:       str   = ""
    elapsed:      float = 0.0
    error_type:   Optional[str] = None
    error_msg:    Optional[str] = None
    script_path:  Optional[str] = None
    auto_fixed:   bool          = False   # True if library was auto-installed mid-run

    def short_summary(self) -> str:
        fix_note = " [auto-fixed library]" if self.auto_fixed else ""
        if self.success:
            return f"SUCCESS{fix_note} in {self.elapsed:.1f}s | metrics: {self.metrics}"
        return f"FAILED ({self.error_type}){fix_note} in {self.elapsed:.1f}s | {self.error_msg}"


class CodeExecutor:
    """
    Writes generated code to a file and runs it as a subprocess.
    Automatically detects ImportErrors and installs missing packages before
    retrying — fully autonomous, no human needed.
    """

    def __init__(
        self,
        timeout:   int  = DEFAULT_TIMEOUT,
        work_dir:  str  = None,
        installer: LibraryInstallerAgent = None,
    ):
        self.timeout   = timeout
        self.work_dir  = work_dir or tempfile.gettempdir()
        self.installer = installer or LibraryInstallerAgent()

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #

    def run(self, code: str, attempt: int = 1) -> ExecutionResult:
        """
        Write code to disk and execute it.
        On ImportError: auto-install missing packages and retry once.
        """
        script_path = os.path.join(self.work_dir, f"train_attempt_{attempt}.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        print(f"\n[EXECUTOR] ▶  Running script: {script_path}")

        result = self._execute(script_path)

        # ── Auto-fix: ImportError → install → retry once ──────────────
        if not result.success and result.error_type == ERROR_IMPORT:
            print(f"\n[EXECUTOR] 📦 ImportError detected — triggering LibraryInstaller...")
            install = self.installer.handle(result.stderr + result.stdout)

            if install.any_success:
                print(
                    f"[EXECUTOR] ✅ Installed {install.succeeded} — "
                    "re-running same script once..."
                )
                retry = self._execute(script_path)
                retry.auto_fixed = True
                retry.elapsed   += result.elapsed   # cumulative time
                return retry
            else:
                print(f"[EXECUTOR] ❌ Library install failed: {install.log}")

        return result

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _execute(self, script_path: str) -> ExecutionResult:
        """Run script_path in a subprocess and return ExecutionResult."""
        start      = time.time()
        timed_out  = False

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.work_dir,
            )
            stdout     = proc.stdout
            stderr     = proc.stderr
            returncode = proc.returncode

        except subprocess.TimeoutExpired as exc:
            timed_out  = True
            stdout     = exc.stdout or ""
            stderr     = exc.stderr or ""
            returncode = -1

        except Exception as exc:
            stdout     = ""
            stderr     = str(exc)
            returncode = -1

        elapsed = time.time() - start
        parsed: ParsedResult = parse(stdout, stderr, returncode, timed_out)

        print(
            f"[EXECUTOR] {'✅' if parsed.success else '❌'} "
            f"exit={returncode} | {elapsed:.1f}s"
            + (f" | metrics={parsed.metrics}" if parsed.metrics else "")
            + (f" | error={parsed.error_type}" if not parsed.success else "")
        )

        return ExecutionResult(
            success     = parsed.success,
            metrics     = parsed.metrics,
            stdout      = stdout,
            stderr      = stderr,
            elapsed     = elapsed,
            error_type  = parsed.error_type,
            error_msg   = parsed.error_msg,
            script_path = script_path,
        )
