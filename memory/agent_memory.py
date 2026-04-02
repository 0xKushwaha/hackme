"""
AgentMemory — per-agent interface for recall and storage.

Three recall modes (inspired by MiroFish's ZepToolsService):
  1. recall()             — standard top-K similarity search
  2. insight_forge_recall() — LLM decomposes query into sub-questions,
                              parallel searches per sub-question, aggregated results
                              (used by agents with use_insight_forge=True)

Temporal memory:
  - expire_run() marks all memories from a failed run as expired
  - Expired memories are excluded from all recall queries
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .vector_store  import VectorStore
from .graph_store   import GraphStore, INFORMED_BY, CROSS_RUN
from .compaction    import ContextCompactor

TOP_K_RECALL    = 3
TOP_K_PER_QUERY = 2   # per sub-question in insight_forge


def _format_memories(memories: list[dict], header: str = "RECALLED MEMORIES FROM PAST RUNS") -> str:
    if not memories:
        return ""
    lines = [f"[{header}]"]
    for i, m in enumerate(memories, 1):
        status = "✅" if m["success"] else "❌ (failed approach — avoid repeating)"
        lines.append(
            f"\nMemory {i} {status} | similarity distance: {m['distance']:.3f}\n"
            f"Past task  : {m['task']}\n"
            f"Past output: {m['output'][:600]}{'...' if len(m['output']) > 600 else ''}"
        )
    lines.append(f"[END OF {header}]")
    return "\n".join(lines)


class AgentMemory:
    """Per-agent memory interface. One instance per agent."""

    def __init__(self, agent_name: str, vector_store: VectorStore, graph_store: GraphStore):
        self.agent_name   = agent_name
        self.vector_store = vector_store
        self.graph_store  = graph_store

    # ------------------------------------------------------------------ #
    # Recall mode 1 — standard top-K                                      #
    # ------------------------------------------------------------------ #

    def recall(self, task: str, run_id: str, top_k: int = TOP_K_RECALL) -> tuple[list[dict], str]:
        memories = self.vector_store.recall(
            agent_name=self.agent_name,
            query=task,
            top_k=top_k,
            run_id_exclude=run_id,
        )
        return memories, _format_memories(memories)

    # ------------------------------------------------------------------ #
    # Recall mode 2 — insight_forge (multi-query decomposition)           #
    # ------------------------------------------------------------------ #

    def insight_forge_recall(
        self,
        task:    str,
        run_id:  str,
        llm,
        top_k:   int = TOP_K_RECALL,
    ) -> tuple[list[dict], str]:
        """
        1. Ask LLM to decompose the task into 3-4 specific sub-questions
        2. Run parallel recall searches for each sub-question
        3. Deduplicate by node_id and rank by minimum distance
        4. Return top_k unique results
        """
        sub_questions = self._decompose_query(task, llm)

        # Parallel recall per sub-question
        all_memories: list[dict] = []
        seen_outputs = set()

        with ThreadPoolExecutor(max_workers=len(sub_questions)) as ex:
            futures = [
                ex.submit(
                    self.vector_store.recall,
                    self.agent_name, q, TOP_K_PER_QUERY, run_id
                )
                for q in sub_questions
            ]
            for f in futures:
                for m in f.result():
                    key = m["output"][:100]   # dedup by content prefix
                    if key not in seen_outputs:
                        seen_outputs.add(key)
                        all_memories.append(m)

        # Sort by similarity (lowest distance = most similar)
        all_memories.sort(key=lambda m: m["distance"])
        top = all_memories[:top_k]

        header = f"INSIGHT FORGE RECALL ({len(sub_questions)} sub-queries, {len(top)} results)"
        return top, _format_memories(top, header=header)

    def _decompose_query(self, query: str, llm) -> list[str]:
        """Use LLM to split a complex task into focused sub-questions for retrieval."""
        from langchain_core.messages import HumanMessage, SystemMessage
        try:
            messages = [
                SystemMessage(content=(
                    "You decompose agent tasks into specific sub-questions for memory retrieval. "
                    "Output ONLY a valid JSON array of 3-4 short question strings. No explanation."
                )),
                HumanMessage(content=f"Decompose this into retrieval sub-questions:\n{query[:800]}"),
            ]
            response = llm.invoke(messages)
            raw = response.content.strip() if hasattr(response, "content") else str(response)
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return [query]   # fallback: single query

    # ------------------------------------------------------------------ #
    # Remember                                                             #
    # ------------------------------------------------------------------ #

    def remember(
        self,
        node_id:  str,
        run_id:   str,
        task:     str,
        output:   str,
        role:     str,
        success:  bool = True,
        metadata: dict = None,
    ):
        self.vector_store.remember(
            agent_name=self.agent_name,
            node_id=node_id,
            run_id=run_id,
            task=task,
            output=output,
            success=success,
            metadata=metadata,
        )
        self.graph_store.add_node(
            node_id=node_id,
            run_id=run_id,
            agent=self.agent_name,
            role=role,
            content=output,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------ #
    # Temporal: expire a failed run's memories                            #
    # ------------------------------------------------------------------ #

    def expire_run(self, run_id: str):
        """Mark all this agent's memories from run_id as expired."""
        self.vector_store.expire_run(self.agent_name, run_id)

    def memory_size(self) -> int:
        return self.vector_store.agent_memory_size(self.agent_name)

    def active_memory_size(self) -> int:
        return self.vector_store.agent_active_memory_size(self.agent_name)


class MemorySystem:
    """
    Factory that creates and holds one AgentMemory per agent.
    Also provides system-level operations (expire all agents for a run).
    """

    def __init__(
        self,
        agent_names: list[str],
        persist_dir: str = "experiments/chroma_db",
        graph_db:    str = "experiments/graph.db",
        llm          = None,
    ):
        self.vector_store = VectorStore(persist_dir=persist_dir)
        self.graph_store  = GraphStore(db_path=graph_db)
        self.agent_names  = agent_names
        self.memories: dict[str, AgentMemory] = {
            name: AgentMemory(name, self.vector_store, self.graph_store)
            for name in agent_names
        }
        # Compactor needs an LLM — wired in after init if not provided
        self.compactor: Optional[ContextCompactor] = ContextCompactor(llm) if llm else None

    def set_llm(self, llm):
        """Wire in the LLM for compaction (called after main LLM is built)."""
        self.compactor = ContextCompactor(llm)

    def get(self, agent_name: str) -> Optional[AgentMemory]:
        return self.memories.get(agent_name)

    def create_for(self, agent_name: str) -> AgentMemory:
        """
        Create (or return existing) AgentMemory for a dynamically spawned agent.
        Dynamic agents share the same VectorStore + GraphStore as the rest.
        """
        if agent_name not in self.memories:
            self.memories[agent_name] = AgentMemory(agent_name, self.vector_store, self.graph_store)
            print(f"[MemorySystem] Created memory slot for dynamic agent: '{agent_name}'")
        return self.memories[agent_name]

    def expire_run(self, run_id: str):
        """
        Called when a training run fails.
        Marks memories from this run as expired across ALL agents.
        Agents will not repeat approaches from this failed run.
        """
        print(f"\n[MemorySystem] Expiring memories for failed run: {run_id}")
        for mem in self.memories.values():
            mem.expire_run(run_id)

    def print_stats(self):
        gs = self.graph_store.stats()
        print(f"\n[MemorySystem] Graph: {gs['nodes']} nodes, {gs['edges']} edges, {gs['runs']} runs")
        for name, mem in self.memories.items():
            total  = mem.memory_size()
            active = mem.active_memory_size()
            if total > 0:
                expired = total - active
                print(f"  {name:20s} → {active} active, {expired} expired memories")
