import re
from langchain.schema import HumanMessage, SystemMessage
from prompts import ORCHESTRATOR_PROMPT


MAX_TOKENS_IN_LOG = 3000   # trim log if it exceeds this (rough char estimate)
MAX_STEPS = 10             # safety limit to prevent infinite loops


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _trim_log(log: str, max_tokens: int = MAX_TOKENS_IN_LOG) -> str:
    """Keep only the most recent entries if log is too long."""
    if _estimate_tokens(log) <= max_tokens:
        return log
    # Split by agent blocks and drop oldest
    blocks = log.strip().split("\n\n[")
    while len(blocks) > 1 and _estimate_tokens("\n\n[".join(blocks)) > max_tokens:
        blocks.pop(0)
    return "\n\n[" + "\n\n[".join(blocks)


class Orchestrator:
    """
    Routes tasks between agents and manages the shared analysis log.
    Can operate in:
        - auto mode: uses an LLM to decide which agent goes next
        - manual mode: caller specifies agent + task explicitly
    """

    def __init__(self, agents: dict, llm=None):
        """
        agents : dict of {name: Agent}
        llm    : optional LLM for auto-orchestration decisions
        """
        self.agents = agents
        self.llm = llm
        self.log = ""
        self.steps_taken = 0

    # ------------------------------------------------------------------ #
    # Manual mode — caller decides which agent + task                     #
    # ------------------------------------------------------------------ #

    def step(self, agent_name: str, task: str) -> str:
        """Run a specific agent on a specific task. Append result to log."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent '{agent_name}'. Available: {list(self.agents.keys())}")

        agent = self.agents[agent_name]
        context = _trim_log(self.log)
        response = agent.run(context, task)

        self.log += f"\n\n[{agent_name.upper()}]\n{response}"
        self.steps_taken += 1

        print(f"\n{'='*60}")
        print(f"  {agent_name.upper()}")
        print(f"{'='*60}")
        print(response)

        return response

    # ------------------------------------------------------------------ #
    # Auto mode — orchestrator LLM decides what to do next               #
    # ------------------------------------------------------------------ #

    def _parse_orchestrator_response(self, raw: str) -> dict:
        """Parse the orchestrator LLM output into a structured dict."""
        result = {"agent": None, "task": None, "complete": False, "reason": ""}
        for line in raw.strip().splitlines():
            if line.startswith("NEXT_AGENT:"):
                result["agent"] = line.split(":", 1)[1].strip().lower()
            elif line.startswith("TASK:"):
                result["task"] = line.split(":", 1)[1].strip()
            elif line.startswith("COMPLETE:"):
                result["complete"] = line.split(":", 1)[1].strip().lower() == "yes"
            elif line.startswith("REASON:"):
                result["reason"] = line.split(":", 1)[1].strip()
        return result

    def auto_step(self) -> dict:
        """
        Ask the orchestrator LLM what to do next.
        Returns the parsed decision dict.
        """
        if self.llm is None:
            raise RuntimeError("Provide an LLM to Orchestrator to use auto mode.")

        messages = [
            SystemMessage(content=ORCHESTRATOR_PROMPT),
            HumanMessage(content=f"""CURRENT ANALYSIS LOG:
{self.log if self.log.strip() else "(Empty — analysis has not started yet.)"}

What should happen next?""")
        ]
        raw = self.llm.invoke(messages)
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
        decision = self._parse_orchestrator_response(raw_text)

        print(f"\n[ORCHESTRATOR] → {decision['agent'].upper()} | {decision['reason']}")
        return decision

    def run_auto(self, initial_context: str = "", max_steps: int = MAX_STEPS):
        """
        Fully automatic pipeline: orchestrator decides each step until done.
        initial_context: dataset summary to seed the log
        """
        if initial_context:
            self.log = f"[DATASET CONTEXT]\n{initial_context}"

        for _ in range(max_steps):
            decision = self.auto_step()

            if decision["complete"]:
                print("\n✅ Orchestrator says analysis is complete.")
                break

            if not decision["agent"] or decision["agent"] not in self.agents:
                print(f"\n⚠️  Orchestrator returned unknown agent: {decision['agent']}. Stopping.")
                break

            self.step(decision["agent"], decision["task"])

        else:
            print(f"\n⚠️  Reached max steps ({max_steps}). Stopping.")

        return self.log

    # ------------------------------------------------------------------ #
    # Utilities                                                           #
    # ------------------------------------------------------------------ #

    def print_log(self):
        print("\n" + "="*60)
        print("  FULL ANALYSIS LOG")
        print("="*60)
        print(self.log)

    def save_log(self, path: str = "analysis_log.txt"):
        with open(path, "w") as f:
            f.write(self.log)
        print(f"\n📄 Log saved to {path}")
