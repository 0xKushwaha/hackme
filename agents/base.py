from typing import Optional

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from agents.agent_config import AgentConfig
from analysis.sampler import DataSampler
from analysis.relationship_extractor import RelationshipExtractor
from data_objects.analysis import RelationshipAnalysis, ValidationResult


class BaseAgent:
    """
    Base class for all agents.

    Behavioral config (AgentConfig) is injected into the system prompt
    so the LLM knows HOW to behave, not just what to do.

    If an AgentMemory is attached, the agent will:
      - recall relevant past memories before running (insight_forge or top-K)
      - store its output after running
    """

    def __init__(self, name: str, system_prompt: str, llm, config: AgentConfig = None):
        self.name          = name
        self._system_prompt = system_prompt
        self.llm           = llm
        self.config        = config or AgentConfig()
        self.memory        = None   # set by Orchestrator via attach_memory()

        # Data access (set by Orchestrator)
        self.dataset: Optional[pd.DataFrame] = None
        self.sampler: Optional[DataSampler] = None
        self.extractor: Optional[RelationshipExtractor] = None
        self.data_repository = None  # set by Orchestrator

    @property
    def system_prompt(self) -> str:
        """System prompt + behavioral instructions appended."""
        return self._system_prompt + self.config.behavioral_instructions()

    def attach_memory(self, agent_memory):
        self.memory = agent_memory

    def set_data_access(
        self,
        dataset: pd.DataFrame,
        sampler: Optional[DataSampler] = None,
        extractor: Optional[RelationshipExtractor] = None,
        data_repository=None,
    ):
        """Set data access for this agent (called by Orchestrator)."""
        self.dataset = dataset
        self.sampler = sampler or DataSampler()
        self.extractor = extractor or RelationshipExtractor()
        self.data_repository = data_repository

    def get_sample(
        self,
        n: int = 5000,
        strategy: str = "stratified",
        target_col: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Get a stratified sample of the dataset."""
        if self.dataset is None or self.sampler is None:
            return None

        return self.sampler.get_sample(
            self.dataset,
            strategy=strategy,
            target_col=target_col,
            n=n,
        )

    def get_all_data(self) -> Optional[pd.DataFrame]:
        """Get the full dataset (use with caution for large datasets)."""
        return self.dataset.copy() if self.dataset is not None else None

    def compute_relationship(
        self,
        feature_a: str,
        feature_b: str,
        sample: Optional[pd.DataFrame] = None,
    ) -> Optional[RelationshipAnalysis]:
        """Compute relationship between two features."""
        if self.extractor is None or self.dataset is None:
            return None

        data = sample if sample is not None else self.dataset
        try:
            # Infer data types
            dtype_a = pd.api.types.infer_dtype(data[feature_a])
            dtype_b = pd.api.types.infer_dtype(data[feature_b])

            # Numeric-numeric: correlation
            if dtype_a in ["integer", "floating"] and dtype_b in ["integer", "floating"]:
                return self.extractor.compute_numeric_correlation(data, feature_a, feature_b)

            # Any with target
            return self.extractor.compute_feature_target_relationship(data, feature_a, feature_b)

        except Exception as e:
            print(f"[{self.name}] Error computing relationship {feature_a}-{feature_b}: {e}")
            return None

    def extract_relationships(
        self,
        features: Optional[list] = None,
        target_col: Optional[str] = None,
    ) -> list:
        """Extract relationships for specified features."""
        if self.extractor is None or self.dataset is None:
            return []

        try:
            # Filter dataset to only requested features
            if features:
                cols = [c for c in features if c in self.dataset.columns]
                if target_col and target_col not in cols:
                    cols.append(target_col)
                data = self.dataset[cols]
            else:
                data = self.dataset

            return self.extractor.extract_all_relationships(data, target_col)
        except Exception as e:
            print(f"[{self.name}] Error extracting relationships: {e}")
            return []

    def discover_constraints(self):
        """Discover mathematical constraints in the dataset."""
        if self.dataset is None:
            return None

        from analysis.constraint_detector import ConstraintDiscoveryEngine
        engine = ConstraintDiscoveryEngine(self.dataset)
        return engine.discover_all_constraints()

    def run(
        self,
        context:  str,
        task:     str,
        node_id:  str  = None,
        run_id:   str  = None,
        role:     str  = "analysis",
        success:  bool = True,
    ) -> str:
        # 1. Recall relevant memories
        # insight_forge costs an extra LLM call to decompose the query — only worth it
        # when there are actual memories to search. Skip it on the first run.
        memory_block = ""
        if self.memory and run_id:
            if self.config.use_insight_forge and self.memory.has_entries():
                _, memory_block = self.memory.insight_forge_recall(
                    task=task, run_id=run_id, llm=self.llm
                )
            else:
                _, memory_block = self.memory.recall(task=task, run_id=run_id)

        # 2. Build full context
        context_block = context.strip() if context.strip() else "(No analysis yet — you are going first.)"
        full_context  = f"{memory_block}\n\n{context_block}" if memory_block else context_block

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"CURRENT ANALYSIS LOG:\n{full_context}\n\nYOUR TASK:\n{task}"),
        ]

        # 3. Run LLM
        response = self.llm.invoke(messages)
        output   = response.content.strip() if hasattr(response, "content") else str(response).strip()

        # 4. Store in memory
        if self.memory and node_id and run_id:
            self.memory.remember(
                node_id=node_id,
                run_id=run_id,
                task=task,
                output=output,
                role=role,
                success=success,
            )

        return output
