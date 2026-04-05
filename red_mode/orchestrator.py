"""
Red Mode Orchestrator — Tournament Architecture
=================================================
Runs the real multi-agent persona tournament debate:

  Stage A:       Each persona responds independently (all parallel, fast_llm)
  Stage A-elect: Champion elected per group by LLM judge (parallel, fast_llm)
  Stage B:       Champion cross-debate — each champion reads others' positions (parallel, full llm)
  Stage C:       Final synthesis + verdict (1 LLM call, full llm)

Total: ~29 LLM calls (20 personas × 1 round + 4 elections + 4 champion debates + 1 synthesis).

Stdout markers (parsed by RedRunState in server.py):
  [RED_STAGE:groups]              — Stage A starting (individual persona round)
  [RED_GROUP:theory]              — specific group starting
  [PERSONA:andrej_karpathy]       — individual persona responding (Stage A or B)
  [PERSONA_DONE:andrej_karpathy]  — individual persona done
  [RED_STAGE:election]            — Stage A-elect starting (champion elections)
  [RED_CHAMPION:andrej_karpathy]  — champion elected for a group
  [RED_GROUP_DONE:theory]         — group election complete
  [RED_STAGE:champions]           — Stage B starting (champion cross-debate)
  [RED_SYNTHESIS]                 — Stage C starting
  [RED_SYNTHESIS_DONE]            — synthesis done
  [RED_MODE_DONE]                 — complete
"""
from __future__ import annotations

import asyncio
import sys
from red_mode.persona_loader import load_personas, persona_display_name
from red_mode.grouping       import group_personas, group_label, TRAIT_GROUPS
from red_mode.rounds         import run_tournament_async


class RedModeOrchestrator:
    """
    Orchestrates the tournament debate using fully async parallel calls.
    Reuses the same LLM backend as Phase 1 — no new dependencies.

    asyncio.run() is called here — safe because this runs in a worker thread
    (FastAPI's main loop is in the main thread, not here).
    """

    def __init__(self, llm, fast_llm=None):
        self.llm      = llm
        self.fast_llm = fast_llm or llm

    # ── Public entry point ────────────────────────────────────────────

    def run(self, persona_names: list[str], brief: str) -> dict:
        """
        Run the full tournament debate.
        Blocks until all stages complete.
        Returns structured results dict.
        """
        personas = load_personas(persona_names)
        groups   = group_personas(persona_names)
        n_groups = len(groups)
        n_total  = len(personas)

        print(f"\n🔴 RED MODE — Tournament Debate ({n_total} Experts, {n_groups} Groups)\n")
        for gk, members in groups.items():
            label = group_label(gk)
            names = ", ".join(persona_display_name(m) for m in members)
            print(f"   {label}: {names}")
        print()
        sys.stdout.flush()

        # ── Callbacks for live stdout streaming ───────────────────────

        n_personas = sum(len(m) for m in groups.values())

        def on_stage_start(stage: str):
            print(f"[RED_STAGE:{stage}]")
            labels = {
                "groups":    f"STAGE A — Individual Persona Round  ({n_personas} parallel calls)",
                "election":  f"STAGE A-elect — Champion Election  ({n_groups} parallel calls)",
                "champions": f"STAGE B — Champion Cross-Debate  ({n_groups} parallel calls)",
                "synthesis": "STAGE C — Final Synthesis + Verdict",
            }
            print(f"\n{'─'*60}")
            print(f"  {labels.get(stage, stage.upper())}")
            print(f"{'─'*60}\n")
            sys.stdout.flush()

        def on_group_start(group_key: str, member_names: list[str]):
            label = group_label(group_key)
            print(f"[RED_GROUP:{group_key}]")
            print(f"\n  ▶ {label} — {len(member_names)} experts responding independently\n")
            sys.stdout.flush()

        def on_persona_start(persona_name: str, group_key: str):
            display = persona_display_name(persona_name)
            print(f"[PERSONA:{persona_name}]")
            print(f"  → {display} responding…")
            sys.stdout.flush()

        def on_persona_done(persona_name: str, group_key: str, output: str):
            display = persona_display_name(persona_name)
            print(output)
            print(f"\n[PERSONA_DONE:{persona_name}]")
            sys.stdout.flush()

        def on_champion_elected(group_key: str, champion: str):
            label   = group_label(group_key)
            display = persona_display_name(champion)
            print(f"  ★ {label} champion: {display}")
            print(f"[RED_CHAMPION:{champion}]")
            sys.stdout.flush()

        def on_group_done(group_key: str, champion: str, election_output: str):
            label = group_label(group_key)
            print(f"\n  ✓ {label} election complete")
            print(f"[RED_GROUP_DONE:{group_key}]")
            print()
            sys.stdout.flush()

        def on_champ_start(champion: str, group_key: str):
            display = persona_display_name(champion)
            label   = group_label(group_key)
            print(f"[PERSONA:{champion}]")
            print(f"\n  ▶ {display} ({label}) entering cross-debate\n")
            sys.stdout.flush()

        def on_champ_done(champion: str, group_key: str, response: str):
            print(response)
            print(f"\n[PERSONA_DONE:{champion}]")
            sys.stdout.flush()

        def on_synth_start():
            print(f"[RED_SYNTHESIS]")
            print(f"\n  Synthesising tournament debate across {n_groups} groups…\n")
            sys.stdout.flush()

        # ── Run tournament ────────────────────────────────────────────
        results = asyncio.run(
            run_tournament_async(
                groups               = groups,
                personas             = personas,
                brief                = brief,
                llm                  = self.llm,
                fast_llm             = self.fast_llm,
                on_stage_start       = on_stage_start,
                on_group_start       = on_group_start,
                on_persona_start     = on_persona_start,
                on_persona_done      = on_persona_done,
                on_champion_elected  = on_champion_elected,
                on_group_done        = on_group_done,
                on_champ_start       = on_champ_start,
                on_champ_done        = on_champ_done,
                on_synth_start       = on_synth_start,
            )
        )

        panel_results   = results["panels"]
        champion_debate = results["champion_debate"]
        synthesis       = results["synthesis"]

        # ── Print synthesis output ────────────────────────────────────
        print(synthesis)
        print(f"\n[RED_SYNTHESIS_DONE]")

        print(f"\n{'─'*60}")
        print(f"  RED MODE COMPLETE")
        print(f"{'─'*60}")
        print(f"\n[RED_MODE_DONE]")
        sys.stdout.flush()

        # ── Build result ──────────────────────────────────────────────
        group_results = {}
        champions_list = []
        for gk, result in panel_results.items():
            group_results[gk] = {
                "label":           group_label(gk),
                "members":         result["members"],
                "round1":          result.get("round1", {}),
                "election_output": result.get("election_output", ""),
                "champion":        result["champion"],
            }
            champions_list.append(result["champion"])

        return {
            "personas":        list(personas.keys()),
            "groups":          group_results,
            "champions":       champions_list,
            "champion_debate": champion_debate,
            "synthesis":       synthesis,
        }
