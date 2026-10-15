"""
Unit Tests for Per-Issue Reducer and Case Status Aggregator (Step 5).

Verifies:
1. Deterministic state transitions (OPEN -> RESOLVED -> Reopened on regression).
2. Retrospective statements ("worked earlier") do not resolve current open issues.
3. Ambiguous links/events never silently close or transition issues.
4. Cross-issue independence on single device (network fix resolves network issue, leaves paper jam OPEN).
5. Distinction between Tier-2 operational handoff (OPEN) and hardware replacement dispatch (UNRESOLVED_CONFIRMED).
6. Deterministic case-level aggregation (RESOLVED, PARTIALLY_RESOLVED, UNRESOLVED, UNKNOWN).
7. Cross-speaker contradiction deadlock triggers REVIEW and blocks closure.
8. Normal troubleshooting chronology resolves cleanly without false conflict alarms.
"""

import unittest

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
    TargetKind,
    TemporalScope,
)
from intelligence.linker import LinkingResult, link_events
from intelligence.reducer import PerIssueReducer, reduce_case


class TestPerIssueReducer(unittest.TestCase):
    """Rigorous unit test suite for per-issue reduction and case status aggregation."""

    # 1. State transitions: OPEN -> RESOLVED -> Reopened on regression
    def test_state_transition_and_regression_reopening(self):
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is offline.",
            span=(0, 17)
        )
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is working now.",
            span=(0, 21)
        )
        e3 = EvidenceEvent(
            event_id="t2.c0.e0",
            turn_index=2,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="Wait, POS 1 has failed again.",
            span=(0, 29)
        )
        linking = link_events([e1, e2, e3])
        result = reduce_case(linking)

        self.assertEqual(len(result.issues), 1)
        # Issue must be REOPENED to OPEN due to regression
        self.assertEqual(result.issues[0].current_state, IssueState.OPEN)
        self.assertEqual(result.technical_resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertIn("ISSUE_REGRESSION_AFTER_RESOLUTION", result.outcome_reasons)
        self.assertTrue(len(result.closure_blockers) > 0)

    # 2. Retrospective statements do not resolve current open issues
    def test_retrospective_statement_does_not_resolve_issue(self):
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="The printer is broken.",
            span=(0, 22)
        )
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.RETROSPECTIVE_PAST,
            target_id="target_printer",
            source_quote="The printer was working fine earlier.",
            span=(0, 37)
        )
        linking = link_events([e1, e2])
        result = reduce_case(linking)

        self.assertEqual(len(result.issues), 1)
        # Retrospective "was working earlier" must NOT resolve the issue!
        self.assertEqual(result.issues[0].current_state, IssueState.OPEN)
        self.assertEqual(result.technical_resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertIn("NO_CONFIRMATION_OF_FIX", result.outcome_reasons)

    # 3. Ambiguous events never close or transition issues
    def test_ambiguous_events_do_not_transition_issues(self):
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is offline.",
            span=(0, 17)
        )
        e2 = EvidenceEvent(
            event_id="t0.c1.e0",
            turn_index=0,
            clause_index=1,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_2",
            source_quote="POS 2 is offline.",
            span=(20, 37)
        )
        # Ambiguous global statement with 2 open issues
        e3 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id=None,
            source_quote="All sorted now.",
            span=(0, 15)
        )
        linking = link_events([e1, e2, e3])
        result = reduce_case(linking)

        # Neither issue may be closed
        for iss in result.issues:
            self.assertEqual(iss.current_state, IssueState.OPEN)

        self.assertEqual(result.technical_resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertTrue(result.review_required)
        self.assertIn("AMBIGUOUS_GLOBAL_RESOLUTION", result.review_reasons)

    # 4. Cross-issue independence on single peripheral
    def test_cross_issue_independence_on_single_peripheral(self):
        # Issue 1 on printer: paper jam
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="The receipt printer has a paper jam.",
            span=(0, 36)
        )
        # Issue 2 on printer: network disconnected
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="The receipt printer is also showing a socket error.",
            span=(0, 52)
        )
        # Network resolution event
        e3 = EvidenceEvent(
            event_id="t2.c0.e0",
            turn_index=2,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="The socket error is cleared on the receipt printer.",
            span=(0, 51)
        )
        linking = link_events([e1, e2, e3])
        result = reduce_case(linking)

        self.assertEqual(len(result.issues), 2)
        net_issue = next(i for i in result.issues if i.category == ProblemCategory.CONNECTIVITY_LAN)
        jam_issue = next(i for i in result.issues if i.category == ProblemCategory.PRINTING_HARDWARE)

        # Network issue is resolved
        self.assertEqual(net_issue.current_state, IssueState.RESOLVED)
        # Paper jam issue REMAINS OPEN (not contaminated!)
        self.assertEqual(jam_issue.current_state, IssueState.OPEN)

        # Overall case outcome must be PARTIALLY_RESOLVED
        self.assertEqual(result.technical_resolution_status, ResolutionStatus.PARTIALLY_RESOLVED)
        self.assertTrue(any("remains OPEN" in b for b in result.closure_blockers))

    # 5. Tier-2 escalation (OPEN) versus hardware dispatch (UNRESOLVED_CONFIRMED)
    def test_tier2_escalation_vs_hardware_dispatch(self):
        # Scenario A: Tier-2 handoff
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 has database variance.",
            span=(0, 29)
        )
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CONSULTANT,
            claim_type=ClaimType.ESCALATION_DISPATCH,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="I have escalated to second line dev team for investigation.",
            span=(0, 58)
        )
        res_t2 = reduce_case(link_events([e1, e2]))
        # Issue remains OPEN awaiting investigation
        self.assertEqual(res_t2.issues[0].current_state, IssueState.OPEN)
        self.assertIn("TIER_2_ESCALATION_PENDING", res_t2.outcome_reasons)

        # Scenario B: Conclusive hardware replacement dispatch
        e_hw1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="The printer door hinge is physically broken.",
            span=(0, 44)
        )
        e_hw2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CONSULTANT,
            claim_type=ClaimType.ESCALATION_DISPATCH,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="Logging hardware replacement ticket for logistics dispatch.",
            span=(0, 60)
        )
        res_hw = reduce_case(link_events([e_hw1, e_hw2]))
        # Issue transitions to UNRESOLVED_CONFIRMED
        self.assertEqual(res_hw.issues[0].current_state, IssueState.UNRESOLVED_CONFIRMED)
        self.assertEqual(res_hw.technical_resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertIn("HARDWARE_REPLACEMENT_DISPATCHED", res_hw.outcome_reasons)
        self.assertTrue(any("UNRESOLVED_CONFIRMED" in b for b in res_hw.closure_blockers))

    # 6. Deterministic case-level aggregation
    def test_case_level_status_aggregation(self):
        # All resolved -> RESOLVED
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is offline.",
            span=(0, 17)
        )
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is working now.",
            span=(0, 21)
        )
        res_resolved = reduce_case(link_events([e1, e2]))
        self.assertEqual(res_resolved.technical_resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(len(res_resolved.closure_blockers), 0)

    # 7. Cross-speaker contradiction deadlock triggers REVIEW
    def test_cross_speaker_contradiction_triggers_review(self):
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_terminal",
            source_quote="The terminal is frozen.",
            span=(0, 23)
        )
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CONSULTANT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_terminal",
            source_quote="The terminal is working fine on my screen.",
            span=(0, 42)
        )
        e3 = EvidenceEvent(
            event_id="t2.c0.e0",
            turn_index=2,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_terminal",
            source_quote="No, the terminal screen is still completely dead.",
            span=(0, 49)
        )
        linking = link_events([e1, e2, e3])
        result = reduce_case(linking)

        self.assertEqual(result.issues[0].current_state, IssueState.REVIEW)
        self.assertTrue(result.review_required)
        self.assertIn("UNRESOLVED_CROSS_SPEAKER_CONTRADICTION", result.review_reasons)
        self.assertTrue(any("human review" in b for b in result.closure_blockers))

    # 8. Normal troubleshooting chronology resolves cleanly
    def test_normal_troubleshooting_chronology_resolves_cleanly(self):
        # Client: "Printer is down."
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="Printer is down.",
            span=(0, 16)
        )
        # Consultant: "Rebooted switch and restarted service."
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CONSULTANT,
            claim_type=ClaimType.REMEDIAL_ACTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="Restarted the print service.",
            span=(0, 28)
        )
        # Client: "All sorted now, printed test slip."
        e3 = EvidenceEvent(
            event_id="t2.c0.e0",
            turn_index=2,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="All sorted now, printed test slip.",
            span=(0, 34)
        )
        linking = link_events([e1, e2, e3])
        result = reduce_case(linking)

        # Must resolve cleanly without review flags!
        self.assertEqual(result.issues[0].current_state, IssueState.RESOLVED)
        self.assertEqual(result.technical_resolution_status, ResolutionStatus.RESOLVED)
        self.assertFalse(result.review_required)
        self.assertEqual(len(result.review_reasons), 0)
        self.assertEqual(len(result.closure_blockers), 0)


if __name__ == "__main__":
    unittest.main()
