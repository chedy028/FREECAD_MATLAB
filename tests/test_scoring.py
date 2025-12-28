"""Test objective scoring and constraint evaluation"""

import pytest
from agent.orchestrator.scoring import ObjectiveScorer
from agent.orchestrator.validators import (
    Constraint,
    ConstraintOperator,
    Objective,
)


def test_compute_objective_score_minimize():
    """Test objective score computation for minimization"""
    objectives = [Objective(name="minimize", metric="mass", weight=1.0)]
    metrics = {"mass": 100.0}
    
    score = ObjectiveScorer.compute_objective_score(objectives, metrics)
    assert score == 100.0


def test_compute_objective_score_maximize():
    """Test objective score computation for maximization"""
    objectives = [Objective(name="maximize", metric="strength", weight=1.0)]
    metrics = {"strength": 50.0}
    
    score = ObjectiveScorer.compute_objective_score(objectives, metrics)
    assert score == -50.0  # Negated for maximization


def test_compute_objective_score_missing_metric():
    """Test with missing metric"""
    objectives = [Objective(name="minimize", metric="mass", weight=1.0)]
    metrics = {"other": 100.0}
    
    score = ObjectiveScorer.compute_objective_score(objectives, metrics)
    assert score is None


def test_evaluate_constraints_satisfied():
    """Test constraint evaluation - all satisfied"""
    constraints = [
        Constraint(metric="temp", op=ConstraintOperator.LE, value=85.0),
        Constraint(metric="mass", op=ConstraintOperator.LE, value=200.0),
    ]
    metrics = {"temp": 80.0, "mass": 150.0}
    
    satisfied, violations = ObjectiveScorer.evaluate_constraints(constraints, metrics)
    assert satisfied is True
    assert len(violations) == 0


def test_evaluate_constraints_violated():
    """Test constraint evaluation - some violated"""
    constraints = [
        Constraint(metric="temp", op=ConstraintOperator.LE, value=85.0),
        Constraint(metric="mass", op=ConstraintOperator.LE, value=200.0),
    ]
    metrics = {"temp": 90.0, "mass": 150.0}
    
    satisfied, violations = ObjectiveScorer.evaluate_constraints(constraints, metrics)
    assert satisfied is False
    assert len(violations) == 1
    assert "temp" in violations[0]


def test_is_converged():
    """Test convergence detection"""
    # Not converged - improving
    scores = [100.0, 95.0, 90.0, 85.0]
    assert ObjectiveScorer.is_converged(scores, epsilon=0.01, stable_iterations=3) is False
    
    # Converged - stable
    scores = [100.0, 99.9, 99.8, 99.7]
    assert ObjectiveScorer.is_converged(scores, epsilon=0.01, stable_iterations=3) is True
    
    # Not enough iterations
    scores = [100.0, 99.9]
    assert ObjectiveScorer.is_converged(scores, epsilon=0.01, stable_iterations=3) is False

