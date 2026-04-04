"""
Rounds — Red Mode (Async, Optimised)
=====================================
Uses asyncio + LangChain's ainvoke() for true I/O concurrency.
A single shared asyncio.Semaphore gates all 3 rounds, preventing
rate-limit spikes at round boundaries.

Execution model:
  asyncio.run() called from the worker thread (safe — creates its own event loop)
  asyncio.gather(N coroutines) — all fire simultaneously, semaphore controls concurrency
  Retry: exponential backoff + jitter on rate-limit errors

Token budget:
  Round 1: 20 × ~800  tokens in  = ~16k
  Round 2: 20 × ~7500 tokens in  = ~150k  (R1 truncated to 500 chars each)
  Round 3:  1 × ~14k  tokens in  = ~14k
  Total: ~180k tokens / full run
"""
from __future__ import annotations

import asyncio
import random
from langchain_core.messages import HumanMessage, SystemMessage

# ── Config ────────────────────────────────────────────────────────────
MAX_CONCURRENT = 8    # semaphore: max concurrent API calls at any moment
MAX_RETRIES    = 4    # per-call retry limit
R1_TRUNC       = 500  # chars — each peer's R1 output truncated in R2 prompt
R2_TRUNC       = 400  # chars — each R1+R2 truncated in R3 synthesis prompt


# ── Core async call with retry + jitter ──────────────────────────────

async def _acall(
    system:    str,
    user:      str,
    llm,
    semaphore: asyncio.Semaphore,
) -> str:
    """
    Single LLM call, bounded by semaphore, with exponential backoff + jitter.
    Handles rate-limit (429) and overload errors gracefully.
    """
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            async with semaphore:
                response = await llm.ainvoke([
                    SystemMessage(content=system),
                    HumanMessage(content=user),
                ])
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()

        except Exception as e:
            last_err = e
            msg = str(e).lower()
            is_rate_err = any(x in msg for x in ("rate", "429", "too many", "overloaded", "capacity"))
            if is_rate_err and attempt < MAX_RETRIES - 1:
                # Exponential backoff: 1s, 2s, 4s + random jitter up to 1.5s
                wait = (2 ** attempt) + random.uniform(0.2, 1.5)
                await asyncio.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded: {last_err}")


# ── Round prompts ─────────────────────────────────────────────────────

_R1_USER = """\
ANALYSIS BRIEF:
{brief}

---
Respond as yourself. Be direct and authentic to your established views.

**What stands out to me:** (your immediate instinctive reaction)
**What everyone is probably missing:** (your contrarian angle — what nobody else will say)
**The assumption I'd challenge:** (pick ONE specific claim from the brief and push back hard)
**What I'd actually do:** (concrete recommendation in your own voice and style)

Be specific. Reference actual details from the brief. Don't hedge. Don't be diplomatic.\
"""

_R2_USER = """\
ORIGINAL ANALYSIS BRIEF:
{brief}

YOUR ROUND 1 TAKE:
{my_take}

YOUR COLLEAGUES' TAKES (summarised):
{others_block}

---
Now engage with the debate. Be yourself — opinionated, direct, in your own voice.

**I disagree with [name] because:** (pick ONE specific person you genuinely disagree with, say exactly why they're wrong)
**[Name] got something right — here's what they missed:** (extend one person's point further)
**What nobody said that should have been said:** (the angle the entire group collectively missed)

Don't be diplomatic. This is where real intellectual conflict should surface.\
"""

_R3_SYSTEM = """\
You are a neutral debate moderator synthesizing a multi-expert debate.
Your job is NOT to declare a winner — it is to extract signal from noise.

Output EXACTLY this structure (no deviation):

## Consensus Points
(Things 4+ experts implicitly or explicitly agree on — even if phrased differently)
- [point] — supported by [names]

## Live Disagreements
(Unresolved genuine conflicts — preserve them, don't paper them over)
- [Expert A] vs [Expert B]: [what they disagree about and why both positions have merit]

## Action Items (ranked by confidence)
1. [Highest agreement action] — endorsed by [N] experts
2. ...

## The Minority Report
(1-2 takes that nobody agreed with but might be right — preserve the dissent)
- [Expert name]: [their contrarian position and why it shouldn't be dismissed]

## Bottom Line
(2-3 sentences. What should the practitioner do FIRST, based on this debate?)\
"""


# ── Round 1: Independent takes — all parallel ─────────────────────────

async def _round_1_async(
    personas:  dict[str, str],
    brief:     str,
    llm,
    semaphore: asyncio.Semaphore,
    on_done:   callable | None = None,
) -> dict[str, str]:
    """
    All N personas respond independently in parallel.
    Results are emitted via on_done(name, result) as each call completes.
    asyncio.gather preserves all results even if individual calls are slow.
    """
    user_msg = _R1_USER.format(brief=brief)

    async def call_one(name: str, system: str) -> tuple[str, str]:
        result = await _acall(system, user_msg, llm, semaphore)
        if on_done:
            on_done(name, result)          # called immediately as it arrives
        return name, result

    pairs = await asyncio.gather(
        *[call_one(name, system) for name, system in personas.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Round 2: Cross-debate — all parallel ─────────────────────────────

def _build_others_block(my_name: str, round1: dict[str, str]) -> str:
    """
    Each peer's R1 output truncated to R1_TRUNC chars.
    This keeps R2 prompt under ~8k tokens regardless of N.
    """
    return "\n\n".join(
        f"[{n.upper().replace('_', ' ')}]:\n"
        f"{take[:R1_TRUNC]}{'…' if len(take) > R1_TRUNC else ''}"
        for n, take in round1.items()
        if n != my_name
    )


async def _round_2_async(
    personas:  dict[str, str],
    round1:    dict[str, str],
    brief:     str,
    llm,
    semaphore: asyncio.Semaphore,
    on_done:   callable | None = None,
) -> dict[str, str]:
    """
    Each persona reads truncated R1 from all others and responds.
    Uses fast_llm — debate responses don't need max quality, just voice fidelity.
    Same semaphore prevents rate spike at round boundary.
    """
    async def call_one(name: str, system: str) -> tuple[str, str]:
        user_msg = _R2_USER.format(
            brief        = brief,
            my_take      = round1.get(name, "")[:R1_TRUNC],
            others_block = _build_others_block(name, round1),
        )
        result = await _acall(system, user_msg, llm, semaphore)
        if on_done:
            on_done(name, result)
        return name, result

    pairs = await asyncio.gather(
        *[call_one(name, system) for name, system in personas.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Round 3: Synthesis — single call ────────────────────────────────

async def _round_3_async(
    round1:    dict[str, str],
    round2:    dict[str, str],
    llm,
    semaphore: asyncio.Semaphore,
) -> str:
    """
    Single synthesis call — no parallelism needed.
    R1+R2 each truncated to R2_TRUNC chars to fit full debate in one prompt.
    """
    debate_block = ""
    for name in round1:
        display = name.replace("_", " ").title()
        r1 = round1[name][:R2_TRUNC]
        r2 = round2.get(name, "")[:R2_TRUNC]
        debate_block += f"\n## {display}\n**R1:** {r1}…\n**R2:** {r2}…\n---\n"

    return await _acall(
        _R3_SYSTEM,
        f"FULL DEBATE:\n{debate_block}",
        llm,
        semaphore,
    )


# ── Main entry point ─────────────────────────────────────────────────

async def run_all_rounds_async(
    personas:        dict[str, str],
    brief:           str,
    llm,
    fast_llm,
    on_round_start:  callable | None = None,   # on_round_start(round_num: int)
    on_r1_done:      callable | None = None,   # on_r1_done(name, result)
    on_r2_done:      callable | None = None,   # on_r2_done(name, result)
    on_synth_start:  callable | None = None,   # on_synth_start()
) -> dict:
    """
    Runs all 3 rounds with a SINGLE shared semaphore across all rounds.
    This prevents burst spikes at round transitions — the API sees a steady
    stream of MAX_CONCURRENT requests throughout the entire run.

    Round 1: full llm    — best quality for initial takes
    Round 2: fast_llm   — cheaper, faster for debate responses
    Round 3: full llm    — synthesis needs quality
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # ── Round 1 ───────────────────────────────────────────────────────
    if on_round_start:
        on_round_start(1)
    round1 = await _round_1_async(personas, brief, llm, semaphore, on_done=on_r1_done)

    # ── Round 2 ───────────────────────────────────────────────────────
    if on_round_start:
        on_round_start(2)
    round2 = await _round_2_async(personas, round1, brief, fast_llm, semaphore, on_done=on_r2_done)

    # ── Round 3 ───────────────────────────────────────────────────────
    if on_synth_start:
        on_synth_start()
    synthesis = await _round_3_async(round1, round2, llm, semaphore)

    return {
        "round1":    round1,
        "round2":    round2,
        "synthesis": synthesis,
    }
