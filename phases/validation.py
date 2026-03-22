"""
ValidationPhase — critical review of training results.

Stress-tests the results: overfitting checks, metric soundness,
production risk assessment.

Agents (required): skeptic
Agents (optional): devil_advocate, statistician

Outputs:
  validation_report  — skeptic's critical evaluation
  risk_analysis      — devil_advocate's production failure scenarios
  stat_validation    — statistician's metric soundness check
"""

from memory.context_manager import ROLE_ANALYSIS
from .base import BasePhase, PhaseResult


class ValidationPhase(BasePhase):

    name = "validation"
    REQUIRED_AGENTS = ["skeptic"]

    def _run(
        self,
        execution_result = None,
        metrics:    dict = None,
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        metrics_str = str(metrics or {})
        status      = "succeeded" if (execution_result and execution_result.success) else "failed/not run"

        print("\n⚡ [Validation] Critical evaluation of results...")

        # Skeptic: are the metrics trustworthy?
        orch.step(
            "skeptic",
            f"The training run {status}. Reported metrics: {metrics_str}.\n\n"
            "Critically evaluate:\n"
            "1. Are these metrics trustworthy? Could there be data leakage?\n"
            "2. Signs of overfitting (train vs. validation gap)?\n"
            "3. Is the evaluation metric appropriate for the business problem?\n"
            "4. What could cause these metrics to look good in training but fail in production?",
            ROLE_ANALYSIS,
        )

        # Devil's Advocate: production failure scenarios (optional)
        if "devil_advocate" in orch.agents:
            orch.step(
                "devil_advocate",
                f"Metrics: {metrics_str}. Training {status}.\n\n"
                "Identify the three most likely ways this model fails in production. "
                "Be specific about edge cases, distribution shifts, and adversarial inputs.",
                ROLE_ANALYSIS,
            )

        # Statistician: metric confidence (optional)
        if "statistician" in orch.agents:
            orch.step(
                "statistician",
                f"Validate statistical soundness. Metrics: {metrics_str}.\n\n"
                "1. Are the reported metrics statistically meaningful given the dataset size?\n"
                "2. Estimate confidence intervals for the primary metric.\n"
                "3. Is cross-validation sufficient, or do we need a separate holdout?",
                ROLE_ANALYSIS,
            )

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary="Validation complete. See skeptic, devil_advocate, and statistician outputs.",
            outputs={
                "validation_report": self._last_output("skeptic"),
                "risk_analysis":     self._last_output("devil_advocate"),
                "stat_validation":   self._last_output("statistician"),
            },
        )
