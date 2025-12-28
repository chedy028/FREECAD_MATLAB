"""Orchestrator state machine - autonomous iteration loop"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from agent.llm.openrouter_client import OpenRouterClient
from agent.llm.prompts.system_prompt import (
    FAILURE_RECOVERY_PROMPT,
    INITIAL_PLANNING_PROMPT,
    ITERATION_PLANNING_PROMPT,
    SYSTEM_PROMPT,
)
from agent.orchestrator.scoring import ConvergenceChecker, ObjectiveScorer
from agent.orchestrator.validators import (
    DesignIteration,
    IterationResult,
    RunState,
    RunStatus,
)
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


class AgentOrchestrator:
    """Autonomous agent orchestrator - implements state machine"""

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        freecad_runner: FreeCADRunner,
        matlab_runner: MATLABRunner,
        runs_base_dir: Path,
        convergence_epsilon: float = 0.001,
        convergence_stable_iters: int = 3,
    ):
        self.llm = openrouter_client
        self.freecad = freecad_runner
        self.matlab = matlab_runner
        self.runs_base_dir = runs_base_dir
        self.convergence_checker = ConvergenceChecker(
            epsilon=convergence_epsilon,
            stable_iterations=convergence_stable_iters,
        )

        # State
        self.current_run_id: Optional[UUID] = None
        self.current_state: RunState = RunState.PLAN
        self.conversation_history: List[Dict] = []
        self.iteration_history: List[IterationResult] = []
        self.consecutive_failures: int = 0

    def _get_run_dir(self, run_id: UUID) -> Path:
        """Get run directory"""
        return self.runs_base_dir / str(run_id)

    def _get_iteration_dir(self, run_id: UUID, iteration: int) -> Path:
        """Get iteration directory"""
        return self._get_run_dir(run_id) / f"iter_{iteration:03d}"

    async def start_run(
        self, user_request: str, run_id: Optional[UUID] = None
    ) -> RunStatus:
        """
        Start a new autonomous run.
        
        Args:
            user_request: User's design request
            run_id: Optional run ID (generated if not provided)
        
        Returns:
            Initial RunStatus
        """
        if run_id is None:
            run_id = uuid4()

        self.current_run_id = run_id
        self.current_state = RunState.PLAN
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": INITIAL_PLANNING_PROMPT.format(user_request=user_request),
            },
        ]
        self.iteration_history = []
        self.consecutive_failures = 0
        self.convergence_checker = ConvergenceChecker()

        # Create run directory
        run_dir = self._get_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        return RunStatus(
            run_id=run_id,
            state=self.current_state,
            started_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

    async def step(self) -> Optional[IterationResult]:
        """
        Execute one step of the state machine.
        
        Returns:
            IterationResult if iteration completed, None if more steps needed
        """
        if self.current_state == RunState.PLAN:
            return await self._state_plan()
        elif self.current_state == RunState.BUILD_CAD:
            return await self._state_build_cad()
        elif self.current_state == RunState.SIMULATE:
            return await self._state_simulate()
        elif self.current_state == RunState.EVALUATE:
            return await self._state_evaluate()
        elif self.current_state == RunState.DECIDE:
            return await self._state_decide()
        elif self.current_state == RunState.FAIL_RECOVERY:
            return await self._state_fail_recovery()
        else:
            # Terminal states
            return None

    async def _state_plan(self) -> None:
        """PLAN state: LLM proposes next DesignIteration"""
        # Call LLM to get DesignIteration JSON
        response = await self.llm.chat_completion_with_retry(
            messages=self.conversation_history,
            model="openai/gpt-4o",  # TODO: Get from current design or config
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        assistant_msg = self.llm.get_assistant_message(response)
        if not assistant_msg:
            raise RuntimeError("LLM did not return a message")

        # Parse DesignIteration
        try:
            design_spec = json.loads(assistant_msg)
            self.current_design = DesignIteration(**design_spec)
        except Exception as e:
            # Parsing failed, add error to conversation and retry
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_msg,
            })
            self.conversation_history.append({
                "role": "user",
                "content": f"Error parsing DesignIteration: {e}. Please output valid JSON matching the schema.",
            })
            # Stay in PLAN state
            return

        # Successfully planned, move to BUILD_CAD
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_msg,
        })
        self.current_state = RunState.BUILD_CAD
        self.iteration_start_time = datetime.utcnow()

    async def _state_build_cad(self) -> None:
        """BUILD_CAD state: Generate CAD geometry"""
        iteration = self.current_design.iteration
        iter_dir = self._get_iteration_dir(self.current_run_id, iteration)
        cad_dir = iter_dir / "cad"

        # Run FreeCAD
        self.cad_result = await self.freecad.build_cad(
            self.current_design.cad, cad_dir
        )

        if self.cad_result.success:
            self.current_state = RunState.SIMULATE
        else:
            self.current_state = RunState.FAIL_RECOVERY

    async def _state_simulate(self) -> None:
        """SIMULATE state: Run MATLAB simulation"""
        iteration = self.current_design.iteration
        iter_dir = self._get_iteration_dir(self.current_run_id, iteration)
        sim_dir = iter_dir / "simulation"

        # Run MATLAB
        self.sim_result = await self.matlab.run_matlab(
            self.current_design.simulation,
            self.cad_result.path,
            sim_dir,
        )

        if self.sim_result.success:
            self.current_state = RunState.EVALUATE
        else:
            self.current_state = RunState.FAIL_RECOVERY

    async def _state_evaluate(self) -> IterationResult:
        """EVALUATE state: Compute objective and constraints"""
        # Compute objective score
        score = ObjectiveScorer.compute_objective_score(
            self.current_design.objectives,
            self.sim_result.metrics,
        )

        # Evaluate constraints
        constraints_ok, violations = ObjectiveScorer.evaluate_constraints(
            self.current_design.constraints,
            self.sim_result.metrics,
        )

        # Create iteration result
        iteration_result = IterationResult(
            iteration=self.current_design.iteration,
            cad_result=self.cad_result,
            simulation_result=self.sim_result,
            objective_score=score,
            constraints_satisfied=constraints_ok,
            constraint_violations=violations,
            timestamp=datetime.utcnow().isoformat(),
            duration_s=(datetime.utcnow() - self.iteration_start_time).total_seconds(),
        )

        self.iteration_history.append(iteration_result)
        
        if score is not None:
            self.convergence_checker.add_score(score)

        # Reset failure counter on success
        self.consecutive_failures = 0

        # Move to DECIDE
        self.current_state = RunState.DECIDE
        return iteration_result

    async def _state_decide(self) -> None:
        """DECIDE state: Determine next action"""
        # Check stop conditions
        last_result = self.iteration_history[-1]
        
        # Check budget
        budgets = self.current_design.budgets
        if self.current_design.iteration >= budgets.max_iterations:
            self.current_state = RunState.COMPLETED
            return

        # Check convergence
        if (
            last_result.constraints_satisfied
            and self.convergence_checker.is_converged()
        ):
            self.current_state = RunState.COMPLETED
            return

        # Otherwise, prepare for next iteration
        # Add results to conversation
        self.conversation_history.append({
            "role": "user",
            "content": ITERATION_PLANNING_PROMPT.format(
                iteration=self.current_design.iteration,
                cad_summary=json.dumps(self.current_design.cad.params),
                metrics=json.dumps(self.sim_result.metrics),
                score=last_result.objective_score,
                constraints_ok=last_result.constraints_satisfied,
                violations="; ".join(last_result.constraint_violations) or "None",
                next_iteration=self.current_design.iteration + 1,
            ),
        })

        # Back to PLAN
        self.current_state = RunState.PLAN

    async def _state_fail_recovery(self) -> None:
        """FAIL_RECOVERY state: Handle iteration failure"""
        self.consecutive_failures += 1

        # Check if we've exceeded failure budget
        budgets = self.current_design.budgets
        if self.consecutive_failures >= budgets.max_failures:
            self.current_state = RunState.FAILED
            return

        # Get error message
        if not self.cad_result.success:
            error = f"CAD generation failed: {self.cad_result.error}"
        else:
            error = f"Simulation failed: {self.sim_result.error}"

        # Add failure recovery prompt
        self.conversation_history.append({
            "role": "user",
            "content": FAILURE_RECOVERY_PROMPT.format(
                error=error,
                failure_count=self.consecutive_failures,
                max_failures=budgets.max_failures,
            ),
        })

        # Back to PLAN for recovery
        self.current_state = RunState.PLAN

    async def run_autonomous(
        self, user_request: str, run_id: Optional[UUID] = None
    ) -> RunStatus:
        """
        Run autonomous loop until completion or failure.
        
        Args:
            user_request: User's design request
            run_id: Optional run ID
        
        Returns:
            Final RunStatus
        """
        status = await self.start_run(user_request, run_id)

        while self.current_state not in [
            RunState.STOPPED,
            RunState.COMPLETED,
            RunState.FAILED,
        ]:
            result = await self.step()
            
            # Save iteration result if completed
            if result:
                iter_dir = self._get_iteration_dir(
                    self.current_run_id, result.iteration
                )
                result_file = iter_dir / "result.json"
                result_file.parent.mkdir(parents=True, exist_ok=True)
                with open(result_file, "w") as f:
                    json.dump(result.dict(), f, indent=2)

        # Final status
        return RunStatus(
            run_id=self.current_run_id,
            state=self.current_state,
            current_iteration=self.current_design.iteration,
            iterations_completed=len(self.iteration_history),
            consecutive_failures=self.consecutive_failures,
            best_iteration=self._get_best_iteration(),
            best_score=self._get_best_score(),
            started_at=status.started_at,
            updated_at=datetime.utcnow().isoformat(),
        )

    def _get_best_iteration(self) -> Optional[int]:
        """Get best iteration by objective score"""
        if not self.iteration_history:
            return None
        
        scored = [
            (i, r.objective_score)
            for i, r in enumerate(self.iteration_history)
            if r.objective_score is not None
        ]
        
        if not scored:
            return None
        
        return min(scored, key=lambda x: x[1])[0]

    def _get_best_score(self) -> Optional[float]:
        """Get best objective score"""
        idx = self._get_best_iteration()
        if idx is None:
            return None
        return self.iteration_history[idx].objective_score

