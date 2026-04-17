"""
LangGraph tournament graph for Red Mode.

Replaces asyncio.gather() coordination in rounds.py with an explicit graph:

  stage_a → [Send × N personas] → stage_b → [Send × G groups] → stage_c
          → [Send × G champions] → synthesis → END

The Send API expresses fan-out parallelism structurally instead of with
asyncio.gather() calls. A shared semaphore (created in stage_a) flows
through state so all concurrent LLM calls respect MAX_CONCURRENT.
"""

import asyncio
from typing import Annotated, Any, Optional

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from red_mode.rounds import (
    _acall,
    MAX_CONCURRENT,
    OTHERS_TRUNC,
    _PERSONA_ROUND1_SYSTEM,
    _PERSONA_ROUND1_USER,
    _ELECTION_SYSTEM,
    _ELECTION_USER,
    _CHAMPION_SYSTEM,
    _CHAMPION_USER,
    _SYNTHESIS_SYSTEM,
    _build_responses_block,
    _build_my_group_discussion,
    _build_others_champions,
)
from red_mode.grouping import elect_champion_from_election, group_label as get_label


# ── Reducer — deep-merges nested dicts as fan-out nodes write partial results ──

def _deep_merge(a: dict, b: dict) -> dict:
    result = dict(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ── State schema ───────────────────────────────────────────────────────────────

class TournamentState(TypedDict):
    groups:          dict[str, list[str]]
    personas:        dict[str, str]
    brief:           str
    semaphore:       Any                           # asyncio.Semaphore — set in stage_a
    round1_results:  Annotated[dict, _deep_merge]  # {gk: {persona_name: response}}
    panel_results:   Annotated[dict, _deep_merge]  # {gk: {champion, election_output, ...}}
    champion_debate: Annotated[dict, _deep_merge]  # {champion_name: response}
    synthesis:       str


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_tournament_graph(llm, fast_llm, callbacks: dict = None):
    """
    Build and compile the async tournament graph.

    callbacks keys (all optional):
      on_stage_start, on_group_start, on_persona_start, on_persona_done,
      on_champion_elected, on_group_done, on_champ_start, on_champ_done,
      on_synth_start
    """
    cb = callbacks or {}
    on_stage_start      = cb.get("on_stage_start")
    on_group_start      = cb.get("on_group_start")
    on_persona_start    = cb.get("on_persona_start")
    on_persona_done     = cb.get("on_persona_done")
    on_champion_elected = cb.get("on_champion_elected")
    on_group_done       = cb.get("on_group_done")
    on_champ_start      = cb.get("on_champ_start")
    on_champ_done       = cb.get("on_champ_done")
    on_synth_start      = cb.get("on_synth_start")

    # ── Stage A: Individual Persona Round ─────────────────────────────────────

    async def node_stage_a(state: TournamentState) -> dict:
        if on_stage_start:
            on_stage_start("groups")
        # Semaphore must be created inside the event loop — stored in state so
        # all concurrent persona nodes share it for correct MAX_CONCURRENT enforcement.
        return {"semaphore": asyncio.Semaphore(MAX_CONCURRENT)}

    def fanout_personas(state: TournamentState) -> list[Send]:
        sends = []
        for group_key, members in state["groups"].items():
            if on_group_start:
                on_group_start(group_key, members)
            for persona_name in members:
                sends.append(Send("node_persona", {
                    "persona_name": persona_name,
                    "group_key":    group_key,
                    "personas":     state["personas"],
                    "brief":        state["brief"],
                    "semaphore":    state["semaphore"],
                }))
        return sends

    async def node_persona(state: dict) -> dict:
        persona_name = state["persona_name"]
        group_key    = state["group_key"]
        semaphore    = state["semaphore"]
        display      = persona_name.replace("_", " ").title()

        if on_persona_start:
            on_persona_start(persona_name, group_key)

        system = _PERSONA_ROUND1_SYSTEM.format(
            persona_prompt=state["personas"].get(persona_name, ""),
            display_name=display,
        )
        user = _PERSONA_ROUND1_USER.format(brief=state["brief"])

        try:
            response = await _acall(system, user, fast_llm, semaphore)
        except Exception as exc:
            response = f"[{display} could not respond: {exc}]"

        if on_persona_done:
            on_persona_done(persona_name, group_key, response)

        return {"round1_results": {group_key: {persona_name: response}}}

    # ── Stage A-elect: Champion Election ──────────────────────────────────────

    def node_stage_b(state: TournamentState) -> dict:
        if on_stage_start:
            on_stage_start("election")
        return {}

    def fanout_elections(state: TournamentState) -> list[Send]:
        return [
            Send("node_election", {
                "group_key":     group_key,
                "member_names":  members,
                "brief":         state["brief"],
                "round1_results": state["round1_results"],
                "semaphore":     state["semaphore"],
            })
            for group_key, members in state["groups"].items()
        ]

    async def node_election(state: dict) -> dict:
        group_key    = state["group_key"]
        member_names = state["member_names"]
        round1       = state["round1_results"].get(group_key, {})
        semaphore    = state["semaphore"]

        responses_block = _build_responses_block(member_names, round1)
        system = _ELECTION_SYSTEM.format(n=len(member_names))
        user   = _ELECTION_USER.format(brief=state["brief"], responses_block=responses_block)

        try:
            election_output = await _acall(system, user, fast_llm, semaphore)
        except Exception as exc:
            election_output = f"[Election call failed: {exc}]"

        champion = elect_champion_from_election(election_output, member_names)

        if on_champion_elected:
            on_champion_elected(group_key, champion)
        if on_group_done:
            on_group_done(group_key, champion, election_output)

        return {
            "panel_results": {
                group_key: {
                    "champion":        champion,
                    "election_output": election_output,
                    "round1":          round1,
                    "members":         member_names,
                }
            }
        }

    # ── Stage B: Champion Cross-Debate ────────────────────────────────────────

    def node_stage_c(state: TournamentState) -> dict:
        if on_stage_start:
            on_stage_start("champions")
        return {}

    def fanout_champions(state: TournamentState) -> list[Send]:
        return [
            Send("node_champion", {
                "group_key":    group_key,
                "panel_results": state["panel_results"],
                "personas":     state["personas"],
                "brief":        state["brief"],
                "semaphore":    state["semaphore"],
            })
            for group_key in state["groups"]
        ]

    async def node_champion(state: dict) -> dict:
        group_key     = state["group_key"]
        panel_results = state["panel_results"]
        semaphore     = state["semaphore"]

        result   = panel_results[group_key]
        champion = result["champion"]

        if on_champ_start:
            on_champ_start(champion, group_key)

        system = _CHAMPION_SYSTEM.format(
            persona_prompt=state["personas"].get(champion, ""),
            group_label=get_label(group_key),
        )
        user = _CHAMPION_USER.format(
            brief               = state["brief"],
            my_group_discussion = _build_my_group_discussion(result["members"], result["round1"]),
            others_block        = _build_others_champions(group_key, panel_results),
        )

        response = await _acall(system, user, llm, semaphore)

        if on_champ_done:
            on_champ_done(champion, group_key, response)

        return {"champion_debate": {champion: response}}

    # ── Stage C: Synthesis + Final Verdict ───────────────────────────────────

    async def node_synthesis(state: TournamentState) -> dict:
        if on_synth_start:
            on_synth_start()

        semaphore    = state["semaphore"]
        panel        = state["panel_results"]
        champ_debate = state["champion_debate"]

        debate_block = ""
        for gk, result in panel.items():
            label    = get_label(gk)
            champion = result["champion"]
            display  = champion.replace("_", " ").title()
            champ_r1    = result["round1"].get(champion, "")[:OTHERS_TRUNC]
            champ_cross = champ_debate.get(champion, "")[:OTHERS_TRUNC]
            debate_block += (
                f"\n## {label} — Champion: {display}\n"
                f"**Round 1 position:** {champ_r1}…\n"
                f"**Cross-debate response:** {champ_cross}…\n"
                f"---\n"
            )

        synthesis = await _acall(
            _SYNTHESIS_SYSTEM,
            f"FULL TOURNAMENT DEBATE:\n{debate_block}",
            llm,
            semaphore,
        )
        return {"synthesis": synthesis}

    # ── Wire the graph ────────────────────────────────────────────────────────

    graph = StateGraph(TournamentState)
    graph.add_node("stage_a",       node_stage_a)
    graph.add_node("node_persona",  node_persona)
    graph.add_node("stage_b",       node_stage_b)
    graph.add_node("node_election", node_election)
    graph.add_node("stage_c",       node_stage_c)
    graph.add_node("node_champion", node_champion)
    graph.add_node("node_synthesis", node_synthesis)

    graph.set_entry_point("stage_a")
    graph.add_conditional_edges("stage_a",  fanout_personas)
    graph.add_edge("node_persona",   "stage_b")
    graph.add_conditional_edges("stage_b",  fanout_elections)
    graph.add_edge("node_election",  "stage_c")
    graph.add_conditional_edges("stage_c",  fanout_champions)
    graph.add_edge("node_champion",  "node_synthesis")
    graph.add_edge("node_synthesis", END)

    return graph.compile()
