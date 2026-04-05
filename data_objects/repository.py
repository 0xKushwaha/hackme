"""Repository for storing and querying data objects across a run."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Type
from .base import DataObject
from .analysis import FeatureAnalysis, RelationshipAnalysis, ValidationResult, ConstraintAnalysis


class DataRepository:
    """In-memory repository for data objects with disk persistence."""

    def __init__(self, run_id: str, experiment_dir: str = "experiments"):
        self.run_id = run_id
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self.feature_analyses: Dict[str, FeatureAnalysis] = {}
        self.relationship_analyses: Dict[str, RelationshipAnalysis] = {}
        self.validation_results: List[ValidationResult] = []
        self.constraint_analyses: List[ConstraintAnalysis] = []

        self._load_from_disk()

    def _get_repo_path(self) -> Path:
        """Get path to repository JSON file."""
        return self.experiment_dir / f"data_objects_{self.run_id}.json"

    def add_feature_analysis(self, analysis: FeatureAnalysis):
        """Store feature analysis."""
        self.feature_analyses[analysis.feature_name] = analysis

    def add_relationship_analysis(self, analysis: RelationshipAnalysis):
        """Store relationship analysis."""
        key = f"{analysis.feature_a}_{analysis.feature_b}"
        self.relationship_analyses[key] = analysis

    def add_validation_result(self, result: ValidationResult):
        """Store validation result."""
        self.validation_results.append(result)

    def add_constraint_analysis(self, analysis: ConstraintAnalysis):
        """Store constraint analysis."""
        self.constraint_analyses.append(analysis)

    def get_feature_analysis(self, feature_name: str) -> Optional[FeatureAnalysis]:
        """Retrieve feature analysis."""
        return self.feature_analyses.get(feature_name)

    def get_relationship_analysis(
        self, feature_a: str, feature_b: str
    ) -> Optional[RelationshipAnalysis]:
        """Retrieve relationship analysis (order-independent)."""
        key1 = f"{feature_a}_{feature_b}"
        key2 = f"{feature_b}_{feature_a}"
        return self.relationship_analyses.get(key1) or self.relationship_analyses.get(key2)

    def get_all_relationships(self) -> List[RelationshipAnalysis]:
        """Get all stored relationships."""
        return list(self.relationship_analyses.values())

    def get_latest_validation(self) -> Optional[ValidationResult]:
        """Get most recent validation result."""
        return self.validation_results[-1] if self.validation_results else None

    def get_latest_constraint_analysis(self) -> Optional[ConstraintAnalysis]:
        """Get most recent constraint analysis."""
        return self.constraint_analyses[-1] if self.constraint_analyses else None

    def get_validated_constraints(self) -> list:
        """Get all validated constraints from all analyses."""
        all_constraints = []
        for analysis in self.constraint_analyses:
            all_constraints.extend(analysis.validated_constraints)
        return all_constraints

    def get_verified_features(self) -> List[FeatureAnalysis]:
        """Get all verified feature analyses."""
        return [f for f in self.feature_analyses.values() if f.verified]

    def get_high_confidence_relationships(
        self, min_confidence: float = 0.7
    ) -> List[RelationshipAnalysis]:
        """Get relationships above confidence threshold."""
        return [
            r for r in self.relationship_analyses.values()
            if r.verified and r.confidence >= min_confidence
        ]

    def save(self):
        """Persist repository to disk."""
        data = {
            "run_id": self.run_id,
            "feature_analyses": {
                k: v.to_dict() for k, v in self.feature_analyses.items()
            },
            "relationship_analyses": {
                k: v.to_dict() for k, v in self.relationship_analyses.items()
            },
            "validation_results": [v.to_dict() for v in self.validation_results],
            "constraint_analyses": [c.to_dict() for c in self.constraint_analyses],
        }

        repo_path = self._get_repo_path()
        with open(repo_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_from_disk(self):
        """Load repository from disk if it exists."""
        repo_path = self._get_repo_path()
        if not repo_path.exists():
            return

        try:
            with open(repo_path, "r") as f:
                data = json.load(f)

            # Reconstruct feature analyses
            for name, obj_dict in data.get("feature_analyses", {}).items():
                self.feature_analyses[name] = FeatureAnalysis.from_dict(obj_dict)

            # Reconstruct relationship analyses
            for key, obj_dict in data.get("relationship_analyses", {}).items():
                self.relationship_analyses[key] = RelationshipAnalysis.from_dict(obj_dict)

            # Reconstruct validation results
            for obj_dict in data.get("validation_results", []):
                self.validation_results.append(ValidationResult.from_dict(obj_dict))

            # Reconstruct constraint analyses
            for obj_dict in data.get("constraint_analyses", []):
                self.constraint_analyses.append(ConstraintAnalysis.from_dict(obj_dict))

        except Exception as e:
            print(f"[DataRepository] Failed to load from disk: {e}")

    def summary(self) -> str:
        """Get summary of repository contents."""
        total_constraints = sum(
            len(ca.validated_constraints) for ca in self.constraint_analyses
        )
        lines = [
            f"[DataRepository] run_id={self.run_id}",
            f"  Features analyzed: {len(self.feature_analyses)}",
            f"  Relationships: {len(self.relationship_analyses)}",
            f"  Validations: {len(self.validation_results)}",
            f"  Constraint analyses: {len(self.constraint_analyses)}",
            f"  Validated constraints: {total_constraints}",
            f"  Verified features: {len(self.get_verified_features())}",
        ]
        return "\n".join(lines)
