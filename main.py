"""
Multi-Agent Data Science Team
==============================
Usage:
    python main.py --dataset data.csv --provider claude
    python main.py --dataset data.csv --provider local --base-url http://localhost:8000/v1 --model mistral-7b
    python main.py --dataset data.csv --provider openai --model gpt-4o-mini
    python main.py --dataset data.csv --provider claude --mode manual
"""

import argparse
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from llm_backends import get_llm
from agents import Agent
from orchestrator import Orchestrator
from prompts import (
    EXPLORER_PROMPT, SKEPTIC_PROMPT, PRAGMATIST_PROMPT, STORYTELLER_PROMPT,
    STATISTICIAN_PROMPT, FEATURE_ENGINEER_PROMPT, DEVIL_ADVOCATE_PROMPT,
    OPTIMIZER_PROMPT, ETHICIST_PROMPT, ARCHITECT_PROMPT,
)


# ------------------------------------------------------------------ #
# Dataset summary builder                                             #
# ------------------------------------------------------------------ #

def build_dataset_summary(df: pd.DataFrame) -> str:
    """Build a compact dataset summary to feed into the agents."""
    missing = df.isnull().sum()
    missing_summary = missing[missing > 0].to_string() if missing.any() else "None"

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    corr_summary = ""
    if len(numeric_cols) > 1:
        corr = df[numeric_cols].corr()
        # Find top correlated pairs (excluding self)
        pairs = (
            corr.abs()
            .unstack()
            .sort_values(ascending=False)
            .drop_duplicates()
        )
        top_pairs = pairs[(pairs < 1.0)].head(5)
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
# Manual pipeline (fixed step order)                                  #
# ------------------------------------------------------------------ #

def run_manual(orchestrator: Orchestrator, dataset_summary: str):
    """
    Full pipeline:
      Round 1 (parallel): Explorer + Skeptic + Statistician
      Round 2 (parallel): Feature Engineer + Ethicist
      Round 3           : Pragmatist
      Round 4           : Devil's Advocate
      Round 5           : Optimizer
      Round 6           : Storyteller
    """
    print("\n🚀 Starting analysis (manual mode)\n")
    orchestrator.log = f"[DATASET CONTEXT]\n{dataset_summary}"

    # Round 1 — Independent initial analysis (all 3 in parallel)
    print("\n⚡ Round 1: Explorer + Skeptic + Statistician (parallel)...")
    with ThreadPoolExecutor() as executor:
        futures = {
            "explorer": executor.submit(
                orchestrator.step, "explorer",
                "Perform a thorough EDA. Find patterns, correlations, key features. Suggest what might be the target variable."
            ),
            "skeptic": executor.submit(
                orchestrator.step, "skeptic",
                "Inspect data quality: missing values, outliers, duplicates, leakage risks, suspicious patterns."
            ),
            "statistician": executor.submit(
                orchestrator.step, "statistician",
                "Analyze distributions, check for multicollinearity, test statistical significance of correlations, flag skewed features."
            ),
        }
        for f in futures.values():
            f.result()

    # Round 2 — Feature ideas + Ethics check (parallel, both read Round 1 output)
    print("\n⚡ Round 2: Feature Engineer + Ethicist (parallel)...")
    with ThreadPoolExecutor() as executor:
        futures = {
            "feature_engineer": executor.submit(
                orchestrator.step, "feature_engineer",
                "Based on the EDA and statistical findings, suggest new features, encoding strategies, and transformations. Flag redundant features."
            ),
            "ethicist": executor.submit(
                orchestrator.step, "ethicist",
                "Identify sensitive attributes, potential bias in the data, fairness concerns, and ethical risks of deploying this model."
            ),
        }
        for f in futures.values():
            f.result()

    # Round 3 — Pragmatist builds the plan from all findings
    print("\n📋 Round 3: Pragmatist building action plan...")
    orchestrator.step(
        "pragmatist",
        "Given all findings so far, create a clear step-by-step modeling plan. Pick top 2-3 models, specify features to use/drop, and define the evaluation metric."
    )

    # Round 4 — Devil's Advocate challenges the plan
    print("\n😈 Round 4: Devil's Advocate stress-testing the plan...")
    orchestrator.step(
        "devil_advocate",
        "Challenge the Pragmatist's plan. Is the problem framed correctly? Are we picking the right model? What critical assumption is wrong? Suggest an alternative approach."
    )

    # Round 5 — Optimizer squeezes performance
    print("\n🔧 Round 5: Optimizer tuning strategy...")
    orchestrator.step(
        "optimizer",
        "Given the chosen models and Devil's Advocate feedback, recommend a concrete hyperparameter tuning and cross-validation strategy. Suggest any ensembling opportunities."
    )

    # Round 6 — Architect designs the deployment
    print("\n🏗️  Round 6: Architect designing deployment...")
    orchestrator.step(
        "architect",
        "Given the chosen model and optimization strategy, design the deployment architecture. Address: serving infrastructure, inference latency, training-serving skew, monitoring, and any bottlenecks."
    )

    # Round 7 — Storyteller wraps up for judges
    print("\n📖 Round 7: Storyteller writing the narrative...")
    orchestrator.step(
        "storyteller",
        "Synthesize everything into a compelling narrative for judges. What is the dataset about, what did we find, what model are we using and why, what ethical concerns exist, how will it be deployed, and what results can we expect?"
    )


# ------------------------------------------------------------------ #
# Auto pipeline (LLM decides steps)                                   #
# ------------------------------------------------------------------ #

def run_auto(orchestrator: Orchestrator, dataset_summary: str):
    print("\n🤖 Starting analysis (auto mode — orchestrator decides)\n")
    orchestrator.run_auto(initial_context=dataset_summary)


# ------------------------------------------------------------------ #
# Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Data Science Team")
    parser.add_argument("--dataset",   required=True,       help="Path to CSV dataset")
    parser.add_argument("--provider",  default="claude",    help="LLM provider: claude | openai | local")
    parser.add_argument("--model",     default=None,        help="Model name override")
    parser.add_argument("--base-url",  default=None,        help="Base URL for local vLLM server")
    parser.add_argument("--mode",      default="manual",    help="Pipeline mode: manual | auto")
    parser.add_argument("--save-log",  action="store_true", help="Save analysis log to file")
    args = parser.parse_args()

    # Load dataset
    if not os.path.exists(args.dataset):
        print(f"❌ Dataset not found: {args.dataset}")
        return

    print(f"📂 Loading dataset: {args.dataset}")
    df = pd.read_csv(args.dataset)
    dataset_summary = build_dataset_summary(df)

    print(f"\n🔧 Provider : {args.provider}")
    print(f"🔧 Model    : {args.model or 'default'}")
    print(f"🔧 Mode     : {args.mode}")

    # Initialize LLM
    llm_kwargs = {}
    if args.base_url:
        llm_kwargs["base_url"] = args.base_url

    llm = get_llm(args.provider, model=args.model, **llm_kwargs)

    # Build agents
    agents = {
        "explorer":         Agent("Explorer",         EXPLORER_PROMPT,         llm),
        "skeptic":          Agent("Skeptic",          SKEPTIC_PROMPT,          llm),
        "statistician":     Agent("Statistician",     STATISTICIAN_PROMPT,     llm),
        "feature_engineer": Agent("Feature Engineer", FEATURE_ENGINEER_PROMPT, llm),
        "pragmatist":       Agent("Pragmatist",       PRAGMATIST_PROMPT,       llm),
        "devil_advocate":   Agent("Devil's Advocate", DEVIL_ADVOCATE_PROMPT,   llm),
        "optimizer":        Agent("Optimizer",        OPTIMIZER_PROMPT,        llm),
        "ethicist":         Agent("Ethicist",         ETHICIST_PROMPT,         llm),
        "architect":        Agent("Architect",        ARCHITECT_PROMPT,        llm),
        "storyteller":      Agent("Storyteller",      STORYTELLER_PROMPT,      llm),
    }

    # Build orchestrator (pass llm only for auto mode)
    orch_llm = llm if args.mode == "auto" else None
    orchestrator = Orchestrator(agents=agents, llm=orch_llm)

    # Run
    if args.mode == "manual":
        run_manual(orchestrator, dataset_summary)
    elif args.mode == "auto":
        run_auto(orchestrator, dataset_summary)
    else:
        print(f"❌ Unknown mode '{args.mode}'. Use 'manual' or 'auto'.")
        return

    # Save log if requested
    if args.save_log:
        orchestrator.save_log("analysis_log.txt")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
