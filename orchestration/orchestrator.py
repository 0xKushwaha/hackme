"""
Orchestrator — routes tasks, manages context, wires per-agent memory.

Modes:
  manual  — fixed pipeline, caller defines agent order
  auto    — orchestrator LLM decides each step
  phases  — discrete pipeline stages (DataUnderstanding, ModelDesign)
"""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from memory.context_manager  import ContextManager, ROLE_ANALYSIS, ROLE_PLAN, ROLE_NARRATIVE, ROLE_META, ROLE_TASK
from memory.agent_memory     import MemorySystem
from memory.graph_store      import INFORMED_BY
from orchestration.registry  import AgentRegistry, OUTCOME_SUCCESS, OUTCOME_FAILURE
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT


MAX_AUTO_STEPS    = 10
MAX_STEP_RETRIES  = 2

# Agents that only need recent context (pinned entries + last 2 outputs)
# rather than the full growing log — saves tokens and LLM latency
SLIM_CONTEXT_AGENTS = {"skeptic", "ethicist", "devil_advocate", "pragmatist"}


class Orchestrator:

    def __init__(
        self,
        agents:           dict,
        llm               = None,
        memory_system:    MemorySystem  = None,
        registry:         AgentRegistry = None,
        task_description: str           = "",
    ):
        self.agents           = agents
        self.llm              = llm
        self.memory           = memory_system
        self.registry         = registry or AgentRegistry()
        self.task_description = task_description.strip()
        self.context          = ContextManager()
        self.run_id           = str(uuid.uuid4())[:12]
        self._last_node_id    = None
        self._data_metrics    = {}
        self._ctx_lock        = threading.Lock()   # guards context writes during parallel steps

        # Wire LLM into compactor
        if self.memory and self.llm:
            self.memory.set_llm(self.llm)

        # Wire memory into each agent
        if self.memory:
            for name, agent in self.agents.items():
                mem = self.memory.get(name)
                if mem:
                    agent.attach_memory(mem)

    # ------------------------------------------------------------------ #
    # Core step (with built-in retry)                                      #
    # ------------------------------------------------------------------ #

    def step(
        self,
        agent_name:  str,
        task:        str,
        role:        str = ROLE_ANALYSIS,
        max_retries: int = MAX_STEP_RETRIES,
    ) -> str:
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent '{agent_name}'. Available: {list(self.agents.keys())}")

        allowed, reason = self.registry.can_spawn()
        if not allowed:
            print(f"[Registry] Spawn denied for {agent_name}: {reason}")
            return f"[SKIPPED — {reason}]"

        last_exc: Optional[Exception] = None
        current_task = task

        print(f"\n⚡ [AGENT:{agent_name}]")

        for attempt in range(1, max_retries + 1):
            node_id = str(uuid.uuid4())[:12]
            self.registry.register(agent_name, current_task, run_id=node_id)
            self.registry.start(node_id)
            t_start = time.time()

            self._maybe_compact()

            agent   = self.agents[agent_name]
            ctx_str = (
                self.context.get_slim_context_string()
                if agent_name in SLIM_CONTEXT_AGENTS
                else self.context.get_context_string()
            )

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

                if attempt < max_retries:
                    current_task = (
                        f"{task}\n\n"
                        f"[RETRY — attempt {attempt + 1}/{max_retries}]\n"
                        f"Previous attempt failed: {err_str[:300]}\n"
                        "Adjust your approach."
                    )
                continue

            # ── Success path ──────────────────────────────────────────
            with self._ctx_lock:
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
            print(f"\n✅ [AGENT_DONE:{agent_name}]")
            return response

        raise RuntimeError(
            f"Agent '{agent_name}' failed after {max_retries} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    def _maybe_compact(self):
        if self.memory and self.memory.compactor:
            compactor = self.memory.compactor
            total_tokens = sum(e.token_estimate() for e in self.context.entries)
            if total_tokens > self.context.max_tokens * 0.85:
                print(f"\n[Compactor] Context near limit — compacting...")
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

    def _pin_task_context(self):
        if self.task_description:
            self.context.add_task_context(self.task_description)

    def run_manual(self, dataset_summary: str):
        print(f"\n🚀 Starting analysis (manual mode) | run_id: {self.run_id}\n")
        self.context.add_dataset_context(dataset_summary)
        self._pin_task_context()

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
        self._pin_task_context()
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
    # Phase-based pipeline                                                 #
    # ------------------------------------------------------------------ #

    def run_phases(
        self,
        dataset_summary:  str,
        dataset_path:     str,
        target_col:       str           = None,
        experiment_dir:   str           = "experiments",
        phases:           Optional[list] = None,
        dataset_profile                 = None,
    ) -> dict:
        from phases import DataUnderstandingPhase, ModelDesignPhase

        os.makedirs(experiment_dir, exist_ok=True)
        print(f"\n🚀 Starting phase-based pipeline | run_id: {self.run_id}\n")
        if self.task_description:
            print(f"   Goal  : {self.task_description[:80]}{'…' if len(self.task_description) > 80 else ''}")

        if phases is None:
            phases = [
                DataUnderstandingPhase(self),
                ModelDesignPhase(self),
            ]

        results: dict = {}

        # --- Phase 1: DataUnderstanding ---
        p = self._get_phase(phases, "data_understanding")
        if p:
            r = p.run(
                dataset_summary=dataset_summary,
                dataset_profile=dataset_profile,
                dataset_path=dataset_path,
                target_col=target_col,
            )
            results["data_understanding"] = r
            if r.outputs.get("data_metrics"):
                self._adapt_agent_personalities(self._data_metrics)
            if not r.success:
                print(f"\n⚠️  DataUnderstanding failed: {r.error}. Continuing anyway.")

        # --- Phase 2: ModelDesign ---
        p = self._get_phase(phases, "model_design")
        if p:
            r = p.run()
            results["model_design"] = r
            if not r.success:
                print(f"\n⚠️  ModelDesign failed: {r.error}. Continuing anyway.")

        # --- Persist context ---
        log_path = os.path.join(experiment_dir, f"context_{self.run_id}.json")
        self.context.save(log_path)
        print(f"\n📄 Context saved to {log_path}")

        if self.memory:
            self.memory.print_stats()
            self.memory.graph_store.print_run(self.run_id)

        return results

    def _get_phase(self, phases: list, name: str):
        for p in phases:
            if p.name == name:
                return p
        return None

    # ------------------------------------------------------------------ #
    # Adaptive personalities                                               #
    # ------------------------------------------------------------------ #

    def _adapt_agent_personalities(self, metrics: dict):
        if not metrics:
            return
        adapted_count = 0
        for name, agent in self.agents.items():
            if agent.config is not None:
                new_cfg = agent.config.adapt(metrics)
                if (new_cfg.activity_level != agent.config.activity_level or
                        new_cfg.sentiment_bias != agent.config.sentiment_bias):
                    agent.config = new_cfg
                    adapted_count += 1
        if adapted_count:
            print(f"[Orchestrator] 🧠 Adapted {adapted_count} agent personality config(s)")

    # ------------------------------------------------------------------ #
    # Conversation interface                                               #
    # ------------------------------------------------------------------ #

    def discuss(self, participants: list, topic: str, max_turns: int = 4) -> list:
        from orchestration.conversation_manager import ConversationManager
        return ConversationManager(self).discuss(participants, topic, max_turns)

    def converge(self, agent_a: str, agent_b: str, question: str, max_turns: int = 4) -> str:
        from orchestration.conversation_manager import ConversationManager
        return ConversationManager(self).converge(agent_a, agent_b, question, max_turns)

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
