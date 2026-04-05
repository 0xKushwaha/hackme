"""
Rounds — Red Mode Tournament Architecture
============================================
Real multi-agent debate: each persona speaks with their own LLM call.

Stage A  — Individual Persona Round (all personas in all groups, fully parallel)
  Each persona reads the brief and responds independently in their own voice.
  No persona sees another's response at this stage.
  Uses fast_llm to keep costs down.

Stage A-elect — Champion Election (1 LLM call per group, parallel)
  A judge LLM reads all Round 1 responses from one group and elects the
  strongest voice. Returns champion handle + reasoning.
  Uses fast_llm.

Stage B — Champion Cross-Debate (1 LLM call per champion, parallel)
  Each champion reads their own group's FULL Round 1 discussion.
  Each champion reads other groups' champion Round 1 responses.
  Champions push back on each other directly, by name.
  Uses full llm.

Stage C — Synthesis + Final Verdict (1 LLM call)
  Neutral moderator synthesises the full tournament into:
  Consensus, Disagreements, Action Items, Minority Report, Final Verdict.
  Uses full llm.

Total calls (20 personas, 4 groups):
  Stage A:       20  (all parallel, bounded by semaphore)
  Stage A-elect:  4  (parallel)
  Stage B:        4  (parallel)
  Stage C:        1
  ─────────────────
  Total:         29  (vs old 9 simulated calls — these are real)

Execution model:
  asyncio.run() from worker thread — creates its own event loop.
  asyncio.gather() — all stages use full parallelism within semaphore limits.
  Retry: exponential backoff + jitter on rate-limit errors.
  Per-persona errors are caught and replaced with fallback text — one bad
  API call never aborts the whole tournament.
"""
from __future__ import annotations

import asyncio
import random
from langchain_core.messages import HumanMessage, SystemMessage


# ── Config ─────────────────────────────────────────────────────────────
MAX_CONCURRENT = 8      # semaphore: max concurrent API calls at any moment
MAX_RETRIES    = 4      # per-call retry limit
OTHERS_TRUNC   = 900    # chars — other groups' champion response shown to each champion in Stage B


# ── Core async call with retry + jitter ────────────────────────────────

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


# ── Prompts ─────────────────────────────────────────────────────────────

_PERSONA_ROUND1_SYSTEM = """\
{persona_prompt}

You are participating in an expert panel debate about a data science analysis.
You are {display_name}. Your COMMUNICATION STYLE and RESPONSE FORMAT sections above \
describe exactly how you write — follow them precisely.
Do NOT write like a generic AI expert. Do NOT use identical bold headers that every other \
panelist will use. Write with your actual voice: your sentence rhythm, your characteristic \
phrases, your format preferences.
Be direct, opinionated, and specific. Reference actual numbers and claims from the brief.\
"""

_PERSONA_ROUND1_USER = """\
ANALYSIS BRIEF:
{brief}

---
Cover these four angles — but write in your own format, not a template:

1. Your sharpest immediate reaction to the most important finding
2. What everyone else here will probably overlook or dismiss too quickly
3. One specific claim from the brief you'd push back on hard — pick one and attack it
4. What you'd actually do first — concrete, specific, no hedging, in your voice

Do NOT number these 1-2-3-4 in your response. Do NOT write "What stands out to me:" or \
similar generic headers. The structure and format of your response should be distinctively yours.\
"""

_ELECTION_SYSTEM = """\
You are a debate judge reviewing {n} expert responses to the same analysis brief.
Your job is to identify which expert made the STRONGEST, most substantive argument.

Evaluate each response on:
1. Originality — did they surface something the others missed?
2. Specificity — concrete claims grounded in the analysis, not vague platitudes
3. Reasoning quality — the logic holds up under scrutiny
4. Actionability — their recommendation is actually useful and non-obvious

Output EXACTLY this format (no deviation):

## Review
[For each expert, one sentence on what they got right or wrong]

## Champion: [name here]
[2-3 sentences explaining why this position was strongest and what set it apart]\
"""

_ELECTION_USER = """\
ANALYSIS BRIEF:
{brief}

---
EXPERT RESPONSES:
{responses_block}\
"""

_CHAMPION_SYSTEM = """\
{persona_prompt}

You were selected as the strongest voice from your expert group ({group_label}).
You are now in the final cross-group debate against champions from 3 other groups.
You have read your group's full Round 1 discussion below. You know what your group argued.
Now engage with the other groups directly — agree where you must, attack where you should.
Stay in character. Be direct. Name names.\
"""

_CHAMPION_USER = """\
ORIGINAL ANALYSIS BRIEF:
{brief}

YOUR GROUP'S FULL ROUND 1 DISCUSSION:
{my_group_discussion}

OTHER GROUPS' CHAMPION POSITIONS:
{others_block}

---
Engage directly with the other groups:

**I disagree with [name/group] because:**
(Quote or closely paraphrase their specific claim, then refute it with your reasoning)

**[Name/group] got something right — here's what they missed:**
(Extend one of their points further than they took it)

**What ALL groups collectively missed:**
(The blind spot the entire debate has — the angle nobody addressed)

**My final recommendation:**
(The single most important thing the practitioner should do first — in your voice, no hedging)\
"""

_SYNTHESIS_SYSTEM = """\
You are a neutral debate moderator synthesizing a multi-group expert tournament.
Four groups debated independently. Each group elected a champion.
The champions then cross-debated each other.
Your job is to extract signal from all of this. Do NOT declare a winner.

Output EXACTLY this structure (no deviation, no extra sections):

## Consensus Points
(Things 3 or more groups implicitly or explicitly agreed on — even if phrased differently)
- [point] — supported by: [group or champion names]

## Live Disagreements
(Genuine unresolved conflicts worth caring about — both sides have a point)
- [Champion A] vs [Champion B]: [what they disagree on and why both perspectives have merit]

## Action Items (ranked by confidence)
1. [Highest-confidence action] — endorsed by N groups
2. [Second action]
3. [Third action]

## The Minority Report
(Positions nobody agreed with that might still be correct)
- [Expert name] from [Group]: [their contrarian position and why it should not be dismissed]

## Final Verdict
(One clear, direct recommendation — the single most important thing the practitioner should do
FIRST, based on the weight of this entire debate. No hedging. No "it depends". Just the call.)\
"""


# ── Stage A: Individual Persona Round ──────────────────────────────────

async def _persona_respond_async(
    persona_name:     str,
    persona_prompt:   str,
    group_key:        str,
    brief:            str,
    llm,
    semaphore:        asyncio.Semaphore,
    on_persona_start: callable | None = None,
    on_persona_done:  callable | None = None,
) -> tuple[str, str]:
    """
    One persona responds to the brief independently.
    Returns (persona_name, response_text).
    Errors are caught — a failed call produces a fallback string, never aborts.
    """
    display = persona_name.replace("_", " ").title()

    if on_persona_start:
        on_persona_start(persona_name, group_key)

    system = _PERSONA_ROUND1_SYSTEM.format(
        persona_prompt=persona_prompt,
        display_name=display,
    )
    user = _PERSONA_ROUND1_USER.format(brief=brief)

    try:
        response = await _acall(system, user, llm, semaphore)
    except Exception as exc:
        response = f"[{display} could not respond: {exc}]"

    if on_persona_done:
        on_persona_done(persona_name, group_key, response)

    return persona_name, response


async def _group_round1_async(
    group_key:        str,
    member_names:     list[str],
    personas:         dict[str, str],
    brief:            str,
    llm,
    semaphore:        asyncio.Semaphore,
    on_group_start:   callable | None = None,
    on_persona_start: callable | None = None,
    on_persona_done:  callable | None = None,
) -> dict[str, str]:
    """
    Fire all personas in a single group in parallel.
    Returns: { persona_name: response_text }
    """
    if on_group_start:
        on_group_start(group_key, member_names)

    tasks = [
        _persona_respond_async(
            persona_name     = name,
            persona_prompt   = personas.get(name, ""),
            group_key        = group_key,
            brief            = brief,
            llm              = llm,
            semaphore        = semaphore,
            on_persona_start = on_persona_start,
            on_persona_done  = on_persona_done,
        )
        for name in member_names
    ]

    pairs = await asyncio.gather(*tasks, return_exceptions=False)
    return dict(pairs)


async def _all_round1_async(
    groups:           dict[str, list[str]],
    personas:         dict[str, str],
    brief:            str,
    llm,
    semaphore:        asyncio.Semaphore,
    on_group_start:   callable | None = None,
    on_persona_start: callable | None = None,
    on_persona_done:  callable | None = None,
) -> dict[str, dict[str, str]]:
    """
    Fire ALL groups' Round 1 in parallel.
    Returns: { group_key: { persona_name: response_text } }
    """
    async def run_group(gk: str, members: list[str]):
        result = await _group_round1_async(
            group_key        = gk,
            member_names     = members,
            personas         = personas,
            brief            = brief,
            llm              = llm,
            semaphore        = semaphore,
            on_group_start   = on_group_start,
            on_persona_start = on_persona_start,
            on_persona_done  = on_persona_done,
        )
        return gk, result

    pairs = await asyncio.gather(
        *[run_group(gk, members) for gk, members in groups.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Stage A-elect: Champion Election ───────────────────────────────────

def _build_responses_block(
    member_names:   list[str],
    round1_outputs: dict[str, str],
) -> str:
    """Format all group member Round 1 responses for the election judge."""
    blocks = []
    for name in member_names:
        display  = name.replace("_", " ").title()
        response = round1_outputs.get(name, "[no response]")
        blocks.append(f"### {display} (handle: {name})\n{response}")
    return "\n\n---\n\n".join(blocks)


async def _elect_champion_async(
    group_key:           str,
    member_names:        list[str],
    round1_outputs:      dict[str, str],
    brief:               str,
    llm,
    semaphore:           asyncio.Semaphore,
    on_champion_elected: callable | None = None,
    on_group_done:       callable | None = None,
) -> dict:
    """
    One LLM call reads all Round 1 responses for a group and elects the champion.
    Falls back to mention-frequency if the LLM call fails.
    Returns: { "champion": str, "election_output": str, "round1": dict, "members": list }
    """
    from red_mode.grouping import elect_champion_from_election

    responses_block = _build_responses_block(member_names, round1_outputs)
    system = _ELECTION_SYSTEM.format(n=len(member_names))
    user   = _ELECTION_USER.format(brief=brief, responses_block=responses_block)

    try:
        election_output = await _acall(system, user, llm, semaphore)
    except Exception as exc:
        election_output = f"[Election call failed: {exc}]"

    champion = elect_champion_from_election(election_output, member_names)

    if on_champion_elected:
        on_champion_elected(group_key, champion)

    if on_group_done:
        on_group_done(group_key, champion, election_output)

    return {
        "champion":        champion,
        "election_output": election_output,
        "round1":          round1_outputs,
        "members":         member_names,
    }


async def _all_elections_async(
    groups:              dict[str, list[str]],
    all_round1:          dict[str, dict[str, str]],
    brief:               str,
    llm,
    semaphore:           asyncio.Semaphore,
    on_champion_elected: callable | None = None,
    on_group_done:       callable | None = None,
) -> dict[str, dict]:
    """
    Run champion elections for all groups in parallel.
    Returns: { group_key: { "champion", "election_output", "round1", "members" } }
    """
    async def run_one(gk: str, members: list[str]):
        result = await _elect_champion_async(
            group_key           = gk,
            member_names        = members,
            round1_outputs      = all_round1.get(gk, {}),
            brief               = brief,
            llm                 = llm,
            semaphore           = semaphore,
            on_champion_elected = on_champion_elected,
            on_group_done       = on_group_done,
        )
        return gk, result

    pairs = await asyncio.gather(
        *[run_one(gk, members) for gk, members in groups.items()],
        return_exceptions=False,
    )
    return dict(pairs)


# ── Stage B: Champion Cross-Debate ─────────────────────────────────────

def _build_my_group_discussion(
    member_names:   list[str],
    round1_outputs: dict[str, str],
) -> str:
    """Full Round 1 discussion from the champion's own group — no truncation."""
    blocks = []
    for name in member_names:
        display  = name.replace("_", " ").title()
        response = round1_outputs.get(name, "[no response]")
        blocks.append(f"### {display}\n{response}")
    return "\n\n---\n\n".join(blocks)


def _build_others_champions(
    my_group:      str,
    panel_results: dict[str, dict],
) -> str:
    """
    Other groups' champion Round 1 responses.
    Each is truncated to OTHERS_TRUNC chars to keep the context manageable
    while still giving each champion meaningful content to push back on.
    """
    from red_mode.grouping import group_label as get_label

    blocks = []
    for gk, result in panel_results.items():
        if gk == my_group:
            continue
        label    = get_label(gk)
        champion = result["champion"]
        display  = champion.replace("_", " ").title()
        response = result["round1"].get(champion, "[no response]")
        if len(response) > OTHERS_TRUNC:
            response = response[:OTHERS_TRUNC] + "…"
        blocks.append(f"### {label} — Champion: {display}\n{response}")

    return "\n\n---\n\n".join(blocks)


async def _champion_debate_async(
    panel_results:  dict[str, dict],
    personas:       dict[str, str],
    brief:          str,
    llm,
    semaphore:      asyncio.Semaphore,
    on_champ_start: callable | None = None,
    on_champ_done:  callable | None = None,
) -> dict[str, str]:
    """
    Each champion engages with other groups' champion positions.
    Returns: { champion_handle: response_text }
    """
    from red_mode.grouping import group_label as get_label

    async def call_one(gk: str, result: dict) -> tuple[str, str]:
        champion       = result["champion"]
        persona_prompt = personas.get(champion, "")
        member_names   = result["members"]
        round1_outputs = result["round1"]

        if on_champ_start:
            on_champ_start(champion, gk)

        system = _CHAMPION_SYSTEM.format(
            persona_prompt=persona_prompt,
            group_label=get_label(gk),
        )
        user = _CHAMPION_USER.format(
            brief               = brief,
            my_group_discussion = _build_my_group_discussion(member_names, round1_outputs),
            others_block        = _build_others_champions(gk, panel_results),
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


# ── Stage C: Final Synthesis + Verdict ─────────────────────────────────

async def _synthesis_async(
    panel_results:   dict[str, dict],
    champion_debate: dict[str, str],
    llm,
    semaphore:       asyncio.Semaphore,
) -> str:
    """Single synthesis call over all champion Round 1 positions + cross-debate responses."""
    from red_mode.grouping import group_label as get_label

    debate_block = ""
    for gk, result in panel_results.items():
        label    = get_label(gk)
        champion = result["champion"]
        display  = champion.replace("_", " ").title()

        champ_r1    = result["round1"].get(champion, "")[:OTHERS_TRUNC]
        champ_cross = champion_debate.get(champion, "")[:OTHERS_TRUNC]

        debate_block += (
            f"\n## {label} — Champion: {display}\n"
            f"**Round 1 position:** {champ_r1}…\n"
            f"**Cross-debate response:** {champ_cross}…\n"
            f"---\n"
        )

    return await _acall(
        _SYNTHESIS_SYSTEM,
        f"FULL TOURNAMENT DEBATE:\n{debate_block}",
        llm,
        semaphore,
    )


# ── Main entry point ────────────────────────────────────────────────────

async def run_tournament_async(
    groups:              dict[str, list[str]],
    personas:            dict[str, str],
    brief:               str,
    llm,
    fast_llm,
    on_stage_start:      callable | None = None,
    on_group_start:      callable | None = None,
    on_persona_start:    callable | None = None,
    on_persona_done:     callable | None = None,
    on_champion_elected: callable | None = None,
    on_group_done:       callable | None = None,
    on_champ_start:      callable | None = None,
    on_champ_done:       callable | None = None,
    on_synth_start:      callable | None = None,
) -> dict:
    """
    Run the full tournament debate.

    Stage A:       Individual persona round — fast_llm (all parallel)
    Stage A-elect: Champion election per group — fast_llm (parallel)
    Stage B:       Champion cross-debate — full llm (parallel)
    Stage C:       Synthesis + Final Verdict — full llm (1 call)
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # ── Stage A: Individual persona round ──────────────────────────────
    if on_stage_start:
        on_stage_start("groups")

    all_round1 = await _all_round1_async(
        groups           = groups,
        personas         = personas,
        brief            = brief,
        llm              = llm,
        semaphore        = semaphore,
        on_group_start   = on_group_start,
        on_persona_start = on_persona_start,
        on_persona_done  = on_persona_done,
    )

    # ── Stage A-elect: Champion election ───────────────────────────────
    if on_stage_start:
        on_stage_start("election")

    panel_results = await _all_elections_async(
        groups              = groups,
        all_round1          = all_round1,
        brief               = brief,
        llm                 = fast_llm,
        semaphore           = semaphore,
        on_champion_elected = on_champion_elected,
        on_group_done       = on_group_done,
    )

    # ── Stage B: Champion cross-debate ─────────────────────────────────
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

    # ── Stage C: Synthesis ─────────────────────────────────────────────
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
