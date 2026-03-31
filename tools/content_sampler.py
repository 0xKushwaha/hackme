"""
content_sampler.py — Raw content extraction in multiple views.

Provides five complementary lenses on any file so the UnknownFormatAgent
(and any LLM reasoning about the file) has rich context without loading
the whole file into memory:

  hex_dump      — first N bytes as annotated hex (like `xxd`)
  text_sample   — decoded text head + tail (good for CSVs, logs, XML)
  binary_stats  — entropy, null ratio, printable ratio, byte histogram
  line_profile  — line length stats, delimiter counts (tabular hinting)
  structure_peek — try a handful of lightweight structural checks

All reads are bounded and safe — never loads more than MAX_SAMPLE_BYTES.
"""

from __future__ import annotations

import math
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


MAX_SAMPLE_BYTES = 64 * 1024   # 64 KB ceiling


# ------------------------------------------------------------------ #
# Result type                                                          #
# ------------------------------------------------------------------ #

@dataclass
class ContentSample:
    path:           str
    file_size:      int

    # Hex view
    hex_dump:       str   = ""   # annotated hex of first 256 bytes

    # Text view
    text_head:      str   = ""   # first ~2 KB decoded
    text_tail:      str   = ""   # last ~1 KB decoded (useful for detecting footers)
    detected_encoding: Optional[str] = None
    text_confidence: float = 0.0

    # Binary stats
    entropy:        float = 0.0   # Shannon entropy 0–8
    null_ratio:     float = 0.0
    printable_ratio:float = 0.0
    byte_histogram: dict  = field(default_factory=dict)   # top-10 most frequent bytes

    # Line profile (text files)
    line_count:     int   = 0
    avg_line_len:   float = 0.0
    max_line_len:   int   = 0
    delimiter_counts: dict = field(default_factory=dict)  # {",": 42, "\t": 0, ...}

    # Structural peek results
    structure_notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-paragraph human-readable summary for agent context."""
        parts = [
            f"File: {os.path.basename(self.path)}  ({self.file_size:,} bytes)",
            f"Entropy: {self.entropy:.2f}/8.0  |  "
            f"Null ratio: {self.null_ratio:.1%}  |  "
            f"Printable: {self.printable_ratio:.1%}",
        ]
        if self.detected_encoding:
            parts.append(f"Encoding: {self.detected_encoding} (conf {self.text_confidence:.0%})")
        if self.line_count:
            parts.append(
                f"Lines: {self.line_count:,}  avg_len={self.avg_line_len:.0f}  "
                f"max_len={self.max_line_len}"
            )
        if self.delimiter_counts:
            dc = {k: v for k, v in self.delimiter_counts.items() if v > 0}
            if dc:
                parts.append(f"Delimiters per line: {dc}")
        if self.structure_notes:
            parts.append("Notes: " + " | ".join(self.structure_notes))
        if self.text_head:
            preview = self.text_head[:300].replace("\n", "↵")
            parts.append(f"Text preview: {preview!r}")
        return "\n".join(parts)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _entropy(data: bytes) -> float:
    """Shannon entropy in bits (0 = all same byte, 8 = fully random)."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq if c > 0)


def _hex_dump(data: bytes, max_bytes: int = 256) -> str:
    """xxd-style annotated hex dump."""
    lines = []
    chunk = data[:max_bytes]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        hex_part  = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{i:08x}  {hex_part:<48}  |{ascii_part}|")
    if len(data) > max_bytes:
        lines.append(f"... ({len(data) - max_bytes} more bytes not shown)")
    return "\n".join(lines)


def _decode_safe(raw: bytes, encoding: str = "utf-8") -> str:
    try:
        return raw.decode(encoding, errors="replace")
    except Exception:
        return raw.decode("latin-1", errors="replace")


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def sample_content(path: str, sample_bytes: int = MAX_SAMPLE_BYTES) -> ContentSample:
    """
    Return a ContentSample with multiple views of the file.

    Args:
        path: file path (absolute or relative)
        sample_bytes: cap on bytes read (default 64 KB)

    Returns:
        ContentSample dataclass
    """
    path     = str(Path(path).resolve())
    file_size = os.path.getsize(path) if os.path.isfile(path) else 0
    cs = ContentSample(path=path, file_size=file_size)

    if not os.path.isfile(path) or file_size == 0:
        cs.structure_notes.append("File missing or empty")
        return cs

    # ── Read raw sample ───────────────────────────────────────────
    read_size = min(sample_bytes, file_size)
    with open(path, "rb") as f:
        raw_head = f.read(read_size)

    # Read tail separately (last 1 KB) if file is bigger than head
    raw_tail = b""
    if file_size > read_size + 1024:
        with open(path, "rb") as f:
            f.seek(max(0, file_size - 1024))
            raw_tail = f.read(1024)

    # ── Binary stats ───────────────────────────────────────────────
    cs.entropy        = _entropy(raw_head)
    cs.null_ratio     = raw_head.count(b"\x00") / len(raw_head)
    cs.printable_ratio = sum(32 <= b < 127 for b in raw_head) / len(raw_head)

    from collections import Counter
    freq = Counter(raw_head)
    cs.byte_histogram = {f"0x{b:02x}": c for b, c in freq.most_common(10)}

    # ── Hex dump ───────────────────────────────────────────────────
    cs.hex_dump = _hex_dump(raw_head)

    # ── Encoding detection ─────────────────────────────────────────
    encoding = "utf-8"
    try:
        import chardet
        det = chardet.detect(raw_head[:8192])
        encoding = det.get("encoding") or "utf-8"
        cs.detected_encoding  = encoding
        cs.text_confidence    = det.get("confidence", 0.0)
    except ImportError:
        cs.detected_encoding  = "utf-8"
        cs.text_confidence    = 0.5

    # ── Text views ─────────────────────────────────────────────────
    if cs.printable_ratio > 0.70:   # likely text
        cs.text_head = _decode_safe(raw_head[:4096], encoding)
        if raw_tail:
            cs.text_tail = _decode_safe(raw_tail, encoding)

        # Line profile
        lines = cs.text_head.splitlines()
        cs.line_count   = lines.__len__()
        lens = [len(l) for l in lines if l]
        if lens:
            cs.avg_line_len = sum(lens) / len(lens)
            cs.max_line_len = max(lens)

        # Delimiter counts (per-line average)
        delimiters = {",": 0, "\t": 0, "|": 0, ";": 0}
        for l in lines[:50]:
            for d in delimiters:
                delimiters[d] += l.count(d)
        n = max(len(lines[:50]), 1)
        cs.delimiter_counts = {d: round(c / n, 1) for d, c in delimiters.items()}

    # ── Structural peek ────────────────────────────────────────────
    notes = cs.structure_notes

    # Entropy interpretation
    if cs.entropy > 7.5:
        notes.append("Very high entropy — likely compressed or encrypted")
    elif cs.entropy > 6.0:
        notes.append("High entropy — binary or dense numeric data")
    elif cs.entropy < 2.0 and file_size > 100:
        notes.append("Very low entropy — highly repetitive or sparse data")

    # Parquet footer magic at end
    if file_size >= 8:
        with open(path, "rb") as f:
            f.seek(-8, 2)
            footer = f.read(8)
        if footer[-4:] == b"PAR1":
            notes.append("Parquet footer magic (PAR1) found at end of file")

    # SQLite check
    if raw_head[:16] == b"SQLite format 3\x00":
        page_size = struct.unpack(">H", raw_head[16:18])[0]
        notes.append(f"SQLite3 database — page size {page_size} bytes")

    # ZIP-based office formats (XLSX, DOCX, etc.)
    if raw_head[:4] == b"PK\x03\x04":
        # Look for [Content_Types].xml inside
        if b"[Content_Types]" in raw_head or b"xl/" in raw_head:
            notes.append("ZIP contains Office XML — likely .xlsx or .docx")
        elif b"AndroidManifest" in raw_head:
            notes.append("ZIP contains AndroidManifest — likely .apk")
        else:
            notes.append("Generic ZIP archive")

    # Pickle protocol
    if len(raw_head) >= 2 and raw_head[0] == 0x80 and raw_head[1] in range(1, 6):
        notes.append(f"Python pickle protocol {raw_head[1]}")

    # NumPy .npy
    if raw_head[:6] == b"\x93NUMPY":
        ver = f"{raw_head[6]}.{raw_head[7]}"
        notes.append(f"NumPy array format version {ver}")

    # HDF5
    if raw_head[:8] == b"\x89HDF\r\n\x1a\n":
        notes.append("HDF5 hierarchical data format")

    # Arrow IPC stream
    if raw_head[:4] == b"\xff\xff\xff\xff":
        notes.append("Possible Arrow IPC stream (continuation marker)")

    return cs
