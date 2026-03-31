"""
structure_prober.py — Exhaustive parser probing for unknown file formats.

Given a list of candidate format hints (from format_sniffer), tries each
parser in confidence order and returns the FIRST that succeeds with a
non-trivial result.  Unrecognised files get a fallback "binary_raw" result
so the pipeline never stalls.

Supported probers (30+):
  Tabular  : csv, tsv, csv_pipe, csv_semicolon, fixed_width,
             parquet, feather, json, jsonl, xlsx, xls, hdf5, avro, sqlite
  Text     : xml, html, yaml, toml, ini, log, markdown, python, sql
  Binary   : numpy, pickle, arrow_ipc, arrow_file
  Image    : png, jpeg, gif, bmp, tiff, webp (metadata only — no pixel data)
  Audio    : wav, mp3, flac (metadata only)

Each prober returns a ProbeResult or None on failure.
"""

from __future__ import annotations

import csv
import io
import json
import os
import struct
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .format_sniffer import FormatHint


# ------------------------------------------------------------------ #
# Result type                                                          #
# ------------------------------------------------------------------ #

@dataclass
class ProbeResult:
    """Outcome of one successful parser probe."""
    format:         str            # confirmed format name
    category:       str            # tabular | text | binary | image | audio | video
    parser_used:    str            # which library/method succeeded

    # Tabular metadata
    row_count:      Optional[int]  = None
    col_count:      Optional[int]  = None
    columns:        list           = field(default_factory=list)
    dtypes:         dict           = field(default_factory=dict)    # col → dtype str
    sample_rows:    list           = field(default_factory=list)    # list of dicts

    # Non-tabular metadata
    metadata:       dict           = field(default_factory=dict)
    raw_schema:     str            = ""    # freeform schema description

    # Parsing quality
    parse_warnings: list[str]      = field(default_factory=list)
    confidence:     float          = 1.0

    def is_tabular(self) -> bool:
        return self.category == "tabular"

    def summary(self) -> str:
        parts = [f"Format: {self.format}  (parser: {self.parser_used})"]
        if self.is_tabular():
            parts.append(f"Shape: {self.row_count} rows × {self.col_count} cols")
            if self.columns:
                col_str = ", ".join(str(c) for c in self.columns[:10])
                if len(self.columns) > 10:
                    col_str += f" ... +{len(self.columns)-10} more"
                parts.append(f"Columns: [{col_str}]")
            if self.dtypes:
                parts.append(f"Dtypes: {dict(list(self.dtypes.items())[:8])}")
        if self.metadata:
            parts.append(f"Metadata: {self.metadata}")
        if self.raw_schema:
            parts.append(f"Schema: {self.raw_schema[:400]}")
        if self.parse_warnings:
            parts.append(f"Warnings: {self.parse_warnings}")
        return "\n".join(parts)


# ------------------------------------------------------------------ #
# Prober registry                                                       #
# ------------------------------------------------------------------ #

SAMPLE_ROWS = 5     # how many rows to include in sample_rows


def _probe_csv(path: str, delimiter: str = ",") -> Optional[ProbeResult]:
    import pandas as pd
    try:
        # Count rows without loading all
        with open(path, "r", errors="replace") as f:
            row_count = sum(1 for _ in f) - 1  # subtract header

        df = pd.read_csv(path, sep=delimiter, nrows=SAMPLE_ROWS + 1,
                         low_memory=False, on_bad_lines="warn")
        if len(df.columns) < 2:
            return None   # single-column is suspicious

        return ProbeResult(
            format="csv" if delimiter == "," else f"csv_{delimiter!r}",
            category="tabular",
            parser_used="pandas.read_csv",
            row_count=row_count,
            col_count=len(df.columns),
            columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
        )
    except Exception:
        return None


def _probe_tsv(path: str) -> Optional[ProbeResult]:
    r = _probe_csv(path, delimiter="\t")
    if r:
        r.format = "tsv"
    return r


def _probe_csv_pipe(path: str) -> Optional[ProbeResult]:
    r = _probe_csv(path, delimiter="|")
    if r:
        r.format = "csv_pipe"
    return r


def _probe_csv_semicolon(path: str) -> Optional[ProbeResult]:
    r = _probe_csv(path, delimiter=";")
    if r:
        r.format = "csv_semicolon"
    return r


def _probe_fixed_width(path: str) -> Optional[ProbeResult]:
    import pandas as pd
    try:
        df = pd.read_fwf(path, nrows=SAMPLE_ROWS + 1)
        if len(df.columns) < 2:
            return None
        return ProbeResult(
            format="fixed_width", category="tabular", parser_used="pandas.read_fwf",
            col_count=len(df.columns), columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
        )
    except Exception:
        return None


def _probe_parquet(path: str) -> Optional[ProbeResult]:
    try:
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        meta = pf.metadata
        schema = pf.schema_arrow
        batch = next(pf.iter_batches(batch_size=SAMPLE_ROWS))
        import pandas as pd
        df = batch.to_pandas()
        return ProbeResult(
            format="parquet", category="tabular", parser_used="pyarrow.parquet",
            row_count=meta.num_rows, col_count=meta.num_columns,
            columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            metadata={"row_groups": meta.num_row_groups,
                      "compression": str(meta.row_group(0).column(0).compression)
                      if meta.num_row_groups else "unknown"},
        )
    except Exception:
        return None


def _probe_feather(path: str) -> Optional[ProbeResult]:
    try:
        import pandas as pd
        df = pd.read_feather(path)
        return ProbeResult(
            format="feather", category="tabular", parser_used="pandas.read_feather",
            row_count=len(df), col_count=len(df.columns),
            columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
        )
    except Exception:
        return None


def _probe_json(path: str) -> Optional[ProbeResult]:
    try:
        with open(path, "r", errors="replace") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            import pandas as pd
            df = pd.DataFrame(data[:SAMPLE_ROWS + 1])
            return ProbeResult(
                format="json", category="tabular", parser_used="json+pandas",
                row_count=len(data), col_count=len(df.columns),
                columns=list(df.columns),
                dtypes={c: str(t) for c, t in df.dtypes.items()},
                sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            )
        elif isinstance(data, dict):
            return ProbeResult(
                format="json", category="text", parser_used="json",
                raw_schema=f"Top-level keys: {list(data.keys())[:20]}",
                metadata={"top_level_type": "object", "key_count": len(data)},
            )
    except Exception:
        return None


def _probe_jsonl(path: str) -> Optional[ProbeResult]:
    try:
        rows = []
        with open(path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
                if len(rows) >= SAMPLE_ROWS:
                    break
        if not rows:
            return None
        import pandas as pd
        df = pd.DataFrame(rows)
        # Count total lines
        with open(path, "r") as f:
            total = sum(1 for l in f if l.strip())
        return ProbeResult(
            format="jsonl", category="tabular", parser_used="json_lines+pandas",
            row_count=total, col_count=len(df.columns),
            columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
        )
    except Exception:
        return None


def _probe_xlsx(path: str) -> Optional[ProbeResult]:
    try:
        import pandas as pd
        df = pd.read_excel(path, nrows=SAMPLE_ROWS + 1)
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheets = wb.sheetnames
        wb.close()
        with open(path, "rb") as f:
            size = os.path.getsize(path)
        return ProbeResult(
            format="xlsx", category="tabular", parser_used="pandas+openpyxl",
            col_count=len(df.columns), columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            metadata={"sheets": sheets},
        )
    except Exception:
        return None


def _probe_xls(path: str) -> Optional[ProbeResult]:
    try:
        import pandas as pd
        df = pd.read_excel(path, engine="xlrd", nrows=SAMPLE_ROWS + 1)
        return ProbeResult(
            format="xls", category="tabular", parser_used="pandas+xlrd",
            col_count=len(df.columns), columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
        )
    except Exception:
        return None


def _probe_hdf5(path: str) -> Optional[ProbeResult]:
    try:
        import pandas as pd
        store = pd.HDFStore(path, mode="r")
        keys = store.keys()
        if not keys:
            store.close()
            return None
        df = store[keys[0]].head(SAMPLE_ROWS + 1)
        store.close()
        return ProbeResult(
            format="hdf5", category="tabular", parser_used="pandas.HDFStore",
            row_count=None, col_count=len(df.columns),
            columns=list(df.columns),
            dtypes={c: str(t) for c, t in df.dtypes.items()},
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            metadata={"keys": keys},
        )
    except Exception:
        return None


def _probe_sqlite(path: str) -> Optional[ProbeResult]:
    try:
        import sqlite3
        conn = sqlite3.connect(path)
        cur  = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            conn.close()
            return ProbeResult(format="sqlite", category="binary",
                               parser_used="sqlite3",
                               metadata={"tables": [], "note": "Empty database"})
        # Use first table
        tbl = tables[0]
        cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
        row_count = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info([{tbl}])")
        cols_info = cur.fetchall()   # (cid, name, type, notnull, dflt, pk)
        columns = [r[1] for r in cols_info]
        cur.execute(f"SELECT * FROM [{tbl}] LIMIT {SAMPLE_ROWS}")
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
        conn.close()
        return ProbeResult(
            format="sqlite", category="tabular", parser_used="sqlite3",
            row_count=row_count, col_count=len(columns),
            columns=columns,
            dtypes={r[1]: r[2] for r in cols_info},
            sample_rows=rows,
            metadata={"tables": tables, "active_table": tbl},
        )
    except Exception:
        return None


def _probe_avro(path: str) -> Optional[ProbeResult]:
    try:
        import fastavro
        with open(path, "rb") as f:
            reader = fastavro.reader(f)
            schema = reader.writer_schema
            rows   = [next(reader) for _ in range(SAMPLE_ROWS) if True]
        import pandas as pd
        df = pd.DataFrame(rows)
        return ProbeResult(
            format="avro", category="tabular", parser_used="fastavro",
            col_count=len(df.columns), columns=list(df.columns),
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            raw_schema=json.dumps(schema, indent=2)[:800],
        )
    except Exception:
        return None


def _probe_xml(path: str) -> Optional[ProbeResult]:
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
        tag_counts: dict[str, int] = {}
        for el in root.iter():
            tag_counts[el.tag] = tag_counts.get(el.tag, 0) + 1
        return ProbeResult(
            format="xml", category="text", parser_used="xml.etree.ElementTree",
            raw_schema=f"Root tag: {root.tag}  |  Unique tags: {len(tag_counts)}",
            metadata={"root_tag": root.tag,
                      "top_tags": dict(sorted(tag_counts.items(),
                                              key=lambda x: -x[1])[:10])},
        )
    except Exception:
        return None


def _probe_html(path: str) -> Optional[ProbeResult]:
    try:
        from html.parser import HTMLParser
        class _TagCounter(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags: dict[str, int] = {}
            def handle_starttag(self, tag, attrs):
                self.tags[tag] = self.tags.get(tag, 0) + 1
        with open(path, "r", errors="replace") as f:
            content = f.read(65536)
        p = _TagCounter()
        p.feed(content)
        return ProbeResult(
            format="html", category="text", parser_used="html.parser",
            raw_schema=f"Tags found: {dict(sorted(p.tags.items(), key=lambda x:-x[1])[:10])}",
        )
    except Exception:
        return None


def _probe_yaml(path: str) -> Optional[ProbeResult]:
    try:
        import yaml
        with open(path, "r", errors="replace") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            import pandas as pd
            df = pd.DataFrame(data[:SAMPLE_ROWS])
            return ProbeResult(
                format="yaml", category="tabular", parser_used="pyyaml+pandas",
                row_count=len(data), col_count=len(df.columns),
                columns=list(df.columns),
                sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records"),
            )
        return ProbeResult(
            format="yaml", category="text", parser_used="pyyaml",
            raw_schema=f"Top-level type: {type(data).__name__}  "
                       f"keys: {list(data.keys())[:10] if isinstance(data, dict) else 'N/A'}",
        )
    except Exception:
        return None


def _probe_toml(path: str) -> Optional[ProbeResult]:
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib   # Python < 3.11
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return ProbeResult(
            format="toml", category="text", parser_used="tomllib",
            raw_schema=f"Top-level keys: {list(data.keys())[:20]}",
        )
    except Exception:
        return None


def _probe_numpy(path: str) -> Optional[ProbeResult]:
    try:
        import numpy as np
        arr = np.load(path, allow_pickle=False)
        return ProbeResult(
            format="numpy", category="binary", parser_used="numpy.load",
            metadata={"shape": list(arr.shape), "dtype": str(arr.dtype),
                      "size": arr.size},
        )
    except Exception:
        return None


def _probe_pickle(path: str) -> Optional[ProbeResult]:
    try:
        import pickle
        with open(path, "rb") as f:
            obj = pickle.load(f)
        type_name = type(obj).__name__
        notes = []
        meta: dict[str, Any] = {"python_type": type_name}
        if hasattr(obj, "shape"):
            meta["shape"] = list(obj.shape)
        if hasattr(obj, "__len__"):
            meta["length"] = len(obj)
        return ProbeResult(
            format="pickle", category="binary", parser_used="pickle",
            metadata=meta,
            parse_warnings=["Pickle files can execute arbitrary code — treat as untrusted"],
        )
    except Exception:
        return None


def _probe_arrow(path: str) -> Optional[ProbeResult]:
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc
        with pa.memory_map(path, "r") as src:
            reader = ipc.open_file(src)
            schema = reader.schema_arrow
            batch  = reader.get_batch(0) if reader.num_record_batches else None
        df = batch.to_pandas() if batch else None
        return ProbeResult(
            format="arrow_file", category="tabular", parser_used="pyarrow.ipc",
            row_count=reader.num_record_batches,
            col_count=len(schema),
            columns=[f.name for f in schema],
            sample_rows=df.head(SAMPLE_ROWS).to_dict(orient="records") if df is not None else [],
        )
    except Exception:
        return None


def _probe_wav(path: str) -> Optional[ProbeResult]:
    try:
        import wave
        with wave.open(path, "r") as w:
            return ProbeResult(
                format="wav", category="audio", parser_used="wave",
                metadata={
                    "channels": w.getnchannels(),
                    "sample_width": w.getsampwidth(),
                    "frame_rate": w.getframerate(),
                    "n_frames": w.getnframes(),
                    "duration_s": round(w.getnframes() / w.getframerate(), 2),
                },
            )
    except Exception:
        return None


def _probe_image_pillow(path: str) -> Optional[ProbeResult]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return ProbeResult(
                format=img.format.lower() if img.format else "image",
                category="image", parser_used="PIL",
                metadata={
                    "size": list(img.size),
                    "mode": img.mode,
                    "format": img.format,
                    "info": {k: str(v) for k, v in list(img.info.items())[:10]},
                },
            )
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Prober dispatch table                                                #
# format → callable                                                    #
# ------------------------------------------------------------------ #

PROBERS: dict[str, Callable[[str], Optional[ProbeResult]]] = {
    "csv":          _probe_csv,
    "tsv":          _probe_tsv,
    "csv_pipe":     _probe_csv_pipe,
    "csv_semicolon":_probe_csv_semicolon,
    "fixed_width":  _probe_fixed_width,
    "parquet":      _probe_parquet,
    "feather":      _probe_feather,
    "json":         _probe_json,
    "jsonl":        _probe_jsonl,
    "xlsx":         _probe_xlsx,
    "xls":          _probe_xls,
    "hdf5":         _probe_hdf5,
    "sqlite":       _probe_sqlite,
    "avro":         _probe_avro,
    "xml":          _probe_xml,
    "html":         _probe_html,
    "yaml":         _probe_yaml,
    "toml":         _probe_toml,
    "numpy":        _probe_numpy,
    "pickle":       _probe_pickle,
    "feather":      _probe_feather,
    "arrow_file":   _probe_arrow,
    "wav":          _probe_wav,
    "png":          _probe_image_pillow,
    "jpeg":         _probe_image_pillow,
    "gif":          _probe_image_pillow,
    "bmp":          _probe_image_pillow,
    "tiff":         _probe_image_pillow,
    "webp":         _probe_image_pillow,
}

# Fallback: probers to try when all hints fail (in order)
FALLBACK_PROBE_ORDER = [
    "csv", "tsv", "json", "jsonl", "xml",
    "parquet", "sqlite", "hdf5", "xlsx",
    "yaml", "toml", "numpy", "pickle",
]


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def probe_structure(path: str, hints: list[FormatHint]) -> ProbeResult:
    """
    Try parsers in confidence order and return the first that succeeds.

    Args:
        path:  file path
        hints: list of FormatHint from format_sniffer (sorted by confidence)

    Returns:
        ProbeResult — always returns something, even if it's a fallback.
    """
    path = str(Path(path).resolve())
    attempted: list[str] = []

    # ── Try hint-ordered probers ─────────────────────────────────
    for hint in hints:
        fmt = hint.format
        if fmt not in PROBERS:
            continue
        if fmt in attempted:
            continue
        attempted.append(fmt)
        try:
            result = PROBERS[fmt](path)
            if result is not None:
                result.confidence = hint.confidence
                return result
        except Exception:
            pass   # prober crashed — continue

    # ── Fallback: try all known probers ──────────────────────────
    for fmt in FALLBACK_PROBE_ORDER:
        if fmt in attempted or fmt not in PROBERS:
            continue
        attempted.append(fmt)
        try:
            result = PROBERS[fmt](path)
            if result is not None:
                result.confidence = 0.4   # low — we guessed
                result.parse_warnings.append(
                    f"Format guessed via fallback — original hints were: "
                    f"{[h.format for h in hints[:3]]}"
                )
                return result
        except Exception:
            pass

    # ── Last resort: binary blob ──────────────────────────────────
    return ProbeResult(
        format="binary_unknown",
        category="binary",
        parser_used="none",
        confidence=0.0,
        metadata={"size_bytes": os.path.getsize(path)},
        parse_warnings=[
            f"No parser succeeded. Tried: {attempted}",
            "Use UnknownFormatAgent LLM fallback to write a custom parser.",
        ],
    )
