"""
BuilderAgent — meta-agent that inspects a DatasetProfile and decides:
  1. What custom Python tool modules to write to tool_registry/
  2. What specialist analysis agents to spawn (ImageAnalyst, AudioAnalyst…)
  3. An overall analysis strategy for the pipeline

RETRY MECHANISMS
================
Every failure is retried with full error context fed back to the LLM:

  LLM plan generation
    └─ JSON parse fails?     → retry LLM call with "previous JSON was invalid: {error}"
                                up to MAX_PLAN_RETRIES times

  Per-tool validation (3 stages: syntax → compile → import)
    └─ Syntax / compile error? → send error to LLM, ask for fixed code, re-validate
    └─ Import error?           → LibraryInstallerAgent installs missing packages first,
                                  then re-validates before asking LLM to rewrite
    └─ Still broken after MAX_TOOL_RETRIES? → tool is skipped with a warning

  Agent spec validation
    └─ Empty system_prompt or task? → retry LLM for that specific agent spec

FAST PATH
=========
Single plain tabular file → skip LLM entirely → return empty BuildPlan.
The standard EDA team handles all tabular datasets without custom tools.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain.schema import HumanMessage, SystemMessage

from phases.discovery import DatasetProfile
from execution.tool_validator import ToolValidator
from agents.installer_agent import LibraryInstallerAgent


MAX_PLAN_RETRIES = 3
MAX_TOOL_RETRIES = 3


# ------------------------------------------------------------------ #
# LLM prompts                                                          #
# ------------------------------------------------------------------ #

BUILDER_SYSTEM_PROMPT = """You are the Builder Agent — a senior ML engineering meta-agent.

Your job: inspect a dataset profile and decide what custom tools and specialist
analysis agents the pipeline needs to understand this data fully.

INPUT: A DatasetProfile describing file types, sizes, column names, and sample rows.

OUTPUT: A single valid JSON object (no markdown fences, no explanation) shaped as:

{
  "tools": [
    {
      "name": "snake_case_module_name",
      "description": "one-line description",
      "tags": ["tag1", "tag2"],
      "code": "complete runnable Python — use \\n for newlines, no if __name__ block"
    }
  ],
  "agents": [
    {
      "name": "snake_case_agent_id",
      "role": "short description of expertise",
      "task": "specific analysis task referencing actual file names and columns",
      "system_prompt": "detailed 3-5 sentence system prompt for this specialist"
    }
  ],
  "strategy": "one paragraph describing the overall analysis approach"
}

RULES:
- For pure single-table tabular data return {"tools": [], "agents": [], "strategy": "Standard tabular ML pipeline."}
- Only create tools for functionality that doesn't already exist:
  image loading, audio feature extraction, multi-table joining, NLP preprocessing, etc.
- Tool code must be self-contained Python using only standard lib + common packages
  (pandas, numpy, PIL/Pillow, librosa, sklearn, etc.). Wrap optional imports in try/except.
- Agent tasks MUST reference the specific files/columns observed — no generic placeholders.
- System prompts: 3-5 sentences, domain-specific, direct.
- Keep each tool under 60 lines. Focused utilities, not full pipelines.
- JSON strings: use \\n for newlines in code, never literal line breaks inside strings.
- Output ONLY the JSON object. Nothing else.
"""

TOOL_FIX_PROMPT = """You are a Python expert. A tool module you wrote has a validation error.
Fix the code so it passes syntax + import checks.
Output ONLY the corrected Python code — no markdown, no explanation, no fences."""

PLAN_RETRY_PREFIX = """Your previous response could not be used due to this error:
{error}

Fix the issue and output a valid JSON build plan. No markdown, no explanation."""


# ------------------------------------------------------------------ #
# Data classes                                                         #
# ------------------------------------------------------------------ #

@dataclass
class ToolSpec:
    name:        str
    description: str
    code:        str
    tags:        list = field(default_factory=list)


@dataclass
class AgentSpec:
    name:          str
    role:          str
    task:          str
    system_prompt: str


@dataclass
class BuildPlan:
    tools:    list[ToolSpec]  = field(default_factory=list)
    agents:   list[AgentSpec] = field(default_factory=list)
    strategy: str             = ""
    raw_json: str             = ""

    @property
    def is_empty(self) -> bool:
        return not self.tools and not self.agents


# ------------------------------------------------------------------ #
# Builder Agent                                                        #
# ------------------------------------------------------------------ #

class BuilderAgent:
    """
    Inspects a DatasetProfile → LLM produces build plan → tools validated
    and written to disk → specialist agents registered in orchestrator.

    Every failure is retried with the error fed back to the LLM so it can
    self-correct without any human intervention.
    """

    def __init__(self, llm, tool_registry=None):
        self.llm           = llm
        self.tool_registry = tool_registry
        self.validator     = ToolValidator()
        self.installer     = LibraryInstallerAgent()

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def run(self, profile: DatasetProfile, profile_text: str) -> BuildPlan:
        print(f"\n[BuilderAgent] 🔍 Analysing dataset...")
        print(f"[BuilderAgent]    Files : {len(profile.files)}")
        print(f"[BuilderAgent]    Types : {profile.types_present}")

        if profile.is_pure_tabular():
            print("[BuilderAgent] ✅ Pure tabular — default agents are sufficient.")
            return BuildPlan(strategy="Standard tabular ML pipeline.")

        # Step 1: get plan from LLM (with retries on JSON failures)
        plan = self._get_plan_with_retry(profile_text)

        # Step 2: validate + write each tool (with retries on validation failures)
        if self.tool_registry and plan.tools:
            validated_tools = []
            for spec in plan.tools:
                ok_spec = self._validate_and_register_tool(spec)
                if ok_spec:
                    validated_tools.append(ok_spec)
            plan.tools = validated_tools

        # Step 3: validate agent specs
        plan.agents = [a for a in plan.agents if self._validate_agent_spec(a)]

        if plan.agents:
            print(f"[BuilderAgent] 🤖 Spawning {len(plan.agents)} specialist(s):")
            for a in plan.agents:
                print(f"               • {a.name}: {a.role}")

        return plan

    # ------------------------------------------------------------------ #
    # Plan generation with retry                                           #
    # ------------------------------------------------------------------ #

    def _get_plan_with_retry(self, profile_text: str) -> BuildPlan:
        last_error: Optional[str] = None

        for attempt in range(1, MAX_PLAN_RETRIES + 1):
            if attempt > 1:
                print(f"[BuilderAgent] 🔁 Plan retry {attempt}/{MAX_PLAN_RETRIES} — prev error: {last_error}")

            try:
                plan = self._call_llm(profile_text, prev_error=last_error)
                # Consider empty plan a soft success (pure tabular fast path already handled)
                return plan
            except Exception as exc:
                last_error = str(exc)
                print(f"[BuilderAgent] ⚠️  Plan attempt {attempt} failed: {exc}")

        print("[BuilderAgent] ❌ All plan attempts failed — returning empty plan.")
        return BuildPlan()

    def _call_llm(self, profile_text: str, prev_error: Optional[str] = None) -> BuildPlan:
        prefix = ""
        if prev_error:
            prefix = PLAN_RETRY_PREFIX.format(error=prev_error) + "\n\n"

        messages = [
            SystemMessage(content=BUILDER_SYSTEM_PROMPT),
            HumanMessage(content=f"{prefix}DATASET PROFILE:\n{profile_text}\n\nProduce the JSON build plan now."),
        ]
        raw = self.llm.invoke(messages)
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
        return self._parse_plan(raw_text)

    def _parse_plan(self, raw: str) -> BuildPlan:
        clean = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().strip("`").strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response (got {len(raw)} chars)")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON parse error: {exc}") from exc

        tools = [
            ToolSpec(
                name=t.get("name", f"tool_{i}"),
                description=t.get("description", ""),
                code=t.get("code", ""),
                tags=t.get("tags", []),
            )
            for i, t in enumerate(data.get("tools", []))
        ]
        agents = [
            AgentSpec(
                name=a.get("name", f"specialist_{i}"),
                role=a.get("role", ""),
                task=a.get("task", ""),
                system_prompt=a.get("system_prompt", ""),
            )
            for i, a in enumerate(data.get("agents", []))
        ]
        return BuildPlan(
            tools=tools,
            agents=agents,
            strategy=data.get("strategy", ""),
            raw_json=raw,
        )

    # ------------------------------------------------------------------ #
    # Tool validation + registration with retry                            #
    # ------------------------------------------------------------------ #

    def _validate_and_register_tool(self, spec: ToolSpec) -> Optional[ToolSpec]:
        """
        Validate a tool spec's code through 3 stages (syntax, compile, import).
        On failure:
          - ImportError → try LibraryInstallerAgent first, then re-validate
          - Other error → ask LLM to fix with error context
        Retries up to MAX_TOOL_RETRIES times.
        Returns the (possibly fixed) ToolSpec on success, or None on permanent failure.
        """
        if not spec.code.strip():
            print(f"[BuilderAgent] ⚠️  Tool '{spec.name}' has empty code — skipping.")
            return None

        last_error: Optional[str] = None

        for attempt in range(1, MAX_TOOL_RETRIES + 1):
            result = self.validator.validate(spec.code, spec.name)

            if result.valid:
                # ── Register to disk ──────────────────────────────────
                try:
                    self.tool_registry.register(
                        name=spec.name,
                        code=spec.code,
                        description=spec.description,
                        author="builder_agent",
                        tags=spec.tags,
                    )
                    print(f"[BuilderAgent] ✅ Tool '{spec.name}' registered.")
                    return spec
                except Exception as exc:
                    last_error = f"Registration failed: {exc}"
                    print(f"[BuilderAgent] ⚠️  Tool '{spec.name}' registration error: {exc}")
                    # fall through to retry
                    if attempt == MAX_TOOL_RETRIES:
                        break
                    continue

            # ── Validation failed ─────────────────────────────────────
            error_msg = f"[{result.stage.upper()}] {result.error}"
            print(f"[BuilderAgent] ⚠️  Tool '{spec.name}' failed ({result.stage}): {result.error[:120]}")

            if result.stage == "import":
                # Try installing missing libraries first — might fix without LLM
                install = self.installer.handle(result.error)
                if install.any_success:
                    print(f"[BuilderAgent] 🔄 Installed {install.succeeded} — re-validating without LLM fix...")
                    last_error = error_msg
                    continue   # re-validate with same code, libraries now present

            # Ask LLM to fix the code (for all failure types)
            if attempt < MAX_TOOL_RETRIES:
                print(f"[BuilderAgent] 🔁 Asking LLM to fix '{spec.name}' (attempt {attempt+1}/{MAX_TOOL_RETRIES})...")
                spec = self._llm_fix_tool(spec, error_msg)
            last_error = error_msg

        print(f"[BuilderAgent] ❌ Tool '{spec.name}' could not be validated after {MAX_TOOL_RETRIES} attempts — skipping.")
        return None

    def _llm_fix_tool(self, spec: ToolSpec, error: str) -> ToolSpec:
        """Ask the LLM to rewrite the tool code given the validation error."""
        messages = [
            SystemMessage(content=TOOL_FIX_PROMPT),
            HumanMessage(content=(
                f"TOOL NAME       : {spec.name}\n"
                f"DESCRIPTION     : {spec.description}\n\n"
                f"CURRENT CODE:\n{spec.code}\n\n"
                f"VALIDATION ERROR:\n{error}\n\n"
                "Provide the fixed Python code:"
            )),
        ]
        raw = self.llm.invoke(messages)
        fixed = raw.content if hasattr(raw, "content") else str(raw)
        fixed = re.sub(r"```(?:python)?", "", fixed, flags=re.IGNORECASE).strip().strip("`").strip()
        return ToolSpec(name=spec.name, description=spec.description, code=fixed, tags=spec.tags)

    # ------------------------------------------------------------------ #
    # Agent spec validation                                                #
    # ------------------------------------------------------------------ #

    def _validate_agent_spec(self, spec: AgentSpec) -> bool:
        """Reject agent specs that are obviously incomplete."""
        if not spec.name.strip():
            return False
        if not spec.system_prompt.strip():
            print(f"[BuilderAgent] ⚠️  Agent '{spec.name}' has no system_prompt — skipping.")
            return False
        if not spec.task.strip():
            print(f"[BuilderAgent] ⚠️  Agent '{spec.name}' has no task — skipping.")
            return False
        return True
