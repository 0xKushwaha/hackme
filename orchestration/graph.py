"""
LangGraph graph definitions for the three pipeline modes.

Each builder closes over the Orchestrator instance — nodes are thin wrappers
that call orch.step(), so all context management, memory, registry tracking,
and retry logic stays exactly as before.

Parallelism in the manual pipeline is expressed via LangGraph's Send API
(fan-out to per-agent nodes) rather than ThreadPoolExecutor.
"""

import os
from typing import Optional, Any

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from memory.context_manager import ROLE_ANALYSIS, ROLE_PLAN, ROLE_NARRATIVE


# ──────────────────────────────────────────────────────────────────────────────
# State schemas
# ──────────────────────────────────────────────────────────────────────────────

class ManualState(TypedDict):
    dataset_summary: str


class AutoState(TypedDict):
    dataset_summary: str
    step_count:      int
    complete:        bool
    next_agent:      Optional[str]
    next_task:       Optional[str]


class PhasesState(TypedDict):
    dataset_summary: str
    dataset_path:    str
    target_col:      Optional[str]
    experiment_dir:  str
    dataset_profile: Any
    phase_results:   dict


# ──────────────────────────────────────────────────────────────────────────────
# Manual graph — fixed 6-round pipeline
# ──────────────────────────────────────────────────────────────────────────────

def build_manual_graph(orch):
    """
    Round 1 (parallel via Send): Explorer + Skeptic + Statistician
    Round 2 (parallel via Send): Feature Engineer + Ethicist
    Rounds 3-6 (sequential):     Pragmatist → Devil's Advocate → Optimizer → Architect

    Graph structure:
      eda_round → [Send × 3 → node_eda_agent] → feature_round (join)
               → [Send × 2 → node_feature_agent] → pragmatist (join)
               → devil_advocate → optimizer → architect → END
    """

    # ── Round 1: EDA fan-out ──────────────────────────────────────────────────

    def node_eda_round(state: ManualState) -> ManualState:
        print("\n⚡ Round 1: Explorer + Skeptic + Statistician (parallel)...")
        return state

    def fanout_eda(state: ManualState) -> list[Send]:
        return [
            Send("node_eda_agent", {"agent_name": name, "task": task, "role": role})
            for name, task, role in [
                ("explorer",     "Perform thorough EDA. Find patterns, correlations, key features. Suggest the target variable.", ROLE_ANALYSIS),
                ("skeptic",      "Inspect data quality: missing values, outliers, duplicates, leakage risks.", ROLE_ANALYSIS),
                ("statistician", "Analyze distributions, multicollinearity, statistical significance of correlations.", ROLE_ANALYSIS),
            ]
        ]

    def node_eda_agent(state: dict) -> dict:
        orch.step(state["agent_name"], state["task"], state["role"])
        return {}  # results live in orch.context — no ManualState update needed

    # ── Round 2: Feature fan-out ──────────────────────────────────────────────

    def node_feature_round(state: ManualState) -> ManualState:
        print("\n⚡ Round 2: Feature Engineer + Ethicist (parallel)...")
        return state

    def fanout_feature(state: ManualState) -> list[Send]:
        return [
            Send("node_feature_agent", {"agent_name": name, "task": task, "role": role})
            for name, task, role in [
                ("feature_engineer", "Suggest new features, encoding strategies, transformations. Flag redundant features.", ROLE_ANALYSIS),
                ("ethicist",         "Identify sensitive attributes, bias risks, and ethical concerns.", ROLE_ANALYSIS),
            ]
        ]

    def node_feature_agent(state: dict) -> dict:
        orch.step(state["agent_name"], state["task"], state["role"])
        return {}

    # ── Rounds 3-6: sequential ────────────────────────────────────────────────

    def node_pragmatist(state: ManualState) -> ManualState:
        print("\n📋 Round 3: Pragmatist building action plan...")
        orch.step("pragmatist", "Create a step-by-step modeling plan. Pick top 2-3 models, specify features, evaluation metric.", ROLE_PLAN)
        return state

    def node_devil_advocate(state: ManualState) -> ManualState:
        print("\n😈 Round 4: Devil's Advocate stress-testing the plan...")
        orch.step("devil_advocate", "Challenge the Pragmatist's plan. Suggest an alternative approach.", ROLE_PLAN)
        return state

    def node_optimizer(state: ManualState) -> ManualState:
        print("\n🔧 Round 5: Optimizer tuning strategy...")
        orch.step("optimizer", "Recommend hyperparameter tuning and cross-validation strategy.", ROLE_PLAN)
        return state

    def node_architect(state: ManualState) -> ManualState:
        print("\n🏗️  Round 6: Architect designing deployment...")
        orch.step("architect", "Design the deployment architecture: serving infra, latency, monitoring.", ROLE_PLAN)
        return state

    # ── Wire ──────────────────────────────────────────────────────────────────

    graph = StateGraph(ManualState)
    graph.add_node("eda_round",          node_eda_round)
    graph.add_node("node_eda_agent",     node_eda_agent)
    graph.add_node("feature_round",      node_feature_round)
    graph.add_node("node_feature_agent", node_feature_agent)
    graph.add_node("pragmatist",         node_pragmatist)
    graph.add_node("devil_advocate",     node_devil_advocate)
    graph.add_node("optimizer",          node_optimizer)
    graph.add_node("architect",          node_architect)

    graph.set_entry_point("eda_round")
    graph.add_conditional_edges("eda_round",     fanout_eda)      # fan-out → 3 agents
    graph.add_edge("node_eda_agent",     "feature_round")         # join → all 3 converge
    graph.add_conditional_edges("feature_round", fanout_feature)  # fan-out → 2 agents
    graph.add_edge("node_feature_agent", "pragmatist")            # join → both converge
    graph.add_edge("pragmatist",         "devil_advocate")
    graph.add_edge("devil_advocate",     "optimizer")
    graph.add_edge("optimizer",          "architect")
    graph.add_edge("architect",          END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────────────────────
# Auto graph — LLM-driven dynamic pipeline
# ──────────────────────────────────────────────────────────────────────────────

def build_auto_graph(orch, max_steps: int = 10):
    """
    Loops: decide → run_agent → decide → ... until the orchestrator LLM signals
    complete or max_steps is reached. The cycle is explicit in the graph edges
    instead of a Python for-loop.
    """

    def node_decide(state: AutoState) -> AutoState:
        if state["step_count"] >= max_steps:
            print(f"\n⚠️  Reached max steps ({max_steps}). Stopping.")
            return {**state, "complete": True}
        decision = orch._orchestrator_decide()
        return {
            **state,
            "complete":   decision["complete"],
            "next_agent": decision.get("agent"),
            "next_task":  decision.get("task"),
        }

    def node_run_agent(state: AutoState) -> AutoState:
        orch.step(state["next_agent"], state["next_task"])
        return {**state, "step_count": state["step_count"] + 1}

    def route_after_decide(state: AutoState) -> str:
        if state["complete"]:
            print("\n✅ Orchestrator says analysis is complete.")
            return END
        agent = state.get("next_agent")
        if not agent or agent not in orch.agents:
            print(f"\n⚠️  Unknown agent: {agent}. Stopping.")
            return END
        return "run_agent"

    graph = StateGraph(AutoState)
    graph.add_node("decide",    node_decide)
    graph.add_node("run_agent", node_run_agent)

    graph.set_entry_point("decide")
    graph.add_conditional_edges(
        "decide",
        route_after_decide,
        {"run_agent": "run_agent", END: END},
    )
    graph.add_edge("run_agent", "decide")

    return graph.compile()


# ──────────────────────────────────────────────────────────────────────────────
# Phases graph — discrete pipeline stages
# ──────────────────────────────────────────────────────────────────────────────

def build_phases_graph(orch, phases_list=None):
    """
    data_understanding → model_design → architecture → storyteller → finalize
    """

    def _get_phase(name: str):
        if phases_list:
            for p in phases_list:
                if p.name == name:
                    return p
        return None

    def node_data_understanding(state: PhasesState) -> PhasesState:
        from phases import DataUnderstandingPhase
        p = _get_phase("data_understanding") or DataUnderstandingPhase(orch)
        r = p.run(
            dataset_summary=state["dataset_summary"],
            dataset_profile=state["dataset_profile"],
            dataset_path=state["dataset_path"],
            target_col=state["target_col"],
        )
        if r.outputs.get("data_metrics"):
            orch._adapt_agent_personalities(orch._data_metrics)
        if not r.success:
            print(f"\n⚠️  DataUnderstanding failed: {r.error}. Continuing anyway.")
        return {**state, "phase_results": {**state["phase_results"], "data_understanding": r}}

    def node_model_design(state: PhasesState) -> PhasesState:
        from phases import ModelDesignPhase
        p = _get_phase("model_design") or ModelDesignPhase(orch)
        r = p.run(
            dataset_path=state["dataset_path"],
            target_col=state["target_col"],
        )
        if not r.success:
            print(f"\n⚠️  ModelDesign failed: {r.error}. Continuing anyway.")
        return {**state, "phase_results": {**state["phase_results"], "model_design": r}}

    def node_architecture(state: PhasesState) -> PhasesState:
        if "architect" not in orch.agents:
            return state
        print("\n⚡ [Architecture] Architect researching and designing...")
        research_ctx = orch._research_search(state["dataset_profile"], state["dataset_path"])
        architect_task = (
            "Based on the full analysis above, design a COMPLETE competition architecture.\n"
            "You MUST produce TWO tracks:\n\n"
            "TRACK 1 — BASELINE: The simplest solid approach to get on the board fast.\n"
            "  A competitor should be able to implement this in < 2 hours and score in top 40%.\n\n"
            "TRACK 2 — ADVANCED: The full competitive architecture to fight for a medal.\n"
            "  Include: exact model stack, ensemble/stacking design, OOF strategy, every marginal\n"
            "  gain technique (pseudo-labeling, TTA, custom loss, post-processing, feature selection),\n"
            "  hyperparameter search plan, and a day-by-day implementation roadmap.\n\n"
            "Consider the FULL spectrum: classical ML, gradient boosting (LightGBM/XGBoost/CatBoost),\n"
            "deep learning (Transformers, CNNs, LSTMs, TabNet, SAINT), and multi-modal approaches.\n"
            "For this competition, 0.001 on the metric matters. Be brutally specific.\n"
        )
        if research_ctx:
            architect_task += (
                f"\n\nRELEVANT RESEARCH & RESOURCES (you MUST cite these in your response):\n"
                f"{research_ctx}\n\n"
                "IMPORTANT: You MUST include a References section at the end citing specific\n"
                "papers and articles using [Author(s), Year] format. Every architectural decision\n"
                "must be justified with at least one citation from the above resources."
            )
        try:
            orch.step("architect", architect_task, ROLE_PLAN)
        except Exception as exc:
            print(f"\n⚠️  Architect failed: {exc}. Continuing anyway.")
        return state

    def node_storyteller(state: PhasesState) -> PhasesState:
        print("\n📋 [Final Report] Synthesising pipeline output...")
        if "storyteller" in orch.agents:
            brief = orch._synthesize_final_report()
            storyteller_task = (
                "You have received the full analysis from the entire data science team.\n"
                "Write a compelling, well-structured final report that:\n"
                "1. Opens with an executive summary (3-5 sentences)\n"
                "2. Highlights the most important findings from each agent\n"
                "3. Synthesises the recommended action plan in plain language\n"
                "4. Closes with the top 3 risks and the single most important next step\n\n"
                "Audience: a technical but non-specialist stakeholder. Be clear, specific, and actionable.\n\n"
                f"FULL PIPELINE OUTPUT:\n{brief}"
            )
            try:
                print(f"\n⚡ [AGENT:storyteller]")
                orch.agent_results["final_report"] = orch.agents["storyteller"].run(
                    context=orch.context.get_context_string(),
                    task=storyteller_task,
                    run_id=orch.run_id,
                    role=ROLE_NARRATIVE,
                )
                print(f"\n✅ [AGENT_DONE:storyteller]")
            except Exception as exc:
                print(f"\n⚠️  Storyteller failed ({exc}), falling back to template report.")
                orch.agent_results["final_report"] = brief
        else:
            orch.agent_results["final_report"] = orch._synthesize_final_report()
        print("\n✅ [AGENT_DONE:final_report]")
        return state

    def node_finalize(state: PhasesState) -> PhasesState:
        orch._wait_for_compaction()
        log_path = os.path.join(state["experiment_dir"], f"context_{orch.run_id}.json")
        orch.context.save(log_path)
        print(f"\n📄 Context saved to {log_path}")
        if orch.memory:
            orch.memory.print_stats()
            orch.memory.graph_store.print_run(orch.run_id)
        print(f"\n[Orchestrator] Total background compactions: {orch._compaction_count}")
        return state

    graph = StateGraph(PhasesState)
    graph.add_node("data_understanding", node_data_understanding)
    graph.add_node("model_design",       node_model_design)
    graph.add_node("architecture",       node_architecture)
    graph.add_node("storyteller",        node_storyteller)
    graph.add_node("finalize",           node_finalize)

    graph.set_entry_point("data_understanding")
    graph.add_edge("data_understanding", "model_design")
    graph.add_edge("model_design",       "architecture")
    graph.add_edge("architecture",       "storyteller")
    graph.add_edge("storyteller",        "finalize")
    graph.add_edge("finalize",           END)

    return graph.compile()
