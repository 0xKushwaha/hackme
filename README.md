# Multi-Agent Data Science Team

An autonomous data science pipeline where a team of 10 specialized AI agents collaborates to analyse **any dataset** — CSV, Parquet, images, audio, JSON, multi-file directories — build models, execute code, and retry on failure. Zero human intervention required.

---

## Quick Start

### 1. Install dependencies

```bash
git clone <repo>
cd hackathon
pip install -r requirements.txt
```

### 2. Set up API key

Create a `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...

# For local vLLM (optional)
VLLM_URL=http://localhost:8000/v1
VLLM_MODEL=mistral-7b-instruct
```

### 3. Start the backend

```bash
python server.py
# Runs at http://localhost:8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## Web UI

The frontend is a Next.js app with three views:

**Home** — Select your LLM provider (Claude, OpenAI, or local vLLM), enter your API key, pick a dataset file or folder, and optionally describe your goal. Click **Launch Analysis**.

**Run** — Watch all 10 agents work in real time. Toggle between:
- **Grid** — agent status cards with live indicators
- **Split** — agents + live log side by side
- **Log** — full-width terminal output

A step indicator in the nav bar tracks your position through the 5-phase pipeline.

**Results** — Browse each agent's full output. Switch between:
- **Agents** — clickable cards per agent with a side drawer
- **Report** — expandable full report with one section per agent

Export the complete analysis as a `.md` file.

---

## CLI

```bash
# Single file
python main.py --dataset data.csv --provider claude --mode phases --target SalePrice

# Directory (any format — BuilderAgent auto-configures)
python main.py --dataset ./my_dataset/ --provider claude --mode phases

# Local vLLM
python main.py --dataset ./data/ --provider local --base-url http://localhost:8000/v1 --mode phases

# Advisory only (no code execution)
python main.py --dataset data.csv --provider claude --mode manual

# Disable memory (faster first run)
python main.py --dataset data.csv --provider claude --mode phases --no-memory
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--dataset` | required | File or directory, any format |
| `--provider` | `claude` | `claude` / `openai` / `local` |
| `--model` | provider default | Model name override |
| `--base-url` | — | vLLM / Ollama / LM Studio server URL |
| `--fallback` | — | Fallback provider on rate limit |
| `--mode` | `manual` | `phases` / `manual` / `auto` / `train` |
| `--target` | — | Target column (auto-detected if blank) |
| `--retries` | `4` | Max training retry attempts |
| `--no-memory` | off | Disable ChromaDB |
| `--no-builder` | off | Skip BuilderAgent |

---

## How It Works

```
Dataset + Task Description
        │
        ▼
  DatasetDiscovery          — scans any file/directory, detects format
        │
        ▼
  DataProfiler              — pre-LLM stats: shape, missing %, outliers,
                              class imbalance, quality score 0–1
        │
        ▼
┌── Phase 1: Data Understanding ──────────────────────────────────┐
│  BuilderAgent    → writes custom tools, spawns specialist agents │
│  LibraryInstaller→ auto pip-installs missing packages            │
│  Explorer        → patterns, correlations, key features          │
│  Skeptic         → outliers, leakage, data quality issues        │
│  Statistician    → distributions, hypothesis tests               │
│  Ethicist        → bias and fairness review (conditional)        │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 2: Model Design ────────────────────────────────────────┐
│  Feature Engineer → new features, transformations, encodings     │
│  Pragmatist       → model selection and eval metric plan         │
│  Devil's Advocate → challenges the plan, proposes alternatives   │
│  Optimizer        → hyperparameter strategy, CV, ensembles       │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 3: Code Generation (retry loop) ────────────────────────┐
│  CodeWriter → generate training script                           │
│  Executor   → run as subprocess                                  │
│                                                                  │
│  On ImportError → LibraryInstaller → retry same script           │
│  On other error → DiagnosticAgent → Devil's Advocate             │
│               → Pragmatist redesign → new attempt (up to 4x)    │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 4: Validation ──────────────────────────────────────────┐
│  Skeptic + Devil's Advocate + Statistician stress-test results   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 5: Inference ───────────────────────────────────────────┐
│  CodeWriter → inference script                                   │
│  Architect  → deployment strategy                                │
│  Storyteller→ final narrative and report                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Team

| Agent | Role | Personality |
|---|---|---|
| **Explorer** | EDA — patterns, correlations, key features | Curious, optimistic |
| **Skeptic** | Data quality — outliers, leakage, missing values | Aggressively critical |
| **Statistician** | Distributions, hypothesis tests, multicollinearity | Rigorous, neutral |
| **Feature Engineer** | New features, encodings, transformations | Inventive |
| **Ethicist** | Bias, fairness, responsible AI | Cautious observer |
| **Pragmatist** | Model plan — which models, eval metric | Results-driven |
| **Devil's Advocate** | Challenges the plan, proposes alternatives | Maximally contrarian |
| **Optimizer** | Hyperparameter tuning, CV strategy, ensembles | Performance-obsessed |
| **Architect** | Deployment design, serving infra | Systems-thinker |
| **Storyteller** | Final narrative and report | Compelling, audience-aware |
| **BuilderAgent** | Creates tools + specialist agents for non-tabular data | Architectural planner |
| **LibraryInstallerAgent** | Detects and auto-installs missing packages | Autonomous ops |
| **DiagnosticAgent** | Root cause analysis before every code retry | Structured, precise |
| **CodeWriter** | Generates executable Python training + inference scripts | Precise, code-only |

Agent personalities adapt at runtime — if data quality is low or training keeps failing, agents automatically shift to more aggressive / redesign-focused modes.

---

## Supported Formats

Point `--dataset` at any file or directory:

| Type | Extensions |
|---|---|
| Tabular | `.csv` `.tsv` `.parquet` `.feather` `.json` `.jsonl` `.xlsx` `.h5` |
| Images | `.jpg` `.png` `.tiff` `.webp` `.gif` `.bmp` |
| Text / NLP | `.txt` `.md` `.xml` `.yaml` `.log` |
| Audio | `.wav` `.mp3` `.flac` `.ogg` |
| Video | `.mp4` `.avi` `.mov` |
| Multi-table | directory with multiple CSVs |
| Mixed | images + CSV labels, audio + metadata, etc. |

For non-tabular data, **BuilderAgent** inspects the directory, writes custom tool modules to `tool_registry/`, and spawns the right specialist agent. Large Parquet files are streamed via PyArrow — never fully loaded into memory.

---

## Memory System

Each agent has individual long-term memory across runs — they remember what worked and avoid repeating failures.

```
Working Memory (ContextManager)
  Current run timeline — pinned dataset summary + task
  Token-aware: drops oldest entries first
  At 85% capacity: LLM summarizes oldest 60%
        ↓
Long-term Memory (ChromaDB, per agent)
  Hybrid search: 55% BM25 keyword + 45% vector similarity
  Temporal decay: errors fade in 3 days, code in 90 days
  Failed run memories auto-expired — never repeated
  MMR re-ranking for result diversity
        ↓
Knowledge Graph (SQLite)
  Nodes = agent steps
  Edges = INFORMED_BY / RETRY_OF / FAILURE_LED_TO / CROSS_RUN
```

---

## Project Structure

```
hackathon/
├── server.py                  ← FastAPI backend (start here)
├── main.py                    ← CLI entry point
├── requirements.txt
│
├── frontend/                  ← Next.js web UI
│   └── src/app/
│       ├── page.tsx           # Home — provider + dataset + launch
│       ├── run/[id]/          # Live run view
│       └── results/[id]/      # Results + report
│
├── agents/
│   ├── base.py                # BaseAgent — memory recall + storage
│   ├── agent_config.py        # Behavioral profiles (adapt on failure)
│   ├── builder_agent.py       # Creates tools + specialist agents
│   ├── installer_agent.py     # Auto pip-install
│   ├── diagnostic_agent.py    # Root cause before retry
│   ├── analyst_agents.py      # Explorer, Skeptic, Statistician, Ethicist
│   ├── planner_agents.py      # Pragmatist, DevilAdvocate, Architect, Optimizer
│   ├── coder_agent.py         # CodeWriter
│   └── storyteller_agent.py
│
├── phases/
│   ├── discovery.py           # Scan any file/directory
│   ├── data_understanding.py  # Phase 1
│   ├── model_design.py        # Phase 2
│   ├── code_generation.py     # Phase 3 — retry loop + diagnostics
│   ├── validation.py          # Phase 4
│   └── inference.py           # Phase 5
│
├── memory/
│   ├── context_manager.py     # Working memory
│   ├── vector_store.py        # ChromaDB with temporal expiry
│   ├── hybrid_search.py       # BM25 + vector + decay + MMR
│   ├── graph_store.py         # SQLite knowledge graph
│   ├── agent_memory.py        # Per-agent recall + insight forge
│   └── compaction.py          # LLM summarization with quality audit
│
├── execution/
│   ├── executor.py            # Subprocess runner + auto ImportError fix
│   ├── tool_validator.py      # 3-stage tool validation
│   └── context_guard.py       # 30% output cap + head/tail truncation
│
└── experiments/               # Auto-created on first run
    ├── chroma_db/             # Per-agent vector store
    ├── graph.db               # Knowledge graph
    ├── tool_registry/         # Tools written by agents mid-run
    ├── train_attempt_*.py     # Generated training scripts
    └── context_{run_id}.json  # Full context log
```
