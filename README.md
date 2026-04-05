# Multi-Agent Data Science Team

An autonomous data science pipeline where a team of specialized AI agents collaborates to analyse **any dataset** — CSV, Parquet, images, audio, JSON, multi-file directories. Browse the dataset, understand patterns, design models, and generate architectural recommendations. All backed by a persistent memory system to learn from prior runs.

Plus a **Red Mode** tournament where 20 real-world AI researcher personas debate the dataset in a structured multi-stage competition.

**Current Status:** Phase 1 (Data Understanding), Phase 2 (Model Design), and Red Mode fully implemented. Phases 3–5 in development. FastAPI + Next.js frontend with live D3 agent graph visualization.

---

## Quick Start

### 1. Install dependencies

```bash
git clone <repo>
cd hackathon
pip install -r requirements.txt
```

### 2. Set up API key

Copy `.env` and fill in your key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...

# For local vLLM (optional)
VLLM_URL=http://localhost:8080/v1
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

Modern Next.js frontend with animated matrix-rain background.

**Home** — Select your LLM provider (Claude, OpenAI, or local vLLM), enter your API key, pick a dataset file or folder, optionally describe your goal. Choose between **Standard Analysis** or **Red Mode** debate. Click **Launch**.

**Live Run** — Watch agents work in real time on a D3 force-directed graph. Each agent node is color-coded and lights up as it becomes active. Click any node to see:
- Running description card while agent is active
- Full markdown output in a side drawer once complete

**Summary View** — After pipeline finishes, switch to the `SYNTHESIS` tab to browse every agent's output as expandable cards. Click to expand inline. Export the full analysis as `.md`.

Results persist to disk and cache in `sessionStorage` — switch tabs to restore state.

---

## Red Mode

A structured multi-stage AI researcher debate tournament. 20 personas (Andrej Karpathy, Geoffrey Hinton, Yann LeCun, etc.) compete to produce the best analysis of your dataset.

```
Phase 1  — Standard pipeline (all 9 agents analyse the dataset)
             │
             ▼
Stage A  — Group debates (5 groups × 4 personas each)
           Each persona argues their take on the dataset
           Group champion selected per round
             │
             ▼
Stage B  — Champions debate (5 winners cross-examine each other)
             │
             ▼
Stage C  — Synthesis (final report combining all perspectives)
```

**Red Mode UI:**
- Animated crimson matrix background during the debate
- Force-directed graph showing all 20 personas, group clusters, and champion connections
- Real-time glow on active personas; checkmark on completed ones
- Side panel per persona: Round 1 output, champion debate, group election summary
- `GRAPH` / `SYNTHESIS` tabs on completion
- Download full report as `.md` (all stages + champion outputs + synthesis)

---

## CLI

```bash
# Single file analysis with phases mode
python main.py --dataset data.csv --provider claude --mode phases --target SalePrice

# Directory analysis
python main.py --dataset ./my_dataset/ --provider claude --mode phases

# Local vLLM
python main.py --dataset ./data/ --provider local --base-url http://localhost:8080/v1 --mode phases

# Manual mode (fixed agent sequence, no LLM-driven routing)
python main.py --dataset data.csv --provider claude --mode manual

# Disable long-term memory (faster for testing)
python main.py --dataset data.csv --provider claude --mode phases --no-memory

# Fallback to OpenAI on Claude rate limit
python main.py --dataset data.csv --provider claude --fallback openai --mode phases
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--dataset` | required | File or directory path (any format) |
| `--provider` | `claude` | `claude` / `openai` / `local` |
| `--model` | provider default | Model name override (e.g., `gpt-4-turbo`) |
| `--base-url` | — | vLLM / Ollama / LM Studio server URL |
| `--fallback` | — | Fallback provider on rate limit |
| `--fallback-model` | — | Fallback model name |
| `--mode` | `manual` | `phases` (Recommended) / `manual` / `auto` |
| `--target` | — | Target column for supervised learning (auto-detected if blank) |
| `--no-memory` | off | Disable ChromaDB long-term memory |
| `--max-agents` | `5` | Max concurrent agents |
| `--save-log` | off | Save full context log to JSON |

---

## How It Works

```
Dataset + Task Description (from UI or CLI)
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
│  ✅ IMPLEMENTED                                                   │
│                                                                  │
│  Explorer        → patterns, correlations, key features          │
│  Skeptic         → outliers, leakage, data quality issues        │
│  Statistician    → distributions, hypothesis tests               │
│  Ethicist        → bias and fairness review (conditional)        │
│  LibraryInstaller→ auto pip-installs missing packages if needed  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 2: Model Design ────────────────────────────────────────┐
│  ✅ IMPLEMENTED                                                   │
│                                                                  │
│  Feature Engineer → new features, transformations, encodings     │
│  Pragmatist       → model selection and eval metric plan         │
│  Devil's Advocate → challenges the plan, proposes alternatives   │
│  Optimizer        → hyperparameter strategy, CV, ensembles       │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 3: Code Generation ─────────────────────────────────────┐
│  🚧 IN DEVELOPMENT                                               │
│                                                                  │
│  CodeWriter → generate training script                           │
│  Executor   → run as subprocess                                  │
│  Retry on error → auto pip-install + DiagnosticAgent analysis   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 4: Validation ──────────────────────────────────────────┐
│  🚧 IN DEVELOPMENT                                               │
│                                                                  │
│  Skeptic + Devil's Advocate → stress-test results                │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── Phase 5: Architecture + Final Report ─────────────────────────┐
│  ✅ IMPLEMENTED (Architecture + Synthesis)                      │
│                                                                  │
│  Architect      → design arch (research-backed, arxiv refs)      │
│  Final Report   → synthesised markdown with all agent outputs    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Team

| Agent | Phase(s) | Role | Personality |
|---|---|---|---|
| **Explorer** | 1 (EDA) | Patterns, correlations, key features | Curious, optimistic, insight-focused |
| **Skeptic** | 1, 4 | Data quality — outliers, leakage, bias | Aggressively critical |
| **Statistician** | 1 | Distributions, hypothesis tests, multicollinearity | Rigorous, neutral |
| **Feature Engineer** | 2 | New features, transformations, encodings | Inventive, practical |
| **Ethicist** | 1 | Bias, fairness, responsible AI ethics | Cautious observer |
| **Pragmatist** | 2 | Model selection, eval metric strategy | Results-driven, fast-tier |
| **Devil's Advocate** | 2, 4 | Challenges plan, proposes alternatives | Maximally contrarian, fast-tier |
| **Optimizer** | 2 | Hyperparameter tuning, CV strategy, ensembles | Performance-obsessed |
| **Architect** | 5 | Research-backed architecture design with arxiv + Wikipedia citations | Systems-thinker |
| **Storyteller** | 5 | Narrative synthesis, report composition | Communicative |
| **LibraryInstallerAgent** | 1, 3 | Auto-detects and pip-installs missing packages | Autonomous ops |
| **DataProfiler** | Pre-phase | Dataset scanning, format detection, quality scoring | Observational |

Agent personalities adapt at runtime — if data quality is low or errors occur, agents shift to more aggressive/redesign-focused modes. Fast-tier agents (marked above) use optimized models for speed on critique/planning tasks.

---

## Red Mode Personas

20 researcher personas drawn from real AI practitioners:

Andrej Karpathy · Andrew Ng · Chip Huyen · Chris Olah · Edward Yang · Ethan Mollick · François Chollet · Geoffrey Hinton · Jay Alammar · Jeremy Howard · Jonas Mueller · Lilian Weng · Matei Zaharia · Sam Altman · Santiago Valdarrama · Sebastian Raschka · Shreya Rajpal · Tim Dettmers · Vicki Boykis · Yann LeCun

Each persona has a distinct analytical style, communication voice, and area of expertise that influences how they debate the dataset.

---

## Supported Formats

Point `--dataset` at any file or directory. DatasetDiscovery auto-detects:

| Type | Formats Detected |
|---|---|
| Tabular | `.csv` `.tsv` `.parquet` `.feather` `.json` `.jsonl` `.xlsx` `.h5` |
| Images | `.jpg` `.png` `.tiff` `.webp` `.gif` `.bmp` |
| Text / NLP | `.txt` `.md` `.xml` `.yaml` `.log` |
| Audio | `.wav` `.mp3` `.flac` `.ogg` |
| Multi-table | Directory with multiple CSVs or parquet files |
| Mixed | Images + CSV labels, audio + metadata, etc. |

For non-tabular or unrecognised formats, **UnknownFormatAgent** runs a 3-phase investigation (magic-byte sniff → 30+ parser probe → deep schema extraction) and reports what it finds. Large Parquet files are streamed via PyArrow — never fully loaded into memory for initial profiling.

---

## Memory System

Each agent has individual long-term memory across runs — they learn what worked and avoid repeating failures.

```
Working Memory (ContextManager)
  ├─ Current run timeline (pinned: dataset summary + task)
  ├─ Token-aware trimming (oldest-first, non-pinned only)
  └─ At 85% capacity: LLM summarizes oldest 60% + quality audit
        ↓
Long-term Memory (ChromaDB, per agent)
  ├─ Hybrid search: 55% BM25 keyword + 45% vector similarity
  ├─ Temporal decay: errors fade in 3 days, code in 90 days
  ├─ Failed run memories auto-expired — never repeated
  ├─ Insight Forge: multi-query decomposition for broad context
  └─ MMR re-ranking for result diversity
        ↓
Knowledge Graph (SQLite)
  ├─ Nodes = agent execution steps
  ├─ Edges = INFORMED_BY / RETRY_OF / FAILURE_LED_TO / CROSS_RUN
  ├─ Audit trail = full agent activity log per run
  └─ Query interface for analyzing causality
```

**Why This Matters:** Agents don't start from scratch each time. If Feature Engineer found a good encoding last run, Pragmatist will reference it. If a retry strategy failed, that memory is marked as poisoned and won't be suggested again.

---

## Security

The backend is hardened for local development use:

- **CORS** restricted to `localhost:3000` with explicit method/header allowlist
- **Server binding** on `127.0.0.1` only — not exposed on LAN
- **Input validation** on all endpoints: path traversal rejected, field length limits enforced, persona names allowlisted
- **Credentials file** written with `chmod 600` — owner-read only
- **Error responses** return generic messages; full stack traces logged server-side only
- **Pickle deserialization disabled** — `UnknownFormatAgent` will not load `.pkl` files
- **No LLM-generated code execution** — the adaptive parser feature that wrote and ran LLM-generated scripts has been removed entirely
- **XSS** — all markdown rendered via `react-markdown`, no `dangerouslySetInnerHTML`
- **Session data** stored in `sessionStorage` (cleared on tab close), not `localStorage`

> The `.env` file is gitignored. Never commit real API keys.

---

## Project Structure

```
hackathon/
├── server.py                  ← FastAPI backend (start here)
├── main.py                    ← CLI entry point
├── requirements.txt
│
├── frontend/                  ← Next.js web UI (TypeScript + Tailwind)
│   └── src/
│       ├── app/
│       │   ├── page.tsx           # Home — provider + dataset + launch
│       │   ├── run/[id]/page.tsx  # Live run + summary view
│       │   └── red/[id]/page.tsx  # Red Mode debate view
│       ├── components/
│       │   ├── PipelineGraph.tsx  # D3 force-directed agent graph
│       │   ├── RedModeGraph.tsx   # Red Mode persona tournament graph
│       │   ├── Background.tsx     # Animated matrix-rain background
│       │   ├── GlobalBackground.tsx
│       │   └── PageTransition.tsx # Smooth page transitions
│       └── lib/
│           ├── mockPipeline.ts    # Test mode mock data
│           └── mockRedMode.ts     # Red mode mock data
│
├── agents/                    # ✅ Phases 1-2 agents implemented
│   ├── base.py                # BaseAgent — core + memory interface
│   ├── agent_config.py        # Behavioral configs (adapt on failure)
│   ├── analyst_agents.py      # Explorer, Skeptic, Statistician, Ethicist
│   ├── planner_agents.py      # Pragmatist, Devil's Advocate, Architect
│   ├── storyteller_agent.py   # Final report synthesis
│   ├── installer_agent.py     # Auto pip-install missing packages
│   └── unknown_format_agent.py # Non-tabular format detection (3-phase)
│
├── orchestration/
│   ├── orchestrator.py        # Core: manual/auto/phases modes
│   ├── registry.py            # Agent execution registry + state tracking
│   └── conversation_manager.py # Multi-agent discussions
│
├── phases/                    # ✅ Phases 1-2, 🚧 Phases 3-5 in dev
│   ├── base.py                # BasePhase class
│   ├── discovery.py           # DatasetDiscovery — format detection
│   ├── data_understanding.py  # Phase 1 ✅
│   └── model_design.py        # Phase 2 ✅
│
├── red_mode/                  # ✅ Red Mode tournament
│   ├── orchestrator.py        # Tournament coordinator
│   ├── rounds.py              # Group + champion debate logic
│   ├── grouping.py            # Persona grouping + champion election
│   ├── brief_builder.py       # Phase 1 → Red Mode brief handoff
│   └── persona_loader.py      # Load persona markdown files
│
├── personas/                  # 20 researcher persona markdown files
│
├── memory/
│   ├── context_manager.py     # Working memory + token management
│   ├── agent_memory.py        # Per-agent interface
│   ├── vector_store.py        # ChromaDB with temporal decay
│   ├── hybrid_search.py       # BM25 + vector + MMR ranking
│   ├── graph_store.py         # SQLite knowledge graph
│   └── compaction.py          # LLM-based summarization + audit
│
├── analysis/
│   └── data_profiler.py       # Pre-LLM dataset statistics
│
├── backends/
│   ├── llm_backends.py        # Claude / OpenAI / vLLM routing
│   └── fallback.py            # Multi-provider fallback on rate limit
│
├── tools/
│   ├── format_sniffer.py      # Magic-byte file format detection
│   ├── content_sampler.py     # Raw content sampling
│   ├── structure_prober.py    # 30+ format probers
│   └── schema_extractor.py    # Column/schema analysis
│
├── prompts/
│   ├── analyst_prompts.py     # Explorer, Skeptic, Statistician prompts
│   ├── planner_prompts.py     # Pragmatist, Devil's Advocate, etc.
│   └── orchestrator_prompt.py # Routing + coordination logic
│
└── experiments/               # Auto-created on first run
    ├── context_*.json         # Full context logs per run
    ├── registry.json          # Agent execution history
    ├── chroma_db/             # ✅ Per-agent vector store
    ├── graph.db               # ✅ Knowledge graph
    └── results/               # Persisted run results
```

**Legend:** ✅ = Implemented, 🚧 = In Development

---

## Development Status

### ✅ Completed

- **Frontend:** Home, Live Run, Summary, and Red Mode pages with D3 graph visualization
- **Backend:** FastAPI with credentials, file browse, run polling, result retrieval, input validation
- **Phase 1 (Data Understanding):** All EDA agents (Explorer, Skeptic, Statistician, Ethicist)
- **Phase 2 (Model Design):** Feature Engineer, Pragmatist, Devil's Advocate, Optimizer
- **Red Mode:** 20-persona tournament (group debates → champion round → synthesis), full report download
- **Memory System:** ChromaDB (per-agent), SQLite graph, hybrid search, temporal decay, compaction
- **Agent Framework:** Base agent class, behavioral configs, registry, context manager
- **Dataset Discovery:** Format detection, profiling, multi-file handling
- **Multi-Provider Support:** Claude, OpenAI, local vLLM with fallback routing
- **Security Hardening:** CORS, path traversal, input validation, no pickle, no LLM code exec, XSS protection

### 🚧 In Development

- **Phase 3 (Code Generation):** CodeWriter, executor, retry loop, error classification
- **Phase 4 (Validation):** Stress-testing and validation agents
- **Execution Layer:** Subprocess runner, tool validator, 3-stage compilation checking
- **BuilderAgent:** Custom tool generation for non-tabular data
- **Result Persistence:** JSON export, run history, model artifact storage

### 📝 Future

- Streaming UI updates for real-time agent metrics
- Model training script export + inference serving suggestions
- Cross-run experiment comparison dashboard
- Agent skill discovery (auto-detection of agent strengths by dataset type)

---

## Architecture Highlights

### Token-Aware Context Management

Working memory automatically compacts at 85% token capacity. Pinned entries (dataset summary + task) are never trimmed. At compaction time, LLM summarizes the oldest 60% of messages and stores the summary as a new entry, preserving information density.

### Behavioral Adaptation

Agents have configurable **activity level**, **stance** (supportive/opposing), and **sentiment_bias**. These values shift at runtime based on data quality metrics:
- If data quality is poor (missing %, outliers, imbalance), Skeptic + Ethicist become more active
- If errors happen during training, Devil's Advocate becomes more confrontational
- These adaptations are logged and inform future runs

### Hybrid Memory Search

Long-term memory combines three scoring approaches:
1. **BM25 keyword matching** (55% weight) — for recall of similar past tasks
2. **Vector similarity** (45% weight) — for semantic relevance
3. **Temporal decay** — errors older than 3 days are deprioritized; code older than 90 days is forgotten
4. **MMR re-ranking** — removes redundant similar results

### Fast-Tier Model Routing

For critique/planning agents (Skeptic, Ethicist, Devil's Advocate, Pragmatist), a smaller/faster model can be substituted when no explicit `--model` override is provided. Full model is used for code generation and feature engineering.

---

## Environment & Dependencies

**Python:** 3.8+
**Main Stack:** LangChain, ChromaDB, FastAPI, Next.js, D3.js
**ML Libraries:** scikit-learn, XGBoost, pandas, PyArrow

See `requirements.txt` for pinned versions.

---

## Contributing

To add a new agent phase:
1. Create a new file in `phases/` inheriting from `BasePhase`
2. Define `name`, `REQUIRED_AGENTS`, `_run()` method
3. Register in `orchestrator.run_phases()`
4. Add prompts to `prompts/` directory

To enhance memory:
- Extend `AgentMemory` for new recall patterns
- Modify `HybridSearch` for custom scoring
- Add new relationship types to knowledge graph in `graph_store.py`

---

## License

Hackathon project. See LICENSE (if present).
