"""
HybridSearchEngine — BM25 + vector similarity + temporal decay + MMR re-ranking.

Ported from OpenClaw's src/memory/hybrid.ts, temporal-decay.ts, and mmr.ts.

Pipeline per query:
  1. Fetch all active docs from ChromaDB (for BM25 corpus)
  2. Score each doc with BM25 (keyword match)
  3. Score top candidates with ChromaDB vector similarity
  4. Normalize both to [0, 1], combine with configurable weights
  5. Multiply by temporal decay (role-dependent half-life, evergreen exemptions)
  6. MMR re-ranking for diversity (Jaccard similarity between candidates)
"""

import math
import re
from datetime import datetime
from typing import Optional

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[HybridSearch] rank-bm25 not installed — falling back to vector-only search.")


# ------------------------------------------------------------------ #
# Weights and thresholds                                               #
# ------------------------------------------------------------------ #

VECTOR_WEIGHT = 0.45    # ChromaDB cosine similarity weight
TEXT_WEIGHT   = 0.55    # BM25 keyword weight
MMR_LAMBDA    = 0.7     # λ: relevance vs diversity (1.0 = pure relevance)

# Role → half-life in days for temporal decay
# Evergreen roles are exempt (score multiplier = 1.0)
EVERGREEN_ROLES = {"dataset_context", "narrative", "meta"}

HALF_LIFE_DAYS: dict[str, float] = {
    "code":     90.0,   # successful scripts last long — reuse is good
    "plan":     30.0,   # plans stay relevant for a month
    "analysis": 30.0,
    "result":   14.0,   # execution results age out faster
    "error":     3.0,   # error memories decay fast — avoid anchoring on old failures
}
DEFAULT_HALF_LIFE = 30.0


# ------------------------------------------------------------------ #
# Tokenizer                                                            #
# ------------------------------------------------------------------ #

# Simple stop words (OpenClaw supports 7 languages; we start with EN)
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "not", "no", "nor", "so", "yet",
    "both", "either", "neither", "each", "few", "more", "most", "this",
    "that", "these", "those", "it", "its", "i", "you", "he", "she", "we",
    "they", "what", "which", "who", "whom", "how", "when", "where", "why",
}

def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


# ------------------------------------------------------------------ #
# Temporal decay                                                       #
# ------------------------------------------------------------------ #

def _age_in_days(timestamp: str) -> float:
    if not timestamp:
        return 0.0
    try:
        ts  = datetime.fromisoformat(timestamp)
        age = (datetime.now() - ts).total_seconds() / 86400.0
        return max(0.0, age)
    except Exception:
        return 0.0


def temporal_decay(age_days: float, role: str) -> float:
    """
    Exponential decay: score * e^(-λ * age_days)
    λ = ln(2) / half_life  →  score halves every `half_life` days.
    Evergreen roles always return 1.0.
    """
    if role in EVERGREEN_ROLES or age_days <= 0:
        return 1.0
    half_life = HALF_LIFE_DAYS.get(role, DEFAULT_HALF_LIFE)
    lambda_   = math.log(2) / half_life
    return math.exp(-lambda_ * age_days)


# ------------------------------------------------------------------ #
# MMR re-ranking                                                       #
# ------------------------------------------------------------------ #

def _jaccard(a: frozenset, b: frozenset) -> float:
    """Matches OpenClaw mmr.ts jaccardSimilarity exactly."""
    if not a and not b:
        return 1.0   # both empty → identical
    if not a or not b:
        return 0.0   # one empty → no overlap
    intersection = len(a & b)
    union = len(a) + len(b) - intersection
    return intersection / union if union > 0 else 0.0


def mmr_rerank(candidates: list[dict], top_k: int, lambda_: float = MMR_LAMBDA) -> list[dict]:
    """
    Maximal Marginal Relevance (Carbonell & Goldstein, 1998):
      Select next item = argmax[ λ * relevance - (1-λ) * max_sim_to_selected ]

    Matches OpenClaw's mmr.ts exactly:
      - Scores normalized to [0,1] before comparison (fair vs Jaccard similarity)
      - Token cache pre-built for O(n) lookups instead of O(n²) tokenization
      - Original score used as tiebreaker
    """
    if len(candidates) <= top_k:
        return candidates

    # Clamp lambda
    lam = max(0.0, min(1.0, lambda_))

    # Normalize scores to [0, 1]
    scores    = [c["score"] for c in candidates]
    max_score = max(scores)
    min_score = min(scores)
    score_range = max_score - min_score

    def normalize(s: float) -> float:
        return 1.0 if score_range == 0 else (s - min_score) / score_range

    # Pre-build token cache (id → frozenset of tokens)
    token_cache: dict[int, frozenset] = {
        i: frozenset(_tokenize(c["output"]))
        for i, c in enumerate(candidates)
    }

    selected_idx: list[int] = []
    remaining    = list(range(len(candidates)))

    while len(selected_idx) < top_k and remaining:
        best_mmr  = float("-inf")
        best_i    = remaining[0]

        for i in remaining:
            norm_rel = normalize(candidates[i]["score"])
            toks_i   = token_cache[i]

            max_sim = max(
                (_jaccard(toks_i, token_cache[s]) for s in selected_idx),
                default=0.0,
            )
            mmr = lam * norm_rel - (1 - lam) * max_sim

            # Tiebreak: prefer higher original score
            if mmr > best_mmr or (
                mmr == best_mmr and candidates[i]["score"] > candidates[best_i]["score"]
            ):
                best_mmr = mmr
                best_i   = i

        selected_idx.append(best_i)
        remaining.remove(best_i)

    return [candidates[i] for i in selected_idx]


# ------------------------------------------------------------------ #
# Main hybrid search engine                                            #
# ------------------------------------------------------------------ #

class HybridSearchEngine:
    """
    Combines BM25 keyword search with ChromaDB vector similarity,
    applies temporal decay per memory role, then MMR re-ranks for diversity.
    """

    def __init__(
        self,
        vector_weight: float = VECTOR_WEIGHT,
        text_weight:   float = TEXT_WEIGHT,
        mmr_lambda:    float = MMR_LAMBDA,
    ):
        self.vector_weight = vector_weight
        self.text_weight   = text_weight
        self.mmr_lambda    = mmr_lambda

    def search(
        self,
        collection,
        query:        str,
        top_k:        int            = 3,
        where_filter: Optional[dict] = None,
    ) -> list[dict]:
        """
        Run hybrid search against a ChromaDB collection.
        Returns list of dicts: {output, task, run_id, success, expired, distance, score}
        """
        # --- Step 1: Fetch all active docs for BM25 corpus ---
        try:
            corpus = collection.get(
                where=where_filter,
                include=["documents", "metadatas", "ids"],
            )
        except Exception:
            return []

        if not corpus["ids"]:
            return []

        ids   = corpus["ids"]
        docs  = corpus["documents"]
        metas = corpus["metadatas"]

        # --- Step 2: BM25 scoring ---
        bm25_scores = self._bm25_score(query, docs)

        # --- Step 3: Vector scoring ---
        vector_score_map = self._vector_score(collection, query, ids, where_filter)

        # Normalize BM25 using OpenClaw's bm25RankToScore formula
        # score = relevance / (1 + relevance) for negative ranks, 1/(1+rank) for positive
        max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1.0
        # We use simple max-normalization since rank_bm25 returns raw scores (always >= 0)

        # --- Step 4: Combine + temporal decay ---
        candidates = []
        for i, (doc_id, doc, meta) in enumerate(zip(ids, docs, metas)):
            v_score = vector_score_map.get(doc_id, 0.0)
            b_score = bm25_scores[i] / max_bm25

            hybrid  = self.vector_weight * v_score + self.text_weight * b_score

            # Temporal decay based on role
            role      = meta.get("role", "analysis")
            timestamp = meta.get("timestamp", "")
            age_days  = _age_in_days(timestamp)
            decay     = temporal_decay(age_days, role)

            final_score = hybrid * decay

            candidates.append({
                "output":   doc,
                "task":     meta.get("task", ""),
                "run_id":   meta.get("run_id", ""),
                "success":  meta.get("success", "True") == "True",
                "expired":  meta.get("expired", "False") == "True",
                "score":    final_score,
                "distance": round(1 - v_score, 4),   # approximate distance
                "age_days": round(age_days, 1),
                "role":     role,
            })

        # Sort by combined score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # --- Step 5: MMR re-ranking ---
        return mmr_rerank(candidates, top_k, self.mmr_lambda)

    # ---------------------------------------------------------------- #
    # Internal helpers                                                   #
    # ---------------------------------------------------------------- #

    def _bm25_score(self, query: str, docs: list[str]) -> list[float]:
        if not BM25_AVAILABLE or not docs:
            return [0.0] * len(docs)
        try:
            tokenized = [_tokenize(doc) for doc in docs]
            bm25      = BM25Okapi(tokenized)
            return list(bm25.get_scores(_tokenize(query)))
        except Exception:
            return [0.0] * len(docs)

    def _vector_score(
        self,
        collection,
        query:        str,
        ids:          list[str],
        where_filter: Optional[dict],
    ) -> dict[str, float]:
        """Query ChromaDB for vector similarity. Returns id → similarity score [0,1]."""
        n = min(len(ids), max(30, len(ids)))
        try:
            results = collection.query(
                query_texts=[query],
                n_results=n,
                where=where_filter,
                include=["ids", "distances"],
            )
            # Convert distance to similarity: 1/(1+d) so 0 distance → 1.0
            return {
                doc_id: 1.0 / (1.0 + dist)
                for doc_id, dist in zip(
                    results["ids"][0],
                    results["distances"][0],
                )
            }
        except Exception:
            return {}
