from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator

PrimaryCategory = Literal[
    "garden", "harvest", "washing", "prep", "cutting",
    "cooking", "plating", "eating", "talking", "other",
]


class TranscriptSpan(BaseModel):
    start: float
    end: float
    text: str


class Segment(BaseModel):
    segment_id: int
    start: float
    end: float
    frame_paths: list[str] = Field(default_factory=list)
    speech: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class SceneSemantic(BaseModel):
    segment_id: int
    start: float
    end: float
    primary_category: PrimaryCategory
    labels: list[str] = Field(default_factory=list)
    description: str
    visual_quality: float = Field(ge=0.0, le=1.0)
    keep_score: float = Field(ge=0.0, le=1.0)
    speech: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class SceneAnalysis(BaseModel):
    source_video: str
    source_hash: str
    scenes: list[SceneSemantic]


class Recipe(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    target_duration: float = 45.0
    max_duration: float = 75.0
    preserve_source_order: bool = True
    min_keep_score: float = 0.45
    min_visual_quality: float = 0.35
    prompt: str = ""

    @model_validator(mode="after")
    def check_duration(self):
        if self.target_duration <= 0 or self.max_duration <= 0:
            raise ValueError("Durations must be positive")
        if self.target_duration > self.max_duration:
            raise ValueError("target_duration cannot exceed max_duration")
        return self


class EditClip(BaseModel):
    segment_id: int
    source_start: float
    source_end: float
    reason: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)


class EditPlan(BaseModel):
    recipe_name: str
    clips: list[EditClip]
    estimated_duration: float = 0.0
    planner: Literal["ai", "rules"] = "rules"

    @model_validator(mode="after")
    def calculate_duration(self):
        self.estimated_duration = sum(c.duration for c in self.clips)
        return self
