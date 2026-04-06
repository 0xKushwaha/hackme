"""
ModelDesignPhase — feature engineering, model selection, planning.

ARCHITECTURE (mirrors DataUnderstandingPhase)
=============================================

Pre-LLM computation:
  Before any agent runs, compute ground-truth feature importances and pull
  constraint discoveries from Phase 1. Inject into every agent's task so
  agents make decisions backed by real numbers, not guesses.

Retry architecture:
  Every agent call wrapped in _step_with_retry. Import errors trigger
  LibraryInstallerAgent before retrying.

Agents (required): feature_engineer, pragmatist
Agents (optional): devil_advocate, optimizer

Outputs:
  feature_plan      — feature engineering recommendations
  modeling_plan     — pragmatist's actionable modeling plan
  critique          — devil's advocate stress-test of the plan
  tuning_strategy   — optimizer's hyperparameter + CV strategy
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from memory.context_manager import ROLE_ANALYSIS, ROLE_PLAN, ROLE_META
from runtime.thread_state import propagate_to_worker
from agents.installer_agent import LibraryInstallerAgent
from analysis.relationship_extractor import RelationshipExtractor
from analysis.sampler import DataSampler
from .base import BasePhase, PhaseResult


MAX_AGENT_RETRIES = 2


class ModelDesignPhase(BasePhase):

    name = "model_design"
    REQUIRED_AGENTS = ["feature_engineer", "pragmatist"]

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self.installer = LibraryInstallerAgent()
        self.extractor = RelationshipExtractor()
        self.sampler   = DataSampler()
        self._dataset  = None

    # ------------------------------------------------------------------ #
    # Main phase entry                                                      #
    # ------------------------------------------------------------------ #

    def _run(
        self,
        dataset_path: str = "",
        target_col:   str = None,
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        # ── Pull task/competition context ─────────────────────────────
        task_desc = getattr(orch, "task_description", "").strip()
        goal_note = (
            f"\n\nCOMPETITION / TASK GOAL:\n{task_desc}\n"
            "All recommendations must directly serve this stated objective."
        ) if task_desc else ""

        # ── Pre-LLM: load dataset + compute feature importances ───────
        feature_ctx = ""
        if dataset_path:
            feature_ctx = self._compute_feature_context(dataset_path, target_col)
            if feature_ctx:
                orch.context.add("model_design_features", ROLE_META, feature_ctx, pinned=False)
                print(f"\n📊 [ModelDesign] Pre-LLM feature context ready")

        # ── Pre-LLM: pull constraint discoveries from Phase 1 ─────────
        constraint_ctx = self._pull_constraint_context()
        if constraint_ctx:
            print(f"\n📊 [ModelDesign] Constraint context injected from Phase 1")

        # ── Set data access on all agents ─────────────────────────────
        if self._dataset is not None:
            for agent_name in ["feature_engineer", "pragmatist", "devil_advocate", "optimizer"]:
                agent = orch.agents.get(agent_name)
                if agent:
                    agent.set_data_access(self._dataset, self.sampler, self.extractor)

        # ── Stage 1: Feature Engineer ─────────────────────────────────
        print("\n⚡ [ModelDesign] Feature engineering...")
        fe_task = (
            "Based on the EDA, data quality analysis, and the computed feature statistics below, "
            "design the complete feature engineering pipeline.\n\n"
            "Use the ADVANCED TECHNIQUES section of your toolkit: target encoding (CV-safe), "
            "group aggregations, ratio features, null importance checks, SHAP-based pruning, "
            "embedding features for high-cardinality categoricals.\n\n"
            "For every proposed feature state: formula, expected impact, reasoning, leakage risk."
            + (f"\n\n{feature_ctx}" if feature_ctx else "")
            + (f"\n\n{constraint_ctx}" if constraint_ctx else "")
            + goal_note
        )
        self._step_with_retry("feature_engineer", fe_task, ROLE_ANALYSIS)

        # ── Stage 2: Pragmatist ───────────────────────────────────────
        print("\n⚡ [ModelDesign] Building modeling plan...")
        metric_instruction = (
            "\n\nIMPORTANT — Begin your response with this exact block (fill in the brackets):\n"
            "TASK TYPE: [regression / binary_classification / multiclass_classification / "
            "ranking / clustering / other]\n"
            "RECOMMENDED METRIC: [metric name, e.g. RMSE, AUC-ROC, F1-macro, MAP@K]\n"
            "METRIC JUSTIFICATION: [one sentence explaining why this metric fits the goal]\n"
            "---\n"
            "Then provide the full 3-tier competition plan below.\n"
        )
        pragmatist_task = (
            "Design the complete competition strategy with a 3-tier model plan:\n"
            "  Tier 1 — Baseline: implementable in < 2 hours, establishes a floor score\n"
            "  Tier 2 — Strong single model: the well-tuned workhorse\n"
            "  Tier 3 — Ensemble: OOF stacking with diverse base learners\n\n"
            "Include: CV strategy (GroupKFold/StratifiedKFold/TimeSeriesSplit as appropriate), "
            "ensemble diversity plan, marginal gain techniques (pseudo-labeling, TTA, custom loss), "
            "and what the typical winning solution for this task type looks like."
            + metric_instruction
            + (f"\n\n{feature_ctx}" if feature_ctx else "")
            + (f"\n\n{constraint_ctx}" if constraint_ctx else "")
            + goal_note
        )
        self._step_with_retry("pragmatist", pragmatist_task, ROLE_PLAN)

        # ── Stage 3: Devil's Advocate + Optimizer in parallel ─────────
        parallel_steps = []

        if "devil_advocate" in orch.agents:
            devil_task = (
                "Critically challenge the Pragmatist's competition plan.\n\n"
                "Focus on:\n"
                "1. CV strategy — does it prevent group/temporal leakage? Will it correlate with LB?\n"
                "2. Model choice — is the team picking the right architecture for this modality?\n"
                "3. Ensemble diversity — are the proposed models actually diverse or just correlated?\n"
                "4. Feature engineering — which proposed features might be noise or leakage?\n"
                "5. The single blind spot that will cost the medal if unchecked.\n\n"
                "For every challenge, propose a specific alternative."
                + (f"\n\n{constraint_ctx}" if constraint_ctx else "")
                + (f"\n\nGoal: {task_desc}" if task_desc else "")
            )
            parallel_steps.append(("devil_advocate", devil_task, ROLE_PLAN))

        if "optimizer" in orch.agents:
            optimizer_task = (
                "Design the hyperparameter search and CV strategy for the models in the plan.\n\n"
                "Cover:\n"
                "1. Exact CV method with leak-prevention reasoning (GroupKFold, stratification)\n"
                "2. For each model: the 3-5 hyperparameters that move the metric most, with ranges\n"
                "3. Optuna TPE search — n_trials and compute budget\n"
                "4. Variance reduction: seed averaging, snapshot ensembling\n"
                "5. Early stopping: metric, patience, overfitting signal threshold\n"
                "6. Expected metric gain from tuning vs. default params"
                + (f"\n\nOptimise for the metric chosen for: {task_desc}" if task_desc else "")
            )
            parallel_steps.append(("optimizer", optimizer_task, ROLE_PLAN))

        if len(parallel_steps) == 2:
            print("\n⚡ [ModelDesign] Devil's Advocate + Optimizer running in parallel...")
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(propagate_to_worker(self._step_with_retry, name, task, role)): name
                    for name, task, role in parallel_steps
                }
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        fut.result()
                    except Exception as exc:
                        print(f"[ModelDesign] ⚠️  {name} parallel run raised: {exc}")
        elif parallel_steps:
            name, task, role = parallel_steps[0]
            print(f"\n⚡ [ModelDesign] {name} running...")
            self._step_with_retry(name, task, role)

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

    # ------------------------------------------------------------------ #
    # Pre-LLM helpers                                                       #
    # ------------------------------------------------------------------ #

    def _compute_feature_context(
        self,
        dataset_path: str,
        target_col: str = None,
    ) -> str:
        """
        Load dataset and compute ground-truth feature importances.
        Injects real numbers into agent tasks so they don't guess.
        """
        if self._dataset is None:
            try:
                # Load a capped sample — enough for statistics, avoids OOM on large files.
                # Uses BasePhase.load_dataframe which explicitly sets engine='c' for CSV
                # so pyarrow (initialised by chromadb) never intercepts the call.
                self._dataset = self.load_dataframe(dataset_path, max_rows=50_000)
                print(f"[ModelDesign] Dataset loaded: {self._dataset.shape}")
            except Exception as e:
                print(f"[ModelDesign] ⚠️  Could not load dataset: {e}")
                return ""

        df = self._dataset
        lines = ["### Pre-Computed Feature Statistics (ground truth — use these numbers)"]

        # Basic shape
        lines.append(f"- Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
        lines.append(f"- Numeric columns: {df.select_dtypes('number').shape[1]}")
        lines.append(f"- Categorical columns: {df.select_dtypes(['object','category']).shape[1]}")

        # Missing values
        missing = df.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        if not missing.empty:
            lines.append(f"\n**Columns with missing values:**")
            for col, n in missing.head(10).items():
                lines.append(f"  - `{col}`: {n} missing ({n/len(df):.1%})")

        # Target column analysis
        if target_col and target_col in df.columns:
            import numpy as np
            tgt = df[target_col].dropna()
            lines.append(f"\n**Target column `{target_col}`:**")
            lines.append(f"  - dtype: {df[target_col].dtype}")
            lines.append(f"  - range: [{tgt.min():.4g}, {tgt.max():.4g}]")
            lines.append(f"  - mean: {tgt.mean():.4g} | std: {tgt.std():.4g}")
            lines.append(f"  - skewness: {tgt.skew():.3f}")
            zero_frac = (tgt == 0).mean()
            if zero_frac > 0.01:
                lines.append(f"  - ⚠️  Zero fraction: {zero_frac:.1%} (zero-inflated)")

        # Feature correlations with target
        if target_col and target_col in df.columns:
            try:
                import numpy as np
                num_df = df.select_dtypes(include=[np.number])
                if target_col in num_df.columns:
                    corr = num_df.corr()[target_col].drop(target_col).abs().sort_values(ascending=False)
                    lines.append(f"\n**Feature correlations with `{target_col}` (|Pearson r|):**")
                    for col, val in corr.head(15).items():
                        lines.append(f"  - `{col}`: r={val:.3f}")
            except Exception:
                pass

        # High-cardinality categoricals
        cat_cols = df.select_dtypes(["object", "category"]).columns
        if len(cat_cols) > 0:
            lines.append(f"\n**Categorical column cardinalities:**")
            for col in cat_cols:
                n_unique = df[col].nunique()
                lines.append(f"  - `{col}`: {n_unique} unique values → "
                             f"{'target_encode' if n_unique > 10 else 'one_hot'}")

        return "\n".join(lines)

    def _pull_constraint_context(self) -> str:
        """
        Pull constraint discovery results written by Phase 1 into context.
        Makes Feature Engineer and Pragmatist aware of compositional structure.
        """
        for entry in reversed(self.orch.context.entries):
            if entry.agent == "constraint_discovery" and entry.content:
                lines = [
                    "### Compositional Constraints (discovered in Phase 1 — CRITICAL for modeling)",
                    entry.content,
                    "\n⚠️  MODELING IMPLICATION: If compositional constraints exist, predicting "
                    "components independently risks violating the sum constraint. "
                    "Consider: constrained multi-output model, or post-process predictions to enforce constraints.",
                ]
                return "\n".join(lines)
        return ""

    # ------------------------------------------------------------------ #
    # Retry helper (mirrors DataUnderstandingPhase._step_with_retry)        #
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
        """
        label = label or agent_name
        last_error: str = ""
        current_task = task

        for attempt in range(1, max_retries + 1):
            try:
                result = self.orch.step(agent_name, current_task, role)
                if attempt > 1:
                    print(f"[ModelDesign] ✅ {label} succeeded on attempt {attempt}")
                return result

            except Exception as exc:
                last_error = str(exc)
                print(
                    f"[ModelDesign] ⚠️  {label} attempt {attempt}/{max_retries} "
                    f"failed: {exc}"
                )

                # Auto-install missing libraries
                if "import" in last_error.lower() or "module" in last_error.lower():
                    install = self.installer.handle(last_error)
                    if install.any_success:
                        print(
                            f"[ModelDesign] 🔄 Installed {install.succeeded} "
                            "— will retry without changing task."
                        )
                        continue

                # Inject error context for next attempt
                if attempt < max_retries:
                    current_task = (
                        f"{task}\n\n"
                        f"[RETRY CONTEXT — attempt {attempt + 1}/{max_retries}]\n"
                        f"Previous attempt failed with: {last_error}\n"
                        "Adjust your approach accordingly."
                    )

        placeholder = f"[{label} failed after {max_retries} attempts: {last_error[:120]}]"
        print(f"[ModelDesign] ❌ {placeholder}")
        return placeholder
