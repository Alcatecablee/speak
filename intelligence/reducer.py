"""
Deterministic Per-Issue Reducer and Case Status Aggregator for Speak V2.

Consumes linked TargetEntity, OperationalIssue, and EvidenceEvent structures.
Enforces:
1. Independent Issue Lifecycles: Each issue transitions strictly via evidence
   reliably linked to that specific issue.
2. Temporal & Polarity Integrity: Retrospective positive claims ("worked earlier")
   do not resolve current open issues; current regressions strictly reopen resolved issues.
3. Ambiguity Containment: Ambiguous events or global referents never silently close issues.
4. Escalation Distinction: Tier-2 operational handoffs leave issues OPEN, while
   hardware replacement dispatches / conclusive no-fix determinations mark UNRESOLVED_CONFIRMED.
5. Cross-Issue Independence: Resolving one problem on a peripheral does not leak into
   or resolve another problem on the same peripheral.
6. Deterministic Case Aggregation: Canonical technical_resolution_status is derived
   strictly from the set of individual issue states and closure blockers.
"""

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
    ResolutionStatus,
    TargetEntity,
    TemporalScope,
)
from intelligence.linker import LinkingResult


@dataclass
class ReductionResult:
    """Output of the per-issue reduction and case status aggregation stage."""
    technical_resolution_status: ResolutionStatus
    issues: List[OperationalIssue]
    review_required: bool
    review_reasons: List[str]
    outcome_reasons: List[str]
    closure_blockers: List[str]


# Cues that distinguish definitive hardware replacement / conclusive remote no-fix
# from an ordinary tier-2 support hand-off
TERMINAL_HARDWARE_NO_FIX_CUES = [
    "hardware replacement", "replacement dispatched", "swap unit", "replace printer",
    "replace till", "replace ped", "cannot resolve remotely", "cannot fix remotely",
    "cannot be resolved over the phone", "cannot fix this over the phone",
    "refuse to troubleshoot", "refused to troubleshoot", "physically broken",
    "door hinge is broken", "latch hinge is broken", "logistics dispatch", "swap-out"
]

TIER_2_HANDOFF_CUES = [
    "escalate to tier 2", "escalated to tier 2", "escalating to tier 2",
    "escalate to second line", "escalated to second line", "escalating to second line",
    "escalate to 2nd line", "escalated to 2nd line", "escalating to 2nd line",
    "escalate to senior", "escalated to senior", "escalating to senior",
    "escalate to dev", "escalated to dev", "escalating to dev",
    "hand off to", "handed off to", "pass to accounts team",
    "pass to dev team", "logged ticket with tier 2"
]


class PerIssueReducer:
    """Deterministic state machine reducing events per issue and aggregating case outcome."""

    def __init__(
        self,
        issues: List[OperationalIssue],
        events: List[EvidenceEvent],
        targets: Optional[List[TargetEntity]] = None,
        initial_review_reasons: Optional[List[str]] = None
    ):
        # Deep copy or index issues by ID
        self.issues: Dict[str, OperationalIssue] = {
            iss.issue_id: iss.model_copy(deep=True) for iss in issues
        }
        self.events: List[EvidenceEvent] = sorted(
            events,
            key=lambda e: (e.turn_index, e.clause_index, e.sub_index)
        )
        self.targets: Dict[str, TargetEntity] = {
            t.target_id: t for t in (targets or [])
        }
        self.review_reasons: List[str] = list(initial_review_reasons or [])
        self.outcome_reasons: List[str] = []
        self.closure_blockers: List[str] = []

    def _is_terminal_hardware_or_no_fix(self, text: str) -> bool:
        """Determines if a statement establishes conclusive hardware swap or no remote fix."""
        lower = text.lower()
        return any(cue in lower for cue in TERMINAL_HARDWARE_NO_FIX_CUES)

    def _is_tier2_handoff(self, text: str) -> bool:
        """Determines if a statement is an operational handoff to another tier."""
        lower = text.lower()
        return any(cue in lower for cue in TIER_2_HANDOFF_CUES)

    def reduce_all(self) -> ReductionResult:
        """Executes chronological reduction across all issues."""
        
        # 1. Process each event chronologically
        for ev in self.events:
            # Check if this event links to a specific issue
            if not ev.issue_id or ev.issue_id not in self.issues:
                # If event was ambiguous, preserve review reason
                if ev.link_confidence == LinkConfidence.AMBIGUOUS:
                    for r in ev.review_reasons:
                        if r not in self.review_reasons:
                            self.review_reasons.append(r)
                continue

            # Event is linked to an issue
            issue = self.issues[ev.issue_id]

            # Ambiguous links must never transition issue states!
            if ev.link_confidence == LinkConfidence.AMBIGUOUS:
                for r in ev.review_reasons:
                    if r not in self.review_reasons:
                        self.review_reasons.append(r)
                continue

            # Process state transition for this issue
            self._apply_event_transition(issue, ev)

        # 2. Check for unresolved cross-speaker contradictions on each issue
        self._check_cross_speaker_contradictions()

        # 3. Aggregate case-level technical_resolution_status & closure blockers
        technical_status = self._aggregate_case_status()

        review_required = len(self.review_reasons) > 0 or any(
            iss.current_state == IssueState.REVIEW for iss in self.issues.values()
        )

        return ReductionResult(
            technical_resolution_status=technical_status,
            issues=list(self.issues.values()),
            review_required=review_required,
            review_reasons=list(dict.fromkeys(self.review_reasons)),
            outcome_reasons=list(dict.fromkeys(self.outcome_reasons)),
            closure_blockers=list(dict.fromkeys(self.closure_blockers))
        )

    def _apply_event_transition(self, issue: OperationalIssue, ev: EvidenceEvent) -> None:
        """Applies state machine transition rules for a single issue based on an evidence event."""
        text = ev.source_quote

        # Rule A: Affirmative Failure or Negated Resolution (Current Failure)
        if (ev.claim_type == ClaimType.FAILURE_ASSERTION and ev.polarity == Polarity.AFFIRMATIVE) or \
           (ev.claim_type == ClaimType.RESOLUTION_ASSERTION and ev.polarity == Polarity.NEGATED):
            
            if ev.temporal_scope == TemporalScope.PRESENT_OR_CURRENT:
                # Check if it's a definitive hardware failure / no remote fix
                if self._is_terminal_hardware_or_no_fix(text):
                    issue.current_state = IssueState.UNRESOLVED_CONFIRMED
                    if "HARDWARE_REPLACEMENT_DISPATCHED" not in self.outcome_reasons:
                        self.outcome_reasons.append("HARDWARE_REPLACEMENT_DISPATCHED")
                else:
                    if issue.current_state == IssueState.RESOLVED:
                        # Regression: was resolved, but failed again!
                        issue.current_state = IssueState.OPEN
                        if "ISSUE_REGRESSION_AFTER_RESOLUTION" not in self.outcome_reasons:
                            self.outcome_reasons.append("ISSUE_REGRESSION_AFTER_RESOLUTION")
                    elif issue.current_state != IssueState.UNRESOLVED_CONFIRMED:
                        issue.current_state = IssueState.OPEN

        # Rule B: Affirmative Resolution
        elif ev.claim_type == ClaimType.RESOLUTION_ASSERTION and ev.polarity == Polarity.AFFIRMATIVE:
            if ev.temporal_scope == TemporalScope.RETROSPECTIVE_PAST:
                # Retrospective past: "was working earlier", "worked fine yesterday"
                # Does NOT resolve a current open issue!
                pass
            elif ev.temporal_scope == TemporalScope.PRESENT_OR_CURRENT:
                # Confirmed current resolution
                issue.current_state = IssueState.RESOLVED

        # Rule C: Escalation Dispatch
        elif ev.claim_type == ClaimType.ESCALATION_DISPATCH:
            if self._is_terminal_hardware_or_no_fix(text):
                # Hardware replacement dispatched
                issue.current_state = IssueState.UNRESOLVED_CONFIRMED
                if "HARDWARE_REPLACEMENT_DISPATCHED" not in self.outcome_reasons:
                    self.outcome_reasons.append("HARDWARE_REPLACEMENT_DISPATCHED")
            elif self._is_tier2_handoff(text):
                # Tier-2 handoff: remains OPEN awaiting investigation
                if issue.current_state != IssueState.RESOLVED:
                    issue.current_state = IssueState.OPEN
                if "TIER_2_ESCALATION_PENDING" not in self.outcome_reasons:
                    self.outcome_reasons.append("TIER_2_ESCALATION_PENDING")

    def _check_cross_speaker_contradictions(self) -> None:
        """
        Detects unresolved cross-speaker terminal contradictions on each issue.
        Normal chronology (Client reports problem -> Consultant acts -> Client confirms fix)
        is explicitly NOT a conflict.
        A conflict occurs only if one speaker asserts resolved, the other immediately refutes it,
        and no subsequent confirmation clarifies the outcome.
        """
        for issue in self.issues.values():
            issue_events = [ev for ev in self.events if ev.event_id in issue.event_history_ids]
            if len(issue_events) < 2:
                continue

            last_ev = issue_events[-1]
            prev_ev = issue_events[-2]

            # If last event and previous event are from DIFFERENT speakers, and one claims resolved
            # while the other claims failure at the end of the interaction
            if last_ev.speaker != prev_ev.speaker and last_ev.speaker != ActorRole.UNKNOWN:
                is_last_res = (last_ev.claim_type == ClaimType.RESOLUTION_ASSERTION and last_ev.polarity == Polarity.AFFIRMATIVE)
                is_prev_res = (prev_ev.claim_type == ClaimType.RESOLUTION_ASSERTION and prev_ev.polarity == Polarity.AFFIRMATIVE)
                is_last_fail = (last_ev.claim_type == ClaimType.FAILURE_ASSERTION and last_ev.polarity == Polarity.AFFIRMATIVE) or \
                               (last_ev.claim_type == ClaimType.RESOLUTION_ASSERTION and last_ev.polarity == Polarity.NEGATED)
                is_prev_fail = (prev_ev.claim_type == ClaimType.FAILURE_ASSERTION and prev_ev.polarity == Polarity.AFFIRMATIVE) or \
                               (prev_ev.claim_type == ClaimType.RESOLUTION_ASSERTION and prev_ev.polarity == Polarity.NEGATED)

                if (is_prev_res and is_last_fail) and (last_ev.temporal_scope == TemporalScope.PRESENT_OR_CURRENT):
                    # Contradiction at end of interaction without subsequent fix
                    issue.current_state = IssueState.REVIEW
                    self.review_reasons.append("UNRESOLVED_CROSS_SPEAKER_CONTRADICTION")

    def _aggregate_case_status(self) -> ResolutionStatus:
        """
        Aggregates canonical technical_resolution_status and compiles closure blockers.
        """
        total_issues = len(self.issues)
        if total_issues == 0:
            self.outcome_reasons.append("NO_OPERATIONAL_ISSUES_IDENTIFIED")
            return ResolutionStatus.UNKNOWN

        resolved_count = 0
        open_count = 0
        unresolved_confirmed_count = 0
        review_count = 0

        for issue in self.issues.values():
            symptom_label = issue.symptom_description[:40]
            target_label = issue.target_id or "system"

            if issue.current_state == IssueState.RESOLVED:
                resolved_count += 1
            elif issue.current_state == IssueState.OPEN:
                open_count += 1
                self.closure_blockers.append(
                    f"Issue '{symptom_label}' on {target_label} remains OPEN (no confirmation of fix received)"
                )
            elif issue.current_state == IssueState.UNRESOLVED_CONFIRMED:
                unresolved_confirmed_count += 1
                self.closure_blockers.append(
                    f"Issue '{symptom_label}' on {target_label} is UNRESOLVED_CONFIRMED (hardware/logistics dispatch pending)"
                )
            elif issue.current_state == IssueState.REVIEW:
                review_count += 1
                self.closure_blockers.append(
                    f"Issue '{symptom_label}' on {target_label} requires human review due to unresolved contradiction"
                )

        # Outcome reasons for incomplete issues
        if open_count > 0:
            self.outcome_reasons.append("NO_CONFIRMATION_OF_FIX")

        # Canonical Status Matrix
        if review_count > 0 and resolved_count == 0 and open_count == 0 and unresolved_confirmed_count == 0:
            return ResolutionStatus.UNKNOWN

        if resolved_count == total_issues and review_count == 0:
            return ResolutionStatus.RESOLVED

        if resolved_count > 0 and (open_count > 0 or unresolved_confirmed_count > 0 or review_count > 0):
            return ResolutionStatus.PARTIALLY_RESOLVED

        if resolved_count == 0 and (open_count > 0 or unresolved_confirmed_count > 0):
            return ResolutionStatus.UNRESOLVED

        return ResolutionStatus.PARTIALLY_RESOLVED if resolved_count > 0 else ResolutionStatus.UNKNOWN


def reduce_case(
    linking_result: LinkingResult,
    targets: Optional[List[TargetEntity]] = None
) -> ReductionResult:
    """
    Convenience function to reduce a LinkingResult into a ReductionResult.
    """
    reducer = PerIssueReducer(
        issues=linking_result.issues,
        events=linking_result.events,
        targets=targets or linking_result.targets,
        initial_review_reasons=linking_result.review_reasons
    )
    return reducer.reduce_all()
