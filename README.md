# Hackme

An autonomous AI-powered data science assistant. Drop in any dataset — CSV, Parquet, images, audio, JSON — and a team of specialized AI agents will analyze it, design a model architecture, and produce a full report.

Also includes **Red Mode**: a live debate tournament where 20 real AI researcher personas (Andrej Karpathy, Geoffrey Hinton, Yann LeCun, etc.) argue over your dataset and synthesize a verdict.

---

## Floe Integration

> **This project integrates [Floe](https://floe-labs.gitbook.io/docs) — the agentic credit layer on Base.**
>
> Agents borrow USDC automatically against WETH/cbBTC collateral to pay for x402 APIs. No wallet logic inside the agents. No per-call setup. Just add `--use-floe` and the pipeline handles the rest.
>
> Built using the official [`floe-agentkit-actions`](https://pypi.org/project/floe-agentkit-actions/) Python SDK, wrapped as LangChain tools and wired into the full multi-agent orchestrator.
>
> See full setup and usage: [Floe Mode section](#floe-mode--agentic-credit-on-base)

---

## What It Does

| Mode | What happens |
|---|---|
| **Standard Analysis** | 9 specialized agents analyze your dataset across two phases: EDA (Explorer, Skeptic, Statistician, Ethicist) then Model Design (Feature Engineer, Pragmatist, Devil's Advocate, Optimizer, Architect). Final synthesis report included. |
| **Red Mode** | Runs standard analysis first, then 20 AI researcher personas debate the dataset in a structured 3-stage tournament (group debates → champion round → synthesis). |
| **Floe Mode** | Integrates the [Floe](https://floelabs.xyz) x402 credit layer — agents automatically borrow USDC on Base to pay for external APIs, zero wallet management. Enable with `--use-floe`. Built on the official [`floe-agentkit-actions`](https://pypi.org/project/floe-agentkit-actions/) SDK. |

---

## Installation & Setup

> **New to this?** Don't worry — just follow the steps in order. Each step tells you exactly what to do.

### Prerequisites

Before you start, make sure you have these installed:

- **Python 3.8+** — [download here](https://python.org) *(check: `python --version`)*
- **Node.js 18+** — [download here](https://nodejs.org) *(check: `node --version`)*
- An API key from [Anthropic](https://console.anthropic.com) (for Claude) **or** [OpenAI](https://platform.openai.com) *(you only need one)*

---

### Step 1 — Clone the repo

```bash
git clone https://github.com/0xKushwaha/hackme
cd hackme
```

---

### Step 2 — Set up Python environment

Create an isolated environment so packages don't conflict with your system:

```bash
# Using conda (recommended)
conda create -n hackme python=3.12
conda activate hackme
pip install -r requirements.txt

# Or using venv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> This installs LangChain, FastAPI, pandas, scikit-learn, XGBoost, Floe SDK, and more. May take a couple of minutes.

---

### Step 3 — Configure your API keys

Copy the example config file:

```bash
cp .env.example .env
```

Open `.env` and fill in the key for whichever LLM provider you want to use — **you only need one**:

```env
# Option A — Claude (recommended, best results)
ANTHROPIC_API_KEY=sk-ant-...

# Option B — OpenAI
OPENAI_API_KEY=sk-...

# Option C — Local model (vLLM / Ollama / LM Studio)
VLLM_URL=http://localhost:8000/v1
VLLM_MODEL=mistral-7b-instruct
```

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

You should see: `Uvicorn running on http://127.0.0.1:8000`

---

### Step 6 — Start the frontend

Open a **second terminal** and run:

```bash
cd frontend
npm run dev
```

Then open **http://localhost:3000** in your browser.

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

# With Floe credit layer enabled
python main.py --dataset data.csv --provider claude --mode phases --use-floe
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
| `--use-floe` | off | Enable Floe x402 credit layer (requires `FLOE_PRIVATE_KEY` + `FLOE_RPC_URL` in `.env`) |

---

## Floe Mode — Agentic Credit on Base

> **References:** [Floe Website](https://floelabs.xyz) · [Floe Docs](https://floe-labs.gitbook.io/docs) · [Agent Quickstart](https://floe-labs.gitbook.io/docs/developers/agent-quickstart) · [x402 Protocol](https://x402.org) · [floe-agentkit-actions on PyPI](https://pypi.org/project/floe-agentkit-actions/)

### What is Floe?

[Floe](https://floelabs.xyz) is a credit layer for AI agents on [Base](https://base.org) (a fast, cheap Ethereum L2 chain). The idea is simple:

- You deposit ETH (as WETH) or cbBTC **once** as collateral
- Whenever an agent needs to pay for an external API call, Floe automatically borrows USDC against that collateral and settles the payment
- **The agent never thinks about money** — no wallet logic, no per-call setup

This is built on the [x402 payment protocol](https://x402.org), which lets APIs charge per-request in USDC. Floe works with 13,000+ x402 APIs today including Exa, Firecrawl, Nansen, and more — see [x402list.fun](https://x402list.fun) for the full directory.

### Why it's useful

Without Floe, if your agents need to call paid APIs, you'd have to manually manage a wallet, approve tokens, handle gas, and write payment logic inside every agent. With Floe, you just add `--use-floe` and it's all handled automatically.

### How to use it — 3 steps

**Step 1 — Install the SDK** (already included in `requirements.txt`):
```bash
pip install floe-agentkit-actions
```

**Step 2 — Add credentials to `.env`**:

```env
# EVM wallet private key — holds your WETH collateral on Base
# Never share this. .env is gitignored.
FLOE_PRIVATE_KEY=0x...

# Free Base RPC from https://alchemy.com
FLOE_RPC_URL=https://mainnet.base.org

# Market ID — run this to find it:
# python -c "from backends.floe_client import FloeClient; print(FloeClient().get_markets())"
FLOE_MARKET_ID=0x...
```

**Step 3 — Run with Floe enabled:**

```bash
python main.py --dataset data.csv --provider claude --mode phases --use-floe
```

When Floe initialises successfully, you'll see:
```
🔧 Floe     : enabled
   Floe  : ✅ wallet 0xYourWalletAddress
```

### Available Floe actions

The `FloeClient` in `backends/floe_client.py` wraps the official [`floe-agentkit-actions`](https://pypi.org/project/floe-agentkit-actions/) SDK and exposes:

| Action | What it does |
|---|---|
| `instant_borrow` | Auto-selects the best lender and borrows USDC in one call |
| `request_credit` | Browse available lend offers before committing |
| `check_loan_health` | Check LTV, health status, distance to liquidation |
| `check_credit_status` | View accrued interest and time to expiry |
| `add_collateral` | Add more collateral to lower LTV |
| `repay_credit` | Repay an outstanding loan |
| `repay_and_reborrow` | Roll over a loan into a new one atomically |
| `get_my_loans` | List all active loans for the agent wallet |
| `get_markets` | List available lending markets and their terms |

You can also use these directly in your own agents:

```python
from backends.floe_client import FloeClient

client = FloeClient()

# Borrow $100 USDC against 0.05 ETH at max 8% APR for 14 days
result = client.instant_borrow(
    borrow_amount_usdc=100.0,
    collateral_eth=0.05,
    max_rate_bps=800,
    duration_days=14,
)

# Or get them as LangChain tools and pass to any LangChain agent
tools = client.as_langchain_tools()
```

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

| Agent | Role |
|---|---|
| **Explorer** | Patterns, correlations, key features |
| **Skeptic** | Data quality — outliers, leakage, bias |
| **Statistician** | Distributions, hypothesis tests |
| **Ethicist** | Bias, fairness, responsible AI |
| **Feature Engineer** | New features, transformations, encodings |
| **Pragmatist** | Model selection, eval strategy |
| **Devil's Advocate** | Challenges the plan, proposes alternatives |
| **Optimizer** | Hyperparameter tuning, CV, ensembles |
| **Architect** | Research-backed architecture design |
| **Storyteller** | Final report synthesis |

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
├── server.py              ← FastAPI backend (start here for web UI)
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
├── backends/              # Claude / OpenAI / vLLM / Floe routing
│   └── floe_client.py     # Floe x402 credit layer integration
├── orchestration/         # Pipeline coordination + routing
├── phases/                # Phase 1 (EDA) + Phase 2 (Model Design)
├── red_mode/              # Persona debate tournament
├── personas/              # 20 researcher persona definitions
├── memory/                # Context management and compaction
├── analysis/              # Pre-LLM data profiling
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

**Floe: `No FLOE_PRIVATE_KEY found`**
Make sure `.env` has `FLOE_PRIVATE_KEY=0x...` set. The key is the private key of the wallet that holds your WETH collateral on Base.

**Floe: `No matching liquidity found`**
Your `max_rate_bps` may be too low or no lenders are available for that market. Try increasing `max_rate_bps` or check the market via `FloeClient().get_markets()`.

---

## Security Notes

- The backend binds to `127.0.0.1` only — not exposed on your network
- CORS is restricted to `localhost:3000`
- API keys are saved locally at `~/.ds_agent_team.json` with `chmod 600`
- No LLM-generated code is executed — safe for local use
- Pickle deserialization is disabled
- `FLOE_PRIVATE_KEY` is read only from `.env` which is gitignored — never commit it

> Never commit your `.env` file — it's gitignored.

---

## Development Status

**Done:** Phase 1 (EDA), Phase 2 (Model Design), Red Mode tournament, memory system, multi-provider support, web UI with live D3 graph, Floe x402 credit layer

**In progress:** Phase 3 (Code Generation), Phase 4 (Validation), execution layer

---

## License

Hackathon project. See LICENSE if present.
