"""Agent for discovering mathematical and compositional constraints."""

from .base import BaseAgent
from .agent_config import AgentConfig
from analysis.constraint_detector import ConstraintDiscoveryEngine
from data_objects.analysis import ConstraintAnalysis, Constraint


CONSTRAINT_DISCOVERY_PROMPT = """You are the Constraint Discovery agent in a data science team.
Your personality: systematic, mathematical, pattern-oriented. You uncover hidden structure.

Your responsibilities:
- Identify mathematical relationships between features (A = B + C, A = B * C, etc.)
- Discover compositional structure (components that sum/combine to totals)
- Find linear dependencies and hierarchical relationships
- Distinguish between compositional features and causal relationships
- Validate constraints against actual data

INPUT:
You will receive automatically discovered constraints from computational analysis:
- Stage 1: Rank analysis (linear dependencies detected)
- Stage 2: Algebraic detection (candidate relationships found)
- Stage 3: Residual analysis (alternative operations tested)
- Stage 4: Statistical validation (p-values computed)

YOUR TASK:
1. Review all discovered constraints
2. Interpret what each constraint means for the dataset
3. Assess whether constraints are compositional (legitimate structure) or leakage
4. For CSIRO biomass: identify if components sum to totals (e.g., gdm = green + clover)
5. Provide business interpretation

OUTPUT FORMAT:

VALIDATED_COMPOSITIONAL_CONSTRAINTS:
- <constraint> (R²=X, confidence=Y)
  Components: [list]
  Interpretation: <what this means>
...

REJECTED_CONSTRAINTS:
- <false positive constraint> - Reason: <why it's spurious>
...

DATASET_STRUCTURE_INTERPRETATION:
<Describe the compositional hierarchy if any>
Example:
  Dry_Total = Dry_GDM + Dry_Dead
  Dry_GDM = Dry_Green + Dry_Clover + Dry_Legume + Dry_Grass

IMPLICATIONS_FOR_MODELING:
- <implication 1>
- <implication 2>
...

CONFIDENCE: High/Medium/Low
NOTES: <Any edge cases or uncertainties>"""


class ConstraintDiscoveryAgent(BaseAgent):
    """Discovers mathematical and compositional constraints in datasets."""

    def __init__(self, llm, config: AgentConfig = None):
        super().__init__(
            "ConstraintDiscovery",
            CONSTRAINT_DISCOVERY_PROMPT,
            llm,
            config,
        )

    def discover_constraints(
        self,
        enable_stage1: bool = True,
        enable_stage2: bool = True,
        enable_stage3: bool = True,
        enable_stage4: bool = True,
    ) -> ConstraintAnalysis:
        """
        Run constraint discovery pipeline on dataset.

        Args:
            enable_stage*: Control which discovery stages to run

        Returns:
            ConstraintAnalysis object with discovered constraints
        """
        if self.dataset is None:
            print("[ConstraintDiscovery] No dataset available")
            return ConstraintAnalysis(
                interpretation="No dataset provided"
            )

        print("\n🔍 [ConstraintDiscovery] Running constraint discovery pipeline...")

        # Run computational discovery
        engine = ConstraintDiscoveryEngine(self.dataset)
        results = engine.discover_all_constraints(
            enable_stage1=enable_stage1,
            enable_stage2=enable_stage2,
            enable_stage3=enable_stage3,
            enable_stage4=enable_stage4,
        )

        # Convert results to ConstraintAnalysis
        analysis = ConstraintAnalysis(
            rank_deficiency=results.get("stage1_rank_analysis", {}).get("rank_deficiency", 0),
            has_compositional_structure=results.get("stage1_rank_analysis", {}).get("has_dependencies", False),
            stage1_rank=results.get("stage1_rank_analysis"),
            stage2_candidates=results.get("stage2_algebraic", []),
            stage3_residuals=results.get("stage3_residual", []),
            stage4_statistical=results.get("stage4_statistical", []),
        )

        # Carry pivot info into the analysis so to_text_summary can report it
        if engine.pivot_info:
            analysis.pivot_info = engine.pivot_info

        # Convert stage4 results to Constraint objects
        for stat_result in results.get("stage4_statistical", []):
            if stat_result.get("valid"):
                constraint = Constraint(
                    formula=f"{stat_result['target']} = sum({stat_result['components']})",
                    strength=stat_result.get("r_squared", 0),
                    type="additive",
                    components=stat_result.get("components", []),
                    target=stat_result.get("target", ""),
                    details=stat_result,
                    validated=True,
                    confidence=stat_result.get("confidence", "medium"),
                )
                analysis.validated_constraints.append(constraint)

        # Convert stage2 results to discovered constraints
        for algebraic in results.get("stage2_algebraic", [])[:5]:
            constraint = Constraint(
                formula=algebraic.get("formula", ""),
                strength=algebraic.get("r_squared", 0),
                type=algebraic.get("type", ""),
                components=algebraic.get("components", []),
                target=algebraic.get("target", ""),
                details=algebraic,
                validated=False,
                confidence="medium",
            )
            analysis.discovered_constraints.append(constraint)

        # Mark as verified
        analysis.mark_verified(
            method="computational_discovery",
            details={"stages_run": 4},
            notes="Discovered via rank analysis, algebraic detection, residual analysis, statistical testing"
        )

        analysis.interpretation = results.get("summary", "")

        return analysis

    def run(self, context: str, task: str, **kwargs) -> str:
        """
        Run constraint discovery and get agent interpretation.

        Args:
            context: Previous analysis context
            task: Task description (usually constraint discovery prompt)

        Returns:
            Formatted text summary
        """
        # First, run computational discovery
        analysis = self.discover_constraints()

        if not analysis.validated_constraints:
            summary = "No compositional constraints discovered."
        else:
            summary = analysis.to_text_summary()

        # Now run LLM to interpret results
        print("[ConstraintDiscovery] Getting LLM interpretation...")

        # Build interpretation task
        interpretation_task = (
            f"{task}\n\n"
            f"DISCOVERED CONSTRAINTS:\n"
            f"{summary}\n\n"
            f"Now interpret these results and provide your analysis."
        )

        # Call parent run method (which calls LLM)
        llm_response = super().run(
            context=context,
            task=interpretation_task,
            **kwargs,
        )

        # Combine computational results with LLM interpretation
        full_output = f"{summary}\n\n## LLM INTERPRETATION:\n{llm_response}"

        # Store analysis in repository if available
        if self.data_repository:
            self.data_repository.add_constraint_analysis(analysis)

        return full_output
