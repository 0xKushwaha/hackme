"""
CodeWriter Agent — generates executable Python training scripts.
Outputs ONLY code. Uses insight_forge recall to avoid repeating failed approaches.
"""

from langchain.schema import HumanMessage, SystemMessage
from prompts.coder_prompts import CODE_WRITER_PROMPT
from agents.agent_config import AgentConfig


class CodeWriterAgent:

    def __init__(self, llm, config: AgentConfig = None):
        self.name   = "code_writer"
        self.llm    = llm
        self.config = config or AgentConfig()
        self.memory = None

    def attach_memory(self, agent_memory):
        self.memory = agent_memory

    @property
    def system_prompt(self) -> str:
        return CODE_WRITER_PROMPT + self.config.behavioral_instructions()

    def run(
        self,
        context:       str,
        dataset_path:  str  = None,
        target_col:    str  = None,
        node_id:       str  = None,
        run_id:        str  = None,
        task_override: str  = None,
    ) -> str:
        if task_override:
            task = task_override
        else:
            task = (
                (f"Dataset path: {dataset_path}\n" if dataset_path else "")
                + (f"Target column: {target_col}\n" if target_col else "")
                + "\nGenerate the complete training script. Output ONLY Python code, no markdown fences."
            )

        # Use insight_forge to recall what approaches failed before
        memory_block = ""
        if self.memory and run_id:
            if self.config.use_insight_forge:
                _, memory_block = self.memory.insight_forge_recall(
                    task=task, run_id=run_id, llm=self.llm
                )
            else:
                _, memory_block = self.memory.recall(task=task, run_id=run_id)

        context_block = context.strip() if context.strip() else "(No analysis yet.)"
        full_context  = f"{memory_block}\n\n{context_block}" if memory_block else context_block

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"CURRENT ANALYSIS LOG:\n{full_context}\n\nYOUR TASK:\n{task}"),
        ]
        response = self.llm.invoke(messages)
        raw = response.content.strip() if hasattr(response, "content") else str(response).strip()

        # Strip markdown fences if the LLM added them despite instructions
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Store in memory
        if self.memory and node_id and run_id:
            self.memory.remember(
                node_id=node_id,
                run_id=run_id,
                task=task,
                output=raw,
                role="code",
            )

        return raw
