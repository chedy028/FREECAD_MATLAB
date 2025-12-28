"""SQLAlchemy database models"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models"""
    pass


class Run(Base):
    """Run metadata"""

    __tablename__ = "runs"

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    state = Column(String(50), nullable=False, default="PLAN")
    current_iteration = Column(Integer, nullable=False, default=0)
    iterations_completed = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    best_iteration = Column(Integer, nullable=True)
    best_score = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    stopped_reason = Column(Text, nullable=True)
    user_request = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)  # Budgets, convergence params, etc.


class Iteration(Base):
    """Iteration results"""

    __tablename__ = "iterations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), nullable=False, index=True)
    iteration = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    duration_s = Column(Float, nullable=True)
    
    # Design spec (DesignIteration JSON)
    design_spec = Column(JSON, nullable=False)
    
    # Results
    cad_success = Column(Integer, nullable=False)  # Boolean as 0/1
    cad_result = Column(JSON, nullable=True)
    
    sim_success = Column(Integer, nullable=False)  # Boolean as 0/1
    sim_result = Column(JSON, nullable=True)
    
    # Evaluation
    objective_score = Column(Float, nullable=True)
    constraints_satisfied = Column(Integer, nullable=True)  # Boolean as 0/1
    constraint_violations = Column(JSON, nullable=True)  # List of strings
    
    # Artifacts
    artifacts_path = Column(Text, nullable=True)


# Database setup utilities

async def init_db(database_url: str):
    """
    Initialize database schema and return engine + session maker.

    Args:
        database_url: SQLAlchemy async database URL

    Returns:
        Tuple of (engine, session_maker)
    """
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_maker


async def get_session_maker(database_url: str):
    """Create async session maker (standalone)"""
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)

