"""
InferencePhase — generates an inference script and deployment architecture.

Agents (required): code_writer
Agents (optional): architect, storyteller

Outputs:
  inference_script  — standalone Python script for predictions
  inference_path    — path where the script was saved
  deployment_plan   — architect's serving + monitoring architecture
  narrative         — storyteller's final summary
"""

import os
import uuid

from memory.context_manager import ROLE_CODE, ROLE_PLAN, ROLE_NARRATIVE
from .base import BasePhase, PhaseResult


class InferencePhase(BasePhase):

    name = "inference"
    REQUIRED_AGENTS = ["code_writer"]

    def _run(
        self,
        metrics:             dict = None,
        training_succeeded:  bool = False,
        experiment_dir:      str  = "experiments",
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        metrics_str = str(metrics or {})
        status      = "succeeded" if training_succeeded else "failed"

        print("\n⚡ [Inference] Generating inference script...")

        # CodeWriter generates the inference script via task_override
        node_id = str(uuid.uuid4())[:12]
        ctx_str = orch.context.get_context_string()
        inference_code = orch.agents["code_writer"].run(
            context=ctx_str,
            dataset_path=None,
            target_col=None,
            node_id=node_id,
            run_id=orch.run_id,
            task_override=(
                "Generate a standalone inference script that:\n"
                "1. Loads the trained model from 'trained_model.pkl'\n"
                "2. Accepts a new CSV file path as a command-line argument\n"
                "3. Applies the EXACT SAME preprocessing pipeline used during training\n"
                "4. Outputs predictions to 'predictions.csv' with an 'id' and 'prediction' column\n"
                "5. Prints a summary of predictions to stdout\n"
                "Output ONLY Python code, no markdown fences, no explanations."
            ),
        )

        # Save inference script
        inference_path = os.path.join(experiment_dir, "inference.py")
        with open(inference_path, "w") as f:
            f.write(inference_code)
        print(f"[Inference] Script saved: {inference_path}")

        orch.context.add("code_writer", ROLE_CODE, f"[INFERENCE SCRIPT]\n{inference_code}")

        if orch.memory and orch._last_node_id:
            from memory.graph_store import INFORMED_BY
            orch.memory.graph_store.add_edge(orch._last_node_id, node_id, INFORMED_BY)
        orch._last_node_id = node_id

        # Architect designs deployment (optional)
        deployment_plan = ""
        if "architect" in orch.agents:
            print("\n⚡ [Inference] Architect designing deployment...")
            deployment_plan = orch.step(
                "architect",
                f"Design a production deployment architecture for this model. "
                f"Training {status}. Metrics: {metrics_str}.\n\n"
                "Cover: serving infrastructure (REST API vs. batch), latency requirements, "
                "model versioning, monitoring and alerting, rollback strategy, and scaling.",
                ROLE_PLAN,
            )

        # Storyteller writes final narrative (optional)
        narrative = ""
        if "storyteller" in orch.agents:
            print("\n⚡ [Inference] Storyteller writing final narrative...")
            narrative = orch.step(
                "storyteller",
                f"Write a compelling technical narrative summarizing the full pipeline:\n"
                f"Data understanding → Model design → Training ({status}) → Validation → Deployment.\n"
                f"Final metrics: {metrics_str}.\n"
                "Highlight key decisions, what worked, what didn't, and what you'd do differently.",
                ROLE_NARRATIVE,
            )

        return PhaseResult(
            phase_name=self.name,
            success=True,
            summary="Inference script generated. Deployment plan and narrative complete.",
            outputs={
                "inference_script": inference_code,
                "inference_path":   inference_path,
                "deployment_plan":  deployment_plan,
                "narrative":        narrative,
            },
        )
