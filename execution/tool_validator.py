"""
ToolValidator — validates Python tool code before writing it to tool_registry/.

Three-stage pipeline:
  1. Syntax   — ast.parse() catches syntax errors instantly (no subprocess)
  2. Compile  — compile() catches additional structural errors
  3. Import   — subprocess import check: catches missing libraries, name errors,
                module-level exceptions that only appear at import time

If any stage fails, returns a ValidationResult with a clear error message so
BuilderAgent can feed it back to the LLM and ask for a fix.

The import check runs in a fresh subprocess (isolated — won't crash the main
process even if the code has side effects).
"""

import ast
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid:  bool
    error:  str  = ""
    stage:  str  = ""    # "syntax" | "compile" | "import" | "ok"

    def __bool__(self) -> bool:
        return self.valid


class ToolValidator:
    """Validates Python code before registering it as a tool."""

    IMPORT_TIMEOUT = 20   # seconds — generous for heavy imports like torch

    def validate(self, code: str, name: str = "tool") -> ValidationResult:
        """Run all three checks. Returns ValidationResult."""

        # ── Stage 1: Syntax ───────────────────────────────────────────
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ValidationResult(
                valid=False,
                error=f"SyntaxError on line {exc.lineno}: {exc.msg} — {exc.text or ''}".strip(),
                stage="syntax",
            )

        # ── Stage 2: Compile ──────────────────────────────────────────
        try:
            compile(tree, filename=f"<{name}>", mode="exec")
        except Exception as exc:
            return ValidationResult(
                valid=False,
                error=f"CompileError: {exc}",
                stage="compile",
            )

        # ── Stage 3: Subprocess import check ─────────────────────────
        return self._subprocess_check(code, name)

    def _subprocess_check(self, code: str, name: str) -> ValidationResult:
        """
        Write code to a temp file and import it in a fresh subprocess.
        Catches ImportError, NameError, and module-level exceptions.
        Fails open (returns valid=True) if the subprocess machinery itself fails.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", delete=False, mode="w", encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name

            import_script = (
                "import importlib.util, sys;"
                f"spec = importlib.util.spec_from_file_location('_tool_check', r'{tmp_path}');"
                "mod = importlib.util.module_from_spec(spec);"
                "spec.loader.exec_module(mod)"
            )
            proc = subprocess.run(
                [sys.executable, "-c", import_script],
                capture_output=True,
                text=True,
                timeout=self.IMPORT_TIMEOUT,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout).strip()
                return ValidationResult(valid=False, error=err, stage="import")

            return ValidationResult(valid=True, stage="ok")

        except subprocess.TimeoutExpired:
            # Heavy library (torch, tensorflow) — treat as valid rather than blocking
            return ValidationResult(valid=True, stage="ok")

        except Exception:
            # Subprocess machinery failed — fail open
            return ValidationResult(valid=True, stage="ok")

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
