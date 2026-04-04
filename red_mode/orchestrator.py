"""
Red Mode Orchestrator
=====================
Runs the 3-round persona debate and emits stdout markers
that the server's Tee captures — same pattern as Phase 1.

Stdout markers:
  [RED_ROUND:1]              — round starting
  [PERSONA:handle_name]      — persona speaking
  [PERSONA_DONE:handle_name] — persona finished
  [RED_SYNTHESIS]            — synthesis starting
  [RED_SYNTHESIS_DONE]       — synthesis done
  [RED_MODE_DONE]            — full debate complete

The RedRunState in server.py parses these markers in real-time.
The frontend polls /api/red-mode/poll/{id} to get live updates.
"""
from __future__ import annotations

import asyncio
import sys
from red_mode.persona_loader import load_personas, persona_display_name
from red_mode.rounds import run_all_rounds_async


class RedModeOrchestrator:
    """
    Orchestrates the 3-round debate using fully async parallel calls.
    Reuses the same LLM backend as Phase 1 — no new dependencies.

    All 3 rounds share a single asyncio.Semaphore(8) to prevent rate spikes.
    asyncio.run() is called here — safe because this runs in a worker thread
    (FastAPI's main loop is in the main thread, not here).
    """

    def __init__(self, llm, fast_llm=None):
        self.llm      = llm
        self.fast_llm = fast_llm or llm  # fast tier used for Round 2 (cheaper responses)

    # ── Public entry point ────────────────────────────────────────────

    def run(self, persona_names: list[str], brief: str) -> dict:
        """
        Run the full debate.
        Blocks until all 3 rounds complete.
        Returns structured results dict.
        """
        personas = load_personas(persona_names)
        n = len(personas)

        print(f"\n🔴 RED MODE — {n} Experts Debate The Analysis\n")
        print(f"   Personas: {', '.join(persona_display_name(p) for p in personas)}\n")
        sys.stdout.flush()

        # ── Callbacks for live stdout streaming ───────────────────────

        def on_round_start(round_num: int):
            print(f"[RED_ROUND:{round_num}]")
            labels = {
                1: f"ROUND 1 — Independent Takes  ({n} parallel calls)",
                2: f"ROUND 2 — Cross-Debate  ({n} parallel calls)",
                3: "ROUND 3 — Synthesis",
            }
            print(f"\n{'─'*60}")
            print(f"  {labels.get(round_num, f'ROUND {round_num}')}")
            print(f"{'─'*60}\n")
            sys.stdout.flush()

        def on_r1_done(name: str, result: str):
            display = persona_display_name(name)
            print(f"[PERSONA:{name}]")
            print(f"\n  ▶ {display} responded\n")
            print(result)
            print(f"\n[PERSONA_DONE:{name}]")
            sys.stdout.flush()

        def on_r2_done(name: str, result: str):
            display = persona_display_name(name)
            print(f"[PERSONA:{name}]")
            print(f"\n  ▶ {display} responds to the group\n")
            print(result)
            print(f"\n[PERSONA_DONE:{name}]")
            sys.stdout.flush()

        def on_synth_start():
            print(f"[RED_SYNTHESIS]")
            print(f"\n  Synthesising {n} takes across 2 rounds of debate…\n")
            sys.stdout.flush()

        # ── Run all rounds (async, parallel, single semaphore) ────────
        results = asyncio.run(
            run_all_rounds_async(
                personas       = personas,
                brief          = brief,
                llm            = self.llm,
                fast_llm       = self.fast_llm,
                on_round_start = on_round_start,
                on_r1_done     = on_r1_done,
                on_r2_done     = on_r2_done,
                on_synth_start = on_synth_start,
            )
        )

        round1_results = results["round1"]
        round2_results = results["round2"]
        synthesis      = results["synthesis"]

        # ── Print synthesis output ────────────────────────────────────
        print(synthesis)
        print(f"\n[RED_SYNTHESIS_DONE]")

        print(f"\n{'─'*60}")
        print(f"  RED MODE COMPLETE")
        print(f"{'─'*60}")
        print(f"\n[RED_MODE_DONE]")
        sys.stdout.flush()

        return {
            "personas":  list(personas.keys()),
            "round1":    round1_results,
            "round2":    round2_results,
            "synthesis": synthesis,
        }
