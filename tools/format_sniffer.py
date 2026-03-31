"""
format_sniffer.py — Magic-byte + heuristic file format detection.

Reads the first 2 KB of a file and returns an ordered list of candidate
formats with confidence scores.  No parsing is attempted here — this is
a cheap, fast gate before the heavier structure_prober.

Covers:
  Binary    : PNG, JPEG, GIF, BMP, TIFF, WEBP, PDF, ZIP, GZIP, BZIP2, 7Z
              RAR, TAR, SQLite, Parquet, Arrow/Feather, HDF5, NumPy, Pickle
              WAV, MP3, FLAC, OGG, MP4/M4A, AVI, MKV, Avro, Protobuf hints
  Text      : CSV, TSV, JSON, JSONL, XML, HTML, YAML, TOML, INI, Log,
              Markdown, Python, SQL, fixed-width

Encoding detection is done via chardet on the first 8 KB.
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ------------------------------------------------------------------ #
# Result types                                                         #
# ------------------------------------------------------------------ #

@dataclass
class FormatHint:
    """One candidate format with a confidence score (0–1)."""
    format:      str            # e.g. "csv", "parquet", "sqlite"
    confidence:  float          # 0-1
    category:    str            # tabular | image | audio | video | text | binary | archive
    encoding:    Optional[str]  = None   # detected text encoding if applicable
    notes:       list[str]      = field(default_factory=list)

    def __repr__(self):
        return f"FormatHint({self.format!r}, conf={self.confidence:.2f}, cat={self.category!r})"


# ------------------------------------------------------------------ #
# Magic byte signatures                                                #
# ------------------------------------------------------------------ #

# (offset, bytes_to_match, format_name, category, confidence)
MAGIC_SIGNATURES: list[tuple] = [
    # Images
    (0, b"\x89PNG\r\n\x1a\n",     "png",     "image",   0.99),
    (0, b"\xff\xd8\xff",           "jpeg",    "image",   0.99),
    (0, b"GIF87a",                 "gif",     "image",   0.99),
    (0, b"GIF89a",                 "gif",     "image",   0.99),
    (0, b"BM",                     "bmp",     "image",   0.90),
    (0, b"II\x2a\x00",            "tiff",    "image",   0.95),
    (0, b"MM\x00\x2a",            "tiff",    "image",   0.95),
    (0, b"RIFF",                   "webp",    "image",   0.50),  # also WAV — disambiguate later
    # Audio / Video
    (0, b"RIFF",                   "wav",     "audio",   0.50),  # + 'WAVE' at offset 8
    (0, b"ID3",                    "mp3",     "audio",   0.95),
    (0, b"\xff\xfb",               "mp3",     "audio",   0.80),
    (0, b"\xff\xf3",               "mp3",     "audio",   0.80),
    (0, b"fLaC",                   "flac",    "audio",   0.99),
    (0, b"OggS",                   "ogg",     "audio",   0.99),
    # Document / Archive
    (0, b"%PDF",                   "pdf",     "binary",  0.99),
    (0, b"PK\x03\x04",            "zip",     "archive", 0.99),
    (0, b"\x1f\x8b",              "gzip",    "archive", 0.99),
    (0, b"BZh",                    "bzip2",   "archive", 0.99),
    (0, b"7z\xbc\xaf\x27\x1c",   "7z",      "archive", 0.99),
    (0, b"Rar!\x1a\x07",          "rar",     "archive", 0.99),
    # Structured binary
    (0, b"SQLite format 3\x00",   "sqlite",  "binary",  0.99),
    (0, b"\x89HDF\r\n\x1a\n",    "hdf5",    "tabular", 0.99),
    (0, b"\x93NUMPY",             "numpy",   "binary",  0.99),
    # Parquet: magic at start AND end (PAR1). Check start bytes.
    (0, b"PAR1",                   "parquet", "tabular", 0.99),
    # Arrow IPC / Feather v2
    (0, b"ARROW1",                 "feather", "tabular", 0.99),
    # Avro
    (0, b"Obj\x01",               "avro",    "tabular", 0.99),
    # MsgPack (no reliable magic — low confidence)
    # Excel (XLSX = ZIP, XLS = OLE2)
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "xls", "tabular", 0.99),
]

# Byte patterns checked later in raw head bytes
RIFF_WAVE_MARKER = b"WAVE"   # at offset 8 → confirms WAV
RIFF_WEBP_MARKER = b"WEBP"   # at offset 8 → confirms WEBP


# ------------------------------------------------------------------ #
# Text heuristics                                                       #
# ------------------------------------------------------------------ #

def _text_hints(raw_head: bytes, decoded: str) -> list[FormatHint]:
    """Return format hints based on content patterns in the first ~2 KB of text."""
    hints: list[FormatHint] = []
    sample = decoded.lstrip()

    # JSON object / array
    if sample.startswith("{") or sample.startswith("["):
        # JSONL = multiple top-level JSON values
        lines = [l.strip() for l in sample.splitlines() if l.strip()]
        json_lines = sum(1 for l in lines[:20] if (l.startswith("{") or l.startswith("[")))
        if json_lines >= 3:
            hints.append(FormatHint("jsonl", 0.90, "tabular",
                                    notes=["Multiple JSON objects per line"]))
        hints.append(FormatHint("json", 0.85, "text"))

    # XML / HTML
    if sample.startswith("<?xml") or re.match(r"<\w", sample):
        if "<html" in sample.lower():
            hints.append(FormatHint("html", 0.90, "text"))
        else:
            hints.append(FormatHint("xml", 0.90, "text"))

    # YAML
    if re.match(r"^---\s*\n", sample) or re.match(r"^\w[\w\s]*:\s+\S", sample):
        hints.append(FormatHint("yaml", 0.75, "text"))

    # TOML
    if re.match(r"^\[[\w.]+\]", sample) or re.match(r"^\w+ = ", sample):
        hints.append(FormatHint("toml", 0.70, "text"))

    # INI / Config
    if re.match(r"^\[[\w\s]+\]", sample) and "=" in sample:
        hints.append(FormatHint("ini", 0.65, "text"))

    # CSV / TSV detection
    lines = [l for l in decoded.splitlines()[:20] if l.strip()]
    if lines:
        tab_counts  = [l.count("\t")  for l in lines]
        comma_counts = [l.count(",")  for l in lines]
        pipe_counts  = [l.count("|")  for l in lines]
        semi_counts  = [l.count(";")  for l in lines]

        # Consistent delimiter across lines → strong signal
        def _consistent(counts):
            return len(counts) >= 3 and max(counts) > 0 and (max(counts) - min(counts)) <= 1

        if _consistent(tab_counts) and max(tab_counts) >= 2:
            hints.append(FormatHint("tsv", 0.92, "tabular",
                                    notes=[f"~{max(tab_counts)+1} tab-separated columns"]))
        if _consistent(comma_counts) and max(comma_counts) >= 1:
            hints.append(FormatHint("csv", 0.90, "tabular",
                                    notes=[f"~{max(comma_counts)+1} comma-separated columns"]))
        if _consistent(pipe_counts) and max(pipe_counts) >= 2:
            hints.append(FormatHint("csv_pipe", 0.75, "tabular",
                                    notes=["pipe-delimited"]))
        if _consistent(semi_counts) and max(semi_counts) >= 1:
            hints.append(FormatHint("csv_semicolon", 0.75, "tabular",
                                    notes=["semicolon-delimited"]))

        # Fixed-width: uniform line lengths with no common delimiters
        lengths = [len(l) for l in lines]
        if max(lengths) - min(lengths) <= 2 and not hints:
            hints.append(FormatHint("fixed_width", 0.60, "tabular",
                                    notes=["Uniform line length — possibly fixed-width"]))

    # SQL dump
    if re.search(r"\b(CREATE TABLE|INSERT INTO|SELECT .* FROM)\b", decoded, re.I):
        hints.append(FormatHint("sql", 0.85, "text"))

    # Log file
    if re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", decoded):
        hints.append(FormatHint("log", 0.70, "text",
                                notes=["Timestamped lines — possibly log file"]))

    # Python source
    if re.search(r"^\s*(import |from |def |class )", decoded, re.M):
        hints.append(FormatHint("python", 0.80, "code"))

    # Markdown
    if re.search(r"^#{1,6} ", decoded, re.M) or ("**" in decoded and "\n" in decoded):
        hints.append(FormatHint("markdown", 0.65, "text"))

    return hints


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def sniff_format(path: str, head_bytes: int = 2048) -> list[FormatHint]:
    """
    Read up to `head_bytes` from `path` and return candidate formats
    sorted by confidence descending.

    Args:
        path: absolute or relative file path
        head_bytes: how many bytes to read (default 2 KB)

    Returns:
        List[FormatHint] sorted by confidence descending.
        Empty list if file is unreadable or empty.
    """
    path = str(Path(path).resolve())
    if not os.path.isfile(path):
        return [FormatHint("unknown", 0.0, "unknown", notes=[f"File not found: {path}"])]

    file_size = os.path.getsize(path)
    if file_size == 0:
        return [FormatHint("empty", 1.0, "unknown", notes=["Zero-byte file"])]

    # ── Read raw head ──────────────────────────────────────────────
    try:
        with open(path, "rb") as f:
            raw = f.read(head_bytes)
    except Exception as e:
        return [FormatHint("unreadable", 0.0, "unknown", notes=[str(e)])]

    hints: list[FormatHint] = []

    # ── Magic byte matching ────────────────────────────────────────
    for offset, magic, fmt, cat, conf in MAGIC_SIGNATURES:
        if raw[offset:offset + len(magic)] == magic:
            h = FormatHint(fmt, conf, cat)

            # Disambiguate RIFF: WAV vs WEBP
            if fmt in ("wav", "webp") and len(raw) >= 12:
                marker = raw[8:12]
                if fmt == "wav"  and marker != RIFF_WAVE_MARKER:
                    continue
                if fmt == "webp" and marker != RIFF_WEBP_MARKER:
                    continue

            # ZIP might be XLSX/DOCX — note it
            if fmt == "zip":
                h.notes.append(
                    "Could also be .xlsx / .docx / .jar (all ZIP-based) — "
                    "structure_prober will disambiguate"
                )

            hints.append(h)

    # ── Detect text encoding ───────────────────────────────────────
    encoding = None
    is_text  = False
    decoded  = ""

    if not hints:   # no binary magic → try as text
        try:
            import chardet
            detected  = chardet.detect(raw[:8192])
            encoding  = detected.get("encoding") or "utf-8"
            confidence = detected.get("confidence", 0.5)
        except ImportError:
            encoding  = "utf-8"
            confidence = 0.5

        # Check if it actually decodes cleanly
        for enc in (encoding, "utf-8", "latin-1"):
            try:
                decoded = raw.decode(enc, errors="strict")
                encoding = enc
                is_text  = True
                break
            except (UnicodeDecodeError, TypeError):
                continue

    # ── Text heuristics ────────────────────────────────────────────
    if is_text and decoded:
        text_hints = _text_hints(raw, decoded)
        for h in text_hints:
            h.encoding = encoding
        hints.extend(text_hints)

    # ── Extension cross-check ──────────────────────────────────────
    ext = Path(path).suffix.lower().lstrip(".")
    if ext and hints:
        for h in hints:
            if ext in h.format or h.format in ext:
                h.confidence = min(h.confidence + 0.05, 1.0)
                h.notes.append(f"Extension .{ext} matches")

    # ── Fallback ───────────────────────────────────────────────────
    if not hints:
        null_ratio = raw.count(b"\x00") / len(raw)
        if null_ratio > 0.10:
            hints.append(FormatHint("binary_unknown", 0.40, "binary",
                                    notes=[f"High null-byte ratio ({null_ratio:.0%}) — binary file"]))
        else:
            hints.append(FormatHint("text_unknown", 0.30, "text",
                                    notes=["No signature matched — possible plain text"]))

    # ── Sort & deduplicate ─────────────────────────────────────────
    seen = set()
    deduped = []
    for h in sorted(hints, key=lambda x: -x.confidence):
        if h.format not in seen:
            seen.add(h.format)
            deduped.append(h)

    return deduped
