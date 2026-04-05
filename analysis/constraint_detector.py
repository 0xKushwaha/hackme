"""Generalized constraint discovery - finds mathematical relationships in any dataset."""

import warnings
from itertools import combinations
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats


class RankAnalysisDetector:
    """Detect linear dependencies through correlation matrix rank analysis."""

    @staticmethod
    def find_dependencies(
        df: pd.DataFrame,
        threshold: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Analyze correlation matrix rank to detect linear dependencies.

        If rank < num_features, some features are linearly dependent.
        This indicates compositional relationships.

        Args:
            df: Input dataframe (numeric columns only)
            threshold: Eigenvalue threshold as fraction of largest eigenvalue

        Returns:
            Dict with rank_deficiency, eigenvalues, interpretation
        """
        # Select numeric columns only
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty or len(numeric_df.columns) < 2:
            return {
                "rank_deficiency": 0,
                "num_features": len(numeric_df.columns),
                "eigenvalues": [],
                "interpretation": "Insufficient numeric features",
            }

        # Compute correlation matrix
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            corr = numeric_df.corr().fillna(0)

        # Compute eigenvalues
        eigenvalues = np.linalg.eigvals(corr)
        eigenvalues = np.sort(eigenvalues)[::-1]  # descending

        # Determine effective rank
        max_eigenvalue = eigenvalues[0]
        effective_rank = (eigenvalues > threshold * max_eigenvalue).sum()
        num_features = len(numeric_df.columns)
        rank_deficiency = num_features - effective_rank

        interpretation = ""
        if rank_deficiency == 0:
            interpretation = "No linear dependencies detected (full rank)"
        elif rank_deficiency == 1:
            interpretation = "One linear dependency - likely one composite feature"
        else:
            interpretation = f"{rank_deficiency} linear dependencies detected"

        return {
            "rank_deficiency": rank_deficiency,
            "effective_rank": effective_rank,
            "num_features": num_features,
            "eigenvalues": eigenvalues.tolist(),
            "interpretation": interpretation,
            "has_dependencies": rank_deficiency > 0,
        }


class AlgebraicRelationshipDetector:
    """Find mathematical relationships through exhaustive correlation testing."""

    @staticmethod
    def find_additive_relationships(
        df: pd.DataFrame,
        tolerance: float = 0.99,
        max_tests: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Find additive relationships: A = B + C

        Args:
            df: Numeric dataframe
            tolerance: R² threshold for considering relationship valid
            max_tests: Limit number of tests (for speed on wide datasets)

        Returns:
            List of relationships sorted by R²
        """
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) < 3:
            return []

        results = []
        columns = numeric_df.columns.tolist()
        test_count = 0

        for col_a in columns:
            for col_b in columns:
                if test_count > (max_tests or float("inf")):
                    break

                for col_c in columns:
                    if test_count > (max_tests or float("inf")):
                        break

                    # Skip self-relationships
                    if len({col_a, col_b, col_c}) < 3:
                        continue

                    test_count += 1

                    try:
                        # Test: A = B + C
                        y = numeric_df[col_a].values
                        X = numeric_df[col_b].values + numeric_df[col_c].values

                        # Skip if constant
                        if np.std(X) < 1e-10 or np.std(y) < 1e-10:
                            continue

                        # Compute R²
                        y_mean = np.mean(y)
                        ss_tot = np.sum((y - y_mean) ** 2)
                        residuals = y - X
                        ss_res = np.sum(residuals ** 2)
                        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                        if r_squared > tolerance:
                            results.append(
                                {
                                    "formula": f"{col_a} = {col_b} + {col_c}",
                                    "r_squared": float(r_squared),
                                    "mean_absolute_error": float(np.mean(np.abs(residuals))),
                                    "max_absolute_error": float(np.max(np.abs(residuals))),
                                    "residual_std": float(np.std(residuals)),
                                    "type": "additive",
                                    "components": [col_b, col_c],
                                    "target": col_a,
                                }
                            )

                    except Exception:
                        continue

        return sorted(results, key=lambda x: x["r_squared"], reverse=True)

    @staticmethod
    def find_linear_combinations(
        df: pd.DataFrame,
        k: int = 2,
        tolerance: float = 0.99,
    ) -> List[Dict[str, Any]]:
        """
        Find linear combinations: A = w₁*B + w₂*C + ... using least squares.

        Args:
            df: Numeric dataframe
            k: Number of terms in combination (2-4 typical)
            tolerance: R² threshold

        Returns:
            List of relationships sorted by R²
        """
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) < k + 1:
            return []

        results = []
        columns = numeric_df.columns.tolist()

        for col_a in columns:
            other_cols = [c for c in columns if c != col_a]

            # Try combinations of k features
            for combo in combinations(other_cols, min(k, len(other_cols))):
                try:
                    y = numeric_df[col_a].values
                    X = numeric_df[list(combo)].values

                    # Skip if constant
                    if np.std(y) < 1e-10:
                        continue

                    # Fit least squares: y = w₁*X₁ + w₂*X₂ + ...
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        w, residuals_vec, rank, s = np.linalg.lstsq(X, y, rcond=None)

                    # Compute R²
                    y_mean = np.mean(y)
                    ss_tot = np.sum((y - y_mean) ** 2)
                    residuals = y - X @ w
                    ss_res = np.sum(residuals ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                    if r_squared > tolerance:
                        # Format formula
                        formula_parts = [
                            f"{w[i]:.4f}*{combo[i]}"
                            for i in range(len(combo))
                        ]
                        formula = f"{col_a} = {' + '.join(formula_parts)}"

                        results.append(
                            {
                                "formula": formula,
                                "r_squared": float(r_squared),
                                "weights": {combo[i]: float(w[i]) for i in range(len(combo))},
                                "mean_absolute_error": float(np.mean(np.abs(residuals))),
                                "max_absolute_error": float(np.max(np.abs(residuals))),
                                "residual_std": float(np.std(residuals)),
                                "type": "linear_combination",
                                "components": list(combo),
                                "target": col_a,
                            }
                        )

                except Exception:
                    continue

        return sorted(results, key=lambda x: x["r_squared"], reverse=True)


class ResidualAnalysisDetector:
    """Find relationships through residual inspection (works with normalized data)."""

    @staticmethod
    def find_all_operations(
        df: pd.DataFrame,
        tolerance: float = 0.01,
    ) -> List[Dict[str, Any]]:
        """
        Test multiple operation types: +, -, *, /, ^2, sqrt

        Args:
            df: Numeric dataframe
            tolerance: Normalized residual threshold

        Returns:
            List of discovered relationships
        """
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) < 2:
            return []

        results = []
        columns = numeric_df.columns.tolist()

        for target in columns:
            y = numeric_df[target].values
            y_clean = y[~np.isnan(y) & ~np.isinf(y)]

            if len(y_clean) < 3 or np.std(y_clean) < 1e-10:
                continue

            # Normalize target
            y_norm = (y_clean - np.mean(y_clean)) / (np.std(y_clean) + 1e-8)

            for col1 in columns:
                if col1 == target:
                    continue

                x1 = numeric_df[col1].values
                x1_clean = x1[~np.isnan(x1) & ~np.isinf(x1)]

                if len(x1_clean) == 0 or np.std(x1_clean) < 1e-10:
                    continue

                for col2 in columns:
                    if col2 in (target, col1):
                        continue

                    x2 = numeric_df[col2].values
                    x2_clean = x2[~np.isnan(x2) & ~np.isinf(x2)]

                    if len(x2_clean) == 0 or np.std(x2_clean) < 1e-10:
                        continue

                    # Ensure same length
                    min_len = min(len(y_clean), len(x1_clean), len(x2_clean))
                    y_norm = y_norm[:min_len]
                    x1_norm = (x1_clean - np.mean(x1_clean)) / (np.std(x1_clean) + 1e-8)
                    x1_norm = x1_norm[:min_len]
                    x2_norm = (x2_clean - np.mean(x2_clean)) / (np.std(x2_clean) + 1e-8)
                    x2_norm = x2_norm[:min_len]

                    # Test operations
                    operations = [
                        (x1_norm + x2_norm, f"{target} = {col1} + {col2}"),
                        (x1_norm - x2_norm, f"{target} = {col1} - {col2}"),
                        (x1_norm * x2_norm, f"{target} = {col1} * {col2}"),
                    ]

                    # Add division (safe)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        div = np.divide(x1_norm, x2_norm + 1e-10)
                        if not np.any(np.isinf(div)):
                            operations.append((div, f"{target} = {col1} / {col2}"))

                    for candidate, formula in operations:
                        try:
                            residual = np.abs(y_norm - candidate)
                            mean_residual = np.mean(residual)
                            max_residual = np.max(residual)

                            if mean_residual < tolerance:
                                results.append(
                                    {
                                        "formula": formula,
                                        "mean_residual": float(mean_residual),
                                        "max_residual": float(max_residual),
                                        "type": "normalized_operation",
                                    }
                                )

                        except Exception:
                            continue

        return sorted(results, key=lambda x: x["mean_residual"])


class StatisticalRelationshipTester:
    """Test proposed relationships with statistical rigor."""

    @staticmethod
    def test_additive_relationship(
        df: pd.DataFrame,
        target: str,
        components: List[str],
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Test if target = sum(components) using linear regression.

        Args:
            df: Dataframe
            target: Target column
            components: List of component columns
            alpha: Significance level

        Returns:
            Test results with p-value and R²
        """
        if target not in df.columns or not all(c in df.columns for c in components):
            return {"valid": False, "reason": "Column not found"}

        try:
            y = df[target].dropna().values
            X_sum = df[components].sum(axis=1).loc[df[target].notna()].values

            if len(y) < 3 or np.std(X_sum) < 1e-10 or np.std(y) < 1e-10:
                return {"valid": False, "reason": "Insufficient variation"}

            # Linear regression
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                slope, intercept, r_value, p_value, std_err = stats.linregress(X_sum, y)

            r_squared = r_value ** 2

            return {
                "valid": True,
                "target": target,
                "components": components,
                "r_squared": float(r_squared),
                "p_value": float(p_value),
                "slope": float(slope),
                "intercept": float(intercept),
                "statistically_significant": p_value < alpha,
                "perfect_match": r_squared > 0.9999,
                "strong_relationship": r_squared > 0.95,
                "confidence": "high" if r_squared > 0.99 and p_value < 0.001 else "medium" if r_squared > 0.95 else "low",
            }

        except Exception as e:
            return {"valid": False, "reason": str(e)}

    @staticmethod
    def test_linear_combination(
        df: pd.DataFrame,
        target: str,
        components: List[str],
        weights: Dict[str, float],
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Test if target = w₁*c₁ + w₂*c₂ + ...

        Args:
            df: Dataframe
            target: Target column
            components: List of component columns
            weights: Weights for each component
            alpha: Significance level

        Returns:
            Test results
        """
        if target not in df.columns or not all(c in df.columns for c in components):
            return {"valid": False, "reason": "Column not found"}

        try:
            y = df[target].dropna().values
            weighted_sum = sum(weights.get(c, 0) * df[c].loc[df[target].notna()].values
                             for c in components)

            if len(y) < 3 or np.std(weighted_sum) < 1e-10 or np.std(y) < 1e-10:
                return {"valid": False, "reason": "Insufficient variation"}

            # Regression
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                slope, intercept, r_value, p_value, std_err = stats.linregress(weighted_sum, y)

            r_squared = r_value ** 2

            return {
                "valid": True,
                "target": target,
                "components": components,
                "weights": weights,
                "r_squared": float(r_squared),
                "p_value": float(p_value),
                "statistically_significant": p_value < alpha,
                "perfect_match": r_squared > 0.9999,
                "confidence": "high" if r_squared > 0.99 and p_value < 0.001 else "medium",
            }

        except Exception as e:
            return {"valid": False, "reason": str(e)}


class ConstraintDiscoveryEngine:
    """Orchestrates full 4-stage constraint discovery pipeline."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.pivot_info: Optional[Dict[str, Any]] = None  # set if long-format detected

        # Auto-detect and reshape long-format datasets before analysis
        analysis_df = self._detect_and_pivot(df)

        self.numeric_df = analysis_df.select_dtypes(include=[np.number])
        self.rank_detector = RankAnalysisDetector()
        self.algebra_detector = AlgebraicRelationshipDetector()
        self.residual_detector = ResidualAnalysisDetector()
        self.stats_tester = StatisticalRelationshipTester()

    def _detect_and_pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect long-format datasets and pivot to wide format for constraint discovery.

        Long format pattern:
          - One 'name' column: string dtype, few unique values (category labels)
          - One 'value' column: numeric dtype
          - One 'id' column: identifies the entity each row belongs to

        If detected, pivots so each category becomes its own column.
        Works on ANY dataset — not specific to any domain.
        """
        n_rows = len(df)
        if n_rows < 10:
            return df

        str_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if not str_cols or not num_cols:
            return df

        # Find candidate 'name' columns: string, few unique values, looks like labels
        name_candidates = []
        for col in str_cols:
            n_unique = df[col].nunique(dropna=True)
            null_frac = df[col].isna().mean()
            if 2 <= n_unique <= 50 and null_frac < 0.3:
                name_candidates.append((col, n_unique))

        if not name_candidates:
            return df

        # For each candidate, find an ID column that creates a clean pivot
        best_pivot = None
        best_score = 0

        for name_col, n_cats in name_candidates:
            for id_col in str_cols + [c for c in df.columns if df[c].dtype in [np.int64, np.int32]]:
                if id_col == name_col:
                    continue
                n_ids = df[id_col].nunique(dropna=True)
                expected_rows = n_ids * n_cats
                # Good pivot: expected rows close to actual rows, and value column is numeric
                completeness = min(n_rows, expected_rows) / max(n_rows, expected_rows)
                if completeness > 0.7:
                    for val_col in num_cols:
                        score = completeness * n_cats  # more categories = more signal
                        if score > best_score:
                            best_score = score
                            best_pivot = (id_col, name_col, val_col)

        if best_pivot is None:
            return df

        id_col, name_col, val_col = best_pivot
        try:
            pivoted = df.pivot_table(
                index=id_col,
                columns=name_col,
                values=val_col,
                aggfunc="mean",
            ).reset_index(drop=True)

            # Flatten column names if multi-level
            pivoted.columns = [str(c) for c in pivoted.columns]
            pivoted = pivoted.dropna(how="all")

            if len(pivoted.columns) >= 3 and len(pivoted) >= 5:
                self.pivot_info = {
                    "id_col": id_col,
                    "name_col": name_col,
                    "val_col": val_col,
                    "n_categories": pivoted.shape[1],
                    "n_entities": len(pivoted),
                    "categories": list(pivoted.columns),
                }
                print(f"[ConstraintDiscovery] Long-format detected → pivoted to {pivoted.shape[1]} columns × {len(pivoted)} rows")
                print(f"[ConstraintDiscovery] Columns: {list(pivoted.columns)}")
                return pivoted
        except Exception as e:
            print(f"[ConstraintDiscovery] Pivot attempt failed ({e}), using original df")

        return df

    def discover_all_constraints(
        self,
        enable_stage1: bool = True,
        enable_stage2: bool = True,
        enable_stage3: bool = True,
        enable_stage4: bool = True,
        tolerance: float = 0.99,
    ) -> Dict[str, Any]:
        """
        Run full 4-stage discovery pipeline.

        Stage 1: Rank analysis (quick, identifies if dependencies exist)
        Stage 2: Algebraic detection (finds candidates)
        Stage 3: Residual analysis (validates with multiple operations)
        Stage 4: Statistical testing (confirms with p-values)

        Args:
            df: Input dataframe
            tolerance: R² threshold for considering relationship valid
            enable_stage*: Control which stages to run

        Returns:
            Dict with all discovered constraints and metadata
        """
        results = {
            "stage1_rank_analysis": None,
            "stage2_algebraic": [],
            "stage3_residual": [],
            "stage4_statistical": [],
            "validated_constraints": [],
            "summary": "",
        }

        # Stage 1: Quick screening
        if enable_stage1:
            print("[ConstraintDiscovery] Stage 1: Rank analysis...")
            results["stage1_rank_analysis"] = self.rank_detector.find_dependencies(
                self.numeric_df
            )

            if not results["stage1_rank_analysis"]["has_dependencies"]:
                results["summary"] = "No linear dependencies detected (likely no compositional features)"
                return results

        # Stage 2: Enumerate candidates
        if enable_stage2:
            print("[ConstraintDiscovery] Stage 2: Algebraic detection...")

            additive = self.algebra_detector.find_additive_relationships(
                self.numeric_df, tolerance=tolerance
            )
            results["stage2_algebraic"] = additive[:10]  # Top 10

            print(f"  Found {len(additive)} additive candidates")

        # Stage 3: Residual validation
        if enable_stage3 and len(results["stage2_algebraic"]) > 0:
            print("[ConstraintDiscovery] Stage 3: Residual analysis...")

            residuals = self.residual_detector.find_all_operations(
                self.numeric_df, tolerance=0.01
            )
            results["stage3_residual"] = residuals[:10]  # Top 10

            print(f"  Found {len(residuals)} residual-based relationships")

        # Stage 4: Statistical validation
        if enable_stage4 and len(results["stage2_algebraic"]) > 0:
            print("[ConstraintDiscovery] Stage 4: Statistical testing...")

            for candidate in results["stage2_algebraic"][:5]:  # Test top 5
                if candidate["type"] == "additive":
                    test_result = self.stats_tester.test_additive_relationship(
                        self.numeric_df,
                        candidate["target"],
                        candidate["components"],
                    )

                    if test_result.get("valid") and test_result.get("statistically_significant"):
                        results["stage4_statistical"].append(test_result)
                        results["validated_constraints"].append(test_result)

            print(f"  Validated {len(results['validated_constraints'])} constraints")

        # Summary
        num_validated = len(results["validated_constraints"])
        if num_validated > 0:
            results["summary"] = (
                f"Found {num_validated} validated compositional relationships. "
                f"These are likely dataset structure (components summing to totals), "
                f"not leakage. Model should respect these constraints."
            )
        else:
            results["summary"] = "No validated compositional constraints found."

        return results
