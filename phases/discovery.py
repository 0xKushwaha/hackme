"""
DatasetDiscovery — scans any file or directory and produces a DatasetProfile.

Supports every common data format:
  Tabular  : .csv  .tsv  .parquet  .feather  .json  .jsonl  .xlsx  .xls  .h5  .hdf5
  Image    : .jpg  .jpeg  .png  .gif  .bmp  .tiff  .webp  .svg
  Text     : .txt  .md  .rst  .log  .xml  .yaml  .yml
  Audio    : .wav  .mp3  .flac  .ogg  .aac
  Video    : .mp4  .avi  .mov  .mkv
  Archive  : .zip  .tar  .gz  — auto-extracted to a temp dir, then scanned
  Code     : .py  .r  .ipynb  .sql

ZIP / TAR / GZ files are automatically extracted before scanning so the rest
of the pipeline always sees real files, never a raw archive.

The DatasetProfile is fed to the BuilderAgent which decides what specialist
tools and agents to create so the rest of the pipeline can handle ANY dataset.
"""

import json
import os
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------ #
# Extension → logical file type mapping                               #
# ------------------------------------------------------------------ #

TABULAR_EXT = {
    ".csv", ".tsv", ".parquet", ".feather",
    ".json", ".jsonl",
    ".xlsx", ".xls", ".h5", ".hdf5",
}
IMAGE_EXT   = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg"}
TEXT_EXT    = {".txt", ".md", ".rst", ".log", ".xml", ".yaml", ".yml", ".toml"}
AUDIO_EXT   = {".wav", ".mp3", ".flac", ".ogg", ".aac", ".m4a"}
VIDEO_EXT   = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ARCHIVE_EXT = {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"}
CODE_EXT    = {".py", ".r", ".ipynb", ".sql", ".sh"}

_EXT_MAP = (
    (TABULAR_EXT,  "tabular"),
    (IMAGE_EXT,    "image"),
    (TEXT_EXT,     "text"),
    (AUDIO_EXT,    "audio"),
    (VIDEO_EXT,    "video"),
    (ARCHIVE_EXT,  "archive"),
    (CODE_EXT,     "code"),
)


# ------------------------------------------------------------------ #
# Data classes                                                         #
# ------------------------------------------------------------------ #

@dataclass
class FileInfo:
    path:       str
    name:       str
    ext:        str
    size_bytes: int
    file_type:  str              # tabular | image | text | audio | video | archive | code | unknown
    preview:    str       = ""   # short text sample (tabular/text only)
    row_count:  Optional[int] = None
    col_count:  Optional[int] = None
    columns:    list      = field(default_factory=list)

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024


@dataclass
class DatasetProfile:
    root:    str
    is_file: bool
    files:   list[FileInfo] = field(default_factory=list)

    @property
    def by_type(self) -> dict[str, list[FileInfo]]:
        out: dict[str, list[FileInfo]] = {}
        for fi in self.files:
            out.setdefault(fi.file_type, []).append(fi)
        return out

    @property
    def types_present(self) -> list[str]:
        return sorted(self.by_type.keys())

    @property
    def tabular_files(self) -> list[FileInfo]:
        return self.by_type.get("tabular", [])

    @property
    def image_files(self) -> list[FileInfo]:
        return self.by_type.get("image", [])

    def is_pure_tabular(self) -> bool:
        """True if the entire dataset is a single tabular file."""
        return len(self.files) == 1 and self.files[0].file_type == "tabular"

    def is_mixed(self) -> bool:
        """True if multiple file types are present."""
        return len(self.types_present) > 1


# ------------------------------------------------------------------ #
# Discovery engine                                                     #
# ------------------------------------------------------------------ #

class DatasetDiscovery:
    """
    Scans a file or directory and returns a DatasetProfile.

    Strategy (two-pass):
      Pass 1 — walk the entire tree collecting only path/size/type metadata.
               No file reading, no limit.  Gives true file counts per type.
      Pass 2 — sample up to SAMPLE_PER_TYPE files from each type for deep
               inspection (preview, columns, row count).  Cheap and fast.

    This avoids both the hard 500-file cap and the cost of reading every file.
    """

    PREVIEW_ROWS    = 3
    PREVIEW_CHARS   = 600
    SAMPLE_PER_TYPE = 5   # files per type to read in detail

    # temp dirs created during archive extraction — caller may clean up
    _extracted_dirs: list[str] = []

    def __init__(self, llm=None):
        # LLM is forwarded to UnknownFormatAgent as a last-resort fallback
        # for files that can't be identified by any static parser.
        self.llm = llm

    def scan(self, path: str) -> DatasetProfile:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset path not found: {path}")

        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in ARCHIVE_EXT:
                path = self._extract_archive(path)
                # fall through to directory walk below
            else:
                fi = self._inspect(path, llm=self.llm)
                return DatasetProfile(root=path, is_file=True, files=[fi])

        # ── Pass 1: full metadata walk (no reading) ──────────────────────
        by_type: dict[str, list[str]] = {}   # type → [full_path, ...]
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in sorted(filenames):
                if fname.startswith("."):
                    continue
                full  = os.path.join(dirpath, fname)
                ext   = os.path.splitext(fname)[1].lower()
                ftype = self._classify(ext)
                by_type.setdefault(ftype, []).append(full)
                total += 1

        print(f"[Discovery] 📂 Found {total} files across {len(by_type)} type(s): "
              f"{', '.join(sorted(by_type))}")

        # ── Pass 2: sample + deep-inspect per type ───────────────────────
        import random
        collected: list[FileInfo] = []
        for ftype, paths in by_type.items():
            sample = paths if len(paths) <= self.SAMPLE_PER_TYPE else random.sample(paths, self.SAMPLE_PER_TYPE)
            skipped = len(paths) - len(sample)
            if skipped:
                print(f"[Discovery] 🔍 {ftype}: sampling {len(sample)}/{len(paths)} files "
                      f"({skipped} skipped — represented in counts only)")
            for fpath in sample:
                try:
                    collected.append(self._inspect(fpath, llm=self.llm))
                except Exception as exc:
                    print(f"[Discovery] Skipping {os.path.basename(fpath)}: {exc}")

            # Add lightweight stub entries for the un-sampled files so the
            # profile's total counts are accurate
            sampled_set = set(sample)
            for fpath in paths:
                if fpath in sampled_set:
                    continue
                fname_ = os.path.basename(fpath)
                ext_   = os.path.splitext(fname_)[1].lower()
                try:
                    size_ = os.path.getsize(fpath)
                except OSError:
                    size_ = 0
                collected.append(FileInfo(
                    path=fpath, name=fname_, ext=ext_,
                    size_bytes=size_, file_type=ftype,
                ))

        # Sort: tabular first, then by type, then by name
        collected.sort(key=lambda f: (f.file_type != "tabular", f.file_type, f.name))
        return DatasetProfile(root=path, is_file=False, files=collected)

    # ------------------------------------------------------------------ #
    # Per-file inspection                                                  #
    # ------------------------------------------------------------------ #

    def _inspect(self, path: str, llm=None) -> FileInfo:
        name  = os.path.basename(path)
        ext   = os.path.splitext(name)[1].lower()
        size  = os.path.getsize(path)
        ftype = self._classify(ext)

        fi = FileInfo(path=path, name=name, ext=ext, size_bytes=size, file_type=ftype)

        if ftype == "tabular":
            self._read_tabular(fi)
        elif ftype == "text":
            self._read_text(fi)
        elif ftype == "unknown":
            # Unknown extension → hand off to UnknownFormatAgent
            discovery = self._run_unknown_format_agent(path, llm)
            if discovery is not None:
                # Reclassify based on what the agent found
                fi.file_type = discovery.category
                fi.preview   = discovery.summary_text[:800]
                if discovery.schema and discovery.schema.columns:
                    fi.columns   = [c.name for c in discovery.schema.columns]
                    fi.col_count = len(fi.columns)
                    fi.row_count = discovery.schema.row_count
                # If a converted CSV was produced, replace path so rest of
                # pipeline can read it normally
                if discovery.converted_csv_path:
                    fi.path      = discovery.converted_csv_path
                    fi.file_type = "tabular"
                    fi.ext       = ".csv"

        return fi

    def _run_unknown_format_agent(self, path: str, llm=None):
        """Lazy-import and run UnknownFormatAgent to identify the file."""
        try:
            from agents.unknown_format_agent import UnknownFormatAgent
            agent = UnknownFormatAgent(llm=llm, verbose=True)
            return agent.investigate(path)
        except Exception as exc:
            print(f"[Discovery] UnknownFormatAgent failed for {os.path.basename(path)}: {exc}")
            return None

    @staticmethod
    def _classify(ext: str) -> str:
        for ext_set, type_name in _EXT_MAP:
            if ext in ext_set:
                return type_name
        return "unknown"

    def _read_tabular(self, fi: FileInfo):
        """Load a tiny preview of a tabular file to expose schema + sample rows."""
        try:
            ext = fi.ext
            if ext == ".csv":
                import pandas as pd
                # Full row count without loading everything
                try:
                    with open(fi.path) as f:
                        fi.row_count = sum(1 for _ in f) - 1
                except Exception:
                    pass
                df = pd.read_csv(fi.path, nrows=self.PREVIEW_ROWS)

            elif ext == ".tsv":
                import pandas as pd
                df = pd.read_csv(fi.path, sep="\t", nrows=self.PREVIEW_ROWS)

            elif ext == ".parquet":
                import pandas as pd
                df = pd.read_parquet(fi.path).head(self.PREVIEW_ROWS)

            elif ext == ".feather":
                import pandas as pd
                df = pd.read_feather(fi.path).head(self.PREVIEW_ROWS)

            elif ext in (".xlsx", ".xls"):
                import pandas as pd
                df = pd.read_excel(fi.path, nrows=self.PREVIEW_ROWS)

            elif ext in (".h5", ".hdf5"):
                import pandas as pd
                df = pd.read_hdf(fi.path).head(self.PREVIEW_ROWS)

            elif ext == ".json":
                import pandas as pd
                try:
                    df = pd.read_json(fi.path).head(self.PREVIEW_ROWS)
                except Exception:
                    with open(fi.path) as f:
                        raw = json.load(f)
                    if isinstance(raw, list):
                        df = pd.DataFrame(raw[: self.PREVIEW_ROWS])
                    else:
                        fi.preview = str(raw)[: self.PREVIEW_CHARS]
                        return

            elif ext == ".jsonl":
                import pandas as pd
                rows = []
                with open(fi.path) as f:
                    for line in f:
                        rows.append(json.loads(line.strip()))
                        if len(rows) >= self.PREVIEW_ROWS:
                            break
                df = pd.DataFrame(rows)

            else:
                return  # unsupported sub-format — leave empty

            fi.row_count = fi.row_count or len(df)
            fi.col_count = len(df.columns)
            fi.columns   = list(df.columns)
            fi.preview   = df.to_string()

        except Exception as exc:
            fi.preview = f"(Could not read: {exc})"

    def _read_text(self, fi: FileInfo):
        try:
            with open(fi.path, errors="replace") as f:
                fi.preview = f.read(self.PREVIEW_CHARS)
        except Exception as exc:
            fi.preview = f"(Could not read: {exc})"

    def _extract_archive(self, path: str) -> str:
        """
        Extract a ZIP / TAR / GZ archive into a fresh temp directory.
        Returns the path to the extracted directory.
        Nested archives are extracted recursively (one level).
        """
        dest = tempfile.mkdtemp(prefix="ds_extract_")
        # Track so callers can clean up later if needed
        DatasetDiscovery._extracted_dirs.append(dest)

        ext = os.path.splitext(path)[1].lower()
        fname = os.path.basename(path)
        print(f"[Discovery] 📦 Extracting archive: {fname} → {dest}")

        try:
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    # Safety: strip absolute paths and path traversal attempts
                    for member in zf.infolist():
                        member_path = os.path.realpath(
                            os.path.join(dest, member.filename)
                        )
                        if not member_path.startswith(os.path.realpath(dest)):
                            print(f"[Discovery] ⚠️  Skipping unsafe path: {member.filename}")
                            continue
                        zf.extract(member, dest)

            elif ext in (".tar", ".gz", ".bz2"):
                with tarfile.open(path, "r:*") as tf:
                    def safe_members(members):
                        for m in members:
                            member_path = os.path.realpath(
                                os.path.join(dest, m.name)
                            )
                            if not member_path.startswith(os.path.realpath(dest)):
                                print(f"[Discovery] ⚠️  Skipping unsafe path: {m.name}")
                                continue
                            yield m
                    tf.extractall(dest, members=safe_members(tf.getmembers()))

            else:
                # Unsupported archive type — copy as-is so the rest of the scan still works
                shutil.copy2(path, dest)
                return dest

        except Exception as exc:
            print(f"[Discovery] ❌ Extraction failed: {exc}")
            shutil.copy2(path, dest)
            return dest

        # Recursively extract any nested archives (one level deep only)
        for dirpath, _, filenames in os.walk(dest):
            for fname_ in filenames:
                nested_ext = os.path.splitext(fname_)[1].lower()
                if nested_ext in ARCHIVE_EXT:
                    nested_path = os.path.join(dirpath, fname_)
                    nested_dest = self._extract_archive(nested_path)
                    # Move extracted contents up
                    for item in os.listdir(nested_dest):
                        shutil.move(os.path.join(nested_dest, item), dirpath)
                    shutil.rmtree(nested_dest, ignore_errors=True)
                    os.remove(nested_path)

        print(f"[Discovery] ✅ Extracted to: {dest}")
        return dest

    # ------------------------------------------------------------------ #
    # Human-readable formatting for agents                                 #
    # ------------------------------------------------------------------ #

    def format_profile(self, profile: DatasetProfile) -> str:
        lines = [
            f"DATASET PATH  : {profile.root}",
            f"TYPE          : {'Single file' if profile.is_file else 'Directory'}",
            f"TOTAL FILES   : {len(profile.files)}",
            f"DATA TYPES    : {', '.join(profile.types_present) or 'none'}",
            f"MIXED DATASET : {'Yes' if profile.is_mixed() else 'No'}",
            f"NOTE          : Deep preview shown for up to {self.SAMPLE_PER_TYPE} sampled files per type.",
            "",
        ]

        for ftype, file_list in sorted(profile.by_type.items(), key=lambda x: x[0] != "tabular"):
            inspected = [f for f in file_list if f.preview or f.columns or f.row_count]
            skipped   = len(file_list) - len(inspected)
            lines.append(f"── {ftype.upper()} FILES ({len(file_list)} total, {len(inspected)} inspected) " + "─" * 20)
            for fi in inspected:
                rel = os.path.relpath(fi.path, profile.root)
                line = f"  📄 {rel}  ({fi.size_kb:.1f} KB)"
                if fi.row_count is not None:
                    line += f"  rows={fi.row_count:,}"
                if fi.col_count is not None:
                    line += f"  cols={fi.col_count}"
                lines.append(line)

                if fi.columns:
                    col_str = ", ".join(fi.columns[:12])
                    if len(fi.columns) > 12:
                        col_str += f" ... +{len(fi.columns) - 12} more"
                    lines.append(f"       columns : [{col_str}]")

                if fi.preview:
                    preview_lines = fi.preview.strip().split("\n")[:5]
                    lines.append("       preview :")
                    lines.extend(f"         {l[:200]}" for l in preview_lines)
                lines.append("")
            if skipped:
                lines.append(f"  ... {skipped:,} more {ftype} file(s) not shown")
                lines.append("")

        return "\n".join(lines)
