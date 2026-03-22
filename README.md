# Multi-Agent Data Science Team

An autonomous data science pipeline where a team of specialized AI agents collaborates to analyze **any dataset** — CSV, Parquet, images, audio, JSON, multi-file directories — generate training code, execute it, and retry with a different approach on failure. Fully autonomous, zero human intervention.

Point it at a directory and the **Builder Agent** automatically inspects what's inside, writes custom tool modules to disk, installs missing libraries, and spawns the right specialist agents (ImageAnalyst, AudioAnalyst, NLPAnalyst…). Every failure at every level is retried with full error context fed back to the LLM so it can self-correct.

---

## Quick Start

### UI (recommended)
```bash
pip install -r requirements.txt
streamlit run app.py
# Opens at http://localhost:8501
```

### CLI
```bash
python main.py --dataset ./my_dataset/ --provider claude --mode phases --target price
```

---

## UI

```
streamlit run app.py
```

```
┌─────────────────────┬──────────────────────────────────────────────┐
│  SIDEBAR            │  TABS                                        │
│                     │                                              │
│  ⚡ LLM Provider    │  📡 Live Agent Log                           │
│  ● claude           │  ┌──────────────────────────────────────┐   │
│  ○ openai           │  │ [BuilderAgent] 🔍 Analysing dataset  │   │
│  ○ local (vLLM)     │  │ [DataUnderstanding] EDA agents...    │   │
│                     │  │ ══════════════════════════════        │   │
│  API Key ••••••••   │  │   EXPLORER                           │   │
│                     │  │   The dataset has 12 features...     │   │
│  ─────────────────  │  └──────────────────────────────────────┘   │
│  🗂️ Dataset         │                                              │
│  /home/user/data/   │  📊 Results Report                           │
│                     │  # 🤖 Multi-Agent Analysis Report            │
│  Task Description   │  ## 🎯 Task / Competition Context            │
│  Kaggle competition │  ## 🔬 Agent Analysis                        │
│  to predict prices. │  ### Explorer  ...                           │
│  Metric: RMSE.      │  ### Skeptic   ...                           │
│                     │                                              │
│  Mode: phases       │  ⬇️ Download                                 │
│  Target: SalePrice  │  ┌──────────────────────────────────────┐   │
│                     │  │  ⬇️  Download Results ZIP            │   │
│  [🚀 Run Analysis]  │  │  analysis_report.md                  │   │
│                     │  │  context_log.json                    │   │
│                     │  │  train_attempt_*.py                  │   │
│                     │  └──────────────────────────────────────┘   │
└─────────────────────┴──────────────────────────────────────────────┘
```

**Sidebar inputs:**
- Provider: Claude / OpenAI / local vLLM (with server URL)
- API key (password field — stored in session only, never written to disk)
- Dataset path — any file or directory
- Task / competition description — free text, pinned in context for every agent
- Mode, target column, retries, memory toggle, builder toggle

**Output tabs:**
- **Live Agent Log** — streams every agent's output in real time as it runs
- **Results Report** — formatted markdown grouped by phase and agent
- **Download** — one-click ZIP with full report, context JSON, generated scripts, tool modules

---

## How It Works

```
User input: dataset path + task description
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  DatasetDiscovery                                               │
│  Scans any path → FileInfo per file (type, size, columns,       │
│  preview). Supports CSV, Parquet, JSON, Excel, images,          │
│  audio, text, code, archives — any format.                      │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Data Understanding                                    │
│                                                                 │
│  BuilderAgent (skipped for plain tabular)                       │
│    LLM reads DatasetProfile → JSON plan                         │
│    Writes custom tool modules to tool_registry/ (validated)     │
│    Spawns specialist agents (ImageAnalyst, AudioAnalyst…)       │
│    Retries on failure — error context fed back to LLM           │
│                                                                 │
│  LibraryInstallerAgent (auto, no user needed)                   │
│    Detects missing packages from ImportError messages           │
│    pip-installs them using the same Python interpreter          │
│    Re-validates / re-runs automatically                         │
│                                                                 │
│  Core EDA: Explorer + Skeptic + Statistician (each with retry) │
│  Specialists: dynamic agents run (each with retry)              │
│  Ethicist: bias + fairness review (optional, with retry)        │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: Model Design                                          │
│  Feature Engineer → Pragmatist → Devil's Advocate → Optimizer   │
│  (all steps with per-agent retry + error context injection)     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: Code Generation (retry loop)                          │
│  CodeWriter → Executor (subprocess) → ✅ success                │
│                              ↓ fail                             │
│    ImportError? → LibraryInstaller → retry same script          │
│    Other error? → Expire memories → Devil's Advocate            │
│                → Pragmatist → new run_id → CodeWriter           │
│                → Executor → repeat up to N times               │
├─────────────────────────────────────────────────────────────────┤
│  Phase 4: Validation                                            │
│  Skeptic + Devil's Advocate + Statistician stress-test results  │
├─────────────────────────────────────────────────────────────────┤
│  Phase 5: Inference                                             │
│  CodeWriter (inference script) → Architect → Storyteller        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Retry Architecture

Every failure anywhere in the pipeline is automatically retried — no human intervention needed.

```
BuilderAgent.run()
  ├─ LLM plan generation  — up to 3 attempts
  │    JSON parse fails?  → retry with "previous JSON was invalid: {error}"
  │
  ├─ Per-tool validation  — up to 3 attempts per tool
  │    Syntax error?      → LLM rewrites tool with error context
  │    Import error?      → LibraryInstallerAgent installs first → re-validate
  │    Still broken?      → tool skipped with warning
  │
  └─ BuilderAgent itself  — up to 2 full attempts
       Exception?         → retry entire builder run

DataUnderstandingPhase
  ├─ Each EDA agent       — up to 2 attempts
  │    Any exception?     → error appended to task → LLM self-corrects
  │    Import error?      → LibraryInstallerAgent runs first
  │
  └─ Each specialist      — up to 2 attempts (same pattern)

Orchestrator.step()       — up to 2 attempts (default, configurable)
  Any agent exception?    → installer check → error in task → retry

CodeExecutor.run()        — 1 automatic inner retry on ImportError
  Script ImportError?     → LibraryInstallerAgent installs package
                          → re-runs SAME script (no outer retry consumed)
```

---

## Agent Team

| Agent | Role | Personality |
|---|---|---|
| **BuilderAgent** | Inspects dataset, creates tools + specialist agents | Architectural planner |
| **LibraryInstallerAgent** | Detects + installs missing packages automatically | Autonomous ops |
| **Explorer** | EDA — patterns, correlations, key features | Curious, constructive |
| **Skeptic** | Data quality — outliers, leakage, missing values | Aggressively critical |
| **Statistician** | Distributions, hypothesis tests, multicollinearity | Rigorous, neutral |
| **Feature Engineer** | New features, encodings, transformations | Inventive |
| **Ethicist** | Bias, fairness, responsible AI concerns | Cautious observer |
| **Pragmatist** | Modeling plan — models to try, eval metric | Results-driven |
| **Devil's Advocate** | Challenges the plan, proposes alternatives | Maximally contrarian |
| **Optimizer** | Hyperparameter tuning, CV strategy, ensembles | Performance-obsessed |
| **Architect** | Deployment design, serving infra, monitoring | Systems-thinker |
| **CodeWriter** | Generates executable Python training + inference scripts | Precise, code-only |
| **Storyteller** | Final narrative for judges/stakeholders | Compelling, audience-aware |
| **Dynamic specialists** | Created by BuilderAgent for non-tabular data | Domain-specific |

---

## Supported Dataset Formats

Point `--dataset` (or the UI path field) at **any file or directory**.

| Type | Extensions | What BuilderAgent creates |
|---|---|---|
| **Tabular** | `.csv` `.tsv` `.parquet` `.feather` `.json` `.jsonl` `.xlsx` `.h5` | Nothing extra — standard EDA team handles it |
| **Image** | `.jpg` `.png` `.tiff` `.webp` `.gif` `.bmp` | `image_loader` tool + `ImageAnalyst` agent |
| **Text / NLP** | `.txt` `.md` `.xml` `.yaml` `.log` | `text_preprocessor` tool + `NLPAnalyst` agent |
| **Audio** | `.wav` `.mp3` `.flac` `.ogg` | `audio_features` tool + `AudioAnalyst` agent |
| **Video** | `.mp4` `.avi` `.mov` | `video_sampler` tool + `VideoAnalyst` agent |
| **Multi-table** | directory with multiple CSVs | `multi_table_joiner` tool + join strategy pinned in context |
| **Mixed** | images + CSV labels, audio + metadata, etc. | combination of the above |

**Example — image classification dataset:**
```
my_dataset/
├── train/
│   ├── cat/  ← 500 .jpg files
│   └── dog/  ← 500 .jpg files
└── labels.csv
```
BuilderAgent sees `image + tabular` → writes `image_loader.py` → spawns `ImageAnalyst` → pins strategy: *"CV classification task. Class-organized images. Use CNN or ViT."*

---

## Memory Architecture

Each agent has **individual long-term memory** across runs — they remember what worked and what didn't, and never repeat a failed approach.

```
┌──────────────────────────────────────────────────┐
│  Working Memory  (ContextManager)                │
│  Shared log for the current run                  │
│  Pinned entries (dataset summary, strategy)      │
│  never trimmed. Token-aware: drops oldest first. │
└──────────────────────────────────────────────────┘
              ↓ stored after every step
┌──────────────────────────────────────────────────┐
│  Long-term Memory  (ChromaDB, per-agent)         │
│  Hybrid search: BM25 (55%) + vector (45%)        │
│  Temporal decay: errors fade in 3d, code in 90d  │
│  MMR re-ranking for result diversity             │
│  Failed run memories auto-expired (filtered out) │
└──────────────────────────────────────────────────┘
              ↓ indexed for lineage
┌──────────────────────────────────────────────────┐
│  Knowledge Graph  (SQLite)                       │
│  Nodes = agent steps                             │
│  Edges = INFORMED_BY / RETRY_OF /                │
│          FAILURE_LED_TO / CROSS_RUN              │
└──────────────────────────────────────────────────┘
```

### Temporal Memory
When a training run **fails**, all its memories are marked `expired`. Future recall queries filter them out — the CodeWriter never re-suggests a failed approach. Each retry gets a fresh `run_id`.

### Hybrid Search (5-stage)
1. Fetch corpus from ChromaDB for BM25 scoring
2. BM25 keyword score — 55% weight
3. ChromaDB vector similarity — 45% weight
4. Temporal decay — `e^(-ln(2)/half_life × age_days)`. Half-lives: error=3d, result=14d, plan=30d, code=90d. Dataset/narrative: never decay.
5. MMR re-ranking — diversity via Maximal Marginal Relevance

### Two Recall Modes
- **Top-K** — standard hybrid search (most agents)
- **Insight Forge** — LLM decomposes task into 3–4 sub-questions, parallel searches, deduplication, MMR re-rank (Explorer, CodeWriter, Optimizer, Pragmatist)

### Context Overflow Protection
- **ToolResultContextGuard** — hard 30% cap on tool output; head+tail truncation biased toward tail (where errors live)
- **ContextCompactor** — at 85% of token budget, LLM summarizes oldest 60% with a quality audit (retries 3× if identifiers/metrics are missing from summary)

---

## BuilderAgent + Tool Registry

### How dynamic tools work
Tools written to `tool_registry/` are available to the **next subprocess immediately** — no orchestrator restart. Each training script runs as a fresh subprocess that imports from disk.

```
BuilderAgent writes:  tool_registry/image_loader.py
                      tool_registry/audio_features.py

Next training subprocess:
  sys.path.insert(0, 'tool_registry')
  import image_loader        ← just works
  import audio_features      ← just works
```

### Tool validation before writing
Every tool the LLM generates goes through 3 stages before being saved:
1. **Syntax** — `ast.parse()` — instant check
2. **Compile** — `compile()` — catches structural errors
3. **Import** — fresh subprocess — catches missing libraries

If validation fails → LLM asked to fix with error context → re-validated. Up to 3 attempts per tool.

### LibraryInstallerAgent
If a tool or script needs a library that isn't installed:
1. Parses the `ImportError` message to find the module name
2. Maps it to a pip package (`PIL→Pillow`, `cv2→opencv-python`, `sklearn→scikit-learn`, `librosa→librosa`, `torch→torch`, 60+ mappings)
3. Runs `pip install` using the same Python interpreter
4. Re-runs validation / re-executes the script

**Triggered automatically by:** BuilderAgent (tool validation), DataUnderstandingPhase (specialist agents), Orchestrator.step() (any agent), CodeExecutor (training scripts).

---

## Phase-Based Architecture

Each phase is an independent, re-runnable unit. Update model design logic → re-run from Phase 2 without redoing EDA.

| Phase | Required Agents | Optional / Dynamic |
|---|---|---|
| `DataUnderstandingPhase` | explorer, skeptic, statistician | ethicist, builder-spawned specialists |
| `ModelDesignPhase` | feature_engineer, pragmatist | devil_advocate, optimizer |
| `CodeGenerationPhase` | code_writer | devil_advocate, pragmatist |
| `ValidationPhase` | skeptic | devil_advocate, statistician |
| `InferencePhase` | code_writer | architect, storyteller |

```python
# Custom phase composition
orchestrator.run_phases(
    dataset_summary=summary,
    dataset_path="./my_dataset/",
    dataset_profile=profile,
    phases=[
        DataUnderstandingPhase(orchestrator),
        ModelDesignPhase(orchestrator),
        CodeGenerationPhase(orchestrator),
        # skip validation, skip inference
    ]
)
```

---

## Project Structure

```
hackathon/
│
├── app.py                     ← Streamlit UI (start here)
├── main.py                    ← CLI entry point
├── requirements.txt
│
├── agents/
│   ├── base.py                # BaseAgent — memory recall + storage
│   ├── agent_config.py        # Behavioral profiles (stance, activity, sentiment)
│   ├── builder_agent.py       # BuilderAgent — creates tools + specialist agents
│   ├── installer_agent.py     # LibraryInstallerAgent — auto pip-install
│   ├── analyst_agents.py      # Explorer, Skeptic, Statistician, Ethicist
│   ├── planner_agents.py      # Pragmatist, DevilAdvocate, Architect, Optimizer
│   ├── coder_agent.py         # CodeWriter
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
│   ├── context_manager.py     # Working memory (current run)
│   ├── vector_store.py        # ChromaDB wrapper with temporal expiry
│   ├── hybrid_search.py       # BM25 + vector + temporal decay + MMR
│   ├── graph_store.py         # SQLite knowledge graph
│   ├── agent_memory.py        # Per-agent recall/remember + insight_forge
│   └── compaction.py          # LLM summarization with quality audit
│
├── execution/
│   ├── executor.py            # Subprocess runner + ImportError auto-fix
│   ├── tool_validator.py      # 3-stage tool code validation
│   ├── result_parser.py       # Parses METRICS:{}, classifies error types
│   └── context_guard.py       # 30% output cap + head/tail truncation
│
├── orchestration/
│   ├── orchestrator.py        # Routes tasks, retry in step(), all pipeline modes
│   └── registry.py            # AgentRegistry — lifecycle tracking, spawn limits
│
├── backends/
│   ├── llm_backends.py        # Claude / OpenAI / local vLLM
│   └── fallback.py            # FallbackLLM — multi-provider rotation with cooldown
│
├── tool_registry/
│   └── registry.py            # ToolRegistry — runtime tool modules
│
├── prompts/
│   ├── analyst_prompts.py
│   ├── planner_prompts.py
│   ├── coder_prompts.py
│   └── orchestrator_prompt.py
│
└── experiments/               # Auto-created on first run
    ├── chroma_db/             # Per-agent ChromaDB (persists across runs)
    ├── graph.db               # SQLite knowledge graph
    ├── registry.json          # AgentRegistry lifecycle log
    ├── tool_registry/         # Tools written by agents mid-run
    ├── train_attempt_*.py     # Generated training scripts
    ├── inference.py           # Generated inference script
    └── context_{run_id}.json  # Full context log
```

---

## Setup

```bash
git clone <repo>
cd hackathon
pip install -r requirements.txt
```

No API key setup needed for the UI — enter it in the sidebar at runtime. For the CLI:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

---

## Usage

### UI (recommended — easiest)

```bash
streamlit run app.py
```

1. Select provider → paste API key (or enter vLLM server URL)
2. Enter dataset path (file or directory, any format)
3. Describe your task/competition in the text area
4. Click **Run Analysis**
5. Watch agents work live in the **Live Agent Log** tab
6. Read the report in **Results Report**
7. Download everything as a ZIP from **Download**

---

### CLI

```bash
# Single file
python main.py --dataset data.csv --provider claude --mode phases --target SalePrice

# Directory (mixed formats — BuilderAgent auto-configures)
python main.py --dataset ./my_dataset/ --provider claude --mode phases --target label

# With fallback provider
python main.py --dataset ./data/ --provider claude --fallback openai --mode phases

# Local vLLM
python main.py --dataset ./data/ --provider local --base-url http://localhost:8000/v1 --mode phases

# Advisory only (no code execution)
python main.py --dataset ./data/ --provider claude --mode manual

# Disable memory (faster first run)
python main.py --dataset data.csv --provider claude --mode phases --no-memory

# Skip BuilderAgent
python main.py --dataset data.csv --provider claude --mode phases --no-builder
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--dataset` | required | File or directory, any format |
| `--provider` | `claude` | `claude` / `openai` / `local` |
| `--model` | provider default | Model name override |
| `--base-url` | — | vLLM server URL |
| `--fallback` | — | Fallback provider on rate limit |
| `--fallback-model` | — | Fallback model name |
| `--mode` | `manual` | `phases` / `manual` / `auto` / `train` |
| `--target` | — | Target column (auto-detected if blank) |
| `--retries` | `4` | Max training retry attempts |
| `--max-agents` | `5` | Max concurrent agents |
| `--no-memory` | off | Disable ChromaDB |
| `--no-builder` | off | Skip BuilderAgent |
| `--save-log` | off | Save context log to JSON |

---

## Generated Script Contract

The CodeWriter produces training scripts that follow a strict contract:
- Print metrics as: `METRICS: {"accuracy": 0.95, "f1": 0.94}`
- Save model to `trained_model.pkl`
- Exit `0` on success, `1` on failure

The inference script (Phase 5):
- Loads `trained_model.pkl`
- Accepts a data path as CLI argument
- Applies the same preprocessing pipeline
- Outputs `predictions.csv`

---

## Agent Behavioral Profiles

Agents have behavioral configs injected into their system prompts, shaping how they respond independently of their task:

```python
# Skeptic is maximally critical
AgentConfig(activity_level=0.7, stance="opposing", sentiment_bias=-0.7)

# Explorer is thorough and optimistic
AgentConfig(activity_level=0.9, stance="supportive", sentiment_bias=0.6,
            use_insight_forge=True)

# Devil's Advocate is contrarian to the extreme
AgentConfig(stance="opposing", sentiment_bias=-0.8)
```
