"""
LibraryInstallerAgent — fully autonomous missing-package detection and installation.

When any tool, specialist agent, or training script fails with an ImportError
or ModuleNotFoundError, this agent:
  1. Parses the error text to identify the missing module
  2. Maps Python module names to pip package names (PIL → Pillow, cv2 → opencv-python)
  3. Runs `pip install` as a subprocess using the SAME Python interpreter
  4. Reports what succeeded / failed

No human intervention. Fully autonomous.

Used by:
  - BuilderAgent   : when tool code fails import validation
  - DataUnderstandingPhase : when a specialist agent import fails
  - CodeExecutor   : when a training script fails with ImportError
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------ #
# Module name → pip package name                                       #
# ------------------------------------------------------------------ #

MODULE_TO_PACKAGE: dict[str, str] = {
    # Image / CV
    "PIL":              "Pillow",
    "cv2":              "opencv-python",
    "skimage":          "scikit-image",
    "imageio":          "imageio",
    "tifffile":         "tifffile",
    "rawpy":            "rawpy",
    "albumentations":   "albumentations",
    "timm":             "timm",
    # Audio
    "librosa":          "librosa",
    "soundfile":        "soundfile",
    "pydub":            "pydub",
    "mutagen":          "mutagen",
    "pyaudio":          "pyaudio",
    # ML / DL frameworks
    "torch":            "torch",
    "torchvision":      "torchvision",
    "torchaudio":       "torchaudio",
    "tensorflow":       "tensorflow",
    "keras":            "keras",
    "jax":              "jax",
    "flax":             "flax",
    # HuggingFace
    "transformers":     "transformers",
    "datasets":         "datasets",
    "tokenizers":       "tokenizers",
    "sentence_transformers": "sentence-transformers",
    "accelerate":       "accelerate",
    "peft":             "peft",
    # ML / Stats
    "sklearn":          "scikit-learn",
    "xgboost":          "xgboost",
    "lightgbm":         "lightgbm",
    "catboost":         "catboost",
    "optuna":           "optuna",
    "shap":             "shap",
    "statsmodels":      "statsmodels",
    "umap":             "umap-learn",
    # NLP
    "nltk":             "nltk",
    "spacy":            "spacy",
    "gensim":           "gensim",
    "textblob":         "textblob",
    # Data / IO
    "pyarrow":          "pyarrow",
    "fastparquet":      "fastparquet",
    "h5py":             "h5py",
    "tables":           "tables",
    "openpyxl":         "openpyxl",
    "xlrd":             "xlrd",
    "xlwt":             "xlwt",
    "pymongo":          "pymongo",
    "sqlalchemy":       "SQLAlchemy",
    "psycopg2":         "psycopg2-binary",
    # Scientific
    "scipy":            "scipy",
    "sympy":            "sympy",
    "networkx":         "networkx",
    # Viz
    "matplotlib":       "matplotlib",
    "seaborn":          "seaborn",
    "plotly":           "plotly",
    "bokeh":            "bokeh",
    # Distributed
    "dask":             "dask",
    "ray":              "ray",
    # Medical imaging
    "pydicom":          "pydicom",
    "SimpleITK":        "SimpleITK",
    "nilearn":          "nilearn",
    "mne":              "mne",
    "wfdb":             "wfdb",
    # Misc
    "tqdm":             "tqdm",
    "requests":         "requests",
    "yaml":             "pyyaml",
    "dotenv":           "python-dotenv",
    "rich":             "rich",
}

# Patterns to extract the module name from error messages
_IMPORT_PATTERNS = [
    r"No module named ['\"]([^'\"\.]+)",           # No module named 'librosa'
    r"ModuleNotFoundError[^'\"]*['\"]([^'\"\.]+)",  # ModuleNotFoundError: ...
    r"ImportError[^'\"]*['\"]([^'\"\.]+)",          # ImportError: ...
    r"cannot import name .+ from ['\"]([^'\"]+)",   # cannot import from 'PIL'
]


# ------------------------------------------------------------------ #
# Result dataclass                                                     #
# ------------------------------------------------------------------ #

@dataclass
class InstallResult:
    attempted:  list[str] = field(default_factory=list)
    succeeded:  list[str] = field(default_factory=list)
    failed:     list[str] = field(default_factory=list)
    skipped:    list[str] = field(default_factory=list)   # already installed
    log:        str       = ""

    @property
    def any_success(self) -> bool:
        return bool(self.succeeded)

    @property
    def all_failed(self) -> bool:
        return bool(self.attempted) and not self.succeeded

    def summary(self) -> str:
        parts = []
        if self.succeeded:
            parts.append(f"installed: {self.succeeded}")
        if self.failed:
            parts.append(f"failed: {self.failed}")
        if self.skipped:
            parts.append(f"already present: {self.skipped}")
        return " | ".join(parts) if parts else "nothing to install"


# ------------------------------------------------------------------ #
# Agent                                                                #
# ------------------------------------------------------------------ #

class LibraryInstallerAgent:
    """
    Detects missing Python packages from error text and installs them
    autonomously using the same Python interpreter that's running the pipeline.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run   # if True, detect but skip actual pip install

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def handle(self, error_text: str) -> InstallResult:
        """
        Full flow: detect → resolve → install.
        Returns InstallResult with what was attempted and what succeeded.
        """
        modules = self.detect_missing_modules(error_text)
        if not modules:
            return InstallResult(log="No missing modules detected in error text.")

        packages = self._resolve_all(modules)
        print(f"\n[LibraryInstaller] 🔍 Missing modules  : {modules}")
        print(f"[LibraryInstaller] 📦 Packages to install: {packages}")

        return self._install_all(packages)

    def detect_missing_modules(self, error_text: str) -> list[str]:
        """Extract raw module names from ImportError messages."""
        found = []
        for pattern in _IMPORT_PATTERNS:
            for match in re.finditer(pattern, error_text, re.IGNORECASE):
                name = match.group(1).split(".")[0].strip()  # 'PIL.Image' → 'PIL'
                if name and name not in found:
                    found.append(name)
        return found

    def resolve_package(self, module_name: str) -> str:
        """Map a Python module name to its pip package name."""
        return MODULE_TO_PACKAGE.get(module_name, module_name)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _resolve_all(self, modules: list[str]) -> list[str]:
        seen, packages = set(), []
        for m in modules:
            pkg = self.resolve_package(m)
            if pkg not in seen:
                seen.add(pkg)
                packages.append(pkg)
        return packages

    def _install_all(self, packages: list[str]) -> InstallResult:
        result = InstallResult(attempted=packages)
        log_lines = []

        for pkg in packages:
            if self.dry_run:
                print(f"[LibraryInstaller] 🔧 [dry-run] Would install: {pkg}")
                result.succeeded.append(pkg)
                log_lines.append(f"[dry-run] {pkg}")
                continue

            status = self._pip_install(pkg)

            if status == "ok":
                result.succeeded.append(pkg)
                log_lines.append(f"✅ {pkg}: installed")
            elif status == "already":
                result.skipped.append(pkg)
                log_lines.append(f"⏭  {pkg}: already satisfied")
            else:
                result.failed.append(pkg)
                log_lines.append(f"❌ {pkg}: {status}")

        result.log = "\n".join(log_lines)
        print(f"[LibraryInstaller] {result.summary()}")
        return result

    def _pip_install(self, package: str) -> str:
        """
        Run pip install. Returns "ok", "already", or error string.
        """
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "--quiet", "--no-warn-script-location"],
                capture_output=True,
                text=True,
                timeout=180,   # 3 min max per package
            )
            if proc.returncode == 0:
                if "already satisfied" in proc.stdout.lower() or "already satisfied" in proc.stderr.lower():
                    return "already"
                print(f"[LibraryInstaller] ✅ {package} installed")
                return "ok"
            else:
                err = (proc.stderr or proc.stdout)[:300].strip()
                print(f"[LibraryInstaller] ❌ {package} failed: {err[:100]}")
                return err
        except subprocess.TimeoutExpired:
            msg = f"pip install {package} timed out after 180s"
            print(f"[LibraryInstaller] ❌ {msg}")
            return msg
        except Exception as exc:
            print(f"[LibraryInstaller] ❌ {package}: {exc}")
            return str(exc)
