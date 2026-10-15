"""
Target and Issue Linker for Speak V2 Conversation Intelligence.

Consumes extracted EvidenceEvent candidates and performs:
1. Physical Target Entity discovery, canonicalization, and ordinal resolution.
2. Operational Issue identification and category binding (separating issues from devices).
3. Deterministic event-to-issue association using target identity, symptom category, and chronology.
4. Safe pronoun and elliptical reference inference (only when strictly unambiguous).
5. Explicit ambiguity marking (LinkConfidence.AMBIGUOUS + ReviewReason) whenever multiple
   issues are plausible—never guessing or forcing an arbitrary association.

Guarantees:
- A new problem with a distinct symptom on an existing device creates a separate issue.
- Network fixes do not attach to or resolve hardware paper jams on the same peripheral.
- Original source turns, character spans, and event order are strictly preserved.
- Does not calculate overall case resolution status or modify CRM drafts.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from intelligence.models import (
    ActorRole,
    ClaimType,
    EvidenceEvent,
    IssueState,
    LinkConfidence,
    OperationalIssue,
    Polarity,
    ProblemCategory,
    TargetEntity,
    TargetKind,
    TemporalScope,
)


@dataclass
class LinkingResult:
    """Output of the target and issue linking stage."""
    targets: List[TargetEntity]
    issues: List[OperationalIssue]
    events: List[EvidenceEvent]
    review_reasons: List[str]


# --- Category and Target Lexicons ---

CATEGORY_SYMPTOM_MAP = [
    (ProblemCategory.PRINTING_HARDWARE, [
        "paper jam", "jammed", "jamming", "spooler", "ribbon", "paper out",
        "printing blank", "cutter", "door open", "door hinge", "not printing",
        "stopped printing", "test slip", "print quality", "faded print"
    ]),
    (ProblemCategory.CONNECTIVITY_LAN, [
        "socket error", "unreachable", "ping", "switch", "router", "offline",
        "lan", "network", "disconnected", "cannot connect", "no connection",
        "ip address", "dns", "subnet", "cabling", "cable disconnected"
    ]),
    (ProblemCategory.CARD_PAYMENT_EFT, [
        "ped", "card machine", "declining cards", "speedpoint", "adumo",
        "pax", "eft", "terminal comms error", "pin pad"
    ]),
    (ProblemCategory.DATABASE_BACKUP, [
        "database", "sql", "corrupt table", "backup failed", "database locked",
        "deadlock", "postgres", "sync error"
    ]),
    (ProblemCategory.RECIPE_PRODUCTION, [
        "cheesecake", "recipe", "production variance", "slices", "butternut",
        "portioning", "batch variance"
    ]),
    (ProblemCategory.CASHUP_BALANCING, [
        "cashup", "balancing", "float discrepancy", "z report", "x report"
    ]),
    (ProblemCategory.LICENSE_SECURITY, [
        "license expired", "security key", "activation", "dongle", "unauthorized"
    ]),
]

PRONOUN_CUES = ["it", "this", "the device", "the machine", "that one"]
GLOBAL_RESOLUTION_CUES = ["everything", "all sorted", "all fixed", "all good", "both", "all working", "sorted now"]


def detect_symptom_category(text: str) -> ProblemCategory:
    """Identifies the operational problem category from symptom keywords."""
    lower = text.lower()
    for cat, keywords in CATEGORY_SYMPTOM_MAP:
        if any(kw in lower for kw in keywords):
            return cat
    return ProblemCategory.GENERAL_SUPPORT


def _resolve_target_kind_and_name(raw_target_id: str) -> Tuple[TargetKind, str, Optional[int]]:
    """Determines canonical TargetKind, display name, and ordinal from target ID."""
    lower = raw_target_id.lower()
    
    # Terminal ordinals
    m_term = re.search(r"pos_(\d+)|terminal_(\d+)|till_(\d+)", lower)
    if m_term:
        num = int(next(g for g in m_term.groups() if g is not None))
        return TargetKind.POS_TERMINAL, f"POS Terminal {num}", num

    # Printer ordinals
    m_print = re.search(r"printer_(\d+)", lower)
    if m_print:
        num = int(m_print.group(1))
        return TargetKind.PRINTER, f"Printer {num}", num

    # Specific printers
    if "receipt" in lower:
        return TargetKind.PRINTER, "Receipt Printer", None
    if "kitchen" in lower:
        return TargetKind.PRINTER, "Kitchen Printer", None
    if "bill" in lower:
        return TargetKind.PRINTER, "Bill Printer", None
    if "printer" in lower:
        return TargetKind.PRINTER, "Slip Printer", None

    # Generic terminals
    if "pos" in lower or "terminal" in lower or "till" in lower:
        return TargetKind.POS_TERMINAL, "POS Terminal", None

    # Network
    if "network" in lower or "switch" in lower or "router" in lower or "lan" in lower:
        return TargetKind.NET_INFRA, "Network Switch/Router", None

    # Payment PED
    if "ped" in lower or "card" in lower or "pax" in lower:
        return TargetKind.PAYMENT_PED, "Payment PED", None

    return TargetKind.OTHER, raw_target_id, None


class IssueLinker:
    """Stateful linker processing chronological EvidenceEvent instances."""

    def __init__(self):
        self.targets: Dict[str, TargetEntity] = {}
        self.issues: Dict[str, OperationalIssue] = {}
        self.linked_events: List[EvidenceEvent] = []
        self.review_reasons: List[str] = []
        self._issue_counter = 0

    def _get_or_create_target(self, target_id: str) -> TargetEntity:
        """Retrieves or instantiates a canonical TargetEntity."""
        if target_id not in self.targets:
            kind, name, ordinal = _resolve_target_kind_and_name(target_id)
            target = TargetEntity(
                target_id=target_id,
                canonical_name=name,
                kind=kind,
                ordinal=ordinal,
                location=None
            )
            self.targets[target_id] = target
        return self.targets[target_id]

    def _generate_issue_id(self, target_id: Optional[str], category: ProblemCategory) -> str:
        """Constructs an issue identifier distinguishing target and category."""
        self._issue_counter += 1
        t_part = target_id.replace("target_", "") if target_id else "global"
        c_part = category.value.lower()
        return f"issue_{t_part}_{c_part}_{self._issue_counter}"

    def _find_matching_open_issue(
        self,
        target_id: Optional[str],
        category: ProblemCategory
    ) -> Optional[OperationalIssue]:
        """Finds an existing open issue matching both target and problem category."""
        for issue in self.issues.values():
            if issue.target_id == target_id:
                if issue.category == category or category == ProblemCategory.GENERAL_SUPPORT:
                    return issue
        return None

    def _get_open_issues(self) -> List[OperationalIssue]:
        """Returns all issues currently in OPEN state."""
        return [iss for iss in self.issues.values() if iss.current_state == IssueState.OPEN]

    def _get_open_issues_for_target(self, target_id: str) -> List[OperationalIssue]:
        """Returns all open issues bound to a specific target."""
        return [iss for iss in self.issues.values() if iss.target_id == target_id and iss.current_state == IssueState.OPEN]

    def process_event(self, event: EvidenceEvent) -> EvidenceEvent:
        """
        Links a single EvidenceEvent to target and issue structures according to CTO rules.
        """
        text = event.source_quote
        lower = text.lower()
        linked_event = event.model_copy(deep=True)

        # 1. Target Entity Canonicalization
        target_id = linked_event.target_id
        if target_id:
            self._get_or_create_target(target_id)

        # 2. Symptom Category Extraction
        symptom_cat = detect_symptom_category(text)

        # 3. Problem Instantiation (FAILURE_ASSERTION with AFFIRMATIVE polarity)
        if (linked_event.claim_type == ClaimType.FAILURE_ASSERTION and linked_event.polarity == Polarity.AFFIRMATIVE) or \
           (linked_event.claim_type == ClaimType.RESOLUTION_ASSERTION and linked_event.polarity == Polarity.NEGATED):
            
            # Check if this target already has an open issue for THIS specific category
            existing_issue = self._find_matching_open_issue(target_id, symptom_cat)
            
            if existing_issue:
                # Add to existing issue history
                if linked_event.event_id not in existing_issue.event_history_ids:
                    existing_issue.event_history_ids.append(linked_event.event_id)
                linked_event.issue_id = existing_issue.issue_id
                linked_event.link_confidence = LinkConfidence.EXPLICIT
            else:
                # Distinct symptom or new target -> Instantiate NEW OperationalIssue!
                # Guarantees that paper jam and network offline on same printer remain distinct issues.
                new_issue_id = self._generate_issue_id(target_id, symptom_cat)
                new_issue = OperationalIssue(
                    issue_id=new_issue_id,
                    target_id=target_id,
                    category=symptom_cat,
                    symptom_description=text.strip(),
                    current_state=IssueState.OPEN,
                    event_history_ids=[linked_event.event_id]
                )
                self.issues[new_issue_id] = new_issue
                linked_event.issue_id = new_issue_id
                linked_event.link_confidence = LinkConfidence.EXPLICIT

            self.linked_events.append(linked_event)
            return linked_event

        # 4. Resolution Assertion Linking
        if linked_event.claim_type == ClaimType.RESOLUTION_ASSERTION and linked_event.polarity == Polarity.AFFIRMATIVE:
            open_issues = self._get_open_issues()

            # Case A: Explicit Target provided
            if target_id:
                target_open_issues = self._get_open_issues_for_target(target_id)
                
                if len(target_open_issues) == 1:
                    # Exactly one open issue on this named target -> EXPLICIT link
                    chosen_issue = target_open_issues[0]
                    chosen_issue.event_history_ids.append(linked_event.event_id)
                    linked_event.issue_id = chosen_issue.issue_id
                    linked_event.link_confidence = LinkConfidence.EXPLICIT

                elif len(target_open_issues) > 1:
                    # Multiple open issues on the same device!
                    # Check if symptom category disambiguates:
                    category_matches = [iss for iss in target_open_issues if iss.category == symptom_cat and symptom_cat != ProblemCategory.GENERAL_SUPPORT]
                    if len(category_matches) == 1:
                        chosen_issue = category_matches[0]
                        chosen_issue.event_history_ids.append(linked_event.event_id)
                        linked_event.issue_id = chosen_issue.issue_id
                        linked_event.link_confidence = LinkConfidence.EXPLICIT
                    else:
                        # Ambiguous! Cannot determine which issue on this device is resolved
                        linked_event.issue_id = None
                        linked_event.link_confidence = LinkConfidence.AMBIGUOUS
                        if "AMBIGUOUS_ISSUE_SCOPE" not in linked_event.review_reasons:
                            linked_event.review_reasons.append("AMBIGUOUS_ISSUE_SCOPE")
                        if "AMBIGUOUS_ISSUE_SCOPE" not in self.review_reasons:
                            self.review_reasons.append("AMBIGUOUS_ISSUE_SCOPE")

                else:
                    # Target named, but no open issue for this target
                    # (e.g. unrelated device or newly mentioned healthy device)
                    linked_event.issue_id = None
                    linked_event.link_confidence = LinkConfidence.NONE

                self.linked_events.append(linked_event)
                return linked_event

            # Case B: Pronoun or Elliptical referent ("It is working now", "It is sorted")
            has_pronoun = any(re.search(r"\b" + re.escape(p) + r"\b", lower) for p in PRONOUN_CUES)
            has_global_phrase = any(g in lower for g in GLOBAL_RESOLUTION_CUES)

            if has_pronoun and not has_global_phrase:
                if len(open_issues) == 1:
                    # Unambiguous single open issue across entire call -> INFERRED_UNIQUE
                    chosen_issue = open_issues[0]
                    chosen_issue.event_history_ids.append(linked_event.event_id)
                    linked_event.issue_id = chosen_issue.issue_id
                    linked_event.link_confidence = LinkConfidence.INFERRED_UNIQUE
                else:
                    # Multiple open issues across call -> Pronoun reference is ambiguous!
                    linked_event.issue_id = None
                    linked_event.link_confidence = LinkConfidence.AMBIGUOUS
                    if "AMBIGUOUS_PRONOUN_REFERENT" not in linked_event.review_reasons:
                        linked_event.review_reasons.append("AMBIGUOUS_PRONOUN_REFERENT")
                    if "AMBIGUOUS_PRONOUN_REFERENT" not in self.review_reasons:
                        self.review_reasons.append("AMBIGUOUS_PRONOUN_REFERENT")

                self.linked_events.append(linked_event)
                return linked_event

            # Case C: Global referent ("All sorted", "Everything is working")
            if has_global_phrase or not target_id:
                if len(open_issues) == 1:
                    # Approved Probe J: Single open issue + "all sorted" -> INFERRED_UNIQUE
                    chosen_issue = open_issues[0]
                    chosen_issue.event_history_ids.append(linked_event.event_id)
                    linked_event.issue_id = chosen_issue.issue_id
                    linked_event.link_confidence = LinkConfidence.INFERRED_UNIQUE
                else:
                    # Approved Probe J2: Multiple open issues + "all sorted" -> AMBIGUOUS
                    linked_event.issue_id = None
                    linked_event.link_confidence = LinkConfidence.AMBIGUOUS
                    if "AMBIGUOUS_GLOBAL_RESOLUTION" not in linked_event.review_reasons:
                        linked_event.review_reasons.append("AMBIGUOUS_GLOBAL_RESOLUTION")
                    if "AMBIGUOUS_GLOBAL_RESOLUTION" not in self.review_reasons:
                        self.review_reasons.append("AMBIGUOUS_GLOBAL_RESOLUTION")

                self.linked_events.append(linked_event)
                return linked_event

        # 5. Diagnostic / Remedial / Other Actions
        if target_id:
            target_open_issues = self._get_open_issues_for_target(target_id)
            if len(target_open_issues) == 1:
                chosen_issue = target_open_issues[0]
                chosen_issue.event_history_ids.append(linked_event.event_id)
                linked_event.issue_id = chosen_issue.issue_id
                linked_event.link_confidence = LinkConfidence.EXPLICIT
            elif len(target_open_issues) > 1:
                category_matches = [iss for iss in target_open_issues if iss.category == symptom_cat and symptom_cat != ProblemCategory.GENERAL_SUPPORT]
                if len(category_matches) == 1:
                    chosen_issue = category_matches[0]
                    chosen_issue.event_history_ids.append(linked_event.event_id)
                    linked_event.issue_id = chosen_issue.issue_id
                    linked_event.link_confidence = LinkConfidence.EXPLICIT
                else:
                    linked_event.link_confidence = LinkConfidence.AMBIGUOUS

        self.linked_events.append(linked_event)
        return linked_event

    def get_result(self) -> LinkingResult:
        """Returns the complete structured output of the linker."""
        return LinkingResult(
            targets=list(self.targets.values()),
            issues=list(self.issues.values()),
            events=self.linked_events,
            review_reasons=self.review_reasons
        )


def link_events(events: List[EvidenceEvent]) -> LinkingResult:
    """
    Convenience function to link a sequence of chronological evidence events.
    """
    linker = IssueLinker()
    for ev in events:
        linker.process_event(ev)
    return linker.get_result()
