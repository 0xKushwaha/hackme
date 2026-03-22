"""
Multi-Agent Data Science Team
==============================
Usage:
    # Advisory only (no code execution)
    python main.py --dataset data.csv --provider claude --mode manual
    python main.py --dataset data.csv --provider claude --mode auto

    # Full training loop: analyze → generate code → execute → retry on failure
    python main.py --dataset data.csv --provider claude --mode train
    python main.py --dataset data.csv --provider claude --mode train --target SalePrice --retries 4

    # Multi-provider fallback (tries claude first, falls back to openai on rate limit)
    python main.py --dataset data.csv --provider claude --fallback openai --mode train

    # Skip long-term memory (useful for first run / testing)
    python main.py --dataset data.csv --provider claude --mode train --no-memory
"""

import argparse
import os
import pandas as pd

from backends.llm_backends  import get_llm
from backends.fallback       import FallbackLLM, ProviderProfile, build_fallback_llm
from agents import (
    ExplorerAgent, SkepticAgent, StatisticianAgent, EthicistAgent,
    PragmatistAgent, DevilAdvocateAgent, ArchitectAgent, OptimizerAgent,
    StorytellerAgent, CodeWriterAgent,
)
from agents.agent_config     import AGENT_CONFIGS
from agents.base             import BaseAgent
from execution.executor      import CodeExecutor
from memory.agent_memory     import MemorySystem
from orchestration.orchestrator import Orchestrator
from orchestration.registry     import AgentRegistry
from tool_registry              import ToolRegistry


EXPERIMENT_DIR = "experiments"


# ------------------------------------------------------------------ #
# Dataset summary                                                      #
# ------------------------------------------------------------------ #

def build_dataset_summary(df: pd.DataFrame) -> str:
    missing = df.isnull().sum()
    missing_summary = missing[missing > 0].to_string() if missing.any() else "None"

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols     = df.select_dtypes(exclude="number").columns.tolist()

    corr_summary = ""
    if len(numeric_cols) > 1:
        corr      = df[numeric_cols].corr()
        pairs     = corr.abs().unstack().sort_values(ascending=False).drop_duplicates()
        top_pairs = pairs[pairs < 1.0].head(5)
        corr_summary = top_pairs.to_string()

    return f"""
Rows       : {len(df)}
Columns    : {len(df.columns)}
Column List: {list(df.columns)}
Numeric    : {numeric_cols}
Categorical: {cat_cols}

Missing Values:
{missing_summary}

Sample (first 3 rows):
{df.head(3).to_string()}

Basic Stats:
{df.describe().to_string()}

Top Correlations:
{corr_summary if corr_summary else 'N/A'}
""".strip()


# ------------------------------------------------------------------ #
# Agent factory                                                        #
# ------------------------------------------------------------------ #

AGENT_NAMES = [
    "explorer", "skeptic", "statistician", "feature_engineer",
    "ethicist", "pragmatist", "devil_advocate", "optimizer",
    "architect", "storyteller", "code_writer",
]

def build_agents(llm) -> dict:
    from prompts.planner_prompts import FEATURE_ENGINEER_PROMPT

    return {
        "explorer":         ExplorerAgent(llm,       config=AGENT_CONFIGS["explorer"]),
        "skeptic":          SkepticAgent(llm,        config=AGENT_CONFIGS["skeptic"]),
        "statistician":     StatisticianAgent(llm,   config=AGENT_CONFIGS["statistician"]),
        "feature_engineer": BaseAgent("Feature Engineer", FEATURE_ENGINEER_PROMPT, llm, config=AGENT_CONFIGS["feature_engineer"]),
        "ethicist":         EthicistAgent(llm,       config=AGENT_CONFIGS["ethicist"]),
        "pragmatist":       PragmatistAgent(llm,     config=AGENT_CONFIGS["pragmatist"]),
        "devil_advocate":   DevilAdvocateAgent(llm,  config=AGENT_CONFIGS["devil_advocate"]),
        "optimizer":        OptimizerAgent(llm,      config=AGENT_CONFIGS["optimizer"]),
        "architect":        ArchitectAgent(llm,      config=AGENT_CONFIGS["architect"]),
        "storyteller":      StorytellerAgent(llm,    config=AGENT_CONFIGS["storyteller"]),
        "code_writer":      CodeWriterAgent(llm,     config=AGENT_CONFIGS["code_writer"]),
    }


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Data Science Team")
    parser.add_argument("--dataset",      required=True,        help="Path to CSV dataset")
    parser.add_argument("--provider",     default="claude",     help="Primary LLM provider: claude | openai | local")
    parser.add_argument("--model",        default=None,         help="Model name override")
    parser.add_argument("--base-url",     default=None,         help="Base URL for local vLLM server")
    parser.add_argument("--fallback",     default=None,         help="Fallback provider on rate limit (e.g. openai)")
    parser.add_argument("--fallback-model", default=None,       help="Fallback model name")
    parser.add_argument("--mode",         default="manual",     help="Pipeline mode: manual | auto | train | phases")
    parser.add_argument("--target",       default=None,         help="Target column name (train mode)")
    parser.add_argument("--retries",      type=int, default=4,  help="Max training retries (train mode)")
    parser.add_argument("--no-memory",    action="store_true",  help="Disable ChromaDB long-term memory")
    parser.add_argument("--max-agents",   type=int, default=5,  help="Max concurrent agents (default 5)")
    parser.add_argument("--save-log",     action="store_true",  help="Save context log to JSON")
    args = parser.parse_args()

    if not os.path.exists(args.dataset):
        print(f"❌ Dataset not found: {args.dataset}")
        return

    os.makedirs(EXPERIMENT_DIR, exist_ok=True)

    print(f"📂 Loading dataset: {args.dataset}")
    df = pd.read_csv(args.dataset)
    dataset_summary = build_dataset_summary(df)

    print(f"\n🔧 Provider : {args.provider}")
    print(f"🔧 Model    : {args.model or 'default'}")
    print(f"🔧 Fallback : {args.fallback or 'none'}")
    print(f"🔧 Mode     : {args.mode}")
    print(f"🔧 Memory   : {'disabled' if args.no_memory else 'ChromaDB (experiments/chroma_db)'}")

    llm_kwargs = {}
    if args.base_url:
        llm_kwargs["base_url"] = args.base_url

    # Build LLM — with optional multi-provider fallback
    if args.fallback:
        provider_list = [
            {"provider": args.provider, "model": args.model},
            {"provider": args.fallback, "model": args.fallback_model},
        ]
        llm = build_fallback_llm(provider_list)
        print(f"🔧 FallbackLLM: {args.provider} → {args.fallback}")
    else:
        llm = get_llm(args.provider, model=args.model, **llm_kwargs)

    agents = build_agents(llm)

    # Memory system (per-agent ChromaDB + SQLite graph)
    memory_system = None
    if not args.no_memory:
        memory_system = MemorySystem(
            agent_names=AGENT_NAMES,
            persist_dir=os.path.join(EXPERIMENT_DIR, "chroma_db"),
            graph_db=os.path.join(EXPERIMENT_DIR, "graph.db"),
        )

    orch_llm     = llm if args.mode == "auto" else None
    needs_exec   = args.mode in ("train", "phases")
    executor     = CodeExecutor(work_dir=EXPERIMENT_DIR) if needs_exec else None
    tool_reg_dir = os.path.join(EXPERIMENT_DIR, "tool_registry")
    tool_registry = ToolRegistry(registry_dir=tool_reg_dir) if needs_exec else None
    registry = AgentRegistry(
        max_concurrent=args.max_agents,
        persist_path=os.path.join(EXPERIMENT_DIR, "registry.json"),
    )

    orchestrator = Orchestrator(
        agents=agents,
        llm=orch_llm,
        executor=executor,
        memory_system=memory_system,
        registry=registry,
        tool_registry=tool_registry,
    )

    if args.mode == "manual":
        orchestrator.run_manual(dataset_summary)

    elif args.mode == "auto":
        orchestrator.run_auto(dataset_summary)

    elif args.mode == "train":
        orchestrator.run_training_loop(
            dataset_summary=dataset_summary,
            dataset_path=os.path.abspath(args.dataset),
            target_col=args.target,
            max_retries=args.retries,
            experiment_dir=EXPERIMENT_DIR,
        )

    elif args.mode == "phases":
        results = orchestrator.run_phases(
            dataset_summary=dataset_summary,
            dataset_path=os.path.abspath(args.dataset),
            target_col=args.target,
            max_retries=args.retries,
            experiment_dir=EXPERIMENT_DIR,
        )
        print("\n📊 Phase summary:")
        for phase_name, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"  {status} {phase_name:25s} | {result.duration_s}s | {result.summary[:80]}")

    else:
        print(f"❌ Unknown mode '{args.mode}'. Use: manual | auto | train | phases")
        return

    if args.save_log:
        orchestrator.save_log()

    orchestrator.print_summary()
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
