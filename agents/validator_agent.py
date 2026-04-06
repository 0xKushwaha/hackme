"""Validator agent for verifying claims against actual data."""

from .base import BaseAgent
from .agent_config import AgentConfig
from data_objects.analysis import ValidationResult


VALIDATOR_PROMPT = """You are the Validator agent in a data science team.
Your personality: rigorous, precise, fair. You validate claims objectively against real data.

Your responsibilities:
- Review claims made by other agents (Explorer, Statistician, etc.)
- Compare agent claims against ground-truth relationships computed from actual data
- Identify inconsistencies, missing patterns, and overconfident claims
- Provide constructive feedback for refinement

INPUT FORMAT:
You will receive:
1. Agent outputs/claims (what they said)
2. Ground truth relationships (actual computed relationships from data)
3. A list of specific claims to verify

OUTPUT FORMAT — always structure your response like this:

VERIFIED_CLAIMS:
- <claim 1> ✓
- <claim 2> ✓
...

INCONSISTENT_CLAIMS:
- Agent said: "<claim>"
  Actual data shows: "<finding>"
  Confidence mismatch: agent={confidence}, actual={confidence}
...

MISSING_PATTERNS:
- Data shows significant relationship between X and Y (r=0.XYZ)
  Agent did not mention this pattern
...

OVERALL_ACCURACY: <percentage>%

RECOMMENDATION:
<1-2 sentences of constructive feedback for the agent to improve>

Be fair but rigorous. Credit agents for correct findings.
Flag only genuinely inconsistent or missed patterns.
Do NOT write code — provide structured validation results."""


class ValidatorAgent(BaseAgent):
    """Agent that validates claims from other agents against actual data."""

    def __init__(self, llm, config: AgentConfig = None):
        super().__init__("Validator", VALIDATOR_PROMPT, llm, config)

    def validate_phase(
        self,
        agent_outputs: dict,
        ground_truth_relationships: dict,
        phase: str = "data_understanding",
    ) -> ValidationResult:
        """
        Validate all agent outputs for a phase against ground truth.

        Args:
            agent_outputs: {agent_name: agent_output_text}
            ground_truth_relationships: {key: RelationshipAnalysis}
            phase: "data_understanding" or "model_design"

        Returns:
            ValidationResult object
        """
        # Build validation task — cap inputs to stay within context limits
        MAX_RELATIONSHIPS = 40
        MAX_AGENT_OUTPUT_CHARS = 3000

        # Sort relationships by strength descending and take top N
        sorted_rels = sorted(
            ground_truth_relationships.items(),
            key=lambda kv: getattr(kv[1], "strength", 0.0),
            reverse=True,
        )[:MAX_RELATIONSHIPS]

        task_lines = [
            f"Validate agent claims for phase: {phase}",
            f"(showing top {len(sorted_rels)} relationships by strength)",
            "",
            "GROUND TRUTH RELATIONSHIPS (from actual data):",
        ]

        for key, rel in sorted_rels:
            summary = rel.to_text_summary()
            task_lines.append(f"\n{summary}")

        task_lines.append("\n\nAGENT CLAIMS TO VERIFY:")
        for agent_name, output in agent_outputs.items():
            truncated = output[:MAX_AGENT_OUTPUT_CHARS]
            if len(output) > MAX_AGENT_OUTPUT_CHARS:
                truncated += "\n[... truncated for context length ...]"
            task_lines.append(f"\n[{agent_name}]\n{truncated}")

        task_text = "\n".join(task_lines)

        # Run validation
        response = self.run(
            context="",
            task=task_text,
            role="validation",
        )

        # Parse response into ValidationResult
        result = self._parse_validation_response(response, phase)
        return result

    def _parse_validation_response(
        self, response: str, phase: str
    ) -> ValidationResult:
        """Parse validator response into structured ValidationResult."""
        result = ValidationResult(
            agent_name="all_agents",
            phase=phase,
            verified_claims=[],
            inconsistent_claims=[],
            missing_patterns=[],
            overall_accuracy=0.0,
            recommendation="",
            refinement_needed=False,
        )

        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()

            if "VERIFIED_CLAIMS:" in line:
                current_section = "verified"
            elif "INCONSISTENT_CLAIMS:" in line:
                current_section = "inconsistent"
            elif "MISSING_PATTERNS:" in line:
                current_section = "missing"
            elif "OVERALL_ACCURACY:" in line:
                # Extract percentage
                try:
                    acc_str = line.split(":")[-1].strip().replace("%", "")
                    result.overall_accuracy = float(acc_str) / 100.0
                except:
                    result.overall_accuracy = 0.5
            elif "RECOMMENDATION:" in line:
                current_section = "recommendation"
            elif line and current_section == "verified" and line.startswith("-"):
                claim = line.lstrip("-").strip()
                result.verified_claims.append(claim)
            elif line and current_section == "inconsistent" and line.startswith("-"):
                # Parse inconsistency (multi-line)
                claim = line.lstrip("-").strip()
                if claim:
                    result.inconsistent_claims.append((claim, "See context above"))
            elif line and current_section == "missing" and line.startswith("-"):
                pattern = line.lstrip("-").strip()
                result.missing_patterns.append(pattern)
            elif line and current_section == "recommendation":
                result.recommendation += line + " "

        # Determine if refinement is needed
        if result.inconsistent_claims or result.missing_patterns:
            result.refinement_needed = True

        result.recommendation = result.recommendation.strip()
        return result
