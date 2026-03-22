"""
Multi-Agent Data Science Team — Streamlit UI
=============================================
Launch with:  streamlit run app.py
Opens at:     http://localhost:8501

Flow:
  1. Configure LLM (API key or local vLLM server)
  2. Enter dataset path + task/competition description
  3. Click Run — watch agents work live
  4. Read formatted report + download results ZIP
"""

import io
import json
import os
import queue
import sys
import threading
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Multi-Agent Data Science Team",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
# Stdout capture → queue (for live log streaming)
# ─────────────────────────────────────────────────────────────────────

class _Tee:
    """Writes to both a queue (→ UI) and the real stdout (→ terminal)."""

    def __init__(self, q: queue.Queue, original):
        self.q        = q
        self.original = original

    def write(self, text: str):
        if text:
            self.q.put(text)
            try:
                self.original.write(text)
                self.original.flush()
            except Exception:
                pass

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass

    def fileno(self):
        return self.original.fileno()


# ─────────────────────────────────────────────────────────────────────
# Pipeline runner (background thread)
# ─────────────────────────────────────────────────────────────────────

def _run_pipeline(cfg: dict) -> dict:
    """Build and execute the full agent pipeline. Called in a background thread."""
    from backends.llm_backends    import get_llm
    from backends.fallback        import build_fallback_llm
    from agents import (
        ExplorerAgent, SkepticAgent, StatisticianAgent, EthicistAgent,
        PragmatistAgent, DevilAdvocateAgent, ArchitectAgent, OptimizerAgent,
        StorytellerAgent, CodeWriterAgent,
    )
    from agents.agent_config        import AGENT_CONFIGS
    from agents.base                import BaseAgent
    from agents.builder_agent       import BuilderAgent
    from execution.executor         import CodeExecutor
    from memory.agent_memory        import MemorySystem
    from orchestration.orchestrator import Orchestrator
    from orchestration.registry     import AgentRegistry
    from phases.discovery           import DatasetDiscovery
    from tool_registry              import ToolRegistry
    from prompts.planner_prompts    import FEATURE_ENGINEER_PROMPT

    exp_dir = cfg["experiment_dir"]
    os.makedirs(exp_dir, exist_ok=True)

    # ── API keys ─────────────────────────────────────────────────────
    if cfg["provider"] == "claude" and cfg.get("api_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
    if cfg["provider"] == "openai" and cfg.get("api_key"):
        os.environ["OPENAI_API_KEY"] = cfg["api_key"]
    if cfg.get("fallback") == "openai" and cfg.get("fallback_key"):
        os.environ["OPENAI_API_KEY"] = cfg["fallback_key"]
    if cfg.get("fallback") == "claude" and cfg.get("fallback_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["fallback_key"]

    # ── Dataset discovery ────────────────────────────────────────────
    print(f"\n📂 Scanning dataset: {cfg['dataset_path']}")
    discovery = DatasetDiscovery()
    profile   = discovery.scan(cfg["dataset_path"])
    print(f"   Files : {len(profile.files)}  |  Types : {', '.join(profile.types_present)}")
    dataset_summary = discovery.format_profile(profile)

    # Prepend competition/task context
    task_desc = cfg.get("task_description", "").strip()
    if task_desc:
        context_block = (
            f"COMPETITION / TASK CONTEXT:\n{task_desc}\n\n"
            f"DATASET PROFILE:\n{dataset_summary}"
        )
    else:
        context_block = dataset_summary

    # ── LLM ─────────────────────────────────────────────────────────
    llm_kwargs = {}
    if cfg.get("server_url"):
        llm_kwargs["base_url"] = cfg["server_url"]

    if cfg.get("fallback"):
        llm = build_fallback_llm([
            {"provider": cfg["provider"], "model": cfg.get("model")},
            {"provider": cfg["fallback"],  "model": cfg.get("fallback_model")},
        ])
        print(f"🔧 FallbackLLM: {cfg['provider']} → {cfg['fallback']}")
    else:
        llm = get_llm(cfg["provider"], model=cfg.get("model"), **llm_kwargs)

    # ── Agents ───────────────────────────────────────────────────────
    agents = {
        "explorer":         ExplorerAgent(llm,       config=AGENT_CONFIGS["explorer"]),
        "skeptic":          SkepticAgent(llm,        config=AGENT_CONFIGS["skeptic"]),
        "statistician":     StatisticianAgent(llm,   config=AGENT_CONFIGS["statistician"]),
        "feature_engineer": BaseAgent("Feature Engineer", FEATURE_ENGINEER_PROMPT, llm,
                                      config=AGENT_CONFIGS["feature_engineer"]),
        "ethicist":         EthicistAgent(llm,       config=AGENT_CONFIGS["ethicist"]),
        "pragmatist":       PragmatistAgent(llm,     config=AGENT_CONFIGS["pragmatist"]),
        "devil_advocate":   DevilAdvocateAgent(llm,  config=AGENT_CONFIGS["devil_advocate"]),
        "optimizer":        OptimizerAgent(llm,      config=AGENT_CONFIGS["optimizer"]),
        "architect":        ArchitectAgent(llm,      config=AGENT_CONFIGS["architect"]),
        "storyteller":      StorytellerAgent(llm,    config=AGENT_CONFIGS["storyteller"]),
        "code_writer":      CodeWriterAgent(llm,     config=AGENT_CONFIGS["code_writer"]),
    }

    # ── Memory ───────────────────────────────────────────────────────
    memory_system = None
    if cfg.get("enable_memory", True):
        memory_system = MemorySystem(
            agent_names=list(agents.keys()),
            persist_dir=os.path.join(exp_dir, "chroma_db"),
            graph_db=os.path.join(exp_dir, "graph.db"),
        )

    # ── Execution infra ──────────────────────────────────────────────
    mode       = cfg["mode"]
    needs_exec = mode in ("train", "phases")
    executor      = CodeExecutor(work_dir=exp_dir) if needs_exec else None
    tool_reg_dir  = os.path.join(exp_dir, "tool_registry")
    tool_registry = ToolRegistry(registry_dir=tool_reg_dir) if needs_exec else None
    registry      = AgentRegistry(
        max_concurrent=cfg.get("max_agents", 5),
        persist_path=os.path.join(exp_dir, "registry.json"),
    )

    builder_agent = None
    if cfg.get("enable_builder", True):
        builder_agent = BuilderAgent(llm=llm, tool_registry=tool_registry)

    # ── Orchestrator ─────────────────────────────────────────────────
    orch = Orchestrator(
        agents=agents, llm=llm, executor=executor,
        memory_system=memory_system, registry=registry,
        tool_registry=tool_registry, builder_agent=builder_agent,
    )

    abs_path = os.path.abspath(cfg["dataset_path"])
    target   = cfg.get("target_col") or None
    retries  = int(cfg.get("max_retries", 4))

    if mode == "manual":
        orch.run_manual(context_block)
    elif mode == "auto":
        orch.run_auto(context_block)
    elif mode == "train":
        orch.run_training_loop(
            dataset_summary=context_block, dataset_path=abs_path,
            target_col=target, max_retries=retries, experiment_dir=exp_dir,
        )
    elif mode == "phases":
        orch.run_phases(
            dataset_summary=context_block, dataset_path=abs_path,
            target_col=target, max_retries=retries,
            experiment_dir=exp_dir, dataset_profile=profile,
        )

    log_path = os.path.join(exp_dir, f"context_{orch.run_id}.json")
    orch.context.save(log_path)

    return {"run_id": orch.run_id, "log_path": log_path,
            "exp_dir": exp_dir, "context": orch.context}


# ─────────────────────────────────────────────────────────────────────
# Results formatting
# ─────────────────────────────────────────────────────────────────────

def _build_report(result: dict, task_description: str) -> str:
    ctx = result["context"]
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 🤖 Multi-Agent Analysis Report",
        f"**Run ID:** `{result['run_id']}`  |  **Generated:** {ts}",
        "",
    ]

    if task_description.strip():
        lines += ["## 🎯 Task / Competition Context", task_description.strip(), ""]

    role_sections = [
        ("dataset_context", "📊 Dataset Profile"),
        ("meta",            "🔨 Builder Strategy"),
        ("analysis",        "🔬 Agent Analysis"),
        ("plan",            "📋 Plans & Recommendations"),
        ("code",            "💻 Generated Training Code"),
        ("result",          "✅ Execution Results"),
        ("error",           "❌ Errors Encountered"),
        ("narrative",       "📖 Final Narrative"),
    ]

    for role, heading in role_sections:
        entries = [e for e in ctx.entries if e.role == role]
        if not entries:
            continue
        lines.append(f"## {heading}")
        for e in entries:
            agent_title = e.agent.replace("_", " ").title()
            if role == "code":
                attempt = e.metadata.get("attempt", 1)
                lines += [f"### {agent_title} — Attempt {attempt}",
                          f"```python\n{e.content[:4000]}\n```", ""]
            else:
                lines += [f"### {agent_title}", e.content, ""]

    return "\n".join(lines)


def _build_zip(result: dict, report_md: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("analysis_report.md", report_md)

        if os.path.exists(result["log_path"]):
            zf.write(result["log_path"], "context_log.json")

        exp = Path(result["exp_dir"])
        for py in exp.glob("train_attempt_*.py"):
            zf.write(str(py), py.name)
        for py in exp.glob("inference*.py"):
            zf.write(str(py), py.name)

        tool_dir = exp / "tool_registry"
        if tool_dir.exists():
            for f in tool_dir.glob("*.py"):
                zf.write(str(f), f"tool_registry/{f.name}")
            idx = tool_dir / "_index.json"
            if idx.exists():
                zf.write(str(idx), "tool_registry/_index.json")

    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Tighter sidebar */
section[data-testid="stSidebar"] { min-width: 340px; max-width: 380px; }
/* Live log font */
.log-box { font-family: monospace; font-size: 0.80rem; background: #0e1117;
           color: #e2e8f0; padding: 12px; border-radius: 6px;
           height: 500px; overflow-y: auto; white-space: pre-wrap; }
/* Run button */
div.stButton > button[kind="primary"] {
    background-color: #6366f1; color: white;
    font-size: 1.05rem; padding: 0.6rem 2rem;
    border: none; border-radius: 8px; width: 100%;
}
div.stButton > button[kind="primary"]:hover { background-color: #4f46e5; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────

for key, default in [
    ("running",    False),
    ("log",        ""),
    ("result",     None),
    ("report_md",  ""),
    ("error",      ""),
    ("zip_bytes",  None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────────────────────────────
# Sidebar — configuration
# ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 DS Agent Team")
    st.caption("Autonomous multi-agent data science pipeline")
    st.divider()

    st.subheader("⚡ LLM Provider")
    provider = st.radio(
        "Provider",
        ["claude", "openai", "local (vLLM)"],
        horizontal=True,
        label_visibility="collapsed",
    )

    is_local = provider == "local (vLLM)"

    if is_local:
        server_url = st.text_input(
            "vLLM Server URL",
            placeholder="http://localhost:8000/v1",
        )
        api_key = ""
    else:
        api_key = st.text_input(
            f"{'Anthropic' if provider == 'claude' else 'OpenAI'} API Key",
            type="password",
            placeholder="sk-ant-...  or  sk-...",
        )
        server_url = ""

    with st.expander("Fallback Provider (optional)"):
        fallback = st.selectbox("Fallback on rate limit", ["none", "claude", "openai"])
        fallback_key = st.text_input("Fallback API Key", type="password",
                                     placeholder="Leave blank if not using fallback")

    st.divider()
    st.subheader("🗂️ Dataset")

    dataset_path = st.text_input(
        "Dataset Path",
        placeholder="/home/user/data/  or  /home/user/train.csv",
        help="Any file or directory. Supports CSV, Parquet, images, audio, JSON, Excel…",
    )

    task_description = st.text_area(
        "Task / Competition Description",
        placeholder=(
            "Describe the goal. E.g.:\n"
            "This is a Kaggle competition to predict house prices.\n"
            "Metric: RMSE. We want the best model with cross-validation."
        ),
        height=130,
        help="Agents will use this as their north star. The more detail the better.",
    )

    st.divider()
    st.subheader("🔧 Pipeline Settings")

    mode = st.radio(
        "Mode",
        ["phases", "manual", "auto", "train"],
        horizontal=True,
        help="phases = full 5-phase pipeline (recommended)",
    )

    target_col = st.text_input(
        "Target Column",
        placeholder="price, label, survived… (blank = auto-detect)",
    )

    with st.expander("Advanced settings"):
        max_retries    = st.slider("Max Training Retries", 1, 8, 4)
        max_agents     = st.slider("Max Concurrent Agents", 1, 10, 5)
        enable_memory  = st.checkbox("Long-Term Memory (ChromaDB)", value=True)
        enable_builder = st.checkbox("Builder Agent (auto-tools)", value=True)
        experiment_dir = st.text_input("Experiment Output Dir", value="experiments")

    st.divider()
    run_clicked = st.button("🚀 Run Analysis", type="primary",
                             disabled=st.session_state.running)


# ─────────────────────────────────────────────────────────────────────
# Main area — tabs
# ─────────────────────────────────────────────────────────────────────

tab_log, tab_results, tab_download = st.tabs([
    "📡 Live Agent Log",
    "📊 Results Report",
    "⬇️ Download",
])

# ─────────────────────────────────────────────────────────────────────
# Run handler
# ─────────────────────────────────────────────────────────────────────

if run_clicked:
    # ── Validate ────────────────────────────────────────────────────
    errors = []
    if not dataset_path.strip():
        errors.append("Dataset path is required.")
    elif not os.path.exists(dataset_path.strip()):
        errors.append(f"Path not found: `{dataset_path}`")
    if not is_local and not api_key.strip():
        errors.append("API key is required.")
    if is_local and not server_url.strip():
        errors.append("vLLM server URL is required.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # ── Reset state ──────────────────────────────────────────────────
    st.session_state.running   = True
    st.session_state.log       = ""
    st.session_state.result    = None
    st.session_state.report_md = ""
    st.session_state.error     = ""
    st.session_state.zip_bytes = None

    # ── Build config ─────────────────────────────────────────────────
    cfg = {
        "provider":        "local" if is_local else provider,
        "api_key":         api_key.strip(),
        "server_url":      server_url.strip() if is_local else None,
        "fallback":        fallback if fallback != "none" else None,
        "fallback_key":    fallback_key.strip() or None,
        "dataset_path":    dataset_path.strip(),
        "task_description": task_description.strip(),
        "mode":            mode,
        "target_col":      target_col.strip() or None,
        "max_retries":     max_retries,
        "max_agents":      max_agents,
        "enable_memory":   enable_memory,
        "enable_builder":  enable_builder,
        "experiment_dir":  experiment_dir.strip() or "experiments",
        "model":           None,
    }

    # ── Thread + queue ───────────────────────────────────────────────
    out_q          = queue.Queue()
    result_holder  = [None]
    error_holder   = [None]

    def _thread():
        old_stdout = sys.stdout
        sys.stdout = _Tee(out_q, old_stdout)
        try:
            result_holder[0] = _run_pipeline(cfg)
        except Exception as exc:
            error_holder[0] = traceback.format_exc()
            out_q.put(f"\n\n❌ PIPELINE ERROR:\n{error_holder[0]}")
        finally:
            sys.stdout = old_stdout
            out_q.put(None)   # sentinel

    t = threading.Thread(target=_thread, daemon=True)
    t.start()

    # ── Stream to Live Log tab ───────────────────────────────────────
    with tab_log:
        st.caption("Streaming live — agents are running…")
        log_placeholder = st.empty()

        full_log = ""
        while True:
            try:
                chunk = out_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if chunk is None:
                break
            full_log += chunk
            # Show last 200 lines to avoid infinite growth in the widget
            display = "\n".join(full_log.splitlines()[-200:])
            log_placeholder.markdown(
                f'<div class="log-box">{display}</div>',
                unsafe_allow_html=True,
            )

        t.join(timeout=10)
        st.session_state.log = full_log

    # ── Process results ──────────────────────────────────────────────
    if error_holder[0]:
        st.session_state.error   = error_holder[0]
        st.session_state.running = False
    elif result_holder[0]:
        result     = result_holder[0]
        report     = _build_report(result, task_description)
        zip_bytes  = _build_zip(result, report)

        st.session_state.result    = result
        st.session_state.report_md = report
        st.session_state.zip_bytes = zip_bytes
        st.session_state.running   = False
        st.success(f"✅ Analysis complete!  Run ID: `{result['run_id']}`")
    else:
        st.session_state.running = False

    st.rerun()


# ─────────────────────────────────────────────────────────────────────
# Render tabs from session state
# ─────────────────────────────────────────────────────────────────────

with tab_log:
    if st.session_state.error:
        st.error("Pipeline failed — see log below.")
        st.code(st.session_state.error, language="text")
    elif st.session_state.log:
        display = "\n".join(st.session_state.log.splitlines()[-300:])
        st.markdown(
            f'<div class="log-box">{display}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Run the analysis to see live output here.")

with tab_results:
    if st.session_state.report_md:
        st.markdown(st.session_state.report_md)
    elif st.session_state.error:
        st.error("Run failed — no results to show.")
    else:
        st.info("Results will appear here after the run completes.")

with tab_download:
    if st.session_state.zip_bytes:
        result = st.session_state.result
        fname  = f"analysis_{result['run_id']}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

        st.success("Your results are ready!")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.download_button(
                label="⬇️ Download Results ZIP",
                data=st.session_state.zip_bytes,
                file_name=fname,
                mime="application/zip",
                use_container_width=True,
            )
        with col2:
            st.caption(
                f"**Contains:**  analysis_report.md · context_log.json · "
                f"generated training scripts · tool_registry modules\n\n"
                f"**Saved to:** `{result['exp_dir']}/`"
            )

        st.divider()
        st.markdown("#### 📄 Preview: Analysis Report")
        with st.expander("Click to expand report", expanded=False):
            st.markdown(st.session_state.report_md)

    elif st.session_state.error:
        st.error("Run failed — nothing to download.")
    else:
        st.info("Download will be available after the run completes.")
        st.markdown("""
**The ZIP will contain:**
- `analysis_report.md` — full formatted report of every agent's output
- `context_log.json` — complete structured context (for programmatic use)
- `train_attempt_*.py` — generated training scripts (train/phases mode)
- `tool_registry/` — any custom tools the Builder Agent created
        """)
