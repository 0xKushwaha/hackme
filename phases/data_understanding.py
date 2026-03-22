"""
DataUnderstandingPhase — EDA, data quality, statistical analysis, ethics.

RETRY ARCHITECTURE
==================

Every agent call in this phase is wrapped in a retry loop. If a step fails,
the error is injected back into the next attempt's task so the agent knows
what went wrong and can adjust.

Stage 0 — BuilderAgent (non-tabular datasets only)
  - Retried up to MAX_BUILDER_RETRIES times on exception
  - Library errors during tool validation → LibraryInstallerAgent runs first
  - Tool code errors → LLM asked to rewrite with error context
  - If BuilderAgent completely fails → continue with default agents only

Stage 1 — Core EDA agents (always run, sequential-with-retry)
  Explorer, Skeptic, Statistician each get MAX_AGENT_RETRIES attempts.
  On failure the error is appended to the task for the next try.

Stage 2 — Specialist agents (from BuilderAgent, sequential-with-retry)
  Each specialist independently retried. One failing doesn't block others.
  Library errors → LibraryInstallerAgent installed → retry.

Stage 3 — Ethicist (optional, with retry)
"""

from memory.context_manager import ROLE_ANALYSIS, ROLE_META
from agents.installer_agent import LibraryInstallerAgent
from .base import BasePhase, PhaseResult


MAX_BUILDER_RETRIES = 2   # how many times to retry the whole BuilderAgent.run()
MAX_AGENT_RETRIES   = 2   # how many times to retry a single agent step


class DataUnderstandingPhase(BasePhase):

    name = "data_understanding"
    REQUIRED_AGENTS = ["explorer", "skeptic", "statistician"]

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self.installer = LibraryInstallerAgent()

    def _run(
        self,
        dataset_summary: str = "",
        dataset_profile  = None,   # phases.discovery.DatasetProfile
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        # ── Pin dataset summary ───────────────────────────────────────────
        if dataset_summary:
            orch.context.add_dataset_context(dataset_summary)

        # ── Stage 0: Builder Agent ────────────────────────────────────────
        build_plan = None

        if dataset_profile and getattr(orch, "builder_agent", None):
            build_plan = self._run_builder_with_retry(dataset_profile, dataset_summary)

            if build_plan and build_plan.strategy:
                orch.context.add(
                    "builder_agent", ROLE_META,
                    f"DATASET ANALYSIS STRATEGY:\n{build_plan.strategy}",
                    pinned=True,
                )

            if build_plan:
                for agent_spec in build_plan.agents:
                    orch.add_dynamic_agent(agent_spec.name, agent_spec.system_prompt)

        # ── Stage 1: Core EDA agents ──────────────────────────────────────
        print("\n⚡ [DataUnderstanding] Core EDA agents starting...")

        self._step_with_retry(
            "explorer",
            "Perform a thorough exploratory data analysis. Identify the most likely "
            "target variable, key predictive features, important patterns, and noteworthy "
            "correlations. If this is a multi-file or non-tabular dataset, describe each "
            "component and how they relate to each other.",
            ROLE_ANALYSIS,
        )
        self._step_with_retry(
            "skeptic",
            "Inspect data quality: missing values, outliers, duplicate rows, class "
            "imbalance, and any potential data leakage between features and target. "
            "If multiple file types are present, flag format inconsistencies.",
            ROLE_ANALYSIS,
        )
        self._step_with_retry(
            "statistician",
            "Analyze feature distributions, skewness, multicollinearity, and the "
            "statistical significance of key correlations. For non-tabular data, "
            "describe what statistical measures apply and flag distributional red flags.",
            ROLE_ANALYSIS,
        )

        # ── Stage 2: Specialist agents ────────────────────────────────────
        specialist_reports: dict[str, str] = {}

        if build_plan and build_plan.agents:
            print(f"\n⚡ [DataUnderstanding] Running {len(build_plan.agents)} specialist agent(s)...")
            for spec in build_plan.agents:
                if spec.name not in orch.agents:
                    continue
                out = self._step_with_retry(
                    spec.name, spec.task, ROLE_ANALYSIS,
                    label=f"specialist:{spec.name}",
                )
                specialist_reports[spec.name] = out

        # ── Stage 3: Ethicist (optional) ──────────────────────────────────
        ethics_notes = ""
        if "ethicist" in orch.agents:
            print("\n⚡ [DataUnderstanding] Ethicist reviewing for bias...")
            ethics_notes = self._step_with_retry(
                "ethicist",
                "Identify sensitive attributes, potential proxy variables, bias risks, "
                "and fairness concerns. If non-tabular data (images, audio, text) is "
                "present, flag representational bias risks.",
                ROLE_ANALYSIS,
            )

        # ── Summary ───────────────────────────────────────────────────────
        explorer_out = self._last_output("explorer")
        n_agents = 3 + len(specialist_reports) + (1 if ethics_notes else 0)
        used_builder = build_plan and not build_plan.is_empty

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary=(
                f"Data understanding complete ({n_agents} agents"
                f"{', builder used' if used_builder else ''}). "
                f"EDA: {explorer_out[:120]}..."
            ),
            outputs={
                "eda_summary":        explorer_out,
                "quality_report":     self._last_output("skeptic"),
                "stats_report":       self._last_output("statistician"),
                "specialist_reports": specialist_reports,
                "ethics_notes":       ethics_notes,
                "build_plan":         build_plan,
            },
        )

    # ------------------------------------------------------------------ #
    # Retry helpers                                                         #
    # ------------------------------------------------------------------ #

    def _run_builder_with_retry(self, profile, profile_text: str):
        """
        Run BuilderAgent.run() with up to MAX_BUILDER_RETRIES attempts.
        On exception, retry. If all fail, return None (pipeline continues
        with default agents only).
        """
        last_error = None
        for attempt in range(1, MAX_BUILDER_RETRIES + 1):
            try:
                plan = self.orch.builder_agent.run(profile, profile_text)
                return plan
            except Exception as exc:
                last_error = str(exc)
                print(
                    f"[DataUnderstanding] ⚠️  BuilderAgent attempt {attempt}/"
                    f"{MAX_BUILDER_RETRIES} failed: {exc}"
                )
                if attempt < MAX_BUILDER_RETRIES:
                    print(f"[DataUnderstanding] 🔁 Retrying BuilderAgent...")

        print(
            f"[DataUnderstanding] ❌ BuilderAgent failed after {MAX_BUILDER_RETRIES} "
            "attempts. Continuing with default agents only."
        )
        return None

    def _step_with_retry(
        self,
        agent_name: str,
        task: str,
        role: str,
        label: str = "",
        max_retries: int = MAX_AGENT_RETRIES,
    ) -> str:
        """
        Run orchestrator.step() with retry. On failure:
          1. Detect ImportError → LibraryInstallerAgent installs packages
          2. Append error context to the task for the next attempt
          3. Retry up to max_retries times

        Returns the agent's output string (or an error placeholder if all fail).
        """
        label = label or agent_name
        last_error: str = ""
        current_task = task

        for attempt in range(1, max_retries + 1):
            try:
                result = self.orch.step(agent_name, current_task, role)
                if attempt > 1:
                    print(f"[DataUnderstanding] ✅ {label} succeeded on attempt {attempt}")
                return result

            except Exception as exc:
                last_error = str(exc)
                print(
                    f"[DataUnderstanding] ⚠️  {label} attempt {attempt}/{max_retries} "
                    f"failed: {exc}"
                )

                # Auto-install missing libraries
                if "import" in last_error.lower() or "module" in last_error.lower():
                    install = self.installer.handle(last_error)
                    if install.any_success:
                        print(
                            f"[DataUnderstanding] 🔄 Installed {install.succeeded} "
                            "— will retry without changing task."
                        )
                        # Don't modify task — just retry after install
                        continue

                # Inject error context for next LLM attempt
                if attempt < max_retries:
                    current_task = (
                        f"{task}\n\n"
                        f"[RETRY CONTEXT — attempt {attempt + 1}/{max_retries}]\n"
                        f"Previous attempt failed with: {last_error}\n"
                        "Adjust your approach accordingly."
                    )

        placeholder = f"[{label} failed after {max_retries} attempts: {last_error[:120]}]"
        print(f"[DataUnderstanding] ❌ {placeholder}")
        return placeholder
