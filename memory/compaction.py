"""
ContextCompactor — LLM-based context summarization with quality audit.

Ported from OpenClaw's src/agents/pi-extensions/compaction-safeguard.ts.

When the working context grows beyond a token budget, this compactor:
  1. Identifies the oldest non-pinned entries to compact
  2. Asks the LLM to summarize them
  3. Quality audit: verifies the summary preserves key identifiers,
     decisions, TODOs, and the latest user request
  4. Retries up to MAX_AUDIT_RETRIES times if audit fails
  5. Replaces the compacted entries with a single [COMPACTED SUMMARY] node
"""

import re
from dataclasses import dataclass
from typing import Optional

from langchain.schema import HumanMessage, SystemMessage

MAX_AUDIT_RETRIES  = 3
MAX_SUMMARY_CHARS  = 800     # cap on custom compaction instructions (OpenClaw: 800)
COMPACT_THRESHOLD  = 0.85    # compact when context exceeds 85% of token budget


COMPACTION_SYSTEM_PROMPT = """You are a context compaction specialist for an AI data science pipeline.
Your job is to summarize a sequence of agent analysis steps into a dense, lossless summary.

The summary MUST preserve:
- All decisions made (model choices, feature engineering choices, evaluation metrics)
- All TODOs and pending tasks
- All identified constraints and warnings (data quality issues, ethical concerns)
- Key identifiers: column names, model names, dataset statistics, error messages
- The most recent plan or instruction given

Write the summary in clear bullet points. Be exhaustive — loss of any detail could cause the pipeline to repeat mistakes or miss important context.
Output ONLY the summary. No preamble."""


AUDIT_SYSTEM_PROMPT = """You are auditing a context summary for completeness.
Given the original entries and the summary, check:
1. Are all key identifiers (column names, model names, numbers, error types) present in the summary?
2. Is the most recent plan/instruction reflected?
3. Are all warnings and constraints preserved?

Respond with exactly:
PASS if the summary is complete.
FAIL: <comma-separated list of missing items> if anything is missing."""


@dataclass
class CompactionResult:
    success:         bool
    summary:         str
    entries_removed: int
    tokens_freed:    int
    audit_attempts:  int


class ContextCompactor:
    """
    Compacts old ContextManager entries via LLM summarization + quality audit.
    Called by the Orchestrator when working context exceeds COMPACT_THRESHOLD.
    """

    def __init__(self, llm):
        self.llm = llm

    def should_compact(self, context_manager) -> bool:
        """Returns True if context is over COMPACT_THRESHOLD of its token budget."""
        total   = sum(e.token_estimate() for e in context_manager.entries)
        budget  = context_manager.max_tokens
        return (total / budget) >= COMPACT_THRESHOLD

    def compact(self, context_manager) -> Optional[CompactionResult]:
        """
        Compact the oldest non-pinned entries in the context manager.
        Returns CompactionResult or None if nothing to compact.
        """
        # Find compactable entries: non-pinned, oldest first
        compactable = [e for e in context_manager.entries if not e.pinned]

        if len(compactable) < 3:
            return None   # nothing worth compacting

        # Compact the oldest 60% of non-pinned entries, keep the rest fresh
        n_to_compact = max(2, int(len(compactable) * 0.6))
        to_compact   = compactable[:n_to_compact]
        tokens_before = sum(e.token_estimate() for e in to_compact)

        # Build the text block to summarize
        entries_text = "\n\n".join(
            f"[{e.agent.upper()} | {e.role} | {e.timestamp}]\n{e.content}"
            for e in to_compact
        )

        # Extract key identifiers for audit
        identifiers = self._extract_identifiers(entries_text)

        # Attempt summarization with quality audit
        summary   = None
        attempts  = 0
        audit_ok  = False
        extra_instructions = ""

        for attempt in range(1, MAX_AUDIT_RETRIES + 1):
            attempts = attempt
            summary  = self._summarize(entries_text, extra_instructions)

            audit_pass, missing = self._audit(entries_text, summary, identifiers)
            if audit_pass:
                audit_ok = True
                break
            else:
                # Feed missing items back as extra instructions for next attempt
                extra_instructions = f"The previous summary was missing: {missing}. Make sure to include these."
                print(f"[Compactor] Audit attempt {attempt} failed. Missing: {missing}. Retrying...")

        if not audit_ok:
            print(f"[Compactor] Audit failed after {MAX_AUDIT_RETRIES} attempts. Using best-effort summary.")

        # Remove compacted entries from context manager
        ids_to_remove = {e.id for e in to_compact}
        context_manager.entries = [e for e in context_manager.entries if e.id not in ids_to_remove]

        # Insert compact summary node at the position of the first removed entry
        from memory.context_manager import ContextEntry, ROLE_META
        compact_entry = ContextEntry(
            agent   = "compactor",
            role    = ROLE_META,
            content = f"[COMPACTED SUMMARY — {n_to_compact} entries]\n{summary}",
            pinned  = False,
        )

        # Insert at start of non-pinned entries
        pinned    = [e for e in context_manager.entries if e.pinned]
        non_pinned = [e for e in context_manager.entries if not e.pinned]
        context_manager.entries = pinned + [compact_entry] + non_pinned

        tokens_after = compact_entry.token_estimate()
        tokens_freed = max(0, tokens_before - tokens_after)

        print(f"[Compactor] Compacted {n_to_compact} entries → ~{tokens_freed} tokens freed ({attempts} audit attempt(s))")

        return CompactionResult(
            success         = True,
            summary         = summary,
            entries_removed = n_to_compact,
            tokens_freed    = tokens_freed,
            audit_attempts  = attempts,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _summarize(self, entries_text: str, extra_instructions: str = "") -> str:
        user_msg = f"Summarize these agent analysis steps:\n\n{entries_text}"
        if extra_instructions:
            user_msg += f"\n\nIMPORTANT: {extra_instructions}"

        messages = [
            SystemMessage(content=COMPACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
        response = self.llm.invoke(messages)
        return response.content.strip() if hasattr(response, "content") else str(response).strip()

    def _audit(self, original: str, summary: str, identifiers: list[str]) -> tuple[bool, str]:
        """
        Quality audit: check if summary preserves key identifiers.
        Returns (passed, missing_items_string).
        """
        if not identifiers:
            return True, ""

        audit_prompt = (
            f"ORIGINAL ENTRIES (excerpt):\n{original[:3000]}\n\n"
            f"SUMMARY:\n{summary}\n\n"
            f"KEY IDENTIFIERS TO CHECK: {', '.join(identifiers[:20])}"
        )
        messages = [
            SystemMessage(content=AUDIT_SYSTEM_PROMPT),
            HumanMessage(content=audit_prompt),
        ]
        try:
            response = self.llm.invoke(messages)
            result   = response.content.strip() if hasattr(response, "content") else str(response).strip()
            if result.upper().startswith("PASS"):
                return True, ""
            missing = result.split("FAIL:")[-1].strip() if "FAIL:" in result.upper() else result
            return False, missing
        except Exception:
            return True, ""   # if audit fails to run, assume pass

    def _extract_identifiers(self, text: str) -> list[str]:
        """
        Extract key identifiers from context for audit checking.
        Looks for: column names (quoted or CamelCase), model names, numbers, error types.
        """
        identifiers = set()

        # Quoted strings (column names, model names)
        identifiers.update(re.findall(r"'([^']{2,40})'", text))
        identifiers.update(re.findall(r'"([^"]{2,40})"', text))

        # Error types (XxxError, XxxWarning)
        identifiers.update(re.findall(r'\b[A-Z][a-z]+(?:Error|Warning|Exception)\b', text))

        # Model names
        for model in ["XGBoost", "RandomForest", "LogisticRegression", "LightGBM",
                      "CatBoost", "SVM", "KNN", "DecisionTree", "LinearRegression"]:
            if model.lower() in text.lower():
                identifiers.add(model)

        # Important metrics (accuracy, f1, etc. followed by numbers)
        identifiers.update(re.findall(r'(accuracy|f1|roc_auc|rmse|mae|r2)\s*[:=]\s*[\d.]+', text.lower()))

        return list(identifiers)[:30]   # cap at 30 identifiers for audit
