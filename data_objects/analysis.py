"""Domain-specific data objects for analysis outputs."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
from .base import DataObject


@dataclass
class Constraint:
    """A single discovered constraint."""
    formula: str
    strength: float  # R² or other metric
    type: str  # "additive", "linear_combination", "normalized_operation"
    components: List[str]
    target: str
    details: Dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    confidence: str = "medium"  # "low", "medium", "high"


@dataclass
class FeatureAnalysis(DataObject):
    """Analysis of a single feature."""
    feature_name: str = ""
    data_type: str = ""  # "numeric", "categorical", "datetime", etc.

    # Distribution info
    distribution_type: str = ""  # "normal", "skewed", "bimodal", etc.
    skewness: float = 0.0
    kurtosis: float = 0.0

    # Data quality
    missing_percent: float = 0.0
    cardinality: int = 0
    unique_values: int = 0

    # Relationships to other features
    correlations: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # {feature: (r, p_value)}
    interaction_features: List[str] = field(default_factory=list)  # features this interacts with

    # Suggested preprocessing
    suggested_engineering: List[str] = field(default_factory=list)
    suggested_transformation: str = ""  # "log", "sqrt", "box-cox", "none"

    # Domain info
    is_target: bool = False
    potential_leakage: bool = False
    leakage_reason: str = ""

    def to_text_summary(self) -> str:
        lines = [f"## Feature: {self.feature_name}"]
        lines.append(f"- Type: {self.data_type}")
        lines.append(f"- Distribution: {self.distribution_type} (skew: {self.skewness:.2f})")
        lines.append(f"- Missing: {self.missing_percent:.1f}% | Unique: {self.unique_values}")

        if self.correlations:
            corr_str = ", ".join([
                f"{k}: r={v[0]:.3f}" for k, v in list(self.correlations.items())[:3]
            ])
            lines.append(f"- Top correlations: {corr_str}")

        if self.suggested_engineering:
            lines.append(f"- Suggested engineering: {', '.join(self.suggested_engineering[:2])}")

        if self.potential_leakage:
            lines.append(f"⚠️  LEAKAGE RISK: {self.leakage_reason}")

        if self.verified:
            lines.append(f"✓ Verified (confidence: {self.confidence:.2f})")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "type": "FeatureAnalysis",
            "feature_name": self.feature_name,
            "data_type": self.data_type,
            "distribution_type": self.distribution_type,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "missing_percent": self.missing_percent,
            "cardinality": self.cardinality,
            "unique_values": self.unique_values,
            "correlations": {k: list(v) for k, v in self.correlations.items()},
            "interaction_features": self.interaction_features,
            "suggested_engineering": self.suggested_engineering,
            "suggested_transformation": self.suggested_transformation,
            "is_target": self.is_target,
            "potential_leakage": self.potential_leakage,
            "leakage_reason": self.leakage_reason,
            "verified": self.verified,
            "confidence": self.confidence,
            "computed_at": self.computed_at,
            "verified_at": self.verified_at,
            "verification_method": self.verification_method,
            "verification_details": self.verification_details,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeatureAnalysis":
        obj = cls(
            feature_name=d.get("feature_name", ""),
            data_type=d.get("data_type", ""),
            distribution_type=d.get("distribution_type", ""),
            skewness=d.get("skewness", 0.0),
            kurtosis=d.get("kurtosis", 0.0),
            missing_percent=d.get("missing_percent", 0.0),
            cardinality=d.get("cardinality", 0),
            unique_values=d.get("unique_values", 0),
            correlations={k: tuple(v) for k, v in d.get("correlations", {}).items()},
            interaction_features=d.get("interaction_features", []),
            suggested_engineering=d.get("suggested_engineering", []),
            suggested_transformation=d.get("suggested_transformation", ""),
            is_target=d.get("is_target", False),
            potential_leakage=d.get("potential_leakage", False),
            leakage_reason=d.get("leakage_reason", ""),
            verified=d.get("verified", False),
            confidence=d.get("confidence", 0.5),
            verification_method=d.get("verification_method", ""),
        )
        obj.computed_at = d.get("computed_at", obj.computed_at)
        obj.verified_at = d.get("verified_at")
        obj.verification_details = d.get("verification_details", {})
        obj.notes = d.get("notes", "")
        return obj


@dataclass
class RelationshipAnalysis(DataObject):
    """Analysis of relationships between two features or feature & target."""
    feature_a: str = ""
    feature_b: str = ""
    relationship_type: str = ""  # "linear", "non_linear", "categorical", "interaction"
    strength: float = 0.0  # 0-1, where 1 is perfect
    p_value: float = 1.0
    correlation: float = 0.0  # for numeric-numeric
    sample_size: int = 0
    verified_by: str = ""  # "Statistician", "Validator", "Engine"

    # Additional details
    interaction_strength: float = 0.0  # for interactions
    conditional_patterns: Dict[str, Any] = field(default_factory=dict)
    non_linear_info: Dict[str, Any] = field(default_factory=dict)  # e.g., LOWESS vs linear fit

    def to_text_summary(self) -> str:
        lines = [f"## Relationship: {self.feature_a} ↔ {self.feature_b}"]
        lines.append(f"- Type: {self.relationship_type}")
        lines.append(f"- Strength: {self.strength:.3f} (r={self.correlation:.3f} if numeric)")
        lines.append(f"- p-value: {self.p_value:.4f}")
        lines.append(f"- Sample size: {self.sample_size}")

        if self.verified:
            lines.append(f"✓ Verified by {self.verified_by} (confidence: {self.confidence:.2f})")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "type": "RelationshipAnalysis",
            "feature_a": self.feature_a,
            "feature_b": self.feature_b,
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "p_value": self.p_value,
            "correlation": self.correlation,
            "sample_size": self.sample_size,
            "verified_by": self.verified_by,
            "interaction_strength": self.interaction_strength,
            "conditional_patterns": self.conditional_patterns,
            "non_linear_info": self.non_linear_info,
            "verified": self.verified,
            "confidence": self.confidence,
            "computed_at": self.computed_at,
            "verified_at": self.verified_at,
            "verification_method": self.verification_method,
            "verification_details": self.verification_details,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RelationshipAnalysis":
        obj = cls(
            feature_a=d.get("feature_a", ""),
            feature_b=d.get("feature_b", ""),
            relationship_type=d.get("relationship_type", ""),
            strength=d.get("strength", 0.0),
            p_value=d.get("p_value", 1.0),
            correlation=d.get("correlation", 0.0),
            sample_size=d.get("sample_size", 0),
            verified_by=d.get("verified_by", ""),
            interaction_strength=d.get("interaction_strength", 0.0),
            conditional_patterns=d.get("conditional_patterns", {}),
            non_linear_info=d.get("non_linear_info", {}),
            verified=d.get("verified", False),
            confidence=d.get("confidence", 0.5),
            verification_method=d.get("verification_method", ""),
        )
        obj.computed_at = d.get("computed_at", obj.computed_at)
        obj.verified_at = d.get("verified_at")
        obj.verification_details = d.get("verification_details", {})
        obj.notes = d.get("notes", "")
        return obj


@dataclass
class ValidationResult(DataObject):
    """Result of validating agent claims against actual data."""
    agent_name: str = ""
    phase: str = ""  # "data_understanding", "model_design"

    verified_claims: List[str] = field(default_factory=list)
    inconsistent_claims: List[Tuple[str, str]] = field(default_factory=list)  # (claim, actual_finding)
    missing_patterns: List[str] = field(default_factory=list)  # patterns data shows but agent missed

    # Computed ground truth to help agents refine
    ground_truth_relationships: Dict[str, RelationshipAnalysis] = field(default_factory=dict)

    # Feedback
    overall_accuracy: float = 0.0  # % of claims that matched actual data
    recommendation: str = ""  # e.g., "refine feature list", "reconsider correlations"
    refinement_needed: bool = False

    def to_text_summary(self) -> str:
        lines = [f"## Validation Report: {self.agent_name}"]
        lines.append(f"- Verified claims: {len(self.verified_claims)}")
        lines.append(f"- Inconsistencies: {len(self.inconsistent_claims)}")
        lines.append(f"- Missing patterns: {len(self.missing_patterns)}")
        lines.append(f"- Overall accuracy: {self.overall_accuracy:.1%}")

        if self.inconsistent_claims:
            lines.append("\nInconsistencies found:")
            for claim, actual in self.inconsistent_claims[:3]:
                lines.append(f"  ✗ Agent said: {claim[:50]}...")
                lines.append(f"    Actual: {actual[:50]}...")

        if self.recommendation:
            lines.append(f"\n📝 Recommendation: {self.recommendation}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "type": "ValidationResult",
            "agent_name": self.agent_name,
            "phase": self.phase,
            "verified_claims": self.verified_claims,
            "inconsistent_claims": self.inconsistent_claims,
            "missing_patterns": self.missing_patterns,
            "ground_truth_relationships": {
                k: v.to_dict() for k, v in self.ground_truth_relationships.items()
            },
            "overall_accuracy": self.overall_accuracy,
            "recommendation": self.recommendation,
            "refinement_needed": self.refinement_needed,
            "verified": self.verified,
            "confidence": self.confidence,
            "computed_at": self.computed_at,
            "verified_at": self.verified_at,
            "verification_method": self.verification_method,
            "verification_details": self.verification_details,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ValidationResult":
        ground_truth = {}
        for k, v in d.get("ground_truth_relationships", {}).items():
            ground_truth[k] = RelationshipAnalysis.from_dict(v)

        obj = cls(
            agent_name=d.get("agent_name", ""),
            phase=d.get("phase", ""),
            verified_claims=d.get("verified_claims", []),
            inconsistent_claims=d.get("inconsistent_claims", []),
            missing_patterns=d.get("missing_patterns", []),
            ground_truth_relationships=ground_truth,
            overall_accuracy=d.get("overall_accuracy", 0.0),
            recommendation=d.get("recommendation", ""),
            refinement_needed=d.get("refinement_needed", False),
            verified=d.get("verified", False),
            confidence=d.get("confidence", 0.5),
            verification_method=d.get("verification_method", ""),
        )
        obj.computed_at = d.get("computed_at", obj.computed_at)
        obj.verified_at = d.get("verified_at")
        obj.verification_details = d.get("verification_details", {})
        obj.notes = d.get("notes", "")
        return obj


@dataclass
class ConstraintAnalysis(DataObject):
    """Analysis of mathematical/compositional constraints in the dataset."""

    discovered_constraints: List[Constraint] = field(default_factory=list)
    validated_constraints: List[Constraint] = field(default_factory=list)
    rank_deficiency: int = 0  # Number of linear dependencies
    has_compositional_structure: bool = False
    interpretation: str = ""

    # Stage results (for transparency)
    stage1_rank: Optional[Dict[str, Any]] = None
    stage2_candidates: List[Dict[str, Any]] = field(default_factory=list)
    stage3_residuals: List[Dict[str, Any]] = field(default_factory=list)
    stage4_statistical: List[Dict[str, Any]] = field(default_factory=list)

    # Set by engine if long-format was detected and pivoted
    pivot_info: Optional[Dict[str, Any]] = None

    def to_text_summary(self) -> str:
        lines = ["## Constraint Analysis"]

        # Report if long-format was detected and pivoted
        if self.pivot_info:
            lines.append(f"\n### Data Reshaping")
            lines.append(f"**Long-format detected** — dataset was auto-pivoted before analysis.")
            lines.append(f"- ID column: `{self.pivot_info.get('id_col')}`")
            lines.append(f"- Name column: `{self.pivot_info.get('name_col')}`")
            lines.append(f"- Value column: `{self.pivot_info.get('val_col')}`")
            lines.append(f"- Pivoted to {self.pivot_info.get('n_categories')} columns × {self.pivot_info.get('n_entities')} rows")
            lines.append(f"- Categories analysed: {', '.join(f'`{c}`' for c in (self.pivot_info.get('categories') or []))}")

        lines.append("")

        if not self.validated_constraints and not self.discovered_constraints:
            lines.append("No compositional constraints found.")
            if self.stage1_rank:
                interp = self.stage1_rank.get("interpretation", "")
                if interp:
                    lines.append(f"\n*Stage 1 rank analysis: {interp}*")
            return "\n".join(lines)

        # Validated constraints (high confidence)
        if self.validated_constraints:
            lines.append(f"### ✅ Validated Compositional Constraints ({len(self.validated_constraints)} found)")
            lines.append("")
            for i, c in enumerate(self.validated_constraints, 1):
                lines.append(f"**{i}. `{c.formula}`**")
                lines.append(f"- R² = {c.strength:.4f} | Confidence: {c.confidence} | Type: {c.type}")
                if c.components:
                    lines.append(f"- Components: {' + '.join(f'`{x}`' for x in c.components)} → `{c.target}`")
                lines.append(f"- ⚠️ **Modeling implication**: These are compositional features — predicting components separately risks violating this sum constraint. Use a constrained multi-output model or post-process to enforce it.")
                lines.append("")

        # Discovered but not yet statistically validated
        if self.discovered_constraints:
            lines.append(f"### 🔍 Candidate Relationships ({len(self.discovered_constraints)} found, not fully validated)")
            lines.append("")
            for i, c in enumerate(self.discovered_constraints[:5], 1):
                lines.append(f"{i}. `{c.formula}` — R² = {c.strength:.4f}")
            lines.append("")

        if self.rank_deficiency > 0:
            lines.append(f"### Rank Analysis")
            lines.append(f"- Rank deficiency: **{self.rank_deficiency}** linear dependencies detected")
            lines.append("- Some features are exact or near-exact linear combinations of others")

        if self.interpretation:
            lines.append(f"\n### Summary")
            lines.append(self.interpretation)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "type": "ConstraintAnalysis",
            "discovered_constraints": [asdict(c) for c in self.discovered_constraints],
            "validated_constraints": [asdict(c) for c in self.validated_constraints],
            "rank_deficiency": self.rank_deficiency,
            "has_compositional_structure": self.has_compositional_structure,
            "interpretation": self.interpretation,
            "stage1_rank": self.stage1_rank,
            "stage2_candidates": self.stage2_candidates,
            "stage3_residuals": self.stage3_residuals,
            "stage4_statistical": self.stage4_statistical,
            "verified": self.verified,
            "confidence": self.confidence,
            "computed_at": self.computed_at,
            "verified_at": self.verified_at,
            "verification_method": self.verification_method,
            "verification_details": self.verification_details,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConstraintAnalysis":
        discovered = [
            Constraint(**c) for c in d.get("discovered_constraints", [])
        ]
        validated = [
            Constraint(**c) for c in d.get("validated_constraints", [])
        ]

        obj = cls(
            discovered_constraints=discovered,
            validated_constraints=validated,
            rank_deficiency=d.get("rank_deficiency", 0),
            has_compositional_structure=d.get("has_compositional_structure", False),
            interpretation=d.get("interpretation", ""),
            stage1_rank=d.get("stage1_rank"),
            stage2_candidates=d.get("stage2_candidates", []),
            stage3_residuals=d.get("stage3_residuals", []),
            stage4_statistical=d.get("stage4_statistical", []),
            verified=d.get("verified", False),
            confidence=d.get("confidence", 0.5),
            verification_method=d.get("verification_method", ""),
        )
        obj.computed_at = d.get("computed_at", obj.computed_at)
        obj.verified_at = d.get("verified_at")
        obj.verification_details = d.get("verification_details", {})
        obj.notes = d.get("notes", "")
        return obj
