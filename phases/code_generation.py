"""
CodeGenerationPhase — generates training code, executes it, retries on failure.

This is the core retry loop. Each attempt:
  1. CodeWriter generates a Python training script
  2. CodeExecutor runs it as a subprocess (fresh process — picks up any new tool_registry files)
  3. On failure: memories from failed run are expired, devil_advocate + pragmatist revise
  4. Next attempt starts with a fresh run_id so memory scoping is correct

Tool registry integration:
  If a ToolRegistry is attached to the orchestrator, this phase injects available
  tools into the code_writer's task prompt so the LLM knows it can import them.
  The subprocess picks them up automatically because sys.path is extended at the
  top of the generated script.

Agents (required): code_writer
Agents (optional): devil_advocate, pragmatist (for failure recovery)
"""

import os
import uuid

from memory.context_manager import ROLE_PLAN
from memory.graph_store      import INFORMED_BY, RETRY_OF, FAILURE_LED_TO
from execution.context_guard import format_execution_result
from .base import BasePhase, PhaseResult


MAX_RETRIES = 4


class CodeGenerationPhase(BasePhase):

    name = "code_generation"
    REQUIRED_AGENTS = ["code_writer"]

    def _run(
        self,
        dataset_path:   str = "",
        target_col:     str = None,
        max_retries:    int = MAX_RETRIES,
        experiment_dir: str = "experiments",
        **kwargs,
    ) -> PhaseResult:
        orch = self.orch

        if not orch.executor:
            return PhaseResult(
                phase_name=self.name,
                success=False,
                summary="No CodeExecutor attached — cannot run code generation phase.",
                error="No CodeExecutor",
            )

        last_result    = None
        last_code_node = None
        last_run_id    = orch.run_id
        final_attempt  = 0

        for attempt in range(1, max_retries + 1):
            print(f"\n🔁 [CodeGeneration] Attempt {attempt}/{max_retries}")
            final_attempt = attempt

            if attempt > 1:
                orch.run_id = str(uuid.uuid4())[:12]
                print(f"   New run_id: {orch.run_id}")

            # Handle previous failure before generating new code
            if attempt > 1 and last_result:
                self._handle_failure(last_result, attempt, last_run_id, last_code_node)

            # Build task string, injecting tool_registry info if available
            tool_context = ""
            if hasattr(orch, "tool_registry") and orch.tool_registry:
                tool_context = orch.tool_registry.build_tool_context()

            task = (
                f"Dataset path : {dataset_path}\n"
                + (f"Target column: {target_col}\n" if target_col else "")
                + (f"\n{tool_context}\n" if tool_context else "")
                + "\nGenerate the complete training script. Output ONLY Python code, no markdown fences."
            )

            # Generate code
            node_id  = str(uuid.uuid4())[:12]
            ctx_str  = orch.context.get_context_string()
            code     = orch.agents["code_writer"].run(
                context=ctx_str,
                dataset_path=dataset_path,
                target_col=target_col,
                node_id=node_id,
                run_id=orch.run_id,
            )
            orch.context.add_code(code, attempt=attempt)
            last_code_node = node_id

            # Graph edge
            if orch.memory and orch._last_node_id:
                edge_type = RETRY_OF if attempt > 1 else INFORMED_BY
                orch.memory.graph_store.add_edge(orch._last_node_id, node_id, edge_type)
            orch._last_node_id = node_id

            # Save script to disk
            script_path = os.path.join(experiment_dir, f"train_attempt_{attempt}.py")
            with open(script_path, "w") as f:
                f.write(code)
            print(f"[EXECUTOR] Script saved: {script_path}")

            # Execute in subprocess — picks up any tool_registry files written this run
            result      = orch.executor.run(code, attempt=attempt)
            last_result = result
            last_run_id = orch.run_id

            # Apply context guard before storing output
            guarded = format_execution_result(
                result.stdout, result.stderr, result.metrics,
                result.success, orch.context_guard,
            )
            orch.context.add_result(guarded, result.metrics, result.success, attempt=attempt)

            print(f"\n{'✅' if result.success else '❌'} {result.short_summary()}")

            if result.success:
                break
        else:
            print(f"\n⚠️  All {max_retries} attempts failed.")

        return PhaseResult(
            phase_name=self.name,
            success=bool(last_result and last_result.success),
            summary=(
                f"Training {'succeeded' if last_result and last_result.success else 'failed'}. "
                f"Metrics: {last_result.metrics if last_result else 'N/A'}"
            ),
            outputs={
                "execution_result": last_result,
                "metrics":          last_result.metrics if last_result else {},
                "attempts":         final_attempt,
                "succeeded":        bool(last_result and last_result.success),
            },
        )

    # ------------------------------------------------------------------ #
    # Failure recovery                                                     #
    # ------------------------------------------------------------------ #

    def _handle_failure(self, result, attempt: int, failed_run_id: str, failed_code_node: str = None):
        orch = self.orch

        failure_summary = (
            f"Training attempt {attempt - 1} FAILED.\n"
            f"Error type : {result.error_type}\n"
            f"Error msg  : {result.error_msg}\n"
            f"Stderr     : {result.stderr[:500]}"
        )

        # Expire memories from the failed run — agents won't repeat that approach
        if orch.memory:
            orch.memory.expire_run(failed_run_id)

        # Devil's Advocate re-evaluates the failure (optional)
        if "devil_advocate" in orch.agents:
            da_node = str(uuid.uuid4())[:12]
            print("\n😈 [CodeGeneration] Devil's Advocate analyzing failure...")
            da_response = orch.agents["devil_advocate"].run(
                context=orch.context.get_context_string(),
                task=(
                    f"{failure_summary}\n\n"
                    "What went wrong? What fundamental assumption was violated? "
                    "Propose a completely different modeling approach."
                ),
                node_id=da_node,
                run_id=orch.run_id,
                role=ROLE_PLAN,
            )
            orch.context.add("devil_advocate", ROLE_PLAN, da_response)

            if orch.memory and failed_code_node:
                orch.memory.graph_store.add_edge(failed_code_node, da_node, FAILURE_LED_TO)
            orch._last_node_id = da_node

        # Pragmatist revises the plan (optional)
        if "pragmatist" in orch.agents:
            print("\n📋 [CodeGeneration] Pragmatist revising plan...")
            orch.step(
                "pragmatist",
                f"{failure_summary}\n\nRevise the modeling plan. Be concrete about exactly what "
                "to change. Specify a different model, different preprocessing, or different "
                "approach entirely.",
                ROLE_PLAN,
            )
