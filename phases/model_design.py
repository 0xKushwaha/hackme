"""
ModelDesignPhase — feature engineering, model selection, planning.

Agents (required): feature_engineer, pragmatist
Agents (optional): devil_advocate, optimizer

Outputs:
  feature_plan      — feature engineering recommendations
  modeling_plan     — pragmatist's actionable modeling plan
  critique          — devil's advocate stress-test of the plan
  tuning_strategy   — optimizer's hyperparameter + CV strategy
"""

from memory.context_manager import ROLE_ANALYSIS, ROLE_PLAN
from .base import BasePhase, PhaseResult


class ModelDesignPhase(BasePhase):

    name = "model_design"
    REQUIRED_AGENTS = ["feature_engineer", "pragmatist"]

    def _run(self, **kwargs) -> PhaseResult:
        orch = self.orch

        # Feature engineering recommendations
        print("\n⚡ [ModelDesign] Feature engineering...")
        orch.step(
            "feature_engineer",
            "Based on the EDA and data quality analysis above, suggest concrete feature engineering "
            "steps: encoding strategies for categorical variables, numerical transformations, "
            "interaction features, columns to drop, and any domain-specific features worth creating.",
            ROLE_ANALYSIS,
        )

        # Modeling plan
        print("\n⚡ [ModelDesign] Building modeling plan...")
        orch.step(
            "pragmatist",
            "Create a clear, actionable modeling plan:\n"
            "1. Identify the target column and task type (regression/classification)\n"
            "2. Recommend the top 2-3 models to try (in order of preference)\n"
            "3. Specify the primary evaluation metric\n"
            "4. Describe the train/validation/test split strategy\n"
            "5. List feature engineering steps to apply before training",
            ROLE_PLAN,
        )

        # Devil's Advocate challenges the plan (optional)
        if "devil_advocate" in orch.agents:
            print("\n⚡ [ModelDesign] Devil's Advocate stress-testing the plan...")
            orch.step(
                "devil_advocate",
                "Critically challenge the Pragmatist's modeling plan. What assumptions might be wrong? "
                "What could go catastrophically wrong? Propose one concrete alternative approach that "
                "takes a meaningfully different direction.",
                ROLE_PLAN,
            )

        # Optimizer adds tuning strategy (optional)
        if "optimizer" in orch.agents:
            print("\n⚡ [ModelDesign] Optimizer adding tuning strategy...")
            orch.step(
                "optimizer",
                "For the models in the plan above, recommend a hyperparameter tuning strategy: "
                "which parameters to tune, ranges to search, cross-validation approach (folds, "
                "stratification), and early stopping criteria if applicable.",
                ROLE_PLAN,
            )

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary="Modeling plan ready. Feature engineering and tuning strategy defined.",
            outputs={
                "feature_plan":    self._last_output("feature_engineer"),
                "modeling_plan":   self._last_output("pragmatist"),
                "critique":        self._last_output("devil_advocate"),
                "tuning_strategy": self._last_output("optimizer"),
            },
        )
