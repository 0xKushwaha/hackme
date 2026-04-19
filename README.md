# Hackme

An autonomous AI-powered data science assistant. Drop in any dataset — CSV, Parquet, images, audio, JSON — and a team of specialized AI agents will analyze it, design a model architecture, and produce a full report.

Also includes **Red Mode**: a live debate tournament where 20 real AI researcher personas (Andrej Karpathy, Geoffrey Hinton, Yann LeCun, etc.) argue over your dataset and synthesize a verdict.

---

## What It Does

| Mode | What happens |
|---|---|
| **Standard Analysis** | 9 specialized agents analyze your dataset across two phases: EDA (Explorer, Skeptic, Statistician, Ethicist) then Model Design (Feature Engineer, Pragmatist, Devil's Advocate, Optimizer, Architect). Final synthesis report included. |
| **Red Mode** | Runs standard analysis first, then 20 AI researcher personas debate the dataset in a structured 3-stage tournament (group debates → champion round → synthesis). |

---

## Installation & Setup

### Prerequisites

- **Python 3.8+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- An API key from [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) *(or a local model — see below)*

---

### Step 1 — Clone the repo

```bash
git clone https://github.com/0xKushwaha/hackme
cd hackme
```

---

### Step 2 — Set up Python environment

It's recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** `requirements.txt` includes LangChain, FastAPI, pandas, scikit-learn, XGBoost, PyArrow, and more. Install may take a minute.

---

### Step 3 — Configure your API key

Copy the example env file and fill in your key:

```bash
cp .env.example .env
```

Open `.env` and set the key for whichever provider you'll use:

```env
# For Claude (Anthropic) — recommended
ANTHROPIC_API_KEY=sk-ant-...

# For OpenAI
OPENAI_API_KEY=sk-...

# For a local model (vLLM / Ollama / LM Studio)
VLLM_URL=http://localhost:8000/v1
VLLM_MODEL=mistral-7b-instruct
```

You only need to fill in the provider you plan to use.

---

### Step 4 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

### Step 5 — Start the backend

```bash
python server.py
```

The API runs at **http://localhost:8000**

---

### Step 6 — Start the frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Using the Web UI

**Home page:**
1. Select your LLM provider (Claude, OpenAI, or local vLLM)
2. Pick a dataset file or folder
3. Optionally describe your goal (e.g. "predict churn", "find anomalies")
4. Choose **Standard Analysis** or **Red Mode**
5. Click **Launch**

**Live Run page:**
- Watch agents work in real time on a D3 force-directed graph
- Each agent node lights up when active — click it to see its output
- Full markdown output appears in a side drawer when each agent finishes

**Summary View:**
- After the run, browse every agent's output as expandable cards
- Export the full analysis as a `.md` file

---

## CLI Usage

You can also run analysis from the command line without the frontend:

```bash
# Basic analysis
python main.py --dataset data.csv --provider claude --mode phases

# Specify a target column (for supervised learning)
python main.py --dataset data.csv --provider claude --mode phases --target SalePrice

# Analyze a folder of files
python main.py --dataset ./my_dataset/ --provider claude --mode phases

# Use OpenAI
python main.py --dataset data.csv --provider openai --mode phases

# Use a local model
python main.py --dataset data.csv --provider local --base-url http://localhost:8000/v1 --mode phases

```

### CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--dataset` | required | File or folder path (any supported format) |
| `--provider` | `claude` | `claude` / `openai` / `local` |
| `--mode` | `manual` | `phases` (recommended) / `manual` / `auto` |
| `--target` | — | Target column name for supervised tasks |
| `--model` | provider default | Override model name (e.g. `gpt-4-turbo`) |
| `--base-url` | — | URL for local vLLM / Ollama / LM Studio |
| `--fallback` | — | Fallback provider if rate-limited |
| `--max-agents` | `5` | Max agents running concurrently |
| `--save-log` | off | Save full context log to JSON |

---

## Supported Dataset Formats

| Type | Formats |
|---|---|
| Tabular | `.csv` `.tsv` `.parquet` `.feather` `.json` `.jsonl` `.xlsx` `.h5` |
| Images | `.jpg` `.png` `.tiff` `.webp` `.gif` `.bmp` |
| Text / NLP | `.txt` `.md` `.xml` `.yaml` `.log` |
| Audio | `.wav` `.mp3` `.flac` `.ogg` |
| Multi-table | Folder with multiple CSVs or Parquet files |
| Mixed | Images + CSV labels, audio + metadata, etc. |

For unrecognized formats, `UnknownFormatAgent` runs a 3-phase deep investigation (magic-byte sniff → 30+ parser probes → schema extraction).

---

## Red Mode

A structured AI researcher debate tournament. 20 personas compete to produce the best analysis of your dataset.

```
Standard Analysis (all 9 agents)
          │
          ▼
Stage A — Group Debates
          5 groups × 4 personas each
          Each persona argues their take
          Group champion selected
          │
          ▼
Stage B — Champion Debate
          5 winners cross-examine each other
          │
          ▼
Stage C — Synthesis
          Final report combining all perspectives
```

**Personas:** Andrej Karpathy · Andrew Ng · Chip Huyen · Chris Olah · Edward Yang · Ethan Mollick · François Chollet · Geoffrey Hinton · Jay Alammar · Jeremy Howard · Jonas Mueller · Lilian Weng · Matei Zaharia · Sam Altman · Santiago Valdarrama · Sebastian Raschka · Shreya Rajpal · Tim Dettmers · Vicki Boykis · Yann LeCun

---

## Agent Team

| Agent | Phase | Role |
|---|---|---|
| **Explorer** | 1 | Patterns, correlations, key features |
| **Skeptic** | 1, 4 | Data quality — outliers, leakage, bias |
| **Statistician** | 1 | Distributions, hypothesis tests |
| **Ethicist** | 1 | Bias, fairness, responsible AI |
| **Feature Engineer** | 2 | New features, transformations, encodings |
| **Pragmatist** | 2 | Model selection, eval strategy |
| **Devil's Advocate** | 2, 4 | Challenges the plan, proposes alternatives |
| **Optimizer** | 2 | Hyperparameter tuning, CV, ensembles |
| **Architect** | 5 | Research-backed architecture design |
| **Storyteller** | 5 | Final report synthesis |

---

## Context Management

Agents share a live context window that grows as each agent finishes. Every agent sees all prior agents' outputs in the same run.

- **Pinned entries** — dataset summary and task goal are always in every agent's context, never dropped
- **Token-aware trimming** — when context approaches the limit, oldest entries are dropped first; pinned entries are never dropped
- **Auto-compaction** — if the context window fills up, an LLM summarizes the oldest entries into a dense bullet-point block, freeing space without losing key decisions. Runs in a background thread so the pipeline doesn't stall.
- **Slim context** — critique agents (Skeptic, Ethicist, Devil's Advocate, Pragmatist) only receive pinned entries + the last 2 outputs, not the full log — reduces latency and token cost

---

## Project Structure

```
hackme/
├── server.py              ← FastAPI backend (start here)
├── main.py                ← CLI entry point
├── requirements.txt
├── .env.example           ← Copy to .env and fill in keys
│
├── frontend/              ← Next.js web UI
│   └── src/
│       ├── app/           # Pages: home, live run, red mode
│       └── components/    # D3 graph, matrix background, etc.
│
├── agents/                # All agent implementations
├── orchestration/         # Pipeline coordination + routing
├── phases/                # Phase 1 (EDA) + Phase 2 (Model Design)
├── red_mode/              # Persona debate tournament
├── personas/              # 20 researcher persona definitions
├── memory/                # Context management and compaction
├── analysis/              # Pre-LLM data profiling
├── backends/              # Claude / OpenAI / vLLM routing
├── tools/                 # Format sniffing, schema extraction
├── prompts/               # Agent prompt templates
│
└── experiments/           # Auto-created on first run
    └── results/           # Persisted run results (JSON)
```

---

## Troubleshooting

**`ModuleNotFoundError` on startup**
Run `pip install -r requirements.txt` inside your virtual environment.

**Frontend can't connect to backend**
Make sure `python server.py` is running and shows `Uvicorn running on http://127.0.0.1:8000`.

**API key not working**
Check that `.env` exists (not just `.env.example`) and the key has no extra spaces or quotes.

**Run hangs or times out**
Check server logs for which agent is stuck. Each agent has a 2-retry limit — if the LLM API is rate-limiting you, wait a moment and try again.

**File picker doesn't open (Linux)**
The native file picker requires a display (`$DISPLAY` or `$WAYLAND_DISPLAY`). If running headless, type the dataset path manually in the UI.

---

## Security Notes

- The backend binds to `127.0.0.1` only — not exposed on your network
- CORS is restricted to `localhost:3000`
- API keys are saved locally at `~/.ds_agent_team.json` with `chmod 600`
- No LLM-generated code is executed — safe for local use
- Pickle deserialization is disabled

> Never commit your `.env` file — it's gitignored.

---

## Development Status

**Done:** Phase 1 (EDA), Phase 2 (Model Design), Red Mode tournament, memory system, multi-provider support, web UI with live D3 graph

**In progress:** Phase 3 (Code Generation), Phase 4 (Validation), execution layer

---

## License

Hackathon project. See LICENSE if present.
