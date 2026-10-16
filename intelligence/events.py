"""
Semantic Event Extractor for Speak V2 Conversation Intelligence.

Extracts atomic EvidenceEvent instances from segmented dialogue clauses.
Decouples:
1. Claim Type (FAILURE_ASSERTION, RESOLUTION_ASSERTION, DIAGNOSTIC_ACTION, etc.)
2. Predicate Polarity (AFFIRMATIVE, NEGATED, UNCERTAIN)
3. Temporal Scope (PRESENT_OR_CURRENT, RETROSPECTIVE_PAST, PROSPECTIVE_FUTURE, UNSPECIFIED)

Guarantees:
- Syntactic negators ('not', 'never', 'didn't') are not conflated with failure events.
- Correlative 'not only ... but also ...' is recognized as emphatic affirmative.
- Retrospective statements ('was working earlier') are isolated from current states ('failed now').
- Speculative/uncertain assertions ('maybe', 'not sure') remain Polarity.UNCERTAIN and are not forced into false confidence.
- Accurate character spans and event ordering are preserved.
"""

import re
from typing import List, Optional, Tuple

from intelligence.models import (
    ActorRole,
    ClaimType,
    EvidenceEvent,
    LinkConfidence,
    Polarity,
    TemporalScope,
)
from intelligence.segmenter import SegmentedClause, segment_turn


# --- Linguistic Lexicons ---

UNCERTAINTY_CUES = [
    "maybe", "perhaps", "might be", "could be", "not sure", "don't know",
    "do not know", "possibly", "i think maybe", "seems like maybe", "hard to tell"
]

FAILURE_LEXICON = [
    "fail", "failed", "fails", "failing", "failure", "broken", "offline", "jammed",
    "jamming", "jam", "jams",
    "crashing", "crashes", "crashed", "corrupt", "damaged", "unreachable",
    "dead", "died", "error", "errors", "socket error", "stopped working",
    "stopped printing", "not responding", "no response", "refused", "blank screen",
    "freezing", "frozen", "freeze", "freezes",
    "problem", "problems", "down", "trouble", "issue", "issues"
]

RESOLUTION_LEXICON = [
    "working", "works", "worked", "fixed", "sorted", "online", "printing",
    "operational", "resolved", "cleared", "back up", "good now",
    "all sorted", "working fine", "printing fine", "connected fine", "solved",
    "that should fix it", "should fix it", "should fix", "work"
]

DIAGNOSTIC_LEXICON = [
    "checked", "checking", "pinged", "ping", "tested", "testing", "inspected",
    "looked at", "looking at", "verified", "verifying", "logged in to see"
]

REMEDIAL_LEXICON = [
    "rebooted", "reboot", "rebooting", "restarted", "restart", "restarting",
    "shut down", "shutting down", "power down",
    "cleared spooler", "reseated", "re-cabled", "swapped", "power cycled",
    "reinstalled", "reset", "reconnected", "reconnect", "reconnecting"
]

COMMITMENT_LEXICON = [
    "call you back", "will call", "follow up", "call tomorrow",
    "give you an update", "investigate and call"
]

CONNECTION_LEXICON = [
    "connected remotely", "connected now", "logged in via anydesk",
    "connected via anydesk", "remote connection established"
]

PAST_TEMPORAL_CUES = [
    "earlier", "was working", "were working", "was connected", "were connected",
    "previously", "before", "initially", "at first", "yesterday", "last week", "prior to"
]

FUTURE_TEMPORAL_CUES = [
    "tomorrow", "later", "will", "going to", "will connect", "going to connect",
    "let me connect", "about to connect", "sometime next week", "next monday", "shortly", "in 15 minutes"
]

PRESENT_TEMPORAL_CUES = [
    "now", "currently", "at the moment", "right now", "still", "today"
]

# Negation words applied to predicates
NEGATION_WORDS = ["not", "never", "no", "nothing", "neither", "didn't", "did not", "doesn't", "does not", "won't", "cannot", "can't"]


def _detect_temporal_scope(text: str, discourse_marker: Optional[str] = None) -> TemporalScope:
    """Determines the temporal horizon of the clause."""
    lower = text.lower()
    
    # 1. Check explicit retrospective past indicators
    if any(re.search(r"\b" + cue + r"\b", lower) for cue in PAST_TEMPORAL_CUES):
        return TemporalScope.RETROSPECTIVE_PAST

    # Past tense of working specifically indicates retrospective state if qualified or followed by contrast
    if re.search(r"\b(?:was|were|had been)\s+(?:working|printing|online|fine)\b", lower):
        return TemporalScope.RETROSPECTIVE_PAST

    # 2. Check future commitment / prospective indicators
    if any(re.search(r"\b" + cue + r"\b", lower) for cue in FUTURE_TEMPORAL_CUES):
        return TemporalScope.PROSPECTIVE_FUTURE

    # 3. Check present / current indicators
    if any(re.search(r"\b" + cue + r"\b", lower) for cue in PRESENT_TEMPORAL_CUES):
        return TemporalScope.PRESENT_OR_CURRENT

    # Default to PRESENT_OR_CURRENT for general assertions in a support call
    return TemporalScope.PRESENT_OR_CURRENT


def _extract_target_references(text: str) -> List[Tuple[Optional[str], LinkConfidence]]:
    """Extracts all candidate target equipment references from the clause."""
    lower = text.lower()
    targets: List[Tuple[str, LinkConfidence]] = []

    # Plural / dual references: "both tills", "both terminals", "both printers", "two terminals", etc.
    if re.search(r"\b(?:both|two|2)\s+(?:tills|terminals|pos)\b", lower):
        return [("target_pos_1", LinkConfidence.EXPLICIT), ("target_pos_2", LinkConfidence.EXPLICIT)]
    if re.search(r"\b(?:both|two|2)\s+printers\b", lower):
        return [("target_printer_1", LinkConfidence.EXPLICIT), ("target_printer_2", LinkConfidence.EXPLICIT)]

    # Ordinals
    for m in re.finditer(r"\b(?:pos|terminal|till)\s*(\d+)\b", lower):
        targets.append((f"target_pos_{m.group(1)}", LinkConfidence.EXPLICIT))

    if re.search(r"\b(?:first|1st)\s+(?:pos|terminal|till)\b", lower):
        targets.append(("target_pos_1", LinkConfidence.EXPLICIT))
    if re.search(r"\b(?:second|2nd)\s+(?:pos|terminal|till)\b", lower):
        targets.append(("target_pos_2", LinkConfidence.EXPLICIT))

    # Printers with ordinals
    m_p = re.search(r"\b(?:printer|bill printer|slip printer|kitchen printer|receipt printer)\s*(\d+)\b", lower)
    if m_p:
        targets.append((f"target_printer_{m_p.group(1)}", LinkConfidence.EXPLICIT))
    if re.search(r"\b(?:first|1st)\s+printer\b", lower):
        targets.append(("target_printer_1", LinkConfidence.EXPLICIT))
    if re.search(r"\b(?:second|2nd)\s+printer\b", lower):
        targets.append(("target_printer_2", LinkConfidence.EXPLICIT))

    # Specific printers
    if "receipt printer" in lower or "slip printer" in lower:
        targets.append(("target_receipt_printer", LinkConfidence.EXPLICIT))
    if "kitchen printer" in lower or "order printer" in lower:
        targets.append(("target_kitchen_printer", LinkConfidence.EXPLICIT))
    if "bill printer" in lower:
        targets.append(("target_bill_printer", LinkConfidence.EXPLICIT))

    # Generic printer (if no specific printer matched yet)
    if "printer" in lower and not any("printer" in t[0] for t in targets):
        targets.append(("target_printer", LinkConfidence.EXPLICIT))
    elif "printing" in lower and not targets:
        targets.append(("target_printer", LinkConfidence.EXPLICIT))

    # Card terminal / Payment PED
    if "card machine" in lower or re.search(r"\b(?:ped|pax|reader)\b", lower):
        targets.append(("target_ped", LinkConfidence.EXPLICIT))
    elif "card terminal" in lower:
        targets.append(("target_terminal", LinkConfidence.EXPLICIT))

    # Generic terminal / till (if not already matched)
    if ("terminal" in lower or "till" in lower or "pos" in lower or "workstation" in lower) and not any(t[0].startswith("target_pos_") or t[0] == "target_terminal" for t in targets):
        targets.append(("target_terminal", LinkConfidence.EXPLICIT))

    # Barcode scanner / Scanner
    if "scanner" in lower:
        m_till = re.search(r"\b(?:pos|terminal|till)\s*(\d+)\b", lower)
        if m_till:
            targets.append((f"target_pos_{m_till.group(1)}", LinkConfidence.EXPLICIT))
        else:
            targets.append(("target_scanner", LinkConfidence.EXPLICIT))

    # Network
    if "switch" in lower or "router" in lower or re.search(r"\b(?:lan|network)\b(?!\s+(?:cable|lead|wire|cord))\b", lower):
        targets.append(("target_network", LinkConfidence.EXPLICIT))

    # De-duplicate while preserving order
    unique_targets: List[Tuple[str, LinkConfidence]] = []
    seen = set()
    for tid, conf in targets:
        if tid not in seen:
            seen.add(tid)
            unique_targets.append((tid, conf))

    # If multiple targets extracted but no coordinating conjunction, it's an attributive specifier (e.g. 'POS1 bill printer')
    has_conjunction = any(c in lower for c in [" and ", " as well as ", " & ", "both ", "two ", "2 "])
    if not has_conjunction and len(unique_targets) > 1:
        if any("printer" in t[0] for t in unique_targets) and any("pos" in t[0] or "terminal" in t[0] for t in unique_targets):
            unique_targets = [t for t in unique_targets if "printer" in t[0]]

    if not unique_targets:
        return [(None, LinkConfidence.NONE)]
    return unique_targets


def _extract_target_reference(text: str) -> Tuple[Optional[str], LinkConfidence]:
    """Single-target extractor returning the first detected target."""
    return _extract_target_references(text)[0]


def extract_events_from_clause(
    clause: SegmentedClause,
    speaker: ActorRole = ActorRole.UNKNOWN,
    full_turn_text: Optional[str] = None
) -> List[EvidenceEvent]:
    """
    Extracts one or more typed EvidenceEvent candidates from a single segmented clause.
    """
    text = clause.text
    lower = text.lower()
    events: List[EvidenceEvent] = []
    
    # Base event ID prefix
    event_id_prefix = f"t{clause.turn_index}.c{clause.clause_index}"

    # 1. Epistemic Uncertainty Check
    is_uncertain = any(re.search(r"\b" + re.escape(u) + r"\b", lower) for u in UNCERTAINTY_CUES)
    
    # 2. Temporal Scope
    temporal_scope = _detect_temporal_scope(text, clause.discourse_marker)

    # 3. Target candidates
    target_refs = _extract_target_references(text)

    # 4. Check for Correlative 'not only' special casing
    # 'Not only does X work' -> This is an affirmative resolution, NOT a negation!
    is_correlative_not_only = (clause.discourse_marker == "not only") or lower.startswith("not only")

    # 5. Determine Predicate Negation (excluding 'not only')
    has_negator = False
    if not is_correlative_not_only:
        for nw in NEGATION_WORDS:
            # Check for word boundary negation
            if re.search(r"\b" + nw + r"\b", lower):
                has_negator = True
                break

    # 6. Classify Claim Type and Polarity
    claim_type = ClaimType.OTHER_CONTEXT
    polarity = Polarity.AFFIRMATIVE

    if is_uncertain:
        polarity = Polarity.UNCERTAIN

    # Diagnostic Actions
    if any(re.search(r"\b" + d + r"\b", lower) for d in DIAGNOSTIC_LEXICON) and speaker == ActorRole.CONSULTANT:
        claim_type = ClaimType.DIAGNOSTIC_ACTION
        polarity = Polarity.AFFIRMATIVE if not has_negator else Polarity.NEGATED

    # Remedial Actions
    elif any(re.search(r"\b" + r + r"\b", lower) for r in REMEDIAL_LEXICON) and speaker == ActorRole.CONSULTANT:
        claim_type = ClaimType.REMEDIAL_ACTION
        polarity = Polarity.AFFIRMATIVE if not has_negator else Polarity.NEGATED

    # Connection Established
    elif any(re.search(r"\b" + c + r"\b", lower) for c in CONNECTION_LEXICON):
        claim_type = ClaimType.CONNECTION_ESTABLISHED
        if has_negator or any(re.search(r"\b" + nw + r"\b", lower) for nw in ["not", "never", "cannot", "can't", "no", "didn't", "failed to"]):
            polarity = Polarity.NEGATED
        elif is_uncertain:
            polarity = Polarity.UNCERTAIN
        else:
            polarity = Polarity.AFFIRMATIVE

    # Commitments
    elif any(re.search(r"\b" + c + r"\b", lower) for c in COMMITMENT_LEXICON):
        claim_type = ClaimType.COMMITMENT
        polarity = Polarity.AFFIRMATIVE

    # Failure Predicates: "failed", "broken", "offline", "jammed", "socket error", "problem"
    elif any(re.search(r"\b" + f + r"\b", lower) and not (f == "down" and ("shut down" in lower or "power down" in lower)) and not (f in ["problem", "problems", "issue", "issues"] and any(rp in lower for rp in ["solved", "fixed", "resolved", "sorted"])) for f in FAILURE_LEXICON):
        claim_type = ClaimType.FAILURE_ASSERTION
        if is_uncertain:
            polarity = Polarity.UNCERTAIN
        elif re.search(r"\b(?:not|didn't|did not|never|no)\s+(?:fail|failed|broken|crash|crashed|error|errors|problem)\b", lower):
            # "has not failed", "didn't fail", "no errors"
            polarity = Polarity.NEGATED
        else:
            # "failed", "is broken", "offline", "not taking transactions", "not syncing"
            polarity = Polarity.AFFIRMATIVE

    # Resolution Predicates: "working", "works", "fixed", "sorted", "online"
    # Procedural phrases ("work on", "working on", "let's work", etc.) are excluded from resolution assertions
    elif any(re.search(r"\b" + r + r"\b", lower) for r in RESOLUTION_LEXICON) and \
         not re.search(r"\b(?:work|working)\s+on\b", lower) and \
         not re.search(r"\b(?:let's|lets|let us|going to|will|about to|can|try to|want to|get to)\s+work\b", lower):
        claim_type = ClaimType.RESOLUTION_ASSERTION
        if is_uncertain:
            polarity = Polarity.UNCERTAIN
        elif is_correlative_not_only:
            # "Not only does the terminal work" -> strictly AFFIRMATIVE resolution!
            polarity = Polarity.AFFIRMATIVE
        elif re.search(r"\b(?:not|didn't|did not|never|doesn't|does not|won't|cannot|can't|nothing\s+is|neither)\s+(?:\w+\s+){0,2}(?:working|works|worked|work|fixed|sorted|online|printing|operational|resolved|cleared|solved)\b", lower) or re.search(r"\b(?:is|are|was|were)\s+(?:not|never)\b", lower):
            # "is not working", "does not work" -> Negated resolution assertion
            polarity = Polarity.NEGATED
        else:
            polarity = Polarity.AFFIRMATIVE

    # Elliptical failure / negative expressions: "printer does not", "second till doesn't"
    elif has_negator and any(k in lower for k in ["does not", "doesn't", "is not", "isn't", "not"]) and any(t[0] is not None for t in target_refs):
        claim_type = ClaimType.RESOLUTION_ASSERTION
        polarity = Polarity.NEGATED if not is_uncertain else Polarity.UNCERTAIN

    # Construct the event(s)
    review_reasons = []
    if polarity == Polarity.UNCERTAIN:
        review_reasons.append("UNCERTAIN_PREDICATE_EVIDENCE")

    for sub_idx, (t_id, link_conf) in enumerate(target_refs):
        event = EvidenceEvent(
            event_id=f"{event_id_prefix}.e{sub_idx}",
            turn_index=clause.turn_index,
            clause_index=clause.clause_index,
            sub_index=sub_idx,
            speaker=speaker,
            claim_type=claim_type,
            polarity=polarity,
            temporal_scope=temporal_scope,
            target_id=t_id,
            issue_id=None,  # Not decided at extraction level
            link_confidence=link_conf,
            source_quote=text,
            span=clause.span,
            review_reasons=review_reasons
        )
        events.append(event)
    return events


def extract_turn_events(
    text: str,
    turn_index: int = 0,
    speaker: ActorRole = ActorRole.UNKNOWN
) -> List[EvidenceEvent]:
    """
    End-to-end pipeline for a single turn: segments text and extracts all evidence events.
    """
    clauses = segment_turn(text, turn_index=turn_index)
    all_events: List[EvidenceEvent] = []
    for clause in clauses:
        clause_events = extract_events_from_clause(clause, speaker=speaker, full_turn_text=text)
        all_events.extend(clause_events)
    return all_events
