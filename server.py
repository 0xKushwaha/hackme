"""
FastAPI backend — Multi-Agent DS Team
======================================
Endpoints:
  GET  /api/creds              — load saved credentials
  POST /api/creds              — save credentials
  GET  /api/browse?dir=false   — open native file/folder picker
  POST /api/run                — start pipeline, returns { runId }
  GET  /api/poll/{run_id}?cursor=N — poll for new log lines + state
  GET  /api/result/{run_id}    — get final result / report

Run:
  python server.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

import platform

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="DS Agent Team API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────
# Credentials persistence
# ─────────────────────────────────────────────────────────────────────
CREDS_FILE = Path.home() / ".ds_agent_team.json"

def _load_creds() -> dict:
    try:
        if CREDS_FILE.exists():
            return json.loads(CREDS_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_creds(data: dict):
    try:
        existing = _load_creds()
        existing.update(data)
        CREDS_FILE.write_text(json.dumps(existing, indent=2))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# File / folder picker (macOS only — subprocess avoids main-thread crash)
# ─────────────────────────────────────────────────────────────────────
def _has_display() -> bool:
    """True when a GUI display is available (always on macOS, env-dependent on Linux)."""
    if platform.system() == "Darwin":
        return True
    if platform.system() == "Linux":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return False   # Windows: not implemented


def _pick_path_sync(pick_dir: bool = False) -> str:
    if not _has_display():
        return ""
    script = f"""
import tkinter as tk
from tkinter import filedialog
root = tk.Tk(); root.withdraw(); root.wm_attributes("-topmost", True)
if {pick_dir}:
    p = filedialog.askdirectory(title="Select dataset folder")
else:
    p = filedialog.askopenfilename(
        title="Select dataset file",
        filetypes=[("Supported","*.csv *.tsv *.parquet *.feather *.json *.jsonl *.xlsx *.xls *.h5 *.zip *.tar *.gz"),("All","*.*")])
root.destroy(); print(p or "", end="")
"""
    try:
        r = subprocess.run([sys.executable, "-c", script],
                           capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────
# Log → agent state parser
# ─────────────────────────────────────────────────────────────────────
_AGENT_KEYS = {
    "explorer":         "Explorer",
    "skeptic":          "Skeptic",
    "statistician":     "Statistician",
    "feature_engineer": "Feat.Eng",
    "feature engineer": "Feat.Eng",
    "ethicist":         "Ethicist",
    "pragmatist":       "Pragmatist",
    "devil_advocate":   "Devil's Adv",
    "devil's advocate": "Devil's Adv",
    "optimizer":        "Optimizer",
    "architect":        "Architect",
    "storyteller":      "Storyteller",
}

def _parse_log_line(line: str) -> dict:
    low = line.lower()
    phase = ""
    if   "phase 1" in low or "data understanding" in low: phase = "Phase 1 · Data Understanding"
    elif "phase 2" in low or "model design"       in low: phase = "Phase 2 · Model Design"
    elif "phase 3" in low or "code generation"    in low: phase = "Phase 3 · Code Generation"
    elif "phase 4" in low or "validation"         in low: phase = "Phase 4 · Validation"
    elif "phase 5" in low or "inference"          in low: phase = "Phase 5 · Inference"

    # Also detect phase from graph log lines like "⚡ [DataUnderstanding]"
    if not phase:
        if "dataunderstanding" in low or "[dataunders" in low: phase = "Phase 1 · Data Understanding"
        elif "modeldesign"     in low or "[modeldesig" in low: phase = "Phase 2 · Model Design"

    # Detect scanning/startup phase from common log prefixes
    if not phase:
        if "scanning dataset" in low or "files :" in low or "builderagent" in low:
            phase = "Phase 1 · Data Understanding"

    agent = ""
    for key, name in _AGENT_KEYS.items():
        if key in low:
            agent = name
            break

    return {"phase": phase, "agent": agent}


# ─────────────────────────────────────────────────────────────────────
# In-memory run store  (log lines list, not queue — supports random access)
# ─────────────────────────────────────────────────────────────────────
class RunState:
    def __init__(self):
        self.lines:       list[str] = []   # all log lines so far
        self.phase:       str       = "Initializing…"
        self.agent:       str       = ""
        self.ever_active: list[str] = []
        self.result:      Optional[dict] = None
        self.error:       Optional[str]  = None
        self.done:        bool           = False
        self._lock = threading.Lock()

    def add_text(self, text: str):
        new_lines = [l for l in text.splitlines() if l.strip()]
        with self._lock:
            self.lines.extend(new_lines)
            for line in new_lines:
                parsed = _parse_log_line(line)
                if parsed["phase"]:
                    self.phase = parsed["phase"]
                if parsed["agent"]:
                    self.agent = parsed["agent"]
                    if parsed["agent"] not in self.ever_active:
                        self.ever_active.append(parsed["agent"])

    def snapshot(self, cursor: int) -> dict:
        with self._lock:
            new_lines = self.lines[cursor:]
            return {
                "lines":      new_lines,
                "cursor":     cursor + len(new_lines),
                "phase":      self.phase,
                "agent":      self.agent,
                "everActive": list(self.ever_active),
                "done":       self.done,
                "error":      self.error,
            }

runs: dict[str, RunState] = {}


# ─────────────────────────────────────────────────────────────────────
# Stdout tee  (writes to RunState directly)
# ─────────────────────────────────────────────────────────────────────
class _Tee:
    def __init__(self, state: RunState, orig):
        self.state = state
        self.orig  = orig

    def write(self, text: str):
        if text:
            self.state.add_text(text)
        try:
            self.orig.write(text)
            self.orig.flush()
        except Exception:
            pass

    def flush(self):
        try: self.orig.flush()
        except Exception: pass

    def fileno(self): return self.orig.fileno()
    def isatty(self): return False


# ─────────────────────────────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────────────────────────────
def _run_pipeline(cfg: dict) -> dict:
    from backends.llm_backends    import get_llm, get_fast_llm
    from agents import (ExplorerAgent, SkepticAgent, StatisticianAgent, EthicistAgent,
                        PragmatistAgent, DevilAdvocateAgent, ArchitectAgent, OptimizerAgent,
                        StorytellerAgent)
    from agents.agent_config        import AGENT_CONFIGS
    from agents.base                import BaseAgent
    from memory.agent_memory        import MemorySystem
    from orchestration.orchestrator import Orchestrator
    from orchestration.registry     import AgentRegistry
    from phases.discovery           import DatasetDiscovery
    from prompts.planner_prompts    import FEATURE_ENGINEER_PROMPT

    exp_dir = cfg.get("experiment_dir", "experiments")
    os.makedirs(exp_dir, exist_ok=True)

    if cfg["provider"] == "claude" and cfg.get("api_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
    if cfg["provider"] == "openai" and cfg.get("api_key"):
        os.environ["OPENAI_API_KEY"] = cfg["api_key"]

    print(f"\n📂 Scanning dataset: {cfg['dataset_path']}")
    disc    = DatasetDiscovery()
    profile = disc.scan(cfg["dataset_path"])
    print(f"   Files : {len(profile.files)}  |  Types : {', '.join(profile.types_present)}")
    ds_sum  = disc.format_profile(profile)

    llm_kw = {}
    if cfg.get("server_url"): llm_kw["base_url"] = cfg["server_url"]
    explicit_model = cfg.get("model")
    llm      = get_llm(cfg["provider"], model=explicit_model, **llm_kw)
    # Fast tier: cheaper/faster model for critique agents — skip if user picked a specific model
    fast_llm = get_fast_llm(cfg["provider"], **llm_kw) if not explicit_model else llm
    f = fast_llm

    agents = {
        "explorer":         ExplorerAgent(llm,      config=AGENT_CONFIGS["explorer"]),
        "skeptic":          SkepticAgent(f,          config=AGENT_CONFIGS["skeptic"]),
        "statistician":     StatisticianAgent(llm,   config=AGENT_CONFIGS["statistician"]),
        "feature_engineer": BaseAgent("Feature Engineer", FEATURE_ENGINEER_PROMPT, llm, config=AGENT_CONFIGS["feature_engineer"]),
        "ethicist":         EthicistAgent(f,         config=AGENT_CONFIGS["ethicist"]),
        "pragmatist":       PragmatistAgent(f,       config=AGENT_CONFIGS["pragmatist"]),
        "devil_advocate":   DevilAdvocateAgent(f,    config=AGENT_CONFIGS["devil_advocate"]),
        "optimizer":        OptimizerAgent(llm,      config=AGENT_CONFIGS["optimizer"]),
        "architect":        ArchitectAgent(llm,      config=AGENT_CONFIGS["architect"]),
        "storyteller":      StorytellerAgent(llm,    config=AGENT_CONFIGS["storyteller"]),
    }

    mem = (MemorySystem(agent_names=list(agents.keys()),
                        persist_dir=os.path.join(exp_dir, "chroma_db"),
                        graph_db=os.path.join(exp_dir, "graph.db"))
           if cfg.get("enable_memory", True) else None)

    mode     = cfg.get("mode", "phases")
    registry = AgentRegistry(max_concurrent=cfg.get("max_agents", 5),
                              persist_path=os.path.join(exp_dir, "registry.json"))

    orch = Orchestrator(agents=agents, llm=llm, memory_system=mem,
                        registry=registry,
                        task_description=cfg.get("task_description", ""))

    absp = os.path.abspath(cfg["dataset_path"])
    tgt  = cfg.get("target_col") or None
    ret  = int(cfg.get("max_retries", 4))

    if   mode == "manual": orch.run_manual(ds_sum)
    elif mode == "auto":   orch.run_auto(ds_sum)
    elif mode == "phases": orch.run_phases(dataset_summary=ds_sum, dataset_path=absp, target_col=tgt, experiment_dir=exp_dir, dataset_profile=profile)

    lp = os.path.join(exp_dir, f"context_{orch.run_id}.json")
    orch.context.save(lp)

    entries = [
        {"role": e.role, "agent": e.agent, "content": e.content,
         "metadata": e.metadata if isinstance(e.metadata, dict) else {}}
        for e in orch.context.entries
    ]
    return {"run_id": orch.run_id, "log_path": lp, "exp_dir": exp_dir, "entries": entries}


def _thread_runner(run_id: str, cfg: dict):
    state = runs[run_id]
    old   = sys.stdout
    sys.stdout = _Tee(state, old)
    try:
        state.result = _run_pipeline(cfg)
    except Exception:
        state.error = traceback.format_exc()
        state.add_text(f"\n❌ ERROR:\n{state.error}")
    finally:
        sys.stdout = old
        state.done = True


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/creds")
def get_creds():
    c   = _load_creds()
    key = c.get("api_key", "")
    return {
        "provider":  c.get("provider", "claude"),
        "hasKey":    bool(key),
        "serverUrl": c.get("server_url", ""),
        "model":     c.get("model", ""),
    }


class CredsPayload(BaseModel):
    provider:   str
    api_key:    str = ""
    server_url: str = ""
    model:      str = ""

@app.post("/api/creds")
def save_creds(body: CredsPayload):
    _save_creds({"provider": body.provider, "api_key": body.api_key,
                 "server_url": body.server_url, "model": body.model})
    return {"ok": True}


@app.get("/api/resolve")
def resolve_path(name: str, dir: bool = False):
    """
    Browser file pickers don't expose the absolute path.
    This endpoint searches for the file/folder by name in common locations
    and returns the first match so the pipeline can use it directly.
    Search order: cwd, home, Desktop, Downloads.
    """
    import fnmatch
    # For folder picks, name is like "myfolder/file.csv" — we want the root folder
    root_name = Path(name).parts[0] if Path(name).parts else name

    search_roots = [
        Path.cwd(),
        Path.home(),
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path.home() / "Documents",
    ]

    target = root_name if dir else name
    for base in search_roots:
        candidate = base / target
        if candidate.exists():
            return {"path": str(candidate), "name": candidate.name}

    # Broader search one level deep under home
    for child in Path.home().iterdir():
        if child.is_dir():
            candidate = child / target
            if candidate.exists():
                return {"path": str(candidate), "name": candidate.name}

    return {"path": "", "name": ""}


@app.get("/api/browse")
async def browse(dir: bool = False):
    if not _has_display():
        return {"path": "", "canBrowse": False}
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: _pick_path_sync(dir))
    return {"path": result, "canBrowse": True}



class RunPayload(BaseModel):
    provider:         str
    api_key:          str  = ""
    server_url:       str  = ""
    dataset_path:     str
    task_description: str  = ""
    mode:             str  = "phases"
    target_col:       str  = ""
    model:            str  = ""
    max_agents:       int  = 5
    enable_memory:    bool = True
    experiment_dir:   str  = "experiments"

@app.post("/api/run")
def start_run(body: RunPayload):
    run_id = str(uuid.uuid4())[:8]
    runs[run_id] = RunState()

    cfg = body.model_dump()
    cfg["provider"]   = "local" if cfg["provider"] == "local (vLLM)" else cfg["provider"]
    cfg["target_col"] = cfg["target_col"] or None
    cfg["model"]      = cfg["model"]      or None

    t = threading.Thread(target=_thread_runner, args=(run_id, cfg), daemon=True)
    t.start()
    return {"runId": run_id}


@app.get("/api/poll/{run_id}")
def poll(run_id: str, cursor: int = 0):
    """
    Returns new log lines since `cursor`, current phase/agent, and done status.
    Frontend calls this every 1–2 seconds.
    """
    state = runs.get(run_id)
    if not state:
        return {"error": "Unknown run ID", "done": True}
    return state.snapshot(cursor)


@app.get("/api/result/{run_id}")
def get_result(run_id: str):
    state = runs.get(run_id)
    if not state:
        return {"error": "Unknown run ID"}
    if not state.done:
        return {"error": "Still running"}
    if state.error:
        return {"error": state.error}
    return state.result


# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import logging

    class _FilterPoll(logging.Filter):
        def filter(self, record):
            return "/api/poll/" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(_FilterPoll())
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
