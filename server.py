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
  DELETE /api/run/{run_id}     — cancel a running pipeline
  DELETE /api/red-mode/{run_id} — cancel a running Red Mode debate

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
import time
import traceback
import uuid
from collections import OrderedDict
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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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
        os.chmod(CREDS_FILE, 0o600)
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
    "explorer":              "Explorer",
    "skeptic":               "Skeptic",
    "statistician":          "Statistician",
    "feature_engineer":      "Feat.Eng",
    "feature engineer":      "Feat.Eng",
    "ethicist":              "Ethicist",
    "constraint_discovery":  "Constraint_Discovery",
    "constraint discovery":  "Constraint_Discovery",
    "pragmatist":            "Pragmatist",
    "devil_advocate":        "Devil's Adv",
    "devil's advocate":      "Devil's Adv",
    "optimizer":             "Optimizer",
    "architect":             "Architect",
}

import re as _re
_AGENT_START_RE = _re.compile(r'\[AGENT:([a-z_]+)\]')
_AGENT_DONE_RE  = _re.compile(r'\[AGENT_DONE:([a-z_]+)\]')

def _parse_log_line(line: str) -> dict:
    m = _AGENT_START_RE.search(line)
    if m:
        return {"agent": m.group(1), "agent_done": None}

    m = _AGENT_DONE_RE.search(line)
    if m:
        return {"agent": None, "agent_done": m.group(1)}

    low = line.lower()
    agent = ""
    for key, name in _AGENT_KEYS.items():
        if key in low:
            agent = name.lower().replace("'", "").replace(" ", "_").replace(".", "")
            break

    return {"agent": agent or None, "agent_done": None}


# ─────────────────────────────────────────────────────────────────────
# FIX #1: Thread-local log routing
#
# Previously each worker thread redirected the global sys.stdout to a
# _Tee, causing nested tees when two runs overlapped — both runs' logs
# mixed together. Now a single _RoutingTee is installed once at startup.
# Worker threads bind their RunState via _thread_local, so print() from
# each thread goes to the right log. No nesting, no cross-contamination.
# ─────────────────────────────────────────────────────────────────────
from runtime.thread_state import _thread_local


class _RoutingTee:
    """
    Permanent sys.stdout replacement installed once at startup.
    Routes print() to the current thread's RunState via _thread_local.
    Threads with no bound state pass output straight to original stdout.
    """
    def __init__(self, orig):
        self._orig = orig

    def write(self, text: str):
        state = getattr(_thread_local, "run_state", None)
        if state and text:
            state.add_text(text)
        try:
            self._orig.write(text)
            self._orig.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._orig.flush()
        except Exception:
            pass

    def fileno(self): return self._orig.fileno()
    def isatty(self): return False


# Install once — all threads share this, routed by thread-local state
sys.stdout = _RoutingTee(sys.__stdout__)


# ─────────────────────────────────────────────────────────────────────
# In-memory run store
# ─────────────────────────────────────────────────────────────────────
class RunState:
    def __init__(self):
        self.lines:        list[str]       = []
        self.agent:        str             = ""
        self.ever_active:  list[str]       = []
        self.done_agents:  list[str]       = []
        self.result:       Optional[dict]  = None
        self.error:        Optional[str]   = None
        self.done:         bool            = False
        # FIX #7: cancellation support
        self.cancel_event  = threading.Event()
        self.cancelled:    bool            = False
        self._lock         = threading.Lock()

    def add_text(self, text: str):
        new_lines = [l for l in text.splitlines() if l.strip()]
        with self._lock:
            self.lines.extend(new_lines)
            for line in new_lines:
                parsed = _parse_log_line(line)
                if parsed["agent"]:
                    self.agent = parsed["agent"]
                    if parsed["agent"] not in self.ever_active:
                        self.ever_active.append(parsed["agent"])
                if parsed["agent_done"]:
                    a = parsed["agent_done"]
                    if a not in self.done_agents:
                        self.done_agents.append(a)

    def snapshot(self, cursor: int) -> dict:
        with self._lock:
            new_lines = self.lines[cursor:]
            return {
                "lines":       new_lines,
                "cursor":      cursor + len(new_lines),
                "agent":       self.agent,
                "everActive":  list(self.ever_active),
                "doneAgents":  list(self.done_agents),
                "done":        self.done,
                "error":       self.error,
                "cancelled":   self.cancelled,
            }


# ─────────────────────────────────────────────────────────────────────
# Red Mode run state
# ─────────────────────────────────────────────────────────────────────
_RED_STAGE_RE      = _re.compile(r'\[RED_STAGE:([a-z_]+)\]')
_RED_GROUP_RE      = _re.compile(r'\[RED_GROUP:([a-z_]+)\]')
_RED_GROUP_DONE_RE = _re.compile(r'\[RED_GROUP_DONE:([a-z_]+)\]')
_RED_CHAMPION_RE   = _re.compile(r'\[RED_CHAMPION:([a-z_]+)\]')
_PERSONA_RE        = _re.compile(r'\[PERSONA:([a-z_]+)\]')
_PERSONA_DONE_RE   = _re.compile(r'\[PERSONA_DONE:([a-z_]+)\]')


class RedRunState(RunState):
    def __init__(self):
        super().__init__()
        # "phase1" | "groups" | "election" | "champions" | "synthesis"
        self.phase:           str            = "phase1"
        self.phase1_agents:   list[str]      = []
        self.stage:           str            = ""
        self.active_group:    str            = ""
        self.done_groups:     list[str]      = []
        self.group_champions: dict[str, str] = {}
        self.active_personas: list[str]      = []
        self.synthesis_done:  bool           = False
        # champion_debate_times: { persona: { start: float, end: float|None, duration: float|None } }
        self.champion_debate_times: dict[str, dict] = {}

    def add_text(self, text: str):
        new_lines = [l for l in text.splitlines() if l.strip()]
        with self._lock:
            self.lines.extend(new_lines)
            for line in new_lines:

                if "[RED_PHASE1_DONE]" in line:
                    self.phase = "groups"

                if self.phase == "phase1":
                    m = _AGENT_START_RE.search(line)
                    if m:
                        self.agent = m.group(1)
                    m = _AGENT_DONE_RE.search(line)
                    if m:
                        name = m.group(1)
                        if name not in self.phase1_agents:
                            self.phase1_agents.append(name)

                else:
                    m = _RED_STAGE_RE.search(line)
                    if m:
                        self.stage = m.group(1)
                        self.phase = m.group(1)
                        self.active_personas = []  # clear on stage transition

                    m = _RED_GROUP_RE.search(line)
                    if m:
                        self.active_group = m.group(1)

                    m = _RED_GROUP_DONE_RE.search(line)
                    if m:
                        gk = m.group(1)
                        if gk not in self.done_groups:
                            self.done_groups.append(gk)

                    m = _RED_CHAMPION_RE.search(line)
                    if m:
                        champion = m.group(1)
                        if self.active_group:
                            self.group_champions[self.active_group] = champion

                    m = _PERSONA_RE.search(line)
                    if m:
                        name = m.group(1)
                        self.agent = name
                        if name not in self.ever_active:
                            self.ever_active.append(name)
                        if name not in self.active_personas:
                            self.active_personas.append(name)
                        # Track champion debate start time
                        if self.phase == "champions" and name not in self.champion_debate_times:
                            self.champion_debate_times[name] = {
                                "start": time.time(),
                                "end": None,
                                "duration": None,
                            }

                    m = _PERSONA_DONE_RE.search(line)
                    if m:
                        name = m.group(1)
                        if name not in self.done_agents:
                            self.done_agents.append(name)
                        # Track champion debate end time
                        if self.phase == "champions" and name in self.champion_debate_times:
                            entry = self.champion_debate_times[name]
                            if entry["end"] is None:
                                entry["end"] = time.time()
                                entry["duration"] = round(entry["end"] - entry["start"], 1)

                    if "[RED_SYNTHESIS_DONE]" in line:
                        self.synthesis_done = True

    def snapshot(self, cursor: int) -> dict:
        snap = super().snapshot(cursor)
        snap["phase"]           = self.phase
        snap["phase1Agents"]    = list(self.phase1_agents)
        snap["stage"]           = self.stage
        snap["activeGroup"]     = self.active_group
        snap["doneGroups"]      = list(self.done_groups)
        snap["groupChampions"]  = dict(self.group_champions)
        snap["activePersonas"]       = list(self.active_personas)
        snap["synthesisDone"]        = self.synthesis_done
        snap["donePersonas"]         = list(self.done_agents)
        snap["championDebateTimes"]  = dict(self.champion_debate_times)
        return snap


# ─────────────────────────────────────────────────────────────────────
# FIX #3: Bounded run stores — evict oldest completed runs at MAX_RUNS
# ─────────────────────────────────────────────────────────────────────
MAX_RUNS = 50


class _RunStore:
    """
    Thread-safe bounded dict for RunState objects.
    When over MAX_RUNS, evicts oldest completed (done=True) entries first,
    then oldest entries regardless of status. Results are on disk so
    evicting from memory loses nothing.
    """
    def __init__(self, maxsize: int = MAX_RUNS):
        self._store: OrderedDict[str, RunState] = OrderedDict()
        self._lock  = threading.Lock()
        self._max   = maxsize

    def __setitem__(self, key: str, value: RunState):
        with self._lock:
            self._store[key] = value
            if len(self._store) > self._max:
                self._evict()

    def __getitem__(self, key: str) -> RunState:
        with self._lock:
            return self._store[key]

    def get(self, key: str, default=None):
        with self._lock:
            return self._store.get(key, default)

    def _evict(self):
        # Prefer evicting done entries
        done_keys = [k for k, v in self._store.items() if v.done]
        for k in done_keys:
            if len(self._store) <= self._max:
                break
            del self._store[k]
        # If still over limit, evict oldest regardless
        while len(self._store) > self._max:
            self._store.popitem(last=False)


runs:     _RunStore = _RunStore()
red_runs: _RunStore = _RunStore()


# ─────────────────────────────────────────────────────────────────────
# Result persistence
# ─────────────────────────────────────────────────────────────────────
RESULTS_DIR = Path("experiments") / "results"

def _persist_result(run_id: str, result: dict):
    """Save completed run result to disk so it survives server restarts."""
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / f"{run_id}.json").write_text(json.dumps(result, default=str))
    except Exception:
        pass

def _load_result(run_id: str) -> Optional[dict]:
    """Load a persisted run result from disk."""
    try:
        p = RESULTS_DIR / f"{run_id}.json"
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────
# Pipeline runner
# FIX #2: API keys are passed directly to get_llm() — never written to
# os.environ — eliminating the race condition where concurrent runs with
# different keys would overwrite each other's environment variable.
# FIX #6: llm/fast_llm are returned so Red Mode can reuse them instead
# of constructing a second set of LLM instances.
# ─────────────────────────────────────────────────────────────────────
def _run_pipeline(cfg: dict) -> dict:
    from backends.llm_backends    import get_llm, get_fast_llm
    from agents import (ExplorerAgent, SkepticAgent, StatisticianAgent, EthicistAgent,
                        PragmatistAgent, DevilAdvocateAgent, ArchitectAgent, OptimizerAgent)
    from agents.agent_config        import AGENT_CONFIGS
    from agents.base                import BaseAgent
    from memory.agent_memory        import MemorySystem
    from orchestration.orchestrator import Orchestrator
    from orchestration.registry     import AgentRegistry
    from phases.discovery           import DatasetDiscovery
    from prompts.planner_prompts    import FEATURE_ENGINEER_PROMPT

    exp_dir = cfg.get("experiment_dir", "experiments")
    os.makedirs(exp_dir, exist_ok=True)

    # FIX #2: pass api_key directly — do NOT write to os.environ
    api_key        = cfg.get("api_key") or None
    explicit_model = cfg.get("model") or None
    llm_kw         = {}
    if cfg.get("server_url"):
        llm_kw["base_url"] = cfg["server_url"]

    print(f"\n📂 Scanning dataset: {cfg['dataset_path']}")
    disc    = DatasetDiscovery()
    profile = disc.scan(cfg["dataset_path"])
    print(f"   Files : {len(profile.files)}  |  Types : {', '.join(profile.types_present)}")
    ds_sum  = disc.format_profile(profile)

    llm      = get_llm(cfg["provider"], model=explicit_model, api_key=api_key, **llm_kw)
    fast_llm = get_fast_llm(cfg["provider"], api_key=api_key, **llm_kw) if not explicit_model else llm
    f = fast_llm

    agents = {
        "explorer":         ExplorerAgent(llm,  config=AGENT_CONFIGS["explorer"]),
        "skeptic":          SkepticAgent(f,      config=AGENT_CONFIGS["skeptic"]),
        "statistician":     StatisticianAgent(llm, config=AGENT_CONFIGS["statistician"]),
        "feature_engineer": BaseAgent("Feature Engineer", FEATURE_ENGINEER_PROMPT, llm, config=AGENT_CONFIGS["feature_engineer"]),
        "ethicist":         EthicistAgent(f,     config=AGENT_CONFIGS["ethicist"]),
        "pragmatist":       PragmatistAgent(f,   config=AGENT_CONFIGS["pragmatist"]),
        "devil_advocate":   DevilAdvocateAgent(f, config=AGENT_CONFIGS["devil_advocate"]),
        "optimizer":        OptimizerAgent(llm,  config=AGENT_CONFIGS["optimizer"]),
        "architect":        ArchitectAgent(llm,  config=AGENT_CONFIGS["architect"]),
    }

    mem = (MemorySystem(agent_names=list(agents.keys()),
                        persist_dir=os.path.join(exp_dir, "chroma_db"),
                        graph_db=os.path.join(exp_dir, "graph.db"))
           if cfg.get("enable_memory", True) else None)

    mode     = cfg.get("mode", "phases")
    registry = AgentRegistry(max_concurrent=cfg.get("max_agents", 5),
                              persist_path=os.path.join(exp_dir, "registry.json"))

    # FIX #7: wire the cancel_event into the orchestrator
    orch = Orchestrator(agents=agents, llm=llm, memory_system=mem,
                        registry=registry,
                        task_description=cfg.get("task_description", ""),
                        cancel_event=cfg.get("_cancel_event"))

    absp = os.path.abspath(cfg["dataset_path"])
    tgt  = cfg.get("target_col") or None

    if   mode == "manual": orch.run_manual(ds_sum)
    elif mode == "auto":   orch.run_auto(ds_sum)
    elif mode == "phases": orch.run_phases(dataset_summary=ds_sum, dataset_path=absp,
                                           target_col=tgt, experiment_dir=exp_dir,
                                           dataset_profile=profile)

    lp = os.path.join(exp_dir, f"context_{orch.run_id}.json")
    orch.context.save(lp)

    entries = [
        {"role": e.role, "agent": e.agent, "content": e.content,
         "metadata": e.metadata if isinstance(e.metadata, dict) else {}}
        for e in orch.context.entries
    ]
    return {
        "run_id":       orch.run_id,
        "log_path":     lp,
        "exp_dir":      exp_dir,
        "entries":      entries,
        "agent_results": orch.agent_results,
        # FIX #6: return LLM instances so Red Mode can reuse them
        "_llm":         llm,
        "_fast_llm":    fast_llm,
    }


# ─────────────────────────────────────────────────────────────────────
# FIX #1: Thread runners use thread-local binding instead of redirecting
# sys.stdout — no more global state mutation, no nested tees.
# ─────────────────────────────────────────────────────────────────────
def _thread_runner(run_id: str, cfg: dict):
    state = runs[run_id]
    cfg["_cancel_event"] = state.cancel_event   # FIX #7
    _thread_local.run_state = state             # FIX #1: bind this thread
    try:
        state.result = _run_pipeline(cfg)
        # Strip internal LLM objects before persisting
        state.result.pop("_llm", None)
        state.result.pop("_fast_llm", None)
        _persist_result(run_id, state.result)
    except Exception as exc:
        if state.cancelled:
            state.error = "Cancelled by user"
        else:
            _internal = traceback.format_exc()
            print(f"[PIPELINE_ERROR] run={run_id}\n{_internal}", flush=True)
            state.error = f"Pipeline failed: {type(exc).__name__}"
            state.add_text(f"\n❌ Pipeline error — check server logs.")
    finally:
        _thread_local.run_state = None          # FIX #1: unbind
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
    Searches common locations and returns the first match.
    """
    # Reject path traversal attempts
    if ".." in name or name.startswith("/") or name.startswith("~"):
        return {"path": "", "name": ""}
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

    def validate_fields(self):
        if len(self.task_description) > 5000:
            raise ValueError("task_description too long (max 5000 chars)")
        if len(self.api_key) > 500:
            raise ValueError("api_key too long")
        if len(self.model) > 200:
            raise ValueError("model name too long")

@app.post("/api/run")
def start_run(body: RunPayload):
    from fastapi import HTTPException
    # Validate input fields
    try:
        body.validate_fields()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Validate dataset_path to prevent path traversal
    dp = body.dataset_path
    if dp and (".." in dp or dp.startswith("~")):
        raise HTTPException(status_code=400, detail="Invalid dataset path")

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
    """Returns new log lines since cursor, current agent, and done status."""
    state = runs.get(run_id)
    if not state:
        return {"error": "Unknown run ID", "done": True}
    return state.snapshot(cursor)


@app.get("/api/result/{run_id}")
def get_result(run_id: str):
    state = runs.get(run_id)
    if state:
        if not state.done:
            return {"error": "Still running"}
        if state.error:
            return {"error": state.error}
        return state.result
    saved = _load_result(run_id)
    if saved:
        return saved
    return {"error": "Unknown run ID"}


# FIX #7: Cancel endpoint for normal runs
@app.delete("/api/run/{run_id}")
def cancel_run(run_id: str):
    state = runs.get(run_id)
    if not state:
        return {"error": "Unknown run ID"}
    if state.done:
        return {"error": "Run already finished"}
    state.cancelled = True
    state.cancel_event.set()
    return {"ok": True, "runId": run_id}


# ─────────────────────────────────────────────────────────────────────
# Red Mode — Persona Debate Engine
# ─────────────────────────────────────────────────────────────────────

def _run_red_mode(cfg: dict) -> dict:
    """
    Red Mode pipeline:
      Stage 1: All Phase 1+2 agents analyse the dataset.
      Stage 2: Expert personas debate the analysis and synthesise a verdict.
    """
    from red_mode.orchestrator  import RedModeOrchestrator
    from red_mode.brief_builder import build_brief_from_result

    # ── Stage 1: agents analyse the dataset ──────────────────────────
    print("\n[RED_PHASE1_START]")
    print("🔬 Phase 1 — Agents gathering analysis...\n")
    sys.stdout.flush()

    pipeline_cfg = {
        **cfg,
        "mode":           "phases",
        "max_agents":     9,
        "enable_memory":  False,
        "experiment_dir": "experiments",
        "target_col":     cfg.get("target_col") or None,
        "model":          cfg.get("model") or None,
    }
    phase1_result = _run_pipeline(pipeline_cfg)

    # FIX #6: reuse LLM instances built during Phase 1 — no second init
    llm      = phase1_result.pop("_llm")
    fast_llm = phase1_result.pop("_fast_llm")

    print(f"\n[RED_PHASE1_DONE]")
    print("✓ Phase 1 complete — handing off to persona debate\n")
    sys.stdout.flush()

    # ── Stage 2: Build brief + run persona debate ─────────────────────
    brief = build_brief_from_result(phase1_result, cfg.get("task_description", ""))
    print(f"   Brief: {len(brief)} chars  |  Personas: {len(cfg['persona_names'])}\n")
    sys.stdout.flush()

    orch   = RedModeOrchestrator(llm=llm, fast_llm=fast_llm)
    debate = orch.run(persona_names=cfg["persona_names"], brief=brief)

    return {
        "phase1":          phase1_result,
        "personas":        debate["personas"],
        "groups":          debate["groups"],
        "champions":       debate["champions"],
        "champion_debate": debate["champion_debate"],
        "synthesis":       debate["synthesis"],
    }


def _thread_runner_red(run_id: str, cfg: dict):
    state = red_runs[run_id]
    cfg["_cancel_event"]    = state.cancel_event    # FIX #7
    _thread_local.run_state = state                 # FIX #1
    try:
        state.result = _run_red_mode(cfg)
        state.done   = True
        _persist_result(run_id, state.result)
    except Exception:
        if state.cancelled:
            state.error = "Cancelled by user"
        else:
            _internal = traceback.format_exc()
            print(f"[RED_MODE_ERROR] run={run_id}\n{_internal}", flush=True)
            state.error = "Red Mode pipeline failed — check server logs."
        state.done = True
    finally:
        _thread_local.run_state = None              # FIX #1


# ── Red Mode payload ──────────────────────────────────────────────────

class RedModePayload(BaseModel):
    provider:         str
    api_key:          str       = ""
    server_url:       str       = ""
    model:            str       = ""
    persona_names:    list[str]
    dataset_path:     str       = ""
    task_description: str       = ""
    target_col:       str       = ""    # FIX #4: was missing, Phase 1 was always blind

    def validate_fields(self):
        if len(self.task_description) > 5000:
            raise ValueError("task_description too long (max 5000 chars)")
        if len(self.persona_names) > 50:
            raise ValueError("too many personas (max 50)")
        for name in self.persona_names:
            if not name.replace("_", "").replace("-", "").replace(" ", "").isalnum():
                raise ValueError(f"Invalid persona name: {name}")
        if len(self.api_key) > 500:
            raise ValueError("api_key too long")


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/personas")
def get_personas():
    """Return the full personas index for the frontend selector."""
    idx_path = Path(__file__).parent / "personas" / "personas_index.json"
    with open(idx_path) as f:
        return json.load(f)


@app.post("/api/red-mode")
def start_red_mode(body: RedModePayload):
    from fastapi import HTTPException
    try:
        body.validate_fields()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run_id = "rm_" + str(uuid.uuid4())[:8]
    red_runs[run_id] = RedRunState()

    cfg = body.model_dump()
    cfg["provider"]   = "local" if cfg["provider"] == "local (vLLM)" else cfg["provider"]
    cfg["model"]      = cfg["model"]      or None
    cfg["target_col"] = cfg["target_col"] or None   # FIX #4

    t = threading.Thread(target=_thread_runner_red, args=(run_id, cfg), daemon=True)
    t.start()
    return {"runId": run_id}


@app.get("/api/red-mode/poll/{run_id}")
def poll_red_mode(run_id: str, cursor: int = 0):
    state = red_runs.get(run_id)
    if not state:
        return {"error": "Unknown red mode run ID", "done": True}
    return state.snapshot(cursor)


@app.get("/api/red-mode/result/{run_id}")
def get_red_mode_result(run_id: str):
    state = red_runs.get(run_id)
    if state:
        if not state.done:
            return {"error": "Still running"}
        if state.error:
            return {"error": state.error}
        return state.result
    saved = _load_result(run_id)
    if saved:
        return saved
    return {"error": "Unknown run ID"}


# FIX #7: Cancel endpoint for Red Mode runs
@app.delete("/api/red-mode/{run_id}")
def cancel_red_mode(run_id: str):
    state = red_runs.get(run_id)
    if not state:
        return {"error": "Unknown run ID"}
    if state.done:
        return {"error": "Run already finished"}
    state.cancelled = True
    state.cancel_event.set()
    return {"ok": True, "runId": run_id}


# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import logging

    class _FilterPoll(logging.Filter):
        def filter(self, record):
            return "/api/poll/" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(_FilterPoll())
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
