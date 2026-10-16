"""
Hardened Pydantic schemas for Speak V2 AI Conversation Intelligence Layer.
Strictly separates direct transcript facts, normalized values, and AI interpretations.
Enforces epistemic status, evidence binding, and action classification.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
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


# --- Phase 3 Additive Enums ---

class ClaimType(str, Enum):
    """Semantic category of an extracted dialogue claim."""
    FAILURE_ASSERTION = "FAILURE_ASSERTION"
    RESOLUTION_ASSERTION = "RESOLUTION_ASSERTION"
    DIAGNOSTIC_ACTION = "DIAGNOSTIC_ACTION"
    REMEDIAL_ACTION = "REMEDIAL_ACTION"
    ESCALATION_DISPATCH = "ESCALATION_DISPATCH"
    COMMITMENT = "COMMITMENT"
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"
    OTHER_CONTEXT = "OTHER_CONTEXT"


class Polarity(str, Enum):
    """Grammatical affirmation or negation of the predicate in the clause."""
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATED = "NEGATED"
    UNCERTAIN = "UNCERTAIN"


class TemporalScope(str, Enum):
    """Temporal frame described by the claim."""
    PRESENT_OR_CURRENT = "PRESENT_OR_CURRENT"
    RETROSPECTIVE_PAST = "RETROSPECTIVE_PAST"
    PROSPECTIVE_FUTURE = "PROSPECTIVE_FUTURE"
    UNSPECIFIED = "UNSPECIFIED"


class LinkConfidence(str, Enum):
    """Confidence level of linking an event to a target or operational issue."""
    EXPLICIT = "EXPLICIT"
    INFERRED_UNIQUE = "INFERRED_UNIQUE"
    AMBIGUOUS = "AMBIGUOUS"
    NONE = "NONE"


class TargetKind(str, Enum):
    """Classification of physical or logical equipment endpoints."""
    POS_TERMINAL = "POS_TERMINAL"
    PRINTER = "PRINTER"
    PAYMENT_PED = "PAYMENT_PED"
    NET_INFRA = "NET_INFRA"
    SERVER_DB = "SERVER_DB"
    OTHER = "OTHER"


class ProblemCategory(str, Enum):
    """Operational/technical category of a reported issue."""
    CONNECTIVITY_LAN = "CONNECTIVITY_LAN"
    PRINTING_HARDWARE = "PRINTING_HARDWARE"
    CARD_PAYMENT_EFT = "CARD_PAYMENT_EFT"
    DATABASE_BACKUP = "DATABASE_BACKUP"
    RECIPE_PRODUCTION = "RECIPE_PRODUCTION"
    CASHUP_BALANCING = "CASHUP_BALANCING"
    LICENSE_SECURITY = "LICENSE_SECURITY"
    GENERAL_SUPPORT = "GENERAL_SUPPORT"
    UNKNOWN = "UNKNOWN"


class IssueState(str, Enum):
    """Lifecycle state of an individual operational issue."""
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    RESOLVED_UNCONFIRMED = "RESOLVED_UNCONFIRMED"
    UNRESOLVED_CONFIRMED = "UNRESOLVED_CONFIRMED"
    REVIEW = "REVIEW"


class RemoteIdAnchor(str, Enum):
    """Remote software anchor verifying a candidate connection identifier."""
    ANYDESK = "ANYDESK"
    TEAMVIEWER = "TEAMVIEWER"
    GENERIC_REMOTE = "GENERIC_REMOTE"
    POSITIONAL = "POSITIONAL"
    NONE = "NONE"


class RemoteIdStatus(str, Enum):
    """Safety status of a remote connection identifier candidate."""
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


# --- Structural Models ---

class EvidenceSpan(BaseModel):
    """Character-level span within transcript text for fine-grained provenance."""
    turn_index: int = Field(description="0-indexed turn position in transcript.")
    start_char: int = Field(description="Starting character offset in turn text.")
    end_char: int = Field(description="Ending character offset in turn text.")
    text: str = Field(description="Exact verbatim span text.")
    role: str = Field(default="PRIMARY", description="Role of this span: PRIMARY, PIVOT, CONTRAST, TARGET_SUBJECT.")


class EvidenceItem(BaseModel):
    """Immutable audit trail linking an extracted fact or claim to transcript source."""
    fact: str = Field(description="The extracted fact or claim.")
    epistemic_type: EpistemicType = Field(default=EpistemicType.DIRECT_FACT, description="Fact vs interpretation.")
    turn_index: Optional[int] = Field(default=None, description="0-indexed turn position in transcript.")
    timestamp: Optional[str] = Field(default=None, description="Timestamp string (HH:MM:SS) of the turn.")
    speaker: Optional[str] = Field(default=None, description="CONSULTANT or CLIENT.")
    source_quote: str = Field(description="Exact verbatim or near-verbatim quote from transcript supporting this fact.")
    spans: List[EvidenceSpan] = Field(default_factory=list, description="Constituent character-level spans for compound evidence.")


class TargetEntity(BaseModel):
    """Physical device, till, peripheral, or network node identified in the conversation."""
    target_id: str = Field(description="Unique identifier for this target (e.g. target_printer_kitchen).")
    canonical_name: str = Field(description="Human-readable canonical target label.")
    kind: TargetKind = Field(default=TargetKind.OTHER, description="Equipment classification.")
    ordinal: Optional[int] = Field(default=None, description="Device ordinal if stated (e.g. 1 for Till 1).")
    location: Optional[str] = Field(default=None, description="Physical location if stated (e.g. second floor, bar).")


class OperationalIssue(BaseModel):
    """Distinct technical or operational problem tracked independently across dialogue."""
    issue_id: str = Field(description="Unique identifier for this issue (e.g. issue_pos1_sync).")
    target_id: Optional[str] = Field(default=None, description="Target entity bound to this issue, if localized.")
    category: ProblemCategory = Field(default=ProblemCategory.GENERAL_SUPPORT, description="Symptom/problem category.")
    symptom_description: str = Field(default="", description="Concise symptom summary.")
    current_state: IssueState = Field(default=IssueState.OPEN, description="Current lifecycle state of this issue.")
    event_history_ids: List[str] = Field(default_factory=list, description="Ordered IDs of evidence events touching this issue.")


class EvidenceEvent(BaseModel):
    """Chronologically ordered atomic evidence event extracted from a dialogue clause."""
    event_id: str = Field(description="Unique event ID (e.g. t0.c0.e0).")
    turn_index: int = Field(description="Transcript turn index.")
    clause_index: int = Field(default=0, description="Clause index within turn.")
    sub_index: int = Field(default=0, description="Order index within clause.")
    speaker: ActorRole = Field(default=ActorRole.UNKNOWN, description="Speaker role uttering this evidence.")
    claim_type: ClaimType = Field(default=ClaimType.OTHER_CONTEXT, description="Categorical nature of the claim.")
    polarity: Polarity = Field(default=Polarity.AFFIRMATIVE, description="Affirmative vs negated predicate.")
    temporal_scope: TemporalScope = Field(default=TemporalScope.PRESENT_OR_CURRENT, description="Time horizon described.")
    target_id: Optional[str] = Field(default=None, description="Associated target entity ID.")
    issue_id: Optional[str] = Field(default=None, description="Associated operational issue ID.")
    link_confidence: LinkConfidence = Field(default=LinkConfidence.NONE, description="Confidence of issue/target association.")
    source_quote: str = Field(default="", description="Verbatim clause text supporting this event.")
    span: Optional[Tuple[int, int]] = Field(default=None, description="Character offsets (start, end) within turn text.")
    supersedes_event_id: Optional[str] = Field(default=None, description="ID of earlier event explicitly superseded by this one.")
    review_reasons: List[str] = Field(default_factory=list, description="Reason codes if this event contains ambiguity.")


class RemoteIdCandidate(BaseModel):
    """Evaluated remote connection ID candidate with provenance and safety validation."""
    candidate_id: str = Field(description="Unique candidate identifier.")
    value: Optional[str] = Field(default=None, description="Extracted numerical identifier (e.g. 419 883 201).")
    turn_index: int = Field(description="Turn index where candidate appeared.")
    clause_index: int = Field(default=0, description="Clause index where candidate appeared.")
    speaker: ActorRole = Field(default=ActorRole.UNKNOWN, description="Speaker offering the candidate.")
    anchor: RemoteIdAnchor = Field(default=RemoteIdAnchor.NONE, description="Remote software anchor category.")
    site_label: Optional[str] = Field(default=None, description="Associated site or location label.")
    target_id: Optional[str] = Field(default=None, description="Associated equipment target.")
    status: RemoteIdStatus = Field(default=RemoteIdStatus.ACTIVE, description="Safety lifecycle status.")
    superseded_by: Optional[str] = Field(default=None, description="ID of superseding candidate if corrected.")
    consultant_connected: bool = Field(default=False, description="Whether consultant explicitly verified connection to this ID.")
    rejected_reasons: List[str] = Field(default_factory=list, description="Audit log of reasons if candidate was rejected.")


class ReviewReason(BaseModel):
    """Machine-readable explanation for why human review is required."""
    code: str = Field(description="Machine-readable error/review code (e.g. AMBIGUOUS_ISSUE_SCOPE).")
    message: str = Field(description="Human-readable guidance explaining the uncertainty.")
    event_ids: List[str] = Field(default_factory=list, description="IDs of evidence events triggering this review.")
    turn_indices: List[int] = Field(default_factory=list, description="Turn indices involved.")
    field_name: Optional[str] = Field(default=None, description="Specific output field impacted, if applicable.")


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
    schema_version: str = Field(default="2.2.0", description="Schema version.")
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

    # Phase 3 Additive Models & Fields (Fully backward-compatible with defaults)
    technical_resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.UNKNOWN,
        description="Canonical technical outcome without follow-up commitment conflation."
    )
    review_required: bool = Field(
        default=False,
        description="Flag indicating human review is required due to ambiguity, conflict, or safety gates."
    )
    review_reasons: List[ReviewReason] = Field(
        default_factory=list,
        description="Structured machine-readable reasons why human review is required."
    )
    outcome_reasons: List[str] = Field(
        default_factory=list,
        description="Descriptive reasons for status assignment (e.g. NO_CONFIRMATION_OF_FIX) that do not trigger human review."
    )
    closure_blockers: List[str] = Field(
        default_factory=list,
        description="Explicit reasons why this case cannot be marked Closed in CRM."
    )
    field_flags: Dict[str, str] = Field(
        default_factory=dict,
        description="Field-specific warnings (e.g. {'Remote_Connection_ID__c': 'MULTIPLE_ACTIVE_REMOTE_IDS'})."
    )
    targets: List[TargetEntity] = Field(
        default_factory=list,
        description="Identified physical endpoints, tills, devices, or network nodes."
    )
    issues: List[OperationalIssue] = Field(
        default_factory=list,
        description="Distinct reported problems tracked across dialogue."
    )
    events: List[EvidenceEvent] = Field(
        default_factory=list,
        description="Chronological evidence events extracted from transcript."
    )
    remote_id_candidates: List[RemoteIdCandidate] = Field(
        default_factory=list,
        description="All evaluated remote connection candidates with provenance and safety statuses."
    )

    @model_validator(mode="before")
    @classmethod
    def sync_technical_resolution(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Resolve technical_resolution_status if not explicitly provided
            if "technical_resolution_status" not in data and "resolution_status" in data:
                raw_status = data["resolution_status"]
                if raw_status in (ResolutionStatus.FOLLOW_UP_REQUIRED, "FOLLOW_UP_REQUIRED"):
                    data["technical_resolution_status"] = ResolutionStatus.UNKNOWN
                    reasons = list(data.get("outcome_reasons") or [])
                    if "LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS" not in reasons:
                        reasons.append("LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS")
                    data["outcome_reasons"] = reasons
                else:
                    data["technical_resolution_status"] = raw_status
            elif data.get("technical_resolution_status") in (ResolutionStatus.FOLLOW_UP_REQUIRED, "FOLLOW_UP_REQUIRED"):
                # Canonical technical status can NEVER be FOLLOW_UP_REQUIRED
                data["technical_resolution_status"] = ResolutionStatus.UNKNOWN
                reasons = list(data.get("outcome_reasons") or [])
                if "LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS" not in reasons:
                    reasons.append("LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS")
                data["outcome_reasons"] = reasons
        return data
