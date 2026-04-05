"""Smart sampling strategies for lightweight data validation."""

import hashlib
from typing import Optional, List

import pandas as pd
import numpy as np


class DataSampler:
    """Provides intelligent sampling for relationship validation."""

    @staticmethod
    def stratified_sample(
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        n: int = 5000,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """
        Get stratified sample proportional to target distribution.

        If target is regression, stratify by quantile bins.
        If target is classification, stratify by class.
        """
        if len(df) <= n:
            return df.copy()

        if target_col and target_col in df.columns:
            # Try to stratify by target
            target_dtype = pd.api.types.infer_dtype(df[target_col])

            if target_dtype in ["integer", "floating"]:
                # Regression: bin into 5-10 quantile groups
                n_bins = min(10, max(5, len(df) // 100))
                bins = pd.qcut(df[target_col], q=n_bins, duplicates="drop")
                return df.groupby(bins, group_keys=False).apply(
                    lambda x: x.sample(
                        n=min(len(x), max(1, int(n * len(x) / len(df)))),
                        random_state=random_state,
                    )
                )
            else:
                # Classification: stratify by class
                return df.groupby(target_col, group_keys=False).apply(
                    lambda x: x.sample(
                        n=min(len(x), max(1, int(n * len(x) / len(df)))),
                        random_state=random_state,
                    )
                )

        # No target: simple random sample
        return df.sample(n=n, random_state=random_state)

    @staticmethod
    def representative_sample(
        df: pd.DataFrame,
        n: int = 5000,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """Get representative sample preserving categorical distributions."""
        if len(df) <= n:
            return df.copy()

        # Find categorical columns with reasonable cardinality
        categorical_cols = []
        for col in df.columns:
            dtype = pd.api.types.infer_dtype(df[col])
            unique_count = df[col].nunique()
            if dtype in ["categorical", "object"] and 2 <= unique_count <= 50:
                categorical_cols.append(col)

        if categorical_cols:
            # Stratify by primary categorical column
            primary_cat = categorical_cols[0]
            return df.groupby(primary_cat, group_keys=False).apply(
                lambda x: x.sample(
                    n=min(len(x), max(1, int(n * len(x) / len(df)))),
                    random_state=random_state,
                )
            )

        # No good categorical: use stratified by target or random
        return df.sample(n=n, random_state=random_state)

    @staticmethod
    def relationship_sample(
        df: pd.DataFrame,
        features: List[str],
        target: Optional[str] = None,
        n: int = 5000,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """Get sample focused on provided features + target for relationship validation."""
        # Ensure all specified columns exist
        cols_to_keep = [c for c in features if c in df.columns]
        if target and target in df.columns:
            cols_to_keep.append(target)

        if not cols_to_keep:
            return df.sample(n=min(n, len(df)), random_state=random_state)

        subset = df[cols_to_keep].copy()
        return DataSampler.stratified_sample(subset, target, n, random_state)

    @staticmethod
    def get_sample(
        df: pd.DataFrame,
        strategy: str = "stratified",
        target_col: Optional[str] = None,
        features: Optional[List[str]] = None,
        n: Optional[int] = None,
        random_state: int = 42,
    ) -> pd.DataFrame:
        """
        Get sample using specified strategy.

        Args:
            df: Input dataframe
            strategy: "stratified", "representative", or "relationship"
            target_col: Target column for stratification
            features: Features to focus on (for relationship strategy)
            n: Sample size (auto-computed if None: min(5000, 10% of df))
            random_state: Random seed

        Returns:
            Sampled dataframe
        """
        # Auto-compute sample size
        if n is None:
            n = min(5000, max(100, len(df) // 10))

        if strategy == "stratified":
            return DataSampler.stratified_sample(df, target_col, n, random_state)
        elif strategy == "representative":
            return DataSampler.representative_sample(df, n, random_state)
        elif strategy == "relationship":
            return DataSampler.relationship_sample(
                df, features or [], target_col, n, random_state
            )
        else:
            return df.sample(n=min(n, len(df)), random_state=random_state)

    @staticmethod
    def cache_key(df: pd.DataFrame, strategy: str) -> str:
        """Generate cache key for a sample."""
        data_str = f"{df.shape}_{strategy}_{df.iloc[0].to_string() if len(df) > 0 else ''}"
        return hashlib.md5(data_str.encode()).hexdigest()[:12]
