"""Objective scoring and constraint evaluation"""

from typing import Dict, List, Optional, Tuple

from agent.orchestrator.validators import Constraint, Objective


class ObjectiveScorer:
    """Compute objective scores and evaluate constraints"""

    @staticmethod
    def compute_objective_score(
        objectives: List[Objective], metrics: Dict[str, float]
    ) -> Optional[float]:
        """
        Compute weighted objective score.
        
        For single objective: return the metric value (negated if maximizing).
        For multi-objective: return weighted sum (all normalized to minimization).
        
        Returns None if any required metric is missing.
        """
        if not objectives:
            return None

        total_score = 0.0
        total_weight = sum(obj.weight for obj in objectives)

        for obj in objectives:
            if obj.metric not in metrics:
                return None  # Missing metric

            value = metrics[obj.metric]
            
            # Convert to minimization (negate if maximizing)
            if obj.name == "maximize":
                value = -value

            weighted_value = value * (obj.weight / total_weight)
            total_score += weighted_value

        return total_score

    @staticmethod
    def evaluate_constraints(
        constraints: List[Constraint], metrics: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Evaluate all constraints.
        
        Returns:
            (all_satisfied, violation_messages)
        """
        if not constraints:
            return True, []

        violations = []
        
        for constraint in constraints:
            if constraint.metric not in metrics:
                violations.append(
                    f"Constraint metric '{constraint.metric}' not found in results"
                )
                continue

            metric_value = metrics[constraint.metric]
            
            if not constraint.evaluate(metric_value):
                violations.append(
                    f"Constraint violated: {constraint.metric} {constraint.op.value} "
                    f"{constraint.value}, got {metric_value:.4f}"
                )

        return len(violations) == 0, violations

    @staticmethod
    def is_converged(
        scores: List[float], epsilon: float = 0.001, stable_iterations: int = 3
    ) -> bool:
        """
        Check if optimization has converged.
        
        Converged if relative improvement < epsilon for stable_iterations.
        """
        if len(scores) < stable_iterations + 1:
            return False

        recent_scores = scores[-stable_iterations - 1 :]
        
        for i in range(len(recent_scores) - 1):
            current = recent_scores[i]
            next_val = recent_scores[i + 1]
            
            if abs(current) < 1e-9:
                # Avoid division by zero
                abs_improvement = abs(next_val - current)
                if abs_improvement > epsilon:
                    return False
            else:
                rel_improvement = abs((next_val - current) / current)
                if rel_improvement > epsilon:
                    return False

        return True


class ConvergenceChecker:
    """Track convergence over iterations"""

    def __init__(self, epsilon: float = 0.001, stable_iterations: int = 3):
        self.epsilon = epsilon
        self.stable_iterations = stable_iterations
        self.scores: List[float] = []

    def add_score(self, score: float) -> None:
        """Add a new score"""
        self.scores.append(score)

    def is_converged(self) -> bool:
        """Check if converged"""
        return ObjectiveScorer.is_converged(
            self.scores, self.epsilon, self.stable_iterations
        )

    def get_improvement(self) -> Optional[float]:
        """Get relative improvement from previous iteration"""
        if len(self.scores) < 2:
            return None
        
        prev = self.scores[-2]
        curr = self.scores[-1]
        
        if abs(prev) < 1e-9:
            return abs(curr - prev)
        
        return (curr - prev) / abs(prev)

