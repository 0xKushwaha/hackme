"""
Red Mode Orchestrator — Tournament Architecture
=================================================
Runs the hierarchical 2-stage persona debate:

  Stage A: 4 group panel debates (parallel, 1 LLM call each)
  Stage B: Champion cross-debate (parallel, 1 LLM call each)
  Stage C: Final synthesis (1 LLM call)

Total: 9 LLM calls.

Stdout markers (parsed by RedRunState in server.py):
  [RED_STAGE:groups]              — group panels starting
  [RED_GROUP:theory]              — specific group starting
  [PERSONA:andrej_karpathy]       — persona active in group panel
  [PERSONA_DONE:andrej_karpathy]  — persona spoke (panel parsed)
  [RED_GROUP_DONE:theory]         — group panel complete
  [RED_CHAMPION:andrej_karpathy]  — champion elected
  [RED_STAGE:champions]           — champion cross-debate starting
  [PERSONA:andrej_karpathy]       — champion debating
  [PERSONA_DONE:andrej_karpathy]  — champion done
  [RED_SYNTHESIS]                 — synthesis starting
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

        def on_stage_start(stage: str):
            print(f"[RED_STAGE:{stage}]")
            labels = {
                "groups":    f"STAGE A — Group Panel Debates  ({n_groups} parallel calls)",
                "champions": f"STAGE B — Champion Cross-Debate  ({n_groups} parallel calls)",
                "synthesis": "STAGE C — Final Synthesis",
            }
            print(f"\n{'─'*60}")
            print(f"  {labels.get(stage, stage.upper())}")
            print(f"{'─'*60}\n")
            sys.stdout.flush()

        def on_group_start(group_key: str, member_names: list[str]):
            label = group_label(group_key)
            print(f"[RED_GROUP:{group_key}]")
            # Emit PERSONA markers for all members in this group
            for name in member_names:
                print(f"[PERSONA:{name}]")
            print(f"\n  ▶ {label} — {len(member_names)} experts debating\n")
            sys.stdout.flush()

        def on_group_done(group_key: str, champion: str, output: str):
            label = group_label(group_key)
            display = persona_display_name(champion)
            # Mark all group members as done
            members = groups.get(group_key, [])
            for name in members:
                print(f"[PERSONA_DONE:{name}]")
            print(f"\n  ✓ {label} complete")
            print(f"  ★ Champion elected: {display}")
            print(f"[RED_CHAMPION:{champion}]")
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
            display = persona_display_name(champion)
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
                groups         = groups,
                personas       = personas,
                brief          = brief,
                llm            = self.llm,
                fast_llm       = self.fast_llm,
                on_stage_start = on_stage_start,
                on_group_start = on_group_start,
                on_group_done  = on_group_done,
                on_champ_start = on_champ_start,
                on_champ_done  = on_champ_done,
                on_synth_start = on_synth_start,
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
                "label":        group_label(gk),
                "members":      result["members"],
                "panel_output": result["output"],
                "champion":     result["champion"],
            }
            champions_list.append(result["champion"])

        return {
            "personas":        list(personas.keys()),
            "groups":          group_results,
            "champions":       champions_list,
            "champion_debate": champion_debate,
            "synthesis":       synthesis,
        }
