from pydantic import BaseModel, Field
from typing import Optional, Any


class RunRequest(BaseModel):
    name: str = "University evaluation"
    mode: str = Field("debate", pattern="^(single|debate)$")
    rounds: int = Field(2, ge=1, le=5)
    model: Optional[str] = None
    question_ids: Optional[list[int]] = None
    question: Optional[str] = None


class Output(BaseModel):
    question_id: int
    question: str
    reference_answer: str
    final_answer: str
    correct: bool
    agents: dict[str, Any] = {}


class Experiment(BaseModel):
    id: int
    name: str
    mode: str
    rounds: int
    model: str
    created_at: str
    summary: Optional[str] = ""
    outputs: list[dict] = []
