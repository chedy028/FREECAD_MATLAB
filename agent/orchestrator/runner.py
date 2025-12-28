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
from agent.logging_config import get_logger
from agent.orchestrator.scoring import ConvergenceChecker, ObjectiveScorer
from agent.orchestrator.validators import (
    CADResult,
    DesignIteration,
    IterationResult,
    RunState,
    RunStatus,
    SimulationResult,
)
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


# Default conversation history limit
DEFAULT_MAX_CONVERSATION_MESSAGES = 50


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
        max_conversation_messages: int = DEFAULT_MAX_CONVERSATION_MESSAGES,
    ):
        self.llm = openrouter_client
        self.freecad = freecad_runner
        self.matlab = matlab_runner
        self.runs_base_dir = runs_base_dir
        self.max_conversation_messages = max_conversation_messages
        self.logger = get_logger("orchestrator")
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
        self.run_start_time: Optional[datetime] = None
        self.stopped_reason: Optional[str] = None

    def _get_run_dir(self, run_id: UUID) -> Path:
        """Get run directory"""
        return self.runs_base_dir / str(run_id)

    def _get_iteration_dir(self, run_id: UUID, iteration: int) -> Path:
        """Get iteration directory"""
        return self._get_run_dir(run_id) / f"iter_{iteration:03d}"

    def _prune_conversation_history(self) -> None:
        """
        Prune conversation history to prevent unbounded memory growth.

        Keeps:
        - System prompt (index 0)
        - Last N messages where N = max_conversation_messages - 1
        """
        if len(self.conversation_history) <= self.max_conversation_messages:
            return

        # Calculate how many messages to keep (excluding system prompt)
        messages_to_keep = self.max_conversation_messages - 1

        # Preserve system prompt + last N messages
        system_prompt = self.conversation_history[0]
        recent_messages = self.conversation_history[-messages_to_keep:]

        pruned_count = len(self.conversation_history) - self.max_conversation_messages
        self.conversation_history = [system_prompt] + recent_messages

        self.logger.info(
            "Pruned conversation history",
            run_id=self.current_run_id,
            extra_data={
                "pruned_count": pruned_count,
                "remaining_count": len(self.conversation_history),
            },
        )

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
        self.run_start_time = datetime.utcnow()
        self.stopped_reason = None
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

        self.logger.info(
            "Starting new run",
            run_id=run_id,
            state="PLAN",
            extra_data={"user_request": user_request[:200]},
        )

        return RunStatus(
            run_id=run_id,
            state=self.current_state,
            started_at=self.run_start_time.isoformat(),
            updated_at=self.run_start_time.isoformat(),
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
        self.logger.info(
            "Planning next iteration",
            run_id=self.current_run_id,
            state="PLAN",
        )

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
            self.logger.warning(
                f"Failed to parse DesignIteration: {e}",
                run_id=self.current_run_id,
                state="PLAN",
            )
            # Parsing failed, add error to conversation and retry
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_msg,
            })
            self.conversation_history.append({
                "role": "user",
                "content": f"Error parsing DesignIteration: {e}. Please output valid JSON matching the schema.",
            })
            self._prune_conversation_history()
            # Stay in PLAN state
            return

        # Successfully planned, move to BUILD_CAD
        self.logger.info(
            "Planning complete",
            run_id=self.current_run_id,
            state="PLAN",
            iteration=self.current_design.iteration,
            extra_data={"template": self.current_design.cad.template},
        )
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_msg,
        })
        self._prune_conversation_history()
        self.current_state = RunState.BUILD_CAD
        self.iteration_start_time = datetime.utcnow()

    async def _state_build_cad(self) -> None:
        """BUILD_CAD state: Generate CAD geometry"""
        iteration = self.current_design.iteration
        iter_dir = self._get_iteration_dir(self.current_run_id, iteration)
        cad_dir = iter_dir / "cad"

        self.logger.info(
            "Building CAD geometry",
            run_id=self.current_run_id,
            state="BUILD_CAD",
            iteration=iteration,
            extra_data={"template": self.current_design.cad.template},
        )

        try:
            # Run FreeCAD
            self.cad_result = await self.freecad.build_cad(
                self.current_design.cad, cad_dir
            )

            if self.cad_result.success:
                self.logger.info(
                    "CAD generation succeeded",
                    run_id=self.current_run_id,
                    state="BUILD_CAD",
                    iteration=iteration,
                    extra_data={"path": self.cad_result.path},
                )
                self.current_state = RunState.SIMULATE
            else:
                self.logger.warning(
                    "CAD generation failed",
                    run_id=self.current_run_id,
                    state="BUILD_CAD",
                    iteration=iteration,
                    extra_data={"error": self.cad_result.error},
                )
                self.current_state = RunState.FAIL_RECOVERY

        except Exception as e:
            self.logger.error(
                f"Exception in BUILD_CAD state: {e}",
                run_id=self.current_run_id,
                state="BUILD_CAD",
                iteration=iteration,
            )
            # Create a failed CAD result for fail recovery
            self.cad_result = CADResult(
                success=False,
                error=f"Exception during CAD generation: {str(e)}",
            )
            self.current_state = RunState.FAIL_RECOVERY

    async def _state_simulate(self) -> None:
        """SIMULATE state: Run MATLAB simulation"""
        iteration = self.current_design.iteration
        iter_dir = self._get_iteration_dir(self.current_run_id, iteration)
        sim_dir = iter_dir / "simulation"

        self.logger.info(
            "Running MATLAB simulation",
            run_id=self.current_run_id,
            state="SIMULATE",
            iteration=iteration,
            extra_data={"entrypoint": self.current_design.simulation.matlab_entrypoint},
        )

        try:
            # Run MATLAB
            self.sim_result = await self.matlab.run_matlab(
                self.current_design.simulation,
                self.cad_result.path,
                sim_dir,
            )

            if self.sim_result.success:
                self.logger.info(
                    "Simulation succeeded",
                    run_id=self.current_run_id,
                    state="SIMULATE",
                    iteration=iteration,
                    extra_data={"metrics": self.sim_result.metrics},
                )
                self.current_state = RunState.EVALUATE
            else:
                self.logger.warning(
                    "Simulation failed",
                    run_id=self.current_run_id,
                    state="SIMULATE",
                    iteration=iteration,
                    extra_data={"error": self.sim_result.error},
                )
                self.current_state = RunState.FAIL_RECOVERY

        except Exception as e:
            self.logger.error(
                f"Exception in SIMULATE state: {e}",
                run_id=self.current_run_id,
                state="SIMULATE",
                iteration=iteration,
            )
            # Create a failed simulation result for fail recovery
            self.sim_result = SimulationResult(
                success=False,
                error=f"Exception during simulation: {str(e)}",
            )
            self.current_state = RunState.FAIL_RECOVERY

    async def _state_evaluate(self) -> Optional[IterationResult]:
        """EVALUATE state: Compute objective and constraints"""
        iteration = self.current_design.iteration

        self.logger.info(
            "Evaluating iteration results",
            run_id=self.current_run_id,
            state="EVALUATE",
            iteration=iteration,
        )

        try:
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
                iteration=iteration,
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

            self.logger.info(
                "Evaluation complete",
                run_id=self.current_run_id,
                state="EVALUATE",
                iteration=iteration,
                extra_data={
                    "objective_score": score,
                    "constraints_satisfied": constraints_ok,
                    "violations": violations,
                },
            )

            # Move to DECIDE
            self.current_state = RunState.DECIDE
            return iteration_result

        except Exception as e:
            self.logger.error(
                f"Exception in EVALUATE state: {e}",
                run_id=self.current_run_id,
                state="EVALUATE",
                iteration=iteration,
            )
            # Create a failed simulation result for fail recovery
            self.sim_result = SimulationResult(
                success=False,
                error=f"Exception during evaluation: {str(e)}",
            )
            self.current_state = RunState.FAIL_RECOVERY
            return None

    async def _state_decide(self) -> None:
        """DECIDE state: Determine next action"""
        # Check stop conditions
        last_result = self.iteration_history[-1]
        budgets = self.current_design.budgets
        iteration = self.current_design.iteration

        # Check max iterations budget
        if iteration >= budgets.max_iterations:
            self.logger.info(
                "Max iterations reached",
                run_id=self.current_run_id,
                state="DECIDE",
                iteration=iteration,
            )
            self.current_state = RunState.COMPLETED
            self.stopped_reason = "max_iterations_reached"
            return

        # Check wall time budget
        elapsed_time = (datetime.utcnow() - self.run_start_time).total_seconds()
        if elapsed_time >= budgets.max_wall_time_s:
            self.logger.warning(
                "Wall time limit exceeded",
                run_id=self.current_run_id,
                state="DECIDE",
                iteration=iteration,
                extra_data={
                    "elapsed_s": elapsed_time,
                    "limit_s": budgets.max_wall_time_s,
                },
            )
            self.current_state = RunState.COMPLETED
            self.stopped_reason = "timeout"
            return

        # Check convergence
        if (
            last_result.constraints_satisfied
            and self.convergence_checker.is_converged()
        ):
            self.logger.info(
                "Convergence achieved",
                run_id=self.current_run_id,
                state="DECIDE",
                iteration=iteration,
                extra_data={"best_score": self._get_best_score()},
            )
            self.current_state = RunState.COMPLETED
            self.stopped_reason = "converged"
            return

        # Otherwise, prepare for next iteration
        self.logger.info(
            "Continuing to next iteration",
            run_id=self.current_run_id,
            state="DECIDE",
            iteration=iteration,
            extra_data={"next_iteration": iteration + 1},
        )

        # Add results to conversation
        self.conversation_history.append({
            "role": "user",
            "content": ITERATION_PLANNING_PROMPT.format(
                iteration=iteration,
                cad_summary=json.dumps(self.current_design.cad.params),
                metrics=json.dumps(self.sim_result.metrics),
                score=last_result.objective_score,
                constraints_ok=last_result.constraints_satisfied,
                violations="; ".join(last_result.constraint_violations) or "None",
                next_iteration=iteration + 1,
            ),
        })
        self._prune_conversation_history()

        # Back to PLAN
        self.current_state = RunState.PLAN

    async def _state_fail_recovery(self) -> None:
        """FAIL_RECOVERY state: Handle iteration failure"""
        self.consecutive_failures += 1
        budgets = self.current_design.budgets
        iteration = getattr(self.current_design, 'iteration', 0)

        # Get error message
        if hasattr(self, 'cad_result') and not self.cad_result.success:
            error = f"CAD generation failed: {self.cad_result.error}"
        elif hasattr(self, 'sim_result'):
            error = f"Simulation failed: {self.sim_result.error}"
        else:
            error = "Unknown failure"

        self.logger.warning(
            "Entering fail recovery",
            run_id=self.current_run_id,
            state="FAIL_RECOVERY",
            iteration=iteration,
            extra_data={
                "error": error,
                "failure_count": self.consecutive_failures,
                "max_failures": budgets.max_failures,
            },
        )

        # Check if we've exceeded failure budget
        if self.consecutive_failures >= budgets.max_failures:
            self.logger.error(
                "Max failures exceeded",
                run_id=self.current_run_id,
                state="FAIL_RECOVERY",
                iteration=iteration,
                exc_info=False,
            )
            self.current_state = RunState.FAILED
            self.stopped_reason = "max_failures_exceeded"
            return

        # Add failure recovery prompt
        self.conversation_history.append({
            "role": "user",
            "content": FAILURE_RECOVERY_PROMPT.format(
                error=error,
                failure_count=self.consecutive_failures,
                max_failures=budgets.max_failures,
            ),
        })
        self._prune_conversation_history()

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

        # Log completion
        elapsed_time = (datetime.utcnow() - self.run_start_time).total_seconds()
        self.logger.info(
            "Run completed",
            run_id=self.current_run_id,
            state=self.current_state.value,
            extra_data={
                "stopped_reason": self.stopped_reason,
                "iterations_completed": len(self.iteration_history),
                "best_score": self._get_best_score(),
                "elapsed_time_s": elapsed_time,
            },
        )

        # Final status
        current_iteration = getattr(self.current_design, 'iteration', 0) if hasattr(self, 'current_design') else 0
        return RunStatus(
            run_id=self.current_run_id,
            state=self.current_state,
            current_iteration=current_iteration,
            iterations_completed=len(self.iteration_history),
            consecutive_failures=self.consecutive_failures,
            best_iteration=self._get_best_iteration(),
            best_score=self._get_best_score(),
            started_at=status.started_at,
            updated_at=datetime.utcnow().isoformat(),
            stopped_reason=self.stopped_reason,
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

    async def save_to_database(self, session_maker, user_request: str) -> None:
        """
        Save run and all iterations to database.

        Args:
            session_maker: SQLAlchemy async session maker
            user_request: Original user request string
        """
        from agent.db.models import Run, Iteration

        if not self.current_run_id:
            return

        async with session_maker() as session:
            # Save or update Run record
            run_record = Run(
                run_id=str(self.current_run_id),
                state=self.current_state.value,
                current_iteration=getattr(self.current_design, 'iteration', 0) if hasattr(self, 'current_design') else 0,
                iterations_completed=len(self.iteration_history),
                consecutive_failures=self.consecutive_failures,
                best_iteration=self._get_best_iteration(),
                best_score=self._get_best_score(),
                started_at=self.run_start_time,
                stopped_reason=self.stopped_reason,
                user_request=user_request,
                config=self.current_design.budgets.dict() if hasattr(self, 'current_design') else None,
            )
            session.add(run_record)

            # Save all iterations
            for result in self.iteration_history:
                iter_record = Iteration(
                    run_id=str(self.current_run_id),
                    iteration=result.iteration,
                    duration_s=result.duration_s,
                    design_spec=self.current_design.dict() if hasattr(self, 'current_design') else {},
                    cad_success=1 if result.cad_result.success else 0,
                    cad_result=result.cad_result.dict(),
                    sim_success=1 if result.simulation_result.success else 0,
                    sim_result=result.simulation_result.dict(),
                    objective_score=result.objective_score,
                    constraints_satisfied=1 if result.constraints_satisfied else 0,
                    constraint_violations=result.constraint_violations,
                    artifacts_path=str(self._get_iteration_dir(self.current_run_id, result.iteration)),
                )
                session.add(iter_record)

            await session.commit()

            self.logger.info(
                "Saved run to database",
                run_id=self.current_run_id,
                extra_data={"iterations_saved": len(self.iteration_history)},
            )

