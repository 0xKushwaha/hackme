"""
schema_extractor.py — Deep schema extraction from a ProbeResult.

Takes a successfully probed file and produces a rich SchemaReport:
  - Per-column statistics (cardinality, nulls, range, top values)
  - Inferred semantic types (ID, timestamp, target, categorical, numeric, text)
  - Relationships (potential FK columns, datetime index)
  - Agent routing hints for the rest of the pipeline

This is one step deeper than DataProfiler — it's called specifically when
the file format was previously unrecognised and we need to teach the pipeline
what it's dealing with.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .structure_prober import ProbeResult


# ------------------------------------------------------------------ #
# Semantic type labels                                                  #
# ------------------------------------------------------------------ #

SEMANTIC_ID          = "identifier"
SEMANTIC_TIMESTAMP   = "timestamp"
SEMANTIC_CATEGORICAL = "categorical"
SEMANTIC_NUMERIC     = "numeric"
SEMANTIC_TARGET      = "target_candidate"
SEMANTIC_TEXT        = "free_text"
SEMANTIC_BINARY_FLAG = "binary_flag"
SEMANTIC_CONSTANT    = "constant"


# ------------------------------------------------------------------ #
# Result type                                                          #
# ------------------------------------------------------------------ #

@dataclass
class ColumnSchema:
    name:           str
    dtype:          str
    semantic_type:  str         # one of the SEMANTIC_* constants above
    null_pct:       float       = 0.0
    unique_count:   int         = 0
    top_values:     list        = field(default_factory=list)   # [(value, count)]
    value_range:    Optional[tuple] = None   # (min, max) for numeric
    sample_values:  list        = field(default_factory=list)
    notes:          list[str]   = field(default_factory=list)


@dataclass
class SchemaReport:
    format:         str
    category:       str
    parser_used:    str

    # Tabular schema
    row_count:      Optional[int]    = None
    col_count:      Optional[int]    = None
    columns:        list[ColumnSchema] = field(default_factory=list)

    # Non-tabular
    raw_description: str = ""

    # Routing output for the pipeline
    routing_hints:  dict   = field(default_factory=dict)
    target_candidates: list[str] = field(default_factory=list)
    datetime_cols:  list[str]    = field(default_factory=list)
    id_cols:        list[str]    = field(default_factory=list)

    # Human-readable summary
    summary_text:   str   = ""

    def to_dict(self) -> dict:
        return {
            "format":    self.format,
            "category":  self.category,
            "row_count": self.row_count,
            "col_count": self.col_count,
            "target_candidates": self.target_candidates,
            "datetime_cols":     self.datetime_cols,
            "id_cols":           self.id_cols,
            "routing_hints":     self.routing_hints,
            "columns": [
                {
                    "name":          c.name,
                    "dtype":         c.dtype,
                    "semantic_type": c.semantic_type,
                    "null_pct":      round(c.null_pct, 4),
                    "unique_count":  c.unique_count,
                    "top_values":    c.top_values[:5],
                    "value_range":   list(c.value_range) if c.value_range else None,
                }
                for c in self.columns
            ],
        }


# ------------------------------------------------------------------ #
# Semantic type inference                                              #
# ------------------------------------------------------------------ #

_ID_KEYWORDS        = ("id", "_id", "uuid", "key", "index", "pk", "code")
_TIMESTAMP_KEYWORDS = ("date", "time", "timestamp", "year", "month", "week",
                       "created", "updated", "ts", "dt")
_TARGET_KEYWORDS    = ("label", "target", "class", "y", "output", "result",
                       "response", "survived", "churn", "default", "fraud",
                       "price", "sale", "revenue", "score")


def _infer_semantic(col_name: str, dtype: str, unique_count: int,
                    total_rows: int, sample_vals: list) -> str:
    cn = col_name.lower()

    # Constant column
    if unique_count <= 1:
        return SEMANTIC_CONSTANT

    # ID / key column
    if any(cn == kw or cn.endswith(kw) for kw in _ID_KEYWORDS):
        if unique_count / max(total_rows, 1) > 0.90:
            return SEMANTIC_ID

    # Timestamp
    if any(kw in cn for kw in _TIMESTAMP_KEYWORDS):
        return SEMANTIC_TIMESTAMP
    if "datetime" in dtype or "timestamp" in dtype:
        return SEMANTIC_TIMESTAMP

    # Binary flag
    if unique_count == 2:
        vals = {str(v).lower() for v in sample_vals}
        if vals <= {"0", "1"} or vals <= {"true", "false"} or vals <= {"yes", "no"}:
            return SEMANTIC_BINARY_FLAG

    # Target candidate
    if any(kw in cn for kw in _TARGET_KEYWORDS):
        return SEMANTIC_TARGET

    # Numeric
    if any(t in dtype for t in ("int", "float", "double", "decimal", "number")):
        cardinality_ratio = unique_count / max(total_rows, 1)
        if cardinality_ratio > 0.90:
            return SEMANTIC_NUMERIC   # high-cardinality numeric — possibly ID
        return SEMANTIC_NUMERIC

    # Free text (long strings)
    if sample_vals:
        avg_len = sum(len(str(v)) for v in sample_vals) / len(sample_vals)
        if avg_len > 50:
            return SEMANTIC_TEXT

    # Categorical
    cardinality_ratio = unique_count / max(total_rows, 1)
    if cardinality_ratio < 0.05 or unique_count <= 30:
        return SEMANTIC_CATEGORICAL

    return SEMANTIC_TEXT


# ------------------------------------------------------------------ #
# Column statistics                                                     #
# ------------------------------------------------------------------ #

def _col_stats(series, total_rows: int) -> tuple:
    """Return (null_pct, unique_count, top_values, value_range, sample_vals)."""
    try:
        import pandas as pd
        null_pct     = float(series.isnull().mean())
        unique_count = int(series.nunique())
        top_values   = []
        value_range  = None
        sample_vals  = series.dropna().head(10).tolist()

        # Top value counts
        vc = series.value_counts().head(5)
        top_values = [(str(v), int(c)) for v, c in vc.items()]

        # Numeric range
        import numpy as np
        if pd.api.types.is_numeric_dtype(series):
            s = series.dropna()
            if len(s):
                value_range = (float(s.min()), float(s.max()))

        return null_pct, unique_count, top_values, value_range, sample_vals
    except Exception:
        return 0.0, 0, [], None, []


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def extract_schema(path: str, probe: ProbeResult) -> SchemaReport:
    """
    Build a deep SchemaReport from a ProbeResult.

    For tabular formats: loads a sample, computes per-column statistics,
    infers semantic types, and produces routing hints.

    For non-tabular: formats the metadata into a readable description.

    Args:
        path:  file path
        probe: ProbeResult from structure_prober.probe_structure()

    Returns:
        SchemaReport
    """
    report = SchemaReport(
        format=probe.format,
        category=probe.category,
        parser_used=probe.parser_used,
        row_count=probe.row_count,
        col_count=probe.col_count,
    )

    # ── Non-tabular: just format the metadata ──────────────────────
    if not probe.is_tabular():
        report.raw_description = (
            f"Format: {probe.format}  (category: {probe.category})\n"
            + (f"Schema: {probe.raw_schema}\n" if probe.raw_schema else "")
            + (f"Metadata: {json.dumps(probe.metadata, indent=2, default=str)[:800]}\n")
        )
        report.summary_text = report.raw_description
        return report

    # ── Tabular: load sample for column stats ──────────────────────
    try:
        import pandas as pd
        path = str(Path(path).resolve())

        # Load sample (avoid re-reading huge files)
        STAT_ROWS = 5000
        fmt = probe.format

        if fmt in ("csv", "csv_pipe", "csv_semicolon"):
            delim = {"csv": ",", "csv_pipe": "|", "csv_semicolon": ";"}.get(fmt, ",")
            df = pd.read_csv(path, sep=delim, nrows=STAT_ROWS,
                             low_memory=False, on_bad_lines="warn")
        elif fmt == "tsv":
            df = pd.read_csv(path, sep="\t", nrows=STAT_ROWS, low_memory=False)
        elif fmt == "parquet":
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(path)
            batch = next(pf.iter_batches(batch_size=STAT_ROWS))
            df = batch.to_pandas()
        elif fmt == "feather":
            df = pd.read_feather(path)
            df = df.head(STAT_ROWS)
        elif fmt in ("json", "jsonl"):
            rows = []
            with open(path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            pass
                    if len(rows) >= STAT_ROWS:
                        break
            df = pd.DataFrame(rows)
        elif fmt in ("xlsx", "xls"):
            engine = "openpyxl" if fmt == "xlsx" else "xlrd"
            df = pd.read_excel(path, nrows=STAT_ROWS, engine=engine)
        elif fmt == "sqlite":
            import sqlite3
            conn = sqlite3.connect(path)
            tbl  = probe.metadata.get("active_table", "")
            df   = pd.read_sql(f"SELECT * FROM [{tbl}] LIMIT {STAT_ROWS}", conn)
            conn.close()
        else:
            # Fall back to sample rows from probe
            if probe.sample_rows:
                df = pd.DataFrame(probe.sample_rows)
            else:
                report.summary_text = probe.summary()
                return report

        total_rows = probe.row_count or len(df)

        # ── Per-column schema ──────────────────────────────────────
        col_schemas: list[ColumnSchema] = []

        for col in df.columns:
            dtype_str = str(df[col].dtype)
            null_pct, unique_count, top_vals, val_range, samples = _col_stats(
                df[col], total_rows
            )
            semantic = _infer_semantic(
                col, dtype_str, unique_count, total_rows, samples
            )

            cs = ColumnSchema(
                name=col, dtype=dtype_str, semantic_type=semantic,
                null_pct=null_pct, unique_count=unique_count,
                top_values=top_vals, value_range=val_range,
                sample_values=[str(s) for s in samples[:5]],
            )

            # Attach notes
            if null_pct > 0.30:
                cs.notes.append(f"{null_pct:.0%} missing — needs imputation")
            if semantic == SEMANTIC_CONSTANT:
                cs.notes.append("Constant column — consider dropping")
            if semantic == SEMANTIC_ID:
                cs.notes.append("High-cardinality identifier — exclude from features")

            col_schemas.append(cs)

        report.columns    = col_schemas
        report.col_count  = len(col_schemas)
        report.row_count  = total_rows

        # ── Special column groups ──────────────────────────────────
        report.target_candidates = [
            c.name for c in col_schemas if c.semantic_type == SEMANTIC_TARGET
        ]
        report.datetime_cols = [
            c.name for c in col_schemas if c.semantic_type == SEMANTIC_TIMESTAMP
        ]
        report.id_cols = [
            c.name for c in col_schemas if c.semantic_type == SEMANTIC_ID
        ]

        # ── Routing hints ──────────────────────────────────────────
        routing: dict[str, Any] = {}

        high_null = [c.name for c in col_schemas if c.null_pct > 0.15]
        if high_null:
            routing["skeptic"]          = "prioritize"
            routing["feature_engineer"] = "focus_imputation"

        high_card = [c.name for c in col_schemas
                     if c.semantic_type == SEMANTIC_CATEGORICAL and c.unique_count > 50]
        if high_card:
            routing["feature_engineer"] = "focus_encoding"

        if report.datetime_cols:
            routing["explorer"]         = "focus_temporal"
            routing["feature_engineer"] = "add_temporal_features"

        if report.target_candidates:
            routing["pragmatist"] = f"use_target={report.target_candidates[0]}"

        constants = [c.name for c in col_schemas if c.semantic_type == SEMANTIC_CONSTANT]
        if constants:
            routing["feature_engineer"] = routing.get("feature_engineer", "") + "+drop_constants"

        report.routing_hints = routing

        # ── Summary text ──────────────────────────────────────────
        lines = [
            f"📋 SCHEMA REPORT  ({probe.format} via {probe.parser_used})",
            f"   Shape    : {total_rows:,} rows × {len(col_schemas)} cols",
        ]
        if report.target_candidates:
            lines.append(f"   Targets  : {report.target_candidates}")
        if report.datetime_cols:
            lines.append(f"   Datetime : {report.datetime_cols}")
        if report.id_cols:
            lines.append(f"   IDs      : {report.id_cols}")

        lines.append("\n   Columns:")
        for cs in col_schemas:
            flag = "⚠️ " if cs.null_pct > 0.15 else "   "
            lines.append(
                f"   {flag}{cs.name:<25} {cs.dtype:<12} "
                f"[{cs.semantic_type}]  "
                f"nulls={cs.null_pct:.0%}  unique={cs.unique_count}"
            )

        if routing:
            lines.append(f"\n   Routing  : {routing}")

        report.summary_text = "\n".join(lines)

    except Exception as exc:
        report.summary_text = (
            f"Schema extraction failed: {exc}\n"
            f"Falling back to probe summary:\n{probe.summary()}"
        )

    return report
