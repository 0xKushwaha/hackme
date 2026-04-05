"""Engine for extracting and analyzing relationships in data."""

import hashlib
import json
import warnings
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import f_oneway, chi2_contingency, spearmanr, friedmanchisquare
from statsmodels.nonparametric.smoothers_lowess import lowess

from data_objects.analysis import RelationshipAnalysis


class RelationshipExtractor:
    """Extracts typed relationships from data with caching."""

    def __init__(self, cache_dir: str = "experiments"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "relationship_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load relationship cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[RelationshipExtractor] Failed to load cache: {e}")
        return {}

    def _save_cache(self):
        """Save relationship cache to disk."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            print(f"[RelationshipExtractor] Failed to save cache: {e}")

    def _get_cache_key(
        self, feature_a: str, feature_b: str, sample_hash: str
    ) -> str:
        """Generate cache key for a relationship."""
        key = f"{min(feature_a, feature_b)}_{max(feature_a, feature_b)}_{sample_hash}"
        return key

    def _hash_sample(self, df: pd.DataFrame) -> str:
        """Generate hash of data sample for cache invalidation."""
        data_str = f"{df.shape}_{df.dtypes.to_string()}_{df.iloc[0].to_string()}"
        return hashlib.md5(data_str.encode()).hexdigest()[:8]

    def compute_numeric_correlation(
        self,
        df: pd.DataFrame,
        feature_a: str,
        feature_b: str,
        method: str = "pearson",
    ) -> RelationshipAnalysis:
        """Compute correlation between two numeric features."""
        if feature_a == feature_b:
            raise ValueError("Cannot compute correlation with itself")

        # Check cache
        sample_hash = self._hash_sample(df)
        cache_key = self._get_cache_key(feature_a, feature_b, sample_hash)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            result = RelationshipAnalysis.from_dict(cached)
            return result

        # Compute
        valid_mask = df[[feature_a, feature_b]].notna().all(axis=1)
        data_clean = df.loc[valid_mask, [feature_a, feature_b]]

        if len(data_clean) < 3:
            return RelationshipAnalysis(
                feature_a=feature_a,
                feature_b=feature_b,
                relationship_type="insufficient_data",
                sample_size=len(data_clean),
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if method == "pearson":
                corr, p_val = stats.pearsonr(data_clean[feature_a], data_clean[feature_b])
            elif method == "spearman":
                corr, p_val = spearmanr(data_clean[feature_a], data_clean[feature_b])
            else:
                corr, p_val = stats.pearsonr(data_clean[feature_a], data_clean[feature_b])

        strength = abs(corr)
        result = RelationshipAnalysis(
            feature_a=feature_a,
            feature_b=feature_b,
            relationship_type="linear",
            strength=strength,
            correlation=corr,
            p_value=p_val,
            sample_size=len(data_clean),
            verified_by="RelationshipExtractor",
            verified=True,
            confidence=min(1.0, 1.0 - p_val) if p_val < 0.05 else 0.5,
        )

        # Cache it
        self._cache[cache_key] = result.to_dict()
        self._save_cache()

        return result

    def compute_feature_target_relationship(
        self,
        df: pd.DataFrame,
        feature: str,
        target: str,
    ) -> RelationshipAnalysis:
        """Compute relationship between a feature and target variable."""
        # Check cache
        sample_hash = self._hash_sample(df)
        cache_key = self._get_cache_key(feature, target, sample_hash)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return RelationshipAnalysis.from_dict(cached)

        # Determine data types
        feature_dtype = pd.api.types.infer_dtype(df[feature])
        target_dtype = pd.api.types.infer_dtype(df[target])

        valid_mask = df[[feature, target]].notna().all(axis=1)
        data_clean = df.loc[valid_mask, [feature, target]]

        if len(data_clean) < 3:
            return RelationshipAnalysis(
                feature_a=feature,
                feature_b=target,
                relationship_type="insufficient_data",
                sample_size=len(data_clean),
            )

        # Case 1: numeric-numeric
        if feature_dtype in ["integer", "floating"] and target_dtype in ["integer", "floating"]:
            corr, p_val = stats.pearsonr(data_clean[feature], data_clean[target])
            result = RelationshipAnalysis(
                feature_a=feature,
                feature_b=target,
                relationship_type="linear",
                strength=abs(corr),
                correlation=corr,
                p_value=p_val,
                sample_size=len(data_clean),
                verified_by="RelationshipExtractor",
                verified=True,
                confidence=min(1.0, 1.0 - p_val) if p_val < 0.05 else 0.5,
            )

        # Case 2: categorical-numeric
        elif feature_dtype in ["categorical", "object"] and target_dtype in ["integer", "floating"]:
            # ANOVA
            groups = [group[target].values for name, group in data_clean.groupby(feature)]
            if len(groups) > 1:
                f_stat, p_val = f_oneway(*groups)
            else:
                f_stat, p_val = 0, 1.0

            # Effect size (eta)
            grand_mean = data_clean[target].mean()
            between_var = sum(len(g) * (g.mean() - grand_mean)**2 for g in groups) / (len(groups) - 1) if len(groups) > 1 else 0
            within_var = sum(((g - g.mean())**2).sum() for g in groups) / (len(data_clean) - len(groups))
            eta = np.sqrt(between_var / (between_var + within_var)) if (between_var + within_var) > 0 else 0

            result = RelationshipAnalysis(
                feature_a=feature,
                feature_b=target,
                relationship_type="categorical",
                strength=eta,
                p_value=p_val,
                sample_size=len(data_clean),
                verified_by="RelationshipExtractor",
                verified=True,
                confidence=min(1.0, 1.0 - p_val) if p_val < 0.05 else 0.5,
            )

        # Case 3: categorical-categorical
        elif feature_dtype in ["categorical", "object"] and target_dtype in ["categorical", "object"]:
            # Chi-square
            contingency_table = pd.crosstab(data_clean[feature], data_clean[target])
            chi2, p_val, dof, expected = chi2_contingency(contingency_table)

            # Cramér's V
            n = contingency_table.sum().sum()
            min_dim = min(contingency_table.shape) - 1
            cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 else 0

            result = RelationshipAnalysis(
                feature_a=feature,
                feature_b=target,
                relationship_type="categorical",
                strength=cramers_v,
                p_value=p_val,
                sample_size=len(data_clean),
                verified_by="RelationshipExtractor",
                verified=True,
                confidence=min(1.0, 1.0 - p_val) if p_val < 0.05 else 0.5,
            )

        else:
            result = RelationshipAnalysis(
                feature_a=feature,
                feature_b=target,
                relationship_type="unknown_dtype",
                sample_size=len(data_clean),
            )

        # Cache it
        self._cache[cache_key] = result.to_dict()
        self._save_cache()

        return result

    def detect_non_linearity(
        self,
        df: pd.DataFrame,
        feature_a: str,
        feature_b: str,
        frac: float = 0.3,
    ) -> Dict[str, Any]:
        """Detect non-linear relationships using LOWESS."""
        valid_mask = df[[feature_a, feature_b]].notna().all(axis=1)
        data_clean = df.loc[valid_mask, [feature_a, feature_b]].sort_values(feature_a)

        if len(data_clean) < 5:
            return {"type": "insufficient_data"}

        # Linear fit
        x = data_clean[feature_a].values
        y = data_clean[feature_b].values
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        linear_fit = p(x)
        linear_mse = np.mean((y - linear_fit) ** 2)

        # LOWESS fit
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lowess_result = lowess(y, x, frac=frac)
            lowess_fit = lowess_result[:, 1]
            lowess_mse = np.mean((y - lowess_fit) ** 2)

        improvement_ratio = (linear_mse - lowess_mse) / linear_mse if linear_mse > 0 else 0

        return {
            "linear_mse": float(linear_mse),
            "lowess_mse": float(lowess_mse),
            "improvement_ratio": float(improvement_ratio),
            "is_non_linear": improvement_ratio > 0.1,  # >10% improvement indicates non-linearity
        }

    def detect_interactions(
        self,
        df: pd.DataFrame,
        feature_a: str,
        feature_b: str,
        target: str,
    ) -> float:
        """Detect interaction effect using Friedman H-statistic (lightweight)."""
        valid_mask = df[[feature_a, feature_b, target]].notna().all(axis=1)
        data_clean = df.loc[valid_mask, [feature_a, feature_b, target]]

        if len(data_clean) < 10:
            return 0.0

        # Simple interaction detection: compute target at extreme values
        try:
            a_quantiles = data_clean[feature_a].quantile([0.25, 0.75]).values
            b_quantiles = data_clean[feature_b].quantile([0.25, 0.75]).values

            # Get targets at each combination
            targets = []
            for a_val in a_quantiles:
                for b_val in b_quantiles:
                    mask = (
                        (data_clean[feature_a] >= a_val - 0.01) &
                        (data_clean[feature_a] <= a_val + 0.01) &
                        (data_clean[feature_b] >= b_val - 0.01) &
                        (data_clean[feature_b] <= b_val + 0.01)
                    )
                    if mask.sum() > 0:
                        targets.append(data_clean.loc[mask, target].mean())

            if len(targets) < 3:
                return 0.0

            # Interaction strength as coefficient of variation in effects
            targets = np.array(targets)
            interaction_strength = np.std(targets) / (np.mean(np.abs(targets)) + 1e-8)
            return float(min(1.0, interaction_strength))

        except Exception:
            return 0.0

    def extract_all_relationships(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        numeric_only: bool = False,
    ) -> List[RelationshipAnalysis]:
        """Extract all pairwise relationships in a dataset."""
        results = []

        if numeric_only:
            cols = df.select_dtypes(include=[np.number]).columns.tolist()
        else:
            cols = df.columns.tolist()

        # Feature-feature relationships (numeric only)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for i, col_a in enumerate(numeric_cols):
            for col_b in numeric_cols[i + 1:]:
                try:
                    rel = self.compute_numeric_correlation(df, col_a, col_b)
                    if rel.strength > 0.1:  # Only store meaningful relationships
                        results.append(rel)
                except Exception as e:
                    print(f"[RelationshipExtractor] Error computing {col_a}-{col_b}: {e}")

        # Feature-target relationships
        if target_col and target_col in df.columns:
            for col in cols:
                if col != target_col:
                    try:
                        rel = self.compute_feature_target_relationship(df, col, target_col)
                        results.append(rel)
                    except Exception as e:
                        print(f"[RelationshipExtractor] Error computing {col}-{target_col}: {e}")

        return results
