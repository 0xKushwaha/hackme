"""
DataUnderstandingPhase — EDA, data quality, statistical analysis, ethics.

RETRY ARCHITECTURE
==================

Every agent call in this phase is wrapped in a retry loop. If a step fails,
the error is injected back into the next attempt's task so the agent knows
what went wrong and can adjust. Library import errors trigger auto-install
via LibraryInstallerAgent before retrying.

Stage 1 — Core EDA agents (always run, sequential-with-retry)
  Explorer, Skeptic, Statistician each get MAX_AGENT_RETRIES attempts.

Stage 2 — Ethicist (optional, with retry)
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from memory.context_manager import ROLE_ANALYSIS, ROLE_META
from agents.installer_agent import LibraryInstallerAgent
from analysis.data_profiler import DataProfiler
from .base import BasePhase, PhaseResult


MAX_AGENT_RETRIES = 2   # how many times to retry a single agent step

# Early stopping thresholds (Karpathy: skip what adds no value)
SKIP_SKEPTIC_QUALITY_THRESHOLD   = 0.92   # data is very clean → skeptic does quick pass
SKIP_ETHICIST_QUALITY_THRESHOLD  = 0.95   # extremely clean data → ethicist optional
FOCUS_STATISTICIAN_CORR_PAIRS    = 2      # if > N high-corr pairs → statistician focuses there


class DataUnderstandingPhase(BasePhase):

    name = "data_understanding"
    REQUIRED_AGENTS = ["explorer", "skeptic", "statistician"]

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self.installer = LibraryInstallerAgent()
        self.profiler  = DataProfiler()

    def _run(
        self,
        dataset_summary: str = "",
        dataset_profile  = None,   # phases.discovery.DatasetProfile
        dataset_path:    str = "",
        target_col:      str = None,
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        # ── Pin dataset summary + task goal ──────────────────────────────
        if dataset_summary:
            orch.context.add_dataset_context(dataset_summary)
        orch._pin_task_context()

        # ── Pre-LLM data profile (no inference cost) ─────────────────────
        # Inspired by Karpathy's data-centric principle: profile first, route second.
        data_metrics = None
        if dataset_path:
            data_metrics = self.profiler.profile(dataset_path, target_col)

        if data_metrics:
            print(f"\n📊 [DataUnderstanding] Pre-LLM profile complete (quality={data_metrics.data_quality_score:.2f})")
            orch.context.add(
                "data_profiler", ROLE_META,
                data_metrics.summary_text,
                pinned=True,
            )
            # Push adaptive metrics to orchestrator for personality adjustment
            orch._data_metrics = {
                "data_quality_score": data_metrics.data_quality_score,
                "n_rows":             data_metrics.n_rows,
                "class_imbalance":    data_metrics.class_imbalance,
            }

        # ── Stage 1: Core EDA agents — run in PARALLEL ───────────────────
        print("\n⚡ [DataUnderstanding] Core EDA agents starting in parallel...")

        task_desc = getattr(orch, "task_description", "").strip()
        goal_suffix = (
            f"\n\nUSER GOAL / COMPETITION CONTEXT:\n{task_desc}\n"
            "Keep this goal in mind — flag features, patterns, and data issues "
            "most relevant to achieving it."
        ) if task_desc else ""

        # Build routing hints from data profile
        routing     = data_metrics.routing if data_metrics else {}
        profile_ctx = f"\n\n{data_metrics.summary_text}" if data_metrics else ""

        # ── Build tasks ──────────────────────────────────────────────────
        explorer_focus = ""
        if routing.get("explorer") == "focus_correlations":
            explorer_focus = "\nFOCUS: High-correlation pairs were detected — prioritize multicollinearity analysis."
        elif routing.get("explorer") == "focus_temporal":
            explorer_focus = "\nFOCUS: Time-series columns detected — prioritize temporal patterns and lag relationships."

        explorer_task = (
            "Perform a thorough exploratory data analysis. Identify the most likely "
            "target variable, key predictive features, important patterns, and noteworthy "
            "correlations. If this is a multi-file or non-tabular dataset, describe each "
            "component and how they relate to each other."
            + profile_ctx + explorer_focus + goal_suffix
        )

        skeptic_mode = routing.get("skeptic", "normal")
        if data_metrics and data_metrics.data_quality_score > SKIP_SKEPTIC_QUALITY_THRESHOLD:
            print(f"\n⚡ [DataUnderstanding] Data quality={data_metrics.data_quality_score:.2f} → Skeptic on QUICK pass")
            skeptic_task = (
                "Data quality pre-scan shows this dataset is very clean "
                f"(quality score {data_metrics.data_quality_score:.2f}/1.0). "
                "Do a QUICK verification pass: confirm the pre-scan results, "
                "flag anything the automated scan may have missed, and sign off "
                "if data is indeed clean enough to proceed."
            )
        else:
            focus_note = ""
            if skeptic_mode == "prioritize":
                focus_note = "\nPRIORITY: High missing value or outlier ratio detected — focus there first."
            skeptic_task = (
                "Inspect data quality: missing values, outliers, duplicate rows, class "
                "imbalance, and any potential data leakage between features and target. "
                "If multiple file types are present, flag format inconsistencies."
                + focus_note + profile_ctx
                + (f"\n\nGiven the goal: {task_desc} — flag issues that would specifically "
                   "hurt performance on that objective." if task_desc else "")
            )

        stat_focus = ""
        if data_metrics and len(data_metrics.high_corr_pairs) > FOCUS_STATISTICIAN_CORR_PAIRS:
            top_pairs = data_metrics.high_corr_pairs[:5]
            stat_focus = (
                f"\nFOCUS: These high-correlation pairs were detected pre-LLM: {top_pairs}. "
                "Prioritize multicollinearity analysis and VIF scores for these pairs."
            )
        if data_metrics and data_metrics.is_time_series:
            stat_focus += "\nFOCUS: Time-series data — also check autocorrelation and stationarity."

        statistician_task = (
            "Analyze feature distributions, skewness, multicollinearity, and the "
            "statistical significance of key correlations. For non-tabular data, "
            "describe what statistical measures apply and flag distributional red flags."
            + stat_focus + profile_ctx
        )

        # ── Run Explorer, Skeptic, Statistician concurrently ─────────────
        # These three are independent — none reads another's output.
        # Orchestrator.step() is thread-safe (context writes use a lock).
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(self._step_with_retry, "explorer",     explorer_task,     ROLE_ANALYSIS): "explorer",
                pool.submit(self._step_with_retry, "skeptic",      skeptic_task,      ROLE_ANALYSIS): "skeptic",
                pool.submit(self._step_with_retry, "statistician", statistician_task, ROLE_ANALYSIS): "statistician",
            }
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    print(f"[DataUnderstanding] ⚠️  {name} parallel run raised: {exc}")

        # ── Stage 2: Ethicist (optional, early-stop if data is very clean) ──
        ethics_notes = ""
        if "ethicist" in orch.agents:
            # Early stopping: skip Ethicist only if data profile shows no sensitive signals
            has_sensitive_signals = (
                data_metrics is None
                or data_metrics.data_quality_score < SKIP_ETHICIST_QUALITY_THRESHOLD
                or data_metrics.class_imbalance > 0.2
                or any(kw in " ".join(orch.agents).lower() for kw in ("image", "audio", "text", "nlp"))
            )
            if has_sensitive_signals:
                print("\n⚡ [DataUnderstanding] Ethicist reviewing for bias...")
                ethics_notes = self._step_with_retry(
                    "ethicist",
                    "Identify sensitive attributes, potential proxy variables, bias risks, "
                    "and fairness concerns. If non-tabular data (images, audio, text) is "
                    "present, flag representational bias risks." + (
                        f"\n\nGiven the stated goal: {task_desc} — flag any ethical concerns "
                        "specifically relevant to this use-case." if task_desc else ""
                    ),
                    ROLE_ANALYSIS,
                )
            else:
                print(f"\n⚡ [DataUnderstanding] Ethicist skipped (data quality={data_metrics.data_quality_score:.2f}, no sensitive signals detected)")

        # ── Summary ───────────────────────────────────────────────────────
        explorer_out = self._last_output("explorer")
        n_agents = 3 + (1 if ethics_notes else 0)

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary=(
                f"Data understanding complete ({n_agents} agents). "
                + (f"Quality={data_metrics.data_quality_score:.2f}. " if data_metrics else "")
                + f"EDA: {explorer_out[:100]}..."
            ),
            outputs={
                "eda_summary":    explorer_out,
                "quality_report": self._last_output("skeptic"),
                "stats_report":   self._last_output("statistician"),
                "ethics_notes":   ethics_notes,
                "data_metrics":   data_metrics,
            },
        )

    # ------------------------------------------------------------------ #
    # Retry helpers                                                         #
    # ------------------------------------------------------------------ #

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
