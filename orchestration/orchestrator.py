"""
Orchestrator — routes tasks, manages context, wires per-agent memory, drives the training retry loop.

Modes:
  manual  — fixed pipeline, caller defines agent order
  auto    — orchestrator LLM decides each step
  train   — full autonomous loop: analyze → generate code → execute → retry on failure

Memory integration:
  - Before each step: agent recalls relevant past memories from ChromaDB
  - After each step:  output stored in agent's ChromaDB collection + graph node added
  - Graph edges are added between consecutive nodes in each run
"""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from langchain.schema import HumanMessage, SystemMessage

from memory.context_manager  import ContextManager, ROLE_ANALYSIS, ROLE_PLAN, ROLE_NARRATIVE, ROLE_META
from memory.agent_memory     import MemorySystem
from memory.graph_store      import INFORMED_BY, RETRY_OF, FAILURE_LED_TO, CROSS_RUN
from execution.executor      import CodeExecutor, ExecutionResult
from execution.context_guard import ToolResultContextGuard, format_execution_result
from orchestration.registry  import AgentRegistry, OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_TIMEOUT
from agents.installer_agent  import LibraryInstallerAgent
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT


MAX_AUTO_STEPS    = 10
MAX_TRAIN_RETRIES = 4
MAX_STEP_RETRIES  = 2    # default per-step retry attempts


class Orchestrator:

    def __init__(
        self,
        agents:        dict,
        llm            = None,
        executor:      CodeExecutor  = None,
        memory_system: MemorySystem  = None,
        registry:      AgentRegistry = None,
        tool_registry                = None,   # optional ToolRegistry
        builder_agent                = None,   # optional BuilderAgent
    ):
        self.agents        = agents
        self.llm           = llm
        self.executor      = executor or CodeExecutor()
        self.memory        = memory_system
        self.registry      = registry or AgentRegistry()
        self.tool_registry = tool_registry
        self.builder_agent = builder_agent
        self.context       = ContextManager()
        self.context_guard = ToolResultContextGuard(max_context_tokens=self.context.max_tokens)
        self.installer     = LibraryInstallerAgent()
        self.run_id        = str(uuid.uuid4())[:12]
        self._last_node_id = None

        # Wire LLM into compactor
        if self.memory and self.llm:
            self.memory.set_llm(self.llm)

        # Wire memory into each agent
        if self.memory:
            for name, agent in self.agents.items():
                mem = self.memory.get(name)
                if mem:
                    agent.attach_memory(mem)

    def add_dynamic_agent(self, name: str, system_prompt: str) -> "BaseAgent":
        """
        Dynamically create and register a specialist agent at runtime.

        Called by BuilderAgent after it decides what specialist agents the
        dataset needs. The new agent is added to self.agents so it can be
        used by subsequent phase steps — no orchestrator restart required.

        Memory: a fresh AgentMemory slot is created in MemorySystem so the
        dynamic agent benefits from the same ChromaDB + graph infrastructure.
        """
        from agents.base       import BaseAgent
        from agents.agent_config import AgentConfig

        agent = BaseAgent(name, system_prompt, self.llm, config=AgentConfig())

        if self.memory:
            mem = self.memory.create_for(name)
            agent.attach_memory(mem)

        self.agents[name] = agent
        print(f"[Orchestrator] 🤖 Dynamic agent registered: '{name}'")
        return agent

    # ------------------------------------------------------------------ #
    # Core step (with built-in retry + library auto-install)              #
    # ------------------------------------------------------------------ #

    def step(
        self,
        agent_name:  str,
        task:        str,
        role:        str = ROLE_ANALYSIS,
        max_retries: int = MAX_STEP_RETRIES,
    ) -> str:
        """
        Run a single agent step with retry logic.

        On failure:
          1. If error looks like a missing library → LibraryInstallerAgent runs
          2. Error message is appended to the task so the LLM can self-correct
          3. Up to max_retries attempts total

        Raises the last exception only if all retries fail.
        """
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent '{agent_name}'. Available: {list(self.agents.keys())}")

        # Registry: check spawn limits
        allowed, reason = self.registry.can_spawn()
        if not allowed:
            print(f"[Registry] Spawn denied for {agent_name}: {reason}")
            return f"[SKIPPED — {reason}]"

        last_exc: Optional[Exception] = None
        current_task = task

        for attempt in range(1, max_retries + 1):
            node_id = str(uuid.uuid4())[:12]
            self.registry.register(agent_name, current_task, run_id=node_id)
            self.registry.start(node_id)
            t_start = time.time()

            self._maybe_compact()

            agent   = self.agents[agent_name]
            ctx_str = self.context.get_context_string()

            try:
                response = agent.run(
                    context=ctx_str,
                    task=current_task,
                    node_id=node_id,
                    run_id=self.run_id,
                    role=role,
                )
                runtime_ms = int((time.time() - t_start) * 1000)
                self.registry.complete(node_id, OUTCOME_SUCCESS, runtime_ms=runtime_ms)

            except Exception as exc:
                runtime_ms = int((time.time() - t_start) * 1000)
                self.registry.complete(node_id, OUTCOME_FAILURE,
                                       error_type=str(exc)[:80], runtime_ms=runtime_ms)
                last_exc = exc
                err_str  = str(exc)

                print(f"\n[Orchestrator] ⚠️  {agent_name} attempt {attempt}/{max_retries} failed: {exc}")

                # Auto-install missing libraries before next attempt
                if "import" in err_str.lower() or "module" in err_str.lower():
                    install = self.installer.handle(err_str)
                    if install.any_success:
                        print(f"[Orchestrator] 🔄 Installed {install.succeeded} — retrying.")

                if attempt < max_retries:
                    current_task = (
                        f"{task}\n\n"
                        f"[RETRY — attempt {attempt + 1}/{max_retries}]\n"
                        f"Previous attempt failed: {err_str[:300]}\n"
                        "Adjust your approach."
                    )
                continue   # next attempt

            # ── Success path ──────────────────────────────────────────
            self.context.add(agent_name, role, response)

            if self.memory and self._last_node_id:
                self.memory.graph_store.add_edge(
                    from_node=self._last_node_id,
                    to_node=node_id,
                    edge_type=INFORMED_BY,
                )
            self._last_node_id = node_id

            print(f"\n{'='*60}")
            print(f"  {agent_name.upper()}{' (retry succeeded)' if attempt > 1 else ''}")
            print(f"{'='*60}")
            print(response)
            return response

        # All attempts failed
        raise RuntimeError(
            f"Agent '{agent_name}' failed after {max_retries} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    def _maybe_compact(self):
        """Trigger LLM compaction if context is near capacity."""
        if self.memory and self.memory.compactor:
            compactor = self.memory.compactor
            level = self.context_guard.context_overflow_level(
                sum(e.token_estimate() for e in self.context.entries)
            )
            if level in ("preemptive", "overflow"):
                print(f"\n[Compactor] Context at {level} — compacting...")
                compactor.compact(self.context)

    def parallel_step(self, steps: list[tuple[str, str, str]]):
        """Run multiple (agent_name, task, role) steps concurrently."""
        with ThreadPoolExecutor() as ex:
            futures = [ex.submit(self.step, name, task, role) for name, task, role in steps]
            for f in futures:
                f.result()

    # ------------------------------------------------------------------ #
    # Manual pipeline                                                      #
    # ------------------------------------------------------------------ #

    def run_manual(self, dataset_summary: str):
        print(f"\n🚀 Starting analysis (manual mode) | run_id: {self.run_id}\n")
        self.context.add_dataset_context(dataset_summary)

        print("\n⚡ Round 1: Explorer + Skeptic + Statistician (parallel)...")
        self.parallel_step([
            ("explorer",     "Perform thorough EDA. Find patterns, correlations, key features. Suggest the target variable.", ROLE_ANALYSIS),
            ("skeptic",      "Inspect data quality: missing values, outliers, duplicates, leakage risks.", ROLE_ANALYSIS),
            ("statistician", "Analyze distributions, multicollinearity, statistical significance of correlations.", ROLE_ANALYSIS),
        ])

        print("\n⚡ Round 2: Feature Engineer + Ethicist (parallel)...")
        self.parallel_step([
            ("feature_engineer", "Suggest new features, encoding strategies, transformations. Flag redundant features.", ROLE_ANALYSIS),
            ("ethicist",         "Identify sensitive attributes, bias risks, and ethical concerns.", ROLE_ANALYSIS),
        ])

        print("\n📋 Round 3: Pragmatist building action plan...")
        self.step("pragmatist", "Create a step-by-step modeling plan. Pick top 2-3 models, specify features, evaluation metric.", ROLE_PLAN)

        print("\n😈 Round 4: Devil's Advocate stress-testing the plan...")
        self.step("devil_advocate", "Challenge the Pragmatist's plan. Suggest an alternative approach.", ROLE_PLAN)

        print("\n🔧 Round 5: Optimizer tuning strategy...")
        self.step("optimizer", "Recommend hyperparameter tuning and cross-validation strategy.", ROLE_PLAN)

        print("\n🏗️  Round 6: Architect designing deployment...")
        self.step("architect", "Design the deployment architecture: serving infra, latency, monitoring.", ROLE_PLAN)

        print("\n📖 Round 7: Storyteller writing the narrative...")
        self.step("storyteller", "Synthesize everything into a compelling narrative for judges.", ROLE_NARRATIVE)

    # ------------------------------------------------------------------ #
    # Auto pipeline                                                        #
    # ------------------------------------------------------------------ #

    def _parse_orchestrator_response(self, raw: str) -> dict:
        result = {"agent": None, "task": None, "complete": False, "reason": ""}
        for line in raw.strip().splitlines():
            if line.startswith("NEXT_AGENT:"):
                result["agent"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("TASK:"):
                result["task"] = line.split(":", 1)[1].strip()
            elif line.startswith("COMPLETE:"):
                result["complete"] = line.split(":", 1)[1].strip().lower() == "yes"
            elif line.startswith("REASON:"):
                result["reason"] = line.split(":", 1)[1].strip()
        return result

    def _orchestrator_decide(self) -> dict:
        if self.llm is None:
            raise RuntimeError("Provide an LLM to use auto mode.")
        messages = [
            SystemMessage(content=ORCHESTRATOR_PROMPT),
            HumanMessage(content=f"CURRENT ANALYSIS LOG:\n{self.context.get_context_string() or '(Empty)'}\n\nWhat should happen next?"),
        ]
        raw = self.llm.invoke(messages)
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
        decision = self._parse_orchestrator_response(raw_text)
        print(f"\n[ORCHESTRATOR] → {(decision['agent'] or '?').upper()} | {decision['reason']}")
        return decision

    def run_auto(self, dataset_summary: str, max_steps: int = MAX_AUTO_STEPS):
        print(f"\n🤖 Starting analysis (auto mode) | run_id: {self.run_id}\n")
        self.context.add_dataset_context(dataset_summary)
        for _ in range(max_steps):
            decision = self._orchestrator_decide()
            if decision["complete"]:
                print("\n✅ Orchestrator says analysis is complete.")
                break
            if not decision["agent"] or decision["agent"] not in self.agents:
                print(f"\n⚠️  Unknown agent: {decision['agent']}. Stopping.")
                break
            self.step(decision["agent"], decision["task"])
        else:
            print(f"\n⚠️  Reached max steps ({max_steps}). Stopping.")

    # ------------------------------------------------------------------ #
    # Training loop                                                        #
    # ------------------------------------------------------------------ #

    def run_training_loop(
        self,
        dataset_summary: str,
        dataset_path:    str,
        target_col:      str  = None,
        max_retries:     int  = MAX_TRAIN_RETRIES,
        experiment_dir:  str  = "experiments",
    ):
        print(f"\n🤖 Starting training loop | run_id: {self.run_id}\n")
        os.makedirs(experiment_dir, exist_ok=True)
        self.context.add_dataset_context(dataset_summary)

        # Phase 1: Analysis
        print("\n⚡ Phase 1: Parallel analysis...")
        self.parallel_step([
            ("explorer",     "Perform thorough EDA. Identify likely target variable and key features.", ROLE_ANALYSIS),
            ("skeptic",      "Flag data quality issues, missing values, leakage risks.", ROLE_ANALYSIS),
            ("statistician", "Analyze distributions and feature correlations.", ROLE_ANALYSIS),
        ])
        self.step("feature_engineer", "Suggest concrete feature engineering steps.", ROLE_ANALYSIS)
        self.step("pragmatist", "Create a clear modeling plan: target column, models to try, evaluation metric.", ROLE_PLAN)

        # Phase 2: Training retry loop
        last_result:     ExecutionResult = None
        last_code_node:  str             = None
        last_run_id:     str             = self.run_id   # tracks the run_id of the last attempt

        for attempt in range(1, max_retries + 1):
            print(f"\n🔁 Training attempt {attempt}/{max_retries}")

            # Each retry gets a fresh run_id so memories are scoped correctly
            if attempt > 1:
                self.run_id = str(uuid.uuid4())[:12]
                print(f"   New run_id for attempt {attempt}: {self.run_id}")

            if attempt > 1 and last_result:
                self._handle_failure(last_result, attempt, last_run_id, last_code_node)

            # Generate code
            print(f"\n💻 CodeWriter generating script (attempt {attempt})...")
            code_agent = self.agents.get("code_writer")
            if code_agent is None:
                raise RuntimeError("'code_writer' agent not found.")

            node_id  = str(uuid.uuid4())[:12]
            ctx_str  = self.context.get_context_string()
            code     = code_agent.run(
                context=ctx_str,
                dataset_path=dataset_path,
                target_col=target_col,
                node_id=node_id,
                run_id=self.run_id,
            )
            self.context.add_code(code, attempt=attempt)
            last_code_node = node_id

            # Graph edge: previous → code node
            if self.memory and self._last_node_id:
                edge_type = RETRY_OF if attempt > 1 else INFORMED_BY
                self.memory.graph_store.add_edge(self._last_node_id, node_id, edge_type)
            self._last_node_id = node_id

            # Save script to disk
            script_path = os.path.join(experiment_dir, f"train_attempt_{attempt}.py")
            with open(script_path, "w") as f:
                f.write(code)
            print(f"[EXECUTOR] Script saved: {script_path}")

            # Execute
            result       = self.executor.run(code, attempt=attempt)
            last_result  = result
            last_run_id  = self.run_id

            # Apply context guard before storing executor output
            guarded_output = format_execution_result(
                result.stdout, result.stderr, result.metrics,
                result.success, self.context_guard
            )
            self.context.add_result(guarded_output, result.metrics, result.success, attempt=attempt)

            print(f"\n{'✅' if result.success else '❌'} {result.short_summary()}")

            if result.success:
                break
        else:
            print(f"\n⚠️  All {max_retries} attempts failed.")

        # Phase 3: Finalize
        print("\n📖 Storyteller writing final narrative...")
        self.step(
            "storyteller",
            f"Summarize the full analysis and training run. "
            f"{'Training succeeded.' if (last_result and last_result.success) else 'Training failed after all attempts.'} "
            f"Final metrics: {last_result.metrics if last_result else 'N/A'}",
            ROLE_NARRATIVE,
        )

        # Persist
        log_path = os.path.join(experiment_dir, f"context_{self.run_id}.json")
        self.context.save(log_path)
        print(f"\n📄 Context saved to {log_path}")

        if self.memory:
            self.memory.print_stats()
            self.memory.graph_store.print_run(self.run_id)

        return last_result

    def _handle_failure(self, result: ExecutionResult, attempt: int, failed_run_id: str, failed_code_node: str = None):
        failure_summary = (
            f"Training attempt {attempt - 1} FAILED.\n"
            f"Error type : {result.error_type}\n"
            f"Error msg  : {result.error_msg}\n"
            f"Stderr     : {result.stderr[:500]}"
        )

        # Expire all memories from the failed run — agents won't repeat that approach
        if self.memory:
            self.memory.expire_run(failed_run_id)

        da_node = str(uuid.uuid4())[:12]
        print("\n😈 Devil's Advocate re-evaluating after failure...")
        da_response = self.agents["devil_advocate"].run(
            context=self.context.get_context_string(),
            task=f"{failure_summary}\n\nWhat went wrong? Suggest a completely different modeling approach.",
            node_id=da_node,
            run_id=self.run_id,
            role=ROLE_PLAN,
        )
        self.context.add("devil_advocate", ROLE_PLAN, da_response)

        # Graph: failed code node → devil_advocate
        if self.memory and failed_code_node:
            self.memory.graph_store.add_edge(failed_code_node, da_node, FAILURE_LED_TO)
        self._last_node_id = da_node

        print("\n📋 Pragmatist revising the plan...")
        self.step(
            "pragmatist",
            f"{failure_summary}\n\nRevise the plan. Be concrete about what to change.",
            ROLE_PLAN,
        )

    # ------------------------------------------------------------------ #
    # Phase-based pipeline                                                 #
    # ------------------------------------------------------------------ #

    def run_phases(
        self,
        dataset_summary:  str,
        dataset_path:     str,
        target_col:       str           = None,
        max_retries:      int           = 4,
        experiment_dir:   str           = "experiments",
        phases:           Optional[list] = None,
        dataset_profile                 = None,   # DatasetProfile from discovery
    ) -> dict:
        """
        Run the pipeline as discrete, independently-defined phases:
          1. DataUnderstanding  — EDA, quality, stats, ethics
          2. ModelDesign        — feature engineering, planning, critique
          3. CodeGeneration     — training retry loop (subprocess-based)
          4. Validation         — stress-test results, production risk
          5. Inference          — inference script + deployment plan + narrative

        The `phases` parameter lets you pass a custom ordered list of
        phase instances, or omit it to use the default five phases.

        Returns a dict of phase_name → PhaseResult.
        """
        from phases import (
            DataUnderstandingPhase, ModelDesignPhase,
            CodeGenerationPhase, ValidationPhase, InferencePhase,
        )

        os.makedirs(experiment_dir, exist_ok=True)
        print(f"\n🚀 Starting phase-based pipeline | run_id: {self.run_id}\n")

        if phases is None:
            phases = [
                DataUnderstandingPhase(self),
                ModelDesignPhase(self),
                CodeGenerationPhase(self),
                ValidationPhase(self),
                InferencePhase(self),
            ]

        results: dict = {}

        # --- Phase 1: DataUnderstanding ---
        p = self._get_phase(phases, "data_understanding")
        if p:
            r = p.run(dataset_summary=dataset_summary, dataset_profile=dataset_profile)
            results["data_understanding"] = r
            if not r.success:
                print(f"\n⚠️  DataUnderstanding failed: {r.error}. Continuing anyway.")

        # --- Phase 2: ModelDesign ---
        p = self._get_phase(phases, "model_design")
        if p:
            r = p.run()
            results["model_design"] = r
            if not r.success:
                print(f"\n⚠️  ModelDesign failed: {r.error}. Continuing anyway.")

        # --- Phase 3: CodeGeneration ---
        code_result = None
        p = self._get_phase(phases, "code_generation")
        if p:
            r = p.run(
                dataset_path=dataset_path,
                target_col=target_col,
                max_retries=max_retries,
                experiment_dir=experiment_dir,
            )
            results["code_generation"] = r
            code_result = r.outputs.get("execution_result")

        # --- Phase 4: Validation ---
        p = self._get_phase(phases, "validation")
        if p:
            cg_r    = results.get("code_generation")
            metrics = cg_r.outputs.get("metrics", {}) if cg_r else {}
            r = p.run(
                execution_result=code_result,
                metrics=metrics,
            )
            results["validation"] = r

        # --- Phase 5: Inference ---
        p = self._get_phase(phases, "inference")
        if p:
            cg = results.get("code_generation")
            r = p.run(
                metrics=cg.outputs.get("metrics", {}) if cg else {},
                training_succeeded=cg.outputs.get("succeeded", False) if cg else False,
                experiment_dir=experiment_dir,
            )
            results["inference"] = r

        # --- Persist context ---
        log_path = os.path.join(experiment_dir, f"context_{self.run_id}.json")
        self.context.save(log_path)
        print(f"\n📄 Context saved to {log_path}")

        if self.memory:
            self.memory.print_stats()
            self.memory.graph_store.print_run(self.run_id)

        if self.tool_registry:
            self.tool_registry.print_summary()

        return results

    def _get_phase(self, phases: list, name: str):
        """Find a phase by name from the phases list."""
        for p in phases:
            if p.name == name:
                return p
        return None

    # ------------------------------------------------------------------ #
    # Utilities                                                            #
    # ------------------------------------------------------------------ #

    def save_log(self, path: str = None):
        path = path or f"experiments/context_{self.run_id}.json"
        self.context.save(path)
        print(f"\n📄 Log saved to {path}")

    def print_summary(self):
        self.context.print_summary()
        if self.memory:
            self.memory.print_stats()
        self.registry.print_summary()
