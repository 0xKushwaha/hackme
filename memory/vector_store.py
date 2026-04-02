"""
VectorStore — ChromaDB wrapper for per-agent persistent memory with temporal support.

Temporal memory (inspired by MiroFish's Zep temporal facts):
  - Every memory entry has an 'expired' flag (default "False")
  - When a training run fails, its memories can be marked expired
  - Recall filters out expired memories — agents won't repeat failed approaches
  - Expired memories still exist in the DB (for audit/lineage), just hidden from recall
"""

import os
import uuid
from datetime import datetime
from typing import Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


CHROMA_PERSIST_DIR = os.path.join("experiments", "chroma_db")
EMBED_MODEL        = "all-MiniLM-L6-v2"


class VectorStore:
    """
    Wraps ChromaDB. Each agent gets its own persistent collection.
    Supports temporal expiry of memories from failed runs.
    """

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self.available = CHROMA_AVAILABLE
        if not self.available:
            print("[VectorStore] chromadb not installed — long-term memory disabled.")
            return

        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        self._collections: dict = {}

    # ------------------------------------------------------------------ #
    # Collection management                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _col_name(agent_name: str) -> str:
        return "agent_" + (
            agent_name.lower()
            .replace("'", "")
            .replace(" ", "_")
            .replace("-", "_")
        )

    def _get_collection(self, agent_name: str):
        col_name = self._col_name(agent_name)
        if col_name not in self._collections:
            self._collections[col_name] = self.client.get_or_create_collection(
                name=col_name,
                embedding_function=self._embed_fn,
                metadata={"agent": agent_name},
            )
        return self._collections[col_name]

    # ------------------------------------------------------------------ #
    # Store a memory                                                       #
    # ------------------------------------------------------------------ #

    def remember(
        self,
        agent_name: str,
        node_id:    str,
        run_id:     str,
        task:       str,
        output:     str,
        success:    bool = True,
        metadata:   dict = None,
    ):
        if not self.available:
            return

        collection = self._get_collection(agent_name)
        meta = {
            "node_id":   node_id,
            "run_id":    run_id,
            "task":      task[:500],
            "success":   str(success),
            "expired":   "False",           # temporal: active by default
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **(metadata or {}),
        }

        collection.add(
            ids=[node_id],
            documents=[output],
            metadatas=[meta],
        )

    # ------------------------------------------------------------------ #
    # Temporal: expire memories from a failed run                         #
    # ------------------------------------------------------------------ #

    def expire_run(self, agent_name: str, run_id: str):
        """
        Mark all memories from a specific run as expired.
        Called when a training attempt fails — agents won't repeat that approach.
        """
        if not self.available:
            return

        collection = self._get_collection(agent_name)
        results    = collection.get(where={"run_id": run_id})

        if not results["ids"]:
            return

        # Update each entry's metadata to mark as expired
        updated_meta = []
        for meta in results["metadatas"]:
            updated = dict(meta)
            updated["expired"]    = "True"
            updated["expired_at"] = datetime.now().isoformat(timespec="seconds")
            updated_meta.append(updated)

        collection.update(ids=results["ids"], metadatas=updated_meta)
        print(f"[VectorStore] Expired {len(results['ids'])} memories for agent '{agent_name}' (run: {run_id})")

    def expire_run_all_agents(self, run_id: str, agent_names: list[str]):
        """Expire memories for this run across all agents."""
        for name in agent_names:
            self.expire_run(name, run_id)

    # ------------------------------------------------------------------ #
    # Recall — filters out expired memories                               #
    # ------------------------------------------------------------------ #

    def recall(
        self,
        agent_name:      str,
        query:           str,
        top_k:           int           = 3,
        run_id_exclude:  Optional[str] = None,
        use_hybrid:      bool          = True,
    ) -> list[dict]:
        """
        Returns top_k most relevant ACTIVE (non-expired) memories.
        Uses hybrid search (BM25 + vector + temporal decay + MMR) when available.
        Falls back to vector-only otherwise.
        """
        if not self.available:
            return []

        collection = self._get_collection(agent_name)
        if collection.count() == 0:
            return []

        # Build where filter — exclude expired AND current run
        conditions = [{"expired": {"$ne": "True"}}]
        if run_id_exclude:
            conditions.append({"run_id": {"$ne": run_id_exclude}})
        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        # --- Hybrid search path ---
        if use_hybrid:
            from memory.hybrid_search import HybridSearchEngine
            engine  = HybridSearchEngine()
            results = engine.search(collection, query, top_k=top_k, where_filter=where)
            return results

        # --- Fallback: vector-only ---
        try:
            active   = collection.get(where=where)
            n_active = len(active["ids"])
        except Exception:
            n_active = collection.count()

        if n_active == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, n_active),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            memories.append({
                "output":   doc,
                "task":     meta.get("task", ""),
                "run_id":   meta.get("run_id", ""),
                "success":  meta.get("success", "True") == "True",
                "expired":  meta.get("expired", "False") == "True",
                "distance": round(dist, 4),
            })

        return memories

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    def agent_memory_size(self, agent_name: str) -> int:
        if not self.available:
            return 0
        return self._get_collection(agent_name).count()

    def agent_active_memory_size(self, agent_name: str) -> int:
        """Count only non-expired memories."""
        if not self.available:
            return 0
        try:
            col     = self._get_collection(agent_name)
            results = col.get(where={"expired": {"$ne": "True"}})
            return len(results["ids"])
        except Exception:
            return 0

    def list_agents(self) -> list[str]:
        if not self.available:
            return []
        return [c.name for c in self.client.list_collections()]
