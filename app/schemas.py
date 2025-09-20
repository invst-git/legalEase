from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class KeyInfoItem(BaseModel):
    key: str
    value: str
    is_negotiable: bool
    is_benchmarkable: bool

class ActionItem(BaseModel):
    """A single action/obligation with its classification."""
    text: str
    is_negotiable: bool
    is_benchmarkable: bool

class IntelligentAnalysis(BaseModel):
    key_info: List[KeyInfoItem]
    identified_actions: List[ActionItem] # Changed from List[str]
    assessment: str
    extracted_text: List[str] = Field([], description="The page-by-page text extracted from the document.")
    page_images: List[str] = Field(default_factory=list, description="Optional data URIs for scanned PDF page images.")
    # Optional metadata for dashboard/navigation
    id: Optional[int] = None
    filename: Optional[str] = None
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None
    created_at: Optional[str] = None
    # Precomputed risky line highlights (applies instantly on first load)
    risk_highlights: List["AnchorMatch"] = Field(default_factory=list)

# --- Keep the other schemas as they are ---
class AnalysisResult(BaseModel):
    id: int; filename: str; assessment: str
    class Config: from_attributes = True

class UserCreate(BaseModel): email: str; password: str
class User(BaseModel):
    id: int; email: str
    class Config: from_attributes = True
class Token(BaseModel): access_token: str; token_type: str

class SimulationRequest(BaseModel):
    clause_text: str; document_context: str; key_info: List[Dict]

class SimulationResponse(BaseModel): simulation_text: str

class RewriteRequest(BaseModel):
    clause_key: str; clause_text: str; document_context: str

class RewriteResponse(BaseModel): rewritten_clauses: list[str]
class BenchmarkRequest(BaseModel): clause_text: str; clause_key: str
class BenchmarkResponse(BaseModel): benchmark_result: str; examples: list[str]
class ChatMessage(BaseModel):
    role: str
    content: str
class QueryRequest(BaseModel):
    question: str
    full_text: str
    history: List[ChatMessage] = Field(default_factory=list)
    analysis_id: Optional[int] = None

class QueryResponse(BaseModel):
    answer: str
    citation: Optional[str] = None  

class DashboardItem(BaseModel):
    id: int
    filename: str
    created_at: Optional[str] = None
    risk_level: Optional[str] = None

class FullAnalysisResponse(BaseModel):
    id: int
    filename: str
    assessment: str
    key_info: List[KeyInfoItem]
    identified_actions: List[ActionItem]
    extracted_text: List[str]
    page_images: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None
    conversation: List[ChatMessage] = Field(default_factory=list)
    # Precomputed spans pinpointing risky lines for instant highlight
    risk_highlights: List["AnchorMatch"] = Field(default_factory=list)

# --- Timeline Schemas ---
class TimelineEvent(BaseModel):
    id: Optional[int] = None
    date: str
    label: str
    kind: str # key_date | payment_due | action_required
    description: str

class TimelineRequest(BaseModel):
    analysis_id: int

class TimelineResponse(BaseModel):
    lifecycle_summary: str
    events: List[TimelineEvent]

class ReminderRequest(BaseModel):
    analysis_id: int
    event_id: int
    email: str
    days_before: int

class ReminderResponse(BaseModel):
    success: bool

# --- Highlighting (Click-to-Highlight) ---
class AnchorBox(BaseModel):
    x: float
    y: float
    w: float
    h: float

class AnchorMatch(BaseModel):
    page_index: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    boxes: List[AnchorBox] = Field(default_factory=list)
    strategy: Optional[str] = None

class LocateRequest(BaseModel):
    text: str

class LocateResponse(BaseModel):
    matches: List[AnchorMatch] = Field(default_factory=list)
