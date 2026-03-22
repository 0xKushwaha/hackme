"""
DataUnderstandingPhase — EDA, data quality, statistical analysis, ethics.

Agents (required): explorer, skeptic, statistician
Agents (optional): ethicist

Outputs:
  eda_summary     — explorer's full EDA output
  quality_report  — skeptic's data quality assessment
  stats_report    — statistician's distribution + correlation analysis
  ethics_notes    — ethicist's bias and fairness concerns (empty if absent)
"""

from memory.context_manager import ROLE_ANALYSIS
from .base import BasePhase, PhaseResult


class DataUnderstandingPhase(BasePhase):

    name = "data_understanding"
    REQUIRED_AGENTS = ["explorer", "skeptic", "statistician"]

    def _run(self, dataset_summary: str = "", **kwargs) -> PhaseResult:
        orch = self.orch

        # Pin dataset summary in context (survives compaction)
        if dataset_summary:
            orch.context.add_dataset_context(dataset_summary)

        # Round 1: parallel EDA — explorer + skeptic + statistician
        print("\n⚡ [DataUnderstanding] EDA agents running in parallel...")
        orch.parallel_step([
            (
                "explorer",
                "Perform a thorough exploratory data analysis. Identify the most likely target "
                "variable, key predictive features, important patterns, and noteworthy correlations.",
                ROLE_ANALYSIS,
            ),
            (
                "skeptic",
                "Inspect data quality: missing values, outliers, duplicate rows, class imbalance, "
                "and any potential data leakage between features and target.",
                ROLE_ANALYSIS,
            ),
            (
                "statistician",
                "Analyze feature distributions, skewness, multicollinearity, and the statistical "
                "significance of key correlations. Flag any distributional red flags.",
                ROLE_ANALYSIS,
            ),
        ])

        # Round 2: ethicist (optional)
        ethics_notes = ""
        if "ethicist" in orch.agents:
            print("\n⚡ [DataUnderstanding] Ethicist reviewing for bias...")
            ethics_notes = orch.step(
                "ethicist",
                "Identify sensitive attributes, potential proxy variables, bias risks, and "
                "fairness concerns. Note any protected characteristics in the data.",
                ROLE_ANALYSIS,
            )

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary=(
                f"Data understanding complete. "
                f"EDA: {self._last_output('explorer')[:150]}..."
            ),
            outputs={
                "eda_summary":    self._last_output("explorer"),
                "quality_report": self._last_output("skeptic"),
                "stats_report":   self._last_output("statistician"),
                "ethics_notes":   ethics_notes,
            },
        )
