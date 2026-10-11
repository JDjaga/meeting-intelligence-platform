"""Structured output schemas — the contract every extractor must satisfy.

No free-form parsing downstream: everything is a validated Pydantic model.
Every action item MUST carry exact transcript evidence.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator

CommitmentType = Literal["explicit", "implicit"]


class ActionItem(BaseModel):
    action: str = Field(min_length=3, max_length=500, description="Normalized action statement")
    owner: str | None = Field(default=None, description="Person responsible, None if unknown")
    deadline: str | None = Field(default=None, description="ISO date YYYY-MM-DD or None")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=5, description="EXACT substring from transcript")
    commitment_type: CommitmentType = "explicit"
    needs_review: bool = False
    review_reason: str | None = None

    @field_validator("evidence")
    @classmethod
    def evidence_must_be_quoted(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("evidence too short — must be an exact transcript quote")
        return v


class Decision(BaseModel):
    decision: str = Field(min_length=3, max_length=500)
    rationale: str | None = None
    evidence: str = Field(min_length=5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class Blocker(BaseModel):
    blocker: str
    impacted_owner: str | None = None
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)


class MeetingExtraction(BaseModel):
    title: str
    date: str | None = None
    attendees: list[str] = Field(default_factory=list)
    summary: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
