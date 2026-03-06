"""
Synthetica — Schema & Validation Layer
======================================
Pydantic V2 models enforcing strict JSON structures for the Blackboard Architecture.
All payloads exchanged via Redis MUST conform to these schemas for consistency and safety.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# -----------------------------------------------------------------------------
# Task lifecycle states (Blackboard workflow)
# -----------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """Canonical status of a task on the blackboard. Drives agent routing and handoffs."""

    TODO = "TODO"  # New task, unassigned
    IN_PROGRESS = "IN_PROGRESS"  # An agent is actively working on it
    NEEDS_PLAN = "NEEDS_PLAN"  # Scout enriched; awaiting Architect decomposition
    REVIEW = "REVIEW"  # Plan ready; awaiting Critic validation
    VALIDATED = "VALIDATED"  # Critic approved; ready for execution
    STUCK = "STUCK"  # Orphaned or failed; eligible for Vulture takeover


# -----------------------------------------------------------------------------
# Blackboard task (single unit of work)
# -----------------------------------------------------------------------------


class BlackboardTask(BaseModel):
    """
    Single crisis-management task on the blackboard.
    Evolves as Scout → Architect → Critic process it; any agent can claim STUCK.
    """

    id: str = Field(..., description="Unique task identifier (e.g. UUID or short code)")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Current workflow state")
    location: Optional[str] = Field(default=None, description="Geographic or logical location (e.g. Slussen)")
    raw_data: Optional[dict[str, Any]] = Field(default_factory=dict, description="Original report (issue, source, etc.)")
    plan_steps: list[str] = Field(default_factory=list, description="Architect-generated actionable steps")
    critic_feedback: Optional[str] = Field(default=None, description="Critic's safety review and alternatives")
    reasoning: Optional[str] = Field(default=None, description="Agent reasoning for audit and judging")
    assigned_agent: Optional[str] = Field(default=None, description="Agent role currently owning this task")
    timestamp: Optional[float] = Field(default=None, description="Unix timestamp of last update")
    risk_level: Optional[int] = Field(default=None, ge=1, le=10, description="Risk score 1-10 for prioritisation")

    model_config = {"extra": "forbid"}  # Reject unknown keys for strict validation

    @field_validator("risk_level")
    @classmethod
    def risk_level_in_range(cls, v: Optional[int]) -> Optional[int]:
        """Ensure risk_level is always between 1 and 10 when present."""
        if v is None:
            return v
        if not (1 <= v <= 10):
            raise ValueError("risk_level must be between 1 and 10")
        return v

    def to_redis_value(self) -> str:
        """Serialize for Redis string storage (JSON)."""
        return self.model_dump_json()

    @classmethod
    def from_redis_value(cls, raw: str) -> "BlackboardTask":
        """Deserialize from Redis; raises ValidationError if invalid."""
        return cls.model_validate_json(raw)


# -----------------------------------------------------------------------------
# Heartbeat (agent liveness)
# -----------------------------------------------------------------------------


class Heartbeat(BaseModel):
    """
    Agent liveness signal. Written to heartbeat:{role} with short TTL.
    Used by Specialist (and others) to detect dead peers and trigger Vulture Protocol.
    """

    agent_name: str = Field(..., description="Role or unique agent identifier")
    status: str = Field(default="alive", description="e.g. alive, busy, recovering")
    unix_timestamp: float = Field(..., description="Time of heartbeat for staleness checks")

    model_config = {"extra": "forbid"}

    def to_redis_value(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_redis_value(cls, raw: str) -> "Heartbeat":
        return cls.model_validate_json(raw)
