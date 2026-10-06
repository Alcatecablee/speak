"""
Hardened Pydantic schemas for Speak V2 AI Conversation Intelligence Layer.
Strictly separates direct transcript facts, normalized values, and AI interpretations.
Enforces epistemic status, evidence binding, and action classification.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    CONFIRMED_COMMITMENT = "CONFIRMED_COMMITMENT"
    PROPOSED_ACTION = "PROPOSED_ACTION"
    COMPLETED_ACTION = "COMPLETED_ACTION"
    CLIENT_REQUEST = "CLIENT_REQUEST"
    UNKNOWN = "UNKNOWN"


class ActorRole(str, Enum):
    CONSULTANT = "CONSULTANT"
    CLIENT = "CLIENT"
    ESCALATION_TEAM = "ESCALATION_TEAM"
    UNKNOWN = "UNKNOWN"
    NONE = "NONE"


class Sentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    FRUSTRATED = "FRUSTRATED"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NormalizationMethod(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    DICTIONARY_MATCH = "DICTIONARY_MATCH"
    PHONETIC_HEURISTIC = "PHONETIC_HEURISTIC"
    PATTERN_EXTRACTION = "PATTERN_EXTRACTION"
    UNNORMALIZED = "UNNORMALIZED"


class EpistemicType(str, Enum):
    DIRECT_FACT = "DIRECT_FACT"
    NORMALIZED_VALUE = "NORMALIZED_VALUE"
    AI_INTERPRETATION = "AI_INTERPRETATION"
    UNVERIFIED = "UNVERIFIED"


class EvidenceItem(BaseModel):
    """Immutable audit trail linking an extracted fact or claim to transcript source."""
    fact: str = Field(description="The extracted fact or claim.")
    epistemic_type: EpistemicType = Field(default=EpistemicType.DIRECT_FACT, description="Fact vs interpretation.")
    turn_index: Optional[int] = Field(default=None, description="0-indexed turn position in transcript.")
    timestamp: Optional[str] = Field(default=None, description="Timestamp string (HH:MM:SS) of the turn.")
    speaker: Optional[str] = Field(default=None, description="CONSULTANT or CLIENT.")
    source_quote: str = Field(description="Exact verbatim or near-verbatim quote from transcript supporting this fact.")


class NormalizedEntity(BaseModel):
    """
    Structured entity representation preserving raw STT text alongside normalized canonical forms.
    Never silently replaces raw evidence.
    """
    raw_text: str = Field(description="Exact raw text as transcribed from audio.")
    normalized_value: str = Field(description="Canonical or standardized domain term.")
    category: str = Field(description="Category (e.g. CUSTOMER_ID, PRODUCT, UNIT_OF_MEASURE, TIMEFRAME).")
    normalization_method: NormalizationMethod = Field(description="Method used for normalization.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this specific normalization (0.0 to 1.0).")
    turn_index: Optional[int] = Field(default=None, description="Transcript turn index.")
    timestamp: Optional[str] = Field(default=None, description="Timestamp string.")
    source_quote: str = Field(default="", description="Verbatim source sentence.")


class StructuredAction(BaseModel):
    """
    Distinguishes confirmed commitments from suggestions, completed work, and client requests.
    """
    description: str = Field(description="Description of the action.")
    action_type: ActionType = Field(description="Action commitment classification.")
    actor: ActorRole = Field(description="Party responsible or performing.")
    timeframe: Optional[str] = Field(default=None, description="Stated timeframe if explicitly mentioned.")
    evidence: Optional[EvidenceItem] = Field(default=None, description="Supporting transcript turn.")


class ConversationSummary(BaseModel):
    """High-level interaction summary strictly grounded in dialogue."""
    reason_for_contact: str = Field(description="Concise statement of why the client reached out.")
    key_events: List[str] = Field(default_factory=list, description="Chronological timeline of verified events.")
    outcome: str = Field(description="Direct outcome or current state at call termination.")


class ClientIssue(BaseModel):
    """The reported technical or operational issue."""
    primary_issue: str = Field(description="Core problem or request reported by the client.")
    details: List[str] = Field(default_factory=list, description="Specific contextual details stated by the client.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Direct quote evidence.")


class ActionsTaken(BaseModel):
    """Actions performed or confirmed during the call."""
    structured_actions: List[StructuredAction] = Field(default_factory=list, description="Categorized actions.")
    consultant_actions: List[str] = Field(default_factory=list, description="Summary list of consultant actions.")
    client_actions: List[str] = Field(default_factory=list, description="Summary list of client actions.")


class FollowUp(BaseModel):
    """Explicit follow-up commitments (excludes unconfirmed suggestions)."""
    required: bool = Field(description="Whether follow-up action is confirmed as required.")
    action_items: List[str] = Field(default_factory=list, description="Specific follow-up tasks.")
    owner: ActorRole = Field(default=ActorRole.UNKNOWN, description="Party responsible: CONSULTANT, CLIENT, ESCALATION_TEAM, NONE.")
    timeframe: Optional[str] = Field(default=None, description="Stated timeframe or callback deadline (or null if unspecified).")
    evidence: Optional[EvidenceItem] = Field(default=None, description="Direct quote committing to follow-up.")


class ExtractedEntities(BaseModel):
    """Explicit collection of normalized and raw entities."""
    normalized_entities: List[NormalizedEntity] = Field(default_factory=list, description="All normalized entities with provenance.")
    customer_identifiers: List[str] = Field(default_factory=list, description="Connection IDs, AnyDesk codes, address, account numbers.")
    case_or_reference_numbers: List[str] = Field(default_factory=list, description="Case or reference numbers if explicitly stated.")
    product_or_system_names: List[str] = Field(default_factory=list, description="Software, module, recipe/stock items, or system names.")
    quantities_or_numbers: List[str] = Field(default_factory=list, description="Quantities, weights, variances, or unit numbers.")
    dates_or_times: List[str] = Field(default_factory=list, description="Temporal references.")
    error_messages: List[str] = Field(default_factory=list, description="Explicit error messages or variance anomalies.")


class SentimentAnalysis(BaseModel):
    """
    AI-derived assessment of customer tone (secondary metadata, NOT objective fact).
    Strictly forbidden from driving resolution status or follow-up.
    """
    sentiment: Sentiment = Field(description="Assessed sentiment category.")
    rationale: str = Field(description="Explanation grounded in dialogue tone and client statements.")
    is_ai_derived: bool = Field(default=True, description="Always true to indicate non-factual AI inference.")


class ConfidenceAssessment(BaseModel):
    """
    Confidence evaluation reflecting evidence completeness, STT quality, and inference density.
    Treat as a review aid, NOT proof of correctness.
    """
    level: ConfidenceLevel = Field(description="Overall confidence level.")
    score: float = Field(ge=0.0, le=1.0, description="Evidence quality score between 0.0 and 1.0.")
    review_notes: str = Field(description="Guidance highlighting ambiguities, STT artifacts, or unconfirmed suggestions.")
    stt_noise_detected: bool = Field(default=False, description="Whether repetitive loops or phonetic anomalies were detected.")


class ConversationAnalysis(BaseModel):
    """Complete, structured conversation intelligence record."""
    schema_version: str = Field(default="2.1.0", description="Schema version.")
    call_start_time: Optional[str] = Field(default=None, description="Original call start timestamp.")
    total_turns_analyzed: int = Field(description="Total speaker turns processed.")
    
    summary: ConversationSummary = Field(description="Conversation overview.")
    client_issue: ClientIssue = Field(description="Client problem breakdown with evidence.")
    actions_taken: ActionsTaken = Field(description="Actions taken with commitment classification.")
    resolution_status: ResolutionStatus = Field(description="Standardized resolution status enum.")
    resolution_rationale: str = Field(default="", description="Explicit factual basis for resolution classification.")
    follow_up: FollowUp = Field(description="Follow-up requirements (confirmed commitments only).")
    entities: ExtractedEntities = Field(description="Directly extracted and normalized entities.")
    sentiment: SentimentAnalysis = Field(description="Customer sentiment (secondary metadata).")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Master audit trail.")
    confidence: ConfidenceAssessment = Field(description="Confidence metrics and human review notes.")
