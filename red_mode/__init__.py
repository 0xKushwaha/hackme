# Red Mode — Persona Tournament Debate Engine
# Phase 2 of the DS Agent Team pipeline.
# 20 real-world AI/ML experts grouped by expertise, debating in a
# hierarchical tournament: group panels → champion election → cross-debate → synthesis.
from red_mode.orchestrator import RedModeOrchestrator
from red_mode.grouping    import TRAIT_GROUPS, group_personas

__all__ = ["RedModeOrchestrator", "TRAIT_GROUPS", "group_personas"]
