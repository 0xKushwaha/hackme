# Multi-Agent Data Science Team

An autonomous data science pipeline where a team of specialized AI agents collaborates to analyze **any dataset** — CSV, Parquet, images, audio, JSON, multi-file directories — generate training code, execute it, and retry with a different approach on failure, all without human intervention.

Point it at a directory and the **Builder Agent** automatically inspects what's inside, writes custom tool modules to disk, and spawns the right specialist agents (ImageAnalyst, AudioAnalyst, NLPAnalyst…). Those tools are instantly available to the next training subprocess with no orchestrator restart.

Each agent has its own personality, long-term memory, and persistent knowledge graph. Agents learn from past runs and never repeat failed approaches. The pipeline is organized into discrete, independently-restartable phases so a big change to one phase doesn't require rerunning the whole pipeline.

---

## How It Works

```
Dataset file OR directory (any format)
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  DatasetDiscovery                                               │
│  Scans path → FileInfo per file (type, size, columns, preview)  │
│  Supports: CSV, Parquet, JSON, Excel, images, audio, text, …    │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Data Understanding                                    │
│                                                                 │
│  [BuilderAgent] — runs only if dataset is non-trivial           │
│  LLM reads DatasetProfile → JSON plan → writes tools to disk   │
│  Spawns specialist agents (ImageAnalyst, AudioAnalyst, etc.)   │
│                                                                 │
│  [Core EDA] Explorer + Skeptic + Statistician (parallel)       │
│  [Specialists] dynamic agents run in parallel                  │
│  [Ethicist] bias + fairness review (optional)                  │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: Model Design                                          │
│  Feature Engineer → Pragmatist → Devil's Advocate → Optimizer   │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: Code Generation (retry loop)                          │
│  CodeWriter → Executor (subprocess) → ✅ success                │
│                              ↓ fail                             │
│           Expire memories → Devil's Advocate → Pragmatist       │
│           New run_id → CodeWriter → Executor → repeat           │
│  (tools written by BuilderAgent are available from attempt 1)  │
├─────────────────────────────────────────────────────────────────┤
│  Phase 4: Validation                                            │
│  Skeptic + Devil's Advocate + Statistician stress-test results  │
├─────────────────────────────────────────────────────────────────┤
│  Phase 5: Inference                                             │
│  CodeWriter (inference script) → Architect → Storyteller        │
└─────────────────────────────────────────────────────────────────┘
```

### The Agent Team

| Agent | Role | Personality |
|---|---|---|
| **BuilderAgent** | Inspects dataset, creates tools + specialist agents | Architectural planner |
| **Explorer** | EDA — patterns, correlations, key features | Curious, constructive |
| **Skeptic** | Data quality — outliers, leakage, missing values | Aggressively critical |
| **Statistician** | Distributions, hypothesis tests, multicollinearity | Pure neutral, rigorous |
| **Feature Engineer** | New features, encodings, transformations | Inventive |
| **Ethicist** | Bias, fairness, responsible AI concerns | Cautious observer |
| **Pragmatist** | Modeling plan — models to try, eval metric | Results-driven |
| **Devil's Advocate** | Challenges the plan, proposes alternatives | Maximally contrarian |
| **Optimizer** | Hyperparameter tuning, CV strategy, ensembles | Performance-obsessed |
| **Architect** | Deployment design, serving infra, monitoring | Systems-thinker |
| **CodeWriter** | Generates executable Python training + inference scripts | Precise, code-only |
| **Storyteller** | Final narrative for judges/stakeholders | Compelling, audience-aware |
| **Dynamic specialists** | Created by BuilderAgent as needed (e.g. ImageAnalyst) | Domain-specific |

---

## Memory Architecture

Each agent maintains **individual long-term memory** across runs — they remember what worked and what didn't.

### Three layers

```
┌─────────────────────────────────────────────────┐
│  Working Memory (ContextManager)                │
│  Current run's shared log — all agents read it  │
│  Pinned entries (dataset summary) never trimmed  │
│  Token-aware trimming drops oldest entries first │
└─────────────────────────────────────────────────┘
           ↓ stored after each step
┌─────────────────────────────────────────────────┐
│  Long-term Memory (ChromaDB)                    │
│  Per-agent vector store — semantic recall       │
│  Hybrid search: BM25 + vector + temporal decay  │
│  Expired facts filtered out automatically       │
│  Persists to: experiments/chroma_db/            │
└─────────────────────────────────────────────────┘
           ↓ indexed for lineage
┌─────────────────────────────────────────────────┐
│  Knowledge Graph (SQLite)                       │
│  Nodes = agent steps, Edges = relationships     │
│  INFORMED_BY / RETRY_OF / FAILURE_LED_TO /      │
│  CROSS_RUN                                      │
│  Persists to: experiments/graph.db              │
└─────────────────────────────────────────────────┘
```

### Temporal Memory
When a training run **fails**, all memories from that run are marked `expired`. Future recall queries automatically filter them out — the CodeWriter will never suggest a previously failed approach again. Each retry gets a fresh `run_id` so memory scoping is correct.

### Hybrid Search
Memory recall uses a 5-stage pipeline (ported from OpenClaw):
1. Fetch full corpus from ChromaDB for BM25
2. BM25 keyword score (55% weight)
3. ChromaDB vector similarity score (45% weight)
4. Temporal decay — `e^(-ln(2)/half_life × age_days)`. Role-specific half-lives: `error=3d`, `result=14d`, `plan=30d`, `code=90d`. Evergreen roles (`dataset_context`, `narrative`) never decay.
5. MMR re-ranking — Maximal Marginal Relevance for result diversity

### Two Recall Modes
- **Top-K recall** — standard hybrid similarity search (used by most agents)
- **Insight Forge** — LLM decomposes the task into 3–4 sub-questions, runs parallel searches per sub-question, deduplicates and MMR-reranks the merged results (used by Explorer, Feature Engineer, Pragmatist, Optimizer, CodeWriter)

### Context Overflow Handling
Two-layer protection:
- **ToolResultContextGuard** — hard 30% cap on tool output size per step; uses head+tail truncation (biased toward tail where errors live)
- **ContextCompactor** — when context hits 85% of token budget, LLM summarizes oldest 60% of entries with a quality audit (extracts identifiers, metric values, model names; retries up to 3× if summary is missing critical items)

---

## BuilderAgent — Universal Dataset Support

The **BuilderAgent** is a meta-agent that runs at the start of Phase 1. It reads the `DatasetProfile` (file types, sizes, schemas, previews) and asks the LLM:

> *"What tools and specialist agents do we need for this dataset?"*

It then:
1. **Writes tool modules** to `tool_registry/` — e.g. `image_loader.py`, `audio_features.py`, `multi_table_joiner.py`
2. **Spawns specialist agents** into the orchestrator — e.g. `image_analyst`, `audio_analyst`, `nlp_analyst`
3. **Pins the analysis strategy** to the context so all subsequent agents see it

### Fast path
For a single plain tabular file (CSV/Parquet), the LLM call is **skipped entirely** — the standard EDA team is sufficient.

### How tools get loaded without restart
Tools written to `tool_registry/` are picked up automatically by the next `CodeExecutor` subprocess because each subprocess starts fresh and imports from disk. The orchestrator keeps running — no reload required.

```
BuilderAgent writes: tool_registry/image_loader.py
                                   audio_features.py
                     ↓
Next subprocess does: sys.path.insert(0, 'tool_registry')
                      import image_loader
                      import audio_features
                      ← just works, no orchestrator restart
```

---

## Phase-Based Architecture

Phases are discrete, independently-restartable units. If you update the model design logic, you can re-run from `ModelDesignPhase` without redoing EDA — the shared context already has Phase 1's outputs.

```bash
# Run the full phase pipeline on a directory
python main.py --dataset ./my_dataset/ --provider claude --mode phases --target label

# Or compose your own phase order in code
from phases import DataUnderstandingPhase, ModelDesignPhase, CodeGenerationPhase

orchestrator.run_phases(
    dataset_summary=summary,
    dataset_path="./my_dataset/",
    dataset_profile=profile,          # DatasetProfile from DatasetDiscovery
    phases=[
        DataUnderstandingPhase(orchestrator),
        ModelDesignPhase(orchestrator),
        CodeGenerationPhase(orchestrator),
    ]
)
```

| Phase | Required Agents | Optional / Dynamic |
|---|---|---|
| `DataUnderstandingPhase` | explorer, skeptic, statistician | ethicist, builder-spawned specialists |
| `ModelDesignPhase` | feature_engineer, pragmatist | devil_advocate, optimizer |
| `CodeGenerationPhase` | code_writer | devil_advocate, pragmatist |
| `ValidationPhase` | skeptic | devil_advocate, statistician |
| `InferencePhase` | code_writer | architect, storyteller |

---

## Tool Registry

Agents can write reusable Python utility modules to disk during a run. The next training subprocess picks them up automatically — **no orchestrator restart needed**.

This works because `CodeExecutor` runs training scripts as fresh subprocesses. Each new subprocess imports from disk, so any file written to `tool_registry/` between attempts is immediately available.

```python
# An agent writes a reusable preprocessing helper
orch.tool_registry.register(
    name="preprocessing_utils",
    code="def robust_scale(X): ...",
    description="Robust scaling and outlier clipping utilities",
    tags=["preprocessing", "scaling"],
)

# The registry injects this context into the CodeWriter's prompt
# Generated scripts get sys.path extended automatically:
#   sys.path.insert(0, '/path/to/tool_registry')
#   import preprocessing_utils
```

The registry is indexed in both JSON (`_index.json`) and ChromaDB for semantic search.

---

## Project Structure

```
hackathon/
├── agents/
│   ├── agent_config.py        # Behavioral profiles (stance, activity, sentiment)
│   ├── base.py                # BaseAgent — memory recall + storage wired in
│   ├── builder_agent.py       # BuilderAgent — inspects dataset, creates tools + agents
│   ├── analyst_agents.py      # Explorer, Skeptic, Statistician, Ethicist
│   ├── planner_agents.py      # Pragmatist, DevilAdvocate, Architect, Optimizer
│   ├── coder_agent.py         # CodeWriter — training + inference script generation
│   └── storyteller_agent.py
│
├── phases/
│   ├── base.py                # BasePhase, PhaseResult
│   ├── discovery.py           # DatasetDiscovery — scans any file/directory
│   ├── data_understanding.py  # Phase 1: Builder → EDA → specialists → ethics
│   ├── model_design.py        # Phase 2: features, plan, critique, tuning
│   ├── code_generation.py     # Phase 3: training retry loop
│   ├── validation.py          # Phase 4: stress-test results
│   └── inference.py           # Phase 5: inference script + deployment + narrative
│
├── memory/
│   ├── context_manager.py     # Working memory for the current run
│   ├── vector_store.py        # ChromaDB wrapper with temporal expiry
│   ├── hybrid_search.py       # BM25 + vector + temporal decay + MMR
│   ├── graph_store.py         # SQLite knowledge graph (nodes + edges)
│   ├── agent_memory.py        # Per-agent recall/remember + insight_forge
│   └── compaction.py          # LLM context summarization with quality audit
│
├── execution/
│   ├── executor.py            # Runs generated code in subprocess, captures output
│   ├── result_parser.py       # Parses METRICS: {...}, classifies error types
│   └── context_guard.py       # 30% output cap + head/tail truncation
│
├── orchestration/
│   ├── orchestrator.py        # Routes tasks, manages memory, drives all pipeline modes
│   └── registry.py            # AgentRegistry — lifecycle tracking, spawn limits
│
├── backends/
│   ├── llm_backends.py        # Claude / OpenAI / local vLLM
│   └── fallback.py            # FallbackLLM — multi-provider rotation with cooldown
│
├── tool_registry/
│   └── registry.py            # ToolRegistry — agents write reusable modules here
│
├── prompts/
│   ├── analyst_prompts.py
│   ├── planner_prompts.py
│   ├── coder_prompts.py
│   └── orchestrator_prompt.py
│
├── experiments/               # Auto-created — scripts, context logs, DB files, tools
├── main.py
└── requirements.txt
```

---

## Setup

```bash
git clone <repo>
cd hackathon
pip install -r requirements.txt
```

Set your API key:
```bash
export ANTHROPIC_API_KEY=your_key_here
# or
export OPENAI_API_KEY=your_key_here
```

---

## Usage

### Phase-based pipeline (recommended)

```bash
# Single CSV — standard pipeline
python main.py --dataset data.csv --provider claude --mode phases --target SalePrice

# Directory with mixed data — BuilderAgent auto-configures
python main.py --dataset ./my_dataset/ --provider claude --mode phases --target label

# With all options
python main.py \
  --dataset    ./my_dataset/ \
  --provider   claude \
  --mode       phases \
  --target     price \
  --retries    4 \
  --save-log
```

### Other modes

```bash
# Advisory only — analysis without code execution (works on any dataset type)
python main.py --dataset ./data/ --provider claude --mode manual

# Orchestrator LLM decides each step dynamically
python main.py --dataset ./data/ --provider claude --mode auto

# Original monolithic training loop
python main.py --dataset data.csv --provider claude --mode train --target price
```

### Multi-provider fallback

```bash
# Tries Claude first, falls back to OpenAI on rate limit
python main.py \
  --dataset    ./my_dataset/ \
  --provider   claude \
  --fallback   openai \
  --mode       phases \
  --target     price
```

### Other LLM backends

```bash
# OpenAI
python main.py --dataset ./data/ --provider openai --model gpt-4o-mini --mode phases

# Local vLLM server
python main.py --dataset ./data/ --provider local --base-url http://localhost:8000/v1 --mode phases

# Disable long-term memory (fast first test)
python main.py --dataset data.csv --provider claude --mode phases --no-memory

# Skip BuilderAgent (use standard agents only)
python main.py --dataset data.csv --provider claude --mode phases --no-builder
```

---

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--dataset` | required | Path to dataset **file or directory** (any format) |
| `--provider` | `claude` | LLM provider: `claude`, `openai`, `local` |
| `--model` | provider default | Model name override |
| `--base-url` | — | Base URL for local vLLM server |
| `--fallback` | — | Fallback provider on rate limit (e.g. `openai`) |
| `--fallback-model` | — | Fallback model name |
| `--mode` | `manual` | Pipeline mode: `manual`, `auto`, `train`, `phases` |
| `--target` | — | Target column name (train/phases mode) |
| `--retries` | `4` | Max training retry attempts |
| `--max-agents` | `5` | Max concurrent agents |
| `--no-memory` | off | Disable ChromaDB long-term memory |
| `--no-builder` | off | Skip BuilderAgent (use default agents only) |
| `--save-log` | off | Save context log to JSON |

---

## Supported Dataset Formats

`--dataset` accepts **any file or directory**. `DatasetDiscovery` scans the path and the `BuilderAgent` adapts the pipeline automatically.

| Type | Extensions | What BuilderAgent creates |
|---|---|---|
| **Tabular** | `.csv` `.tsv` `.parquet` `.feather` `.json` `.jsonl` `.xlsx` `.h5` | Nothing extra (standard EDA team handles it) |
| **Image** | `.jpg` `.png` `.tiff` `.webp` `.gif` `.bmp` | `image_loader` tool + `ImageAnalyst` agent |
| **Text / NLP** | `.txt` `.md` `.xml` `.yaml` `.log` | `text_preprocessor` tool + `NLPAnalyst` agent |
| **Audio** | `.wav` `.mp3` `.flac` `.ogg` | `audio_features` tool + `AudioAnalyst` agent |
| **Video** | `.mp4` `.avi` `.mov` | `video_sampler` tool + `VideoAnalyst` agent |
| **Multi-table** | directory with multiple CSVs | `multi_table_joiner` tool + join strategy in context |
| **Mixed** | images + CSV labels, audio + metadata, etc. | combination of the above |

### Example: image classification directory
```
my_dataset/
├── train/
│   ├── cat/  ← 500 .jpg files
│   └── dog/  ← 500 .jpg files
└── labels.csv
```
BuilderAgent sees: `image` + `tabular` types → writes `image_loader.py` to `tool_registry/`, spawns `ImageAnalyst` agent, pins strategy: *"Computer vision classification task. Images are class-organized. Use CNN or ViT. Labels from labels.csv."*

---

## Agent Behavioral Profiles

Agents have more than a system prompt — they have a behavioral config that shapes how they respond:

```python
# Skeptic is maximally critical
AgentConfig(
    activity_level = 0.7,
    stance         = "opposing",   # actively pushes back
    sentiment_bias = -0.7,         # frames everything negatively
)

# Explorer is thorough and constructive
AgentConfig(
    activity_level    = 0.9,       # exhaustive responses
    stance            = "supportive",
    sentiment_bias    = 0.6,
    use_insight_forge = True,      # multi-query memory recall
)

# Devil's Advocate is contrarian to the extreme
AgentConfig(
    stance         = "opposing",
    sentiment_bias = -0.8,
)
```

These are injected as `BEHAVIORAL PARAMETERS` into each agent's system prompt at runtime.

---

## Generated Script Contract

The CodeWriter produces training scripts that follow this contract:
- Print metrics as: `METRICS: {"accuracy": 0.95, "f1": 0.94}`
- Save model to `trained_model.pkl`
- Exit `0` on success, `1` on failure

The inference script (Phase 5):
- Loads `trained_model.pkl`
- Accepts a CSV path as CLI argument
- Applies the same preprocessing pipeline
- Outputs `predictions.csv`

---

## Experiments Directory

After a run, `experiments/` contains:

```
experiments/
├── chroma_db/                  # Per-agent ChromaDB collections (persists across runs)
├── graph.db                    # SQLite knowledge graph
├── registry.json               # AgentRegistry lifecycle log
├── tool_registry/              # Reusable Python modules written by agents
│   ├── _index.json             # Tool index
│   └── preprocessing_utils.py  # (example tool written during run)
├── train_attempt_1.py          # Generated training scripts
├── train_attempt_2.py
├── inference.py                # Generated inference script
└── context_{run_id}.json       # Full context log for each run
```
