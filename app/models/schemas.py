from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel


class Layer1Decision(str, Enum):
    BLOCK = "BLOCK"
    PASS = "PASS"
    ENQUEUE = "ENQUEUE"


class Layer1Result(BaseModel):
    decision: Layer1Decision
    nsfw_score: float
    text_risk_score: float
    extracted_text: str = ""
    matched_word: str = ""
    reason: str = ""


class Layer2Report(BaseModel):
    nsfw_score: float
    nsfw_reason: str
    text_risk_score: float
    text_reason: str
    ai_generated_score: float
    ai_generated_reason: str
    final_verdict: str  # "SAFE" | "VIOLATION" | "UNCERTAIN"
    overall_reason: str


class PostRecord(BaseModel):
    id: int
    image_path: str
    status: str  # "under_review" | "safe" | "removed"
    layer1: Optional[Dict] = None
    layer2: Optional[Dict] = None
    created_at: Optional[str] = None
