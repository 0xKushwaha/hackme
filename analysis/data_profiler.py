"""
DataProfiler — fast pre-LLM data statistics.

Computes key metrics about the dataset WITHOUT any LLM calls:
  - Shape, dtypes, missing %, outlier %, near-zero variance
  - Class distribution and imbalance for classification
  - High-correlation pairs (multicollinearity risk)
  - Data quality score (0-1)
  - Routing recommendations per agent (skip / quick / prioritize)

Inspired by Karpathy's data-centric AI principle:
  "Profile data first. Route agents based on what the data actually needs."

Used by DataUnderstandingPhase to:
  1. Inject rich numeric context into agent prompts (no LLM needed)
  2. Skip agents that would add no value (clean data → Skeptic on quick pass)
  3. Focus agents on specific issues (high imbalance → Optimizer on stratification)
"""

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DataProfile:
    """Fast data statistics computed without any LLM calls."""

    # Basic shape
    n_rows:    int   = 0
    n_cols:    int   = 0

    # Quality metrics
    missing_pct:   float = 0.0   # avg missing per column (0-1)
    outlier_pct:   float = 0.0   # avg outlier ratio per numeric col (0-1)
    data_quality_score: float = 1.0   # composite 0-1 (higher = cleaner)

    # Feature characteristics
    high_cardinality_cols:    list = field(default_factory=list)
    near_zero_variance_cols:  list = field(default_factory=list)
    high_corr_pairs:          list = field(default_factory=list)  # [(col_a, col_b, r)]

    # Task characteristics
    is_time_series: bool  = False
    n_classes:      int   = 0
    class_imbalance: float = 0.0   # 0=balanced, 1=extreme

    # Routing hints per agent
    routing: dict = field(default_factory=dict)

    # Human-readable summary injected into agent context
    summary_text: str = ""


class DataProfiler:
    """
    Computes fast data profile from a tabular file (CSV/Parquet).
    Pure pandas/numpy — no LLM calls, runs in milliseconds.
    """

    CORR_THRESHOLD     = 0.85
    CARDINALITY_LIMIT  = 50
    NZV_THRESHOLD      = 0.01    # near-zero variance coefficient-of-variation
    OUTLIER_IQR_FACTOR = 1.5
    SAMPLE_SIZE        = 10_000  # cap rows for speed

    def profile(self, path: str, target_col: str = None) -> Optional[DataProfile]:
        """
        Returns DataProfile for a tabular file, or None for non-tabular / read errors.
        """
        try:
            import pandas as pd
        except ImportError:
            return None

        try:
            p = Path(path)
            ext = p.suffix.lower()

            if ext == ".csv":
                df = pd.read_csv(p, nrows=self.SAMPLE_SIZE)
            elif ext in (".parquet", ".feather"):
                try:
                    import pyarrow.parquet as pq
                    pf = pq.ParquetFile(p)
                    batch = next(pf.iter_batches(batch_size=self.SAMPLE_SIZE))
                    df = batch.to_pandas()
                except Exception:
                    # feather or pyarrow unavailable — fall back (small files only)
                    df = pd.read_parquet(p)
                    if len(df) > self.SAMPLE_SIZE:
                        df = df.sample(self.SAMPLE_SIZE, random_state=42)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(p, nrows=self.SAMPLE_SIZE)
            elif ext in (".json",):
                df = pd.read_json(p, lines=True, nrows=self.SAMPLE_SIZE)
            else:
                return None   # non-tabular

            return self._compute(df, target_col)

        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _compute(self, df, target_col: str = None) -> DataProfile:
        import numpy as np

        n_rows, n_cols = df.shape
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols     = df.select_dtypes(include=["object", "category"]).columns.tolist()

        # ── Missing values ────────────────────────────────────────────────
        missing_pct = float(df.isnull().mean().mean())

        # ── Outliers (IQR method, numeric cols) ───────────────────────────
        outlier_ratios = []
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) < 10:
                continue
            q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
            iqr = q3 - q1
            if iqr == 0:
                continue
            lo, hi = q1 - self.OUTLIER_IQR_FACTOR * iqr, q3 + self.OUTLIER_IQR_FACTOR * iqr
            ratio = float(((s < lo) | (s > hi)).sum()) / len(s)
            outlier_ratios.append(ratio)
        outlier_pct = float(np.mean(outlier_ratios)) if outlier_ratios else 0.0

        # ── High cardinality categoricals ─────────────────────────────────
        high_cardinality_cols = [
            col for col in cat_cols
            if df[col].nunique() > self.CARDINALITY_LIMIT
        ]

        # ── Near-zero variance ────────────────────────────────────────────
        near_zero_variance_cols = []
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) > 0:
                cv = float(s.std()) / (abs(float(s.mean())) + 1e-9)
                if cv < self.NZV_THRESHOLD:
                    near_zero_variance_cols.append(col)

        # ── High correlation pairs ─────────────────────────────────────────
        high_corr_pairs = []
        if len(numeric_cols) >= 2:
            try:
                corr = df[numeric_cols].corr().abs()
                for i, col_a in enumerate(numeric_cols):
                    for col_b in numeric_cols[i + 1:]:
                        v = corr.loc[col_a, col_b]
                        if v > self.CORR_THRESHOLD:
                            high_corr_pairs.append((col_a, col_b, round(float(v), 3)))
            except Exception:
                pass

        # ── Class imbalance ───────────────────────────────────────────────
        class_imbalance = 0.0
        n_classes = 0
        if target_col and target_col in df.columns:
            vc = df[target_col].value_counts(normalize=True)
            n_classes = int(len(vc))
            if n_classes >= 2:
                # Normalized entropy as imbalance measure (0=extreme, 1=balanced)
                import math
                entropy = -sum(p * math.log(p + 1e-9) for p in vc)
                max_entropy = math.log(n_classes)
                class_imbalance = float(1.0 - (entropy / max_entropy if max_entropy > 0 else 0))

        # ── Time series detection ──────────────────────────────────────────
        is_time_series = any(
            any(kw in col.lower() for kw in ("date", "time", "timestamp", "year", "month", "week"))
            for col in df.columns
        )

        # ── Data quality score ─────────────────────────────────────────────
        # Penalty: missing (40%), outliers (30%), high-corr multicollinearity (30%)
        multicollinearity_penalty = min(len(high_corr_pairs) / max(n_cols, 1), 0.3)
        quality_score = max(0.0, min(1.0,
            1.0
            - (missing_pct * 0.4)
            - (outlier_pct * 0.3)
            - (multicollinearity_penalty * 0.3)
        ))

        # ── Routing recommendations ───────────────────────────────────────
        routing = {}

        # Skeptic: skip to quick pass if data is very clean
        if missing_pct < 0.01 and outlier_pct < 0.02 and not high_cardinality_cols:
            routing["skeptic"] = "quick"
        elif missing_pct > 0.15 or outlier_pct > 0.12:
            routing["skeptic"] = "prioritize"

        # Explorer: guide towards what actually matters
        if len(high_corr_pairs) > 3:
            routing["explorer"] = "focus_correlations"
        if is_time_series:
            routing["explorer"] = "focus_temporal"

        # Feature engineer: target specific issues
        if high_cardinality_cols:
            routing["feature_engineer"] = "focus_encoding"
        if near_zero_variance_cols:
            routing["feature_engineer"] = "focus_selection"
        if is_time_series:
            routing["feature_engineer"] = "add_temporal_features"

        # Optimizer: adjust CV strategy based on data characteristics
        if n_rows < 500:
            routing["optimizer"] = "skip_cv"       # too small for k-fold
        elif class_imbalance > 0.35:
            routing["optimizer"] = "stratified_cv"
        elif is_time_series:
            routing["optimizer"] = "timeseries_cv"

        # Statistician: flag multicollinearity for analysis
        if len(high_corr_pairs) > 2:
            routing["statistician"] = "focus_multicollinearity"

        # ── Summary text ──────────────────────────────────────────────────
        lines = [
            "📊 PRE-LLM DATA PROFILE (computed without inference cost):",
            f"   Shape         : {n_rows:,} rows × {n_cols} cols",
            f"   Missing       : {missing_pct:.1%} avg per column",
            f"   Outlier ratio : {outlier_pct:.1%} avg per numeric col",
            f"   Quality score : {quality_score:.2f} / 1.0",
        ]
        if high_corr_pairs:
            top = sorted(high_corr_pairs, key=lambda x: -x[2])[:3]
            lines.append(f"   High-corr pairs : {top}")
        if high_cardinality_cols:
            lines.append(f"   High-cardinality: {high_cardinality_cols[:4]}")
        if near_zero_variance_cols:
            lines.append(f"   Near-zero var   : {near_zero_variance_cols[:4]}")
        if is_time_series:
            lines.append("   🕐 Time-series columns detected")
        if n_classes > 0:
            lines.append(f"   Target classes  : {n_classes}  |  imbalance score: {class_imbalance:.2f}")
        if routing:
            lines.append(f"   Agent routing   : {routing}")

        return DataProfile(
            n_rows=n_rows,
            n_cols=n_cols,
            missing_pct=missing_pct,
            outlier_pct=outlier_pct,
            data_quality_score=quality_score,
            high_cardinality_cols=high_cardinality_cols,
            near_zero_variance_cols=near_zero_variance_cols,
            high_corr_pairs=high_corr_pairs,
            is_time_series=is_time_series,
            n_classes=n_classes,
            class_imbalance=class_imbalance,
            routing=routing,
            summary_text="\n".join(lines),
        )
