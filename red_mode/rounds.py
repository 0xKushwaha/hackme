"""
Rounds — Red Mode Tournament Architecture
============================================
Hierarchical 2-stage debate replacing the flat 3-round structure.

Stage A: Panel Debates (1 LLM call per group, all groups parallel)
  - Each group of ~5 personas debates in a single prompt.
  - The LLM role-plays all members and identifies the strongest position.
  - Champion is elected from the output.

Stage B: Champion Cross-Debate (1 LLM call per champion, all parallel)
  - Each champion responds to the other groups' panel summaries.

Stage C: Synthesis (1 LLM call — unchanged)
  - Moderator synthesises the champion debate.

Total: ~9 LLM calls (down from 41).

Execution model:
  asyncio.run() from worker thread — creates its own event loop.
  asyncio.gather() — groups fire simultaneously, semaphore gates concurrency.
  Retry: exponential backoff + jitter on rate-limit errors.
"""
from __future__ import annotations

import asyncio
import random
from langchain_core.messages import HumanMessage, SystemMessage


# ── Config ────────────────────────────────────────────────────────────
MAX_CONCURRENT = 8    # semaphore: max concurrent API calls at any moment
MAX_RETRIES    = 4    # per-call retry limit
PANEL_TRUNC    = 600  # chars — each panel output truncated for champion context
CHAMP_TRUNC    = 500  # chars — each champion response truncated for synthesis


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
                wait = (2 ** attempt) + random.uniform(0.2, 1.5)
                await asyncio.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded: {last_err}")


# ── Prompts ───────────────────────────────────────────────────────────

_PANEL_SYSTEM = """\
You are moderating a panel debate between {n} AI/ML experts.
Your job is to role-play EACH expert authentically based on their profiles below.

For each panelist, produce their response under a clearly labeled header.
Stay true to each expert's thinking style, priorities, and communication patterns.

After all panelists respond, add a final section identifying which panelist
made the strongest, most substantive case.

PANELIST PROFILES:
{profiles_block}

OUTPUT FORMAT (follow exactly):

## [{NAME_1}]
(their authentic response — direct, opinionated, in their voice)

## [{NAME_2}]
(their authentic response)

...

## STRONGEST POSITION: [{name_of_winner}]
(1-2 sentences explaining why this position was strongest)\
"""

_PANEL_USER = """\
ANALYSIS BRIEF:
{brief}

---
Each panelist should address:
**What stands out to me:** (immediate instinctive reaction)
**What everyone is probably missing:** (contrarian angle)
**The assumption I'd challenge:** (pick ONE claim from the brief and push back)
**What I'd actually do:** (concrete recommendation)

Be specific. Reference actual details from the brief. Don't hedge.\
"""

_CHAMPION_SYSTEM = """\
{persona_prompt}

You were selected as the strongest voice from your panel group ({group_label}).
Now you're debating against champions from other expert groups.
Stay in character. Be direct and opinionated.\
"""

_CHAMPION_USER = """\
ORIGINAL ANALYSIS BRIEF:
{brief}

YOUR GROUP'S FULL PANEL DEBATE:
{my_panel}

OTHER GROUPS' PANEL SUMMARIES:
{others_block}

---
Now engage with the other groups' positions:
**I disagree with [group/person] because:** (pick ONE specific position from another group)
**[Group/person] got something right — here's what they missed:** (extend one point further)
**What ALL groups collectively missed:** (the angle the entire debate missed)
**My final recommendation:** (concrete, actionable, in your voice)\
"""

_SYNTHESIS_SYSTEM = """\
You are a neutral debate moderator synthesizing a multi-group tournament debate.
Four expert groups debated independently, then their champions cross-debated.
Your job is NOT to declare a winner — it is to extract signal from noise.

Output EXACTLY this structure (no deviation):

## Consensus Points
(Things 3+ groups implicitly or explicitly agree on — even if phrased differently)
- [point] — supported by [group names]

## Live Disagreements
(Unresolved genuine conflicts between groups or champions)
- [Group A champion] vs [Group B champion]: [what they disagree about and why both have merit]

## Action Items (ranked by confidence)
1. [Highest agreement action] — endorsed by [N] groups
2. ...

## The Minority Report
(Takes from the panel debates that nobody else agreed with but might be right)
- [Expert name] from [Group]: [their contrarian position and why it shouldn't be dismissed]

## Bottom Line
(2-3 sentences. What should the practitioner do FIRST, based on this debate?)\
"""


# ── Stage A: Panel Debates — one call per group, all parallel ────────

async def _panel_debate_async(
    group_key:    str,
    group_label:  str,
    member_names: list[str],
    personas:     dict[str, str],   # handle → system prompt text
    brief:        str,
    llm,
    semaphore:    asyncio.Semaphore,
    on_group_start: callable | None = None,
    on_group_done:  callable | None = None,
) -> dict:
    """
    Run one panel debate for a single group.
    All members debate in a single LLM call — the LLM role-plays each.
    Returns: { "output": str, "champion": str, "members": list[str] }
    """
    from red_mode.grouping import elect_champion

    # Notify frontend that this group is starting
    if on_group_start:
        on_group_start(group_key, member_names)

    # Build merged profiles block from persona .md content
    profiles = []
    for name in member_names:
        display = name.replace("_", " ").title()
        prompt = personas.get(name, "")
        # Take first ~1500 chars of the persona prompt for the panel
        truncated = prompt[:1500] + ("…" if len(prompt) > 1500 else "")
        profiles.append(f"### {display}\n{truncated}")

    profiles_block = "\n\n---\n\n".join(profiles)
    system = _PANEL_SYSTEM.format(n=len(member_names), profiles_block=profiles_block)
    user   = _PANEL_USER.format(brief=brief)

    output = await _acall(system, user, llm, semaphore)

    # Elect champion from the output
    champion = elect_champion(output, member_names)

    if on_group_done:
        on_group_done(group_key, champion, output)

    return {
        "output":   output,
        "champion": champion,
        "members":  member_names,
    }


async def _all_panels_async(
    groups:    dict[str, list[str]],
    personas:  dict[str, str],
    brief:     str,
    llm,
    semaphore: asyncio.Semaphore,
    on_group_start: callable | None = None,
    on_group_done:  callable | None = None,
) -> dict[str, dict]:
    """
    Run all group panels in parallel.
    Returns: { group_key: { "output", "champion", "members" } }
    """
    from red_mode.grouping import group_label as get_label

    async def run_one(gk: str, members: list[str]):
        result = await _panel_debate_async(
            group_key    = gk,
            group_label  = get_label(gk),
            member_names = members,
            personas     = personas,
            brief        = brief,
            llm          = llm,
            semaphore    = semaphore,
            on_group_start = on_group_start,
            on_group_done  = on_group_done,
        )
        return gk, result

    pairs = await asyncio.gather(
        *[run_one(gk, members) for gk, members in groups.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Stage B: Champion Cross-Debate — one call per champion ───────────

def _build_others_panels(
    my_group: str,
    panel_results: dict[str, dict],
) -> str:
    """Build truncated summaries of other groups' panel outputs."""
    from red_mode.grouping import group_label as get_label

    blocks = []
    for gk, result in panel_results.items():
        if gk == my_group:
            continue
        label = get_label(gk)
        champion = result["champion"].replace("_", " ").title()
        output = result["output"][:PANEL_TRUNC]
        if len(result["output"]) > PANEL_TRUNC:
            output += "…"
        blocks.append(f"### {label} (Champion: {champion})\n{output}")

    return "\n\n---\n\n".join(blocks)


async def _champion_debate_async(
    panel_results: dict[str, dict],
    personas:      dict[str, str],
    brief:         str,
    llm,
    semaphore:     asyncio.Semaphore,
    on_champ_start: callable | None = None,
    on_champ_done:  callable | None = None,
) -> dict[str, str]:
    """
    Each champion responds to all other groups' positions.
    Returns: { champion_handle: response_text }
    """
    from red_mode.grouping import group_label as get_label

    async def call_one(gk: str, result: dict) -> tuple[str, str]:
        champion = result["champion"]
        persona_prompt = personas.get(champion, "")

        if on_champ_start:
            on_champ_start(champion, gk)

        system = _CHAMPION_SYSTEM.format(
            persona_prompt = persona_prompt,
            group_label    = get_label(gk),
        )
        user = _CHAMPION_USER.format(
            brief        = brief,
            my_panel     = result["output"][:PANEL_TRUNC * 2],
            others_block = _build_others_panels(gk, panel_results),
        )

        response = await _acall(system, user, llm, semaphore)

        if on_champ_done:
            on_champ_done(champion, gk, response)

        return champion, response

    pairs = await asyncio.gather(
        *[call_one(gk, result) for gk, result in panel_results.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Stage C: Final Synthesis — single call ───────────────────────────

async def _synthesis_async(
    panel_results:   dict[str, dict],
    champion_debate: dict[str, str],
    llm,
    semaphore:       asyncio.Semaphore,
) -> str:
    """Single synthesis call over all panel + champion outputs."""
    from red_mode.grouping import group_label as get_label

    debate_block = ""
    for gk, result in panel_results.items():
        label    = get_label(gk)
        champion = result["champion"]
        display  = champion.replace("_", " ").title()
        panel    = result["output"][:CHAMP_TRUNC]
        champ_r  = champion_debate.get(champion, "")[:CHAMP_TRUNC]

        debate_block += (
            f"\n## {label}\n"
            f"**Panel debate (5 experts):** {panel}…\n"
            f"**Champion ({display}) cross-debate:** {champ_r}…\n"
            f"---\n"
        )

    return await _acall(
        _SYNTHESIS_SYSTEM,
        f"FULL TOURNAMENT DEBATE:\n{debate_block}",
        llm,
        semaphore,
    )


# ── Main entry point ─────────────────────────────────────────────────

async def run_tournament_async(
    groups:          dict[str, list[str]],
    personas:        dict[str, str],
    brief:           str,
    llm,
    fast_llm,
    on_stage_start:  callable | None = None,  # on_stage_start("groups" | "champions" | "synthesis")
    on_group_start:  callable | None = None,  # on_group_start(group_key, member_names)
    on_group_done:   callable | None = None,  # on_group_done(group_key, champion, output)
    on_champ_start:  callable | None = None,  # on_champ_start(champion_handle, group_key)
    on_champ_done:   callable | None = None,  # on_champ_done(champion_handle, group_key, response)
    on_synth_start:  callable | None = None,  # on_synth_start()
) -> dict:
    """
    Run the full tournament debate:
      Stage A: Group panels (parallel, 1 call each)  — full LLM
      Stage B: Champion cross-debate (parallel, 1 call each) — full LLM
      Stage C: Synthesis (1 call) — full LLM
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # ── Stage A: Group Panels ─────────────────────────────────────────
    if on_stage_start:
        on_stage_start("groups")

    panel_results = await _all_panels_async(
        groups         = groups,
        personas       = personas,
        brief          = brief,
        llm            = llm,
        semaphore      = semaphore,
        on_group_start = on_group_start,
        on_group_done  = on_group_done,
    )

    # ── Stage B: Champion Cross-Debate ────────────────────────────────
    if on_stage_start:
        on_stage_start("champions")

    champion_debate = await _champion_debate_async(
        panel_results  = panel_results,
        personas       = personas,
        brief          = brief,
        llm            = llm,
        semaphore      = semaphore,
        on_champ_start = on_champ_start,
        on_champ_done  = on_champ_done,
    )

    # ── Stage C: Synthesis ────────────────────────────────────────────
    if on_synth_start:
        on_synth_start()

    synthesis = await _synthesis_async(
        panel_results, champion_debate, llm, semaphore,
    )

    return {
        "panels":          panel_results,
        "champion_debate": champion_debate,
        "synthesis":       synthesis,
    }
