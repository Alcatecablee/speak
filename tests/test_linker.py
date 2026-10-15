"""
Unit Tests for Target and Issue Linker (Step 4).

Verifies:
1. Explicit target and symptom matches.
2. Multiple devices, tills, and ordinals.
3. Multiple independent problems on a single device (e.g. paper jam vs network offline).
4. Pronouns with one possible referent versus multiple possible referents.
5. Targetless statements with exactly one open issue versus multiple open issues.
6. A new symptom creates a separate issue rather than attaching to existing one.
7. Unrelated device mention does not alter another issue's association.
8. Ambiguous associations remain flagged instead of guessing.
"""

import unittest

from intelligence.models import (
    ActorRole,
    ClaimType,
    EvidenceEvent,
    IssueState,
    LinkConfidence,
    Polarity,
    ProblemCategory,
    TargetKind,
    TemporalScope,
)
from intelligence.events import extract_turn_events
from intelligence.linker import (
    IssueLinker,
    detect_symptom_category,
    link_events,
)


class TestTargetAndIssueLinker(unittest.TestCase):
    """Rigorous unit test suite for target and issue linking."""

    # 1. Explicit target and symptom matches
    def test_explicit_target_and_symptom_match(self):
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
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="The receipt printer paper jam is cleared.",
            span=(0, 41)
        )
        result = link_events([e1, e2])
        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, "target_receipt_printer")
        self.assertEqual(result.targets[0].kind, TargetKind.PRINTER)

        self.assertEqual(len(result.issues), 1)
        issue = result.issues[0]
        self.assertEqual(issue.category, ProblemCategory.PRINTING_HARDWARE)
        self.assertEqual(issue.target_id, "target_receipt_printer")
        self.assertEqual(issue.event_history_ids, ["t0.c0.e0", "t1.c0.e0"])

        # Resolution event is explicitly linked
        self.assertEqual(result.events[1].issue_id, issue.issue_id)
        self.assertEqual(result.events[1].link_confidence, LinkConfidence.EXPLICIT)

    # 2. Multiple devices, tills, and ordinals
    def test_multiple_devices_and_ordinals(self):
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 is crashing.",
            span=(0, 18)
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
            source_quote="second till is offline.",
            span=(20, 43)
        )
        result = link_events([e1, e2])
        self.assertEqual(len(result.targets), 2)
        target_ids = {t.target_id for t in result.targets}
        self.assertEqual(target_ids, {"target_pos_1", "target_pos_2"})

        self.assertEqual(len(result.issues), 2)
        issue_targets = {i.target_id for i in result.issues}
        self.assertEqual(issue_targets, {"target_pos_1", "target_pos_2"})

    # 3. Multiple independent problems on a single device
    def test_multiple_independent_problems_on_single_device(self):
        # Event 1: Receipt printer paper jam (PRINTING_HARDWARE)
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
        # Event 2: Receipt printer network offline (CONNECTIVITY_LAN)
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="The receipt printer also cannot connect to the network.",
            span=(0, 55)
        )
        # Event 3: Network fix event ("network is back on the receipt printer")
        e3 = EvidenceEvent(
            event_id="t2.c0.e0",
            turn_index=2,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="Network is back on the receipt printer.",
            span=(0, 39)
        )

        result = link_events([e1, e2, e3])

        # Must have exactly 1 target entity (the receipt printer)
        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, "target_receipt_printer")

        # Must have TWO distinct issues on this single device!
        self.assertEqual(len(result.issues), 2)
        categories = {i.category for i in result.issues}
        self.assertEqual(categories, {ProblemCategory.PRINTING_HARDWARE, ProblemCategory.CONNECTIVITY_LAN})

        # Event 3 (network fix) must attach to the CONNECTIVITY_LAN issue, NOT the paper jam issue!
        net_issue = next(i for i in result.issues if i.category == ProblemCategory.CONNECTIVITY_LAN)
        jam_issue = next(i for i in result.issues if i.category == ProblemCategory.PRINTING_HARDWARE)

        self.assertEqual(result.events[2].issue_id, net_issue.issue_id)
        self.assertEqual(result.events[2].link_confidence, LinkConfidence.EXPLICIT)
        self.assertIn("t2.c0.e0", net_issue.event_history_ids)
        self.assertNotIn("t2.c0.e0", jam_issue.event_history_ids)

    # 4. Pronouns: single open issue vs multiple open issues
    def test_pronoun_with_single_vs_multiple_open_issues(self):
        # Scenario A: Exactly one open issue + "It is working now"
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
            target_id=None,
            source_quote="It is working now.",
            span=(0, 18)
        )
        res_single = link_events([e1, e2])
        self.assertEqual(res_single.events[1].issue_id, res_single.issues[0].issue_id)
        self.assertEqual(res_single.events[1].link_confidence, LinkConfidence.INFERRED_UNIQUE)

        # Scenario B: Multiple open issues + "It is working now"
        e_multi_1 = EvidenceEvent(
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
        e_multi_2 = EvidenceEvent(
            event_id="t0.c1.e0",
            turn_index=0,
            clause_index=1,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="Printer is broken.",
            span=(20, 38)
        )
        e_multi_3 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id=None,
            source_quote="It is working now.",
            span=(0, 18)
        )
        res_multi = link_events([e_multi_1, e_multi_2, e_multi_3])
        # Ambiguous pronoun must NOT guess or pick one arbitrarily!
        self.assertIsNone(res_multi.events[2].issue_id)
        self.assertEqual(res_multi.events[2].link_confidence, LinkConfidence.AMBIGUOUS)
        self.assertIn("AMBIGUOUS_PRONOUN_REFERENT", res_multi.events[2].review_reasons)
        self.assertIn("AMBIGUOUS_PRONOUN_REFERENT", res_multi.review_reasons)

    # 5. Targetless statements: single vs multiple open issues
    def test_targetless_global_statements(self):
        # Scenario A: Single open issue + "All sorted now" -> INFERRED_UNIQUE (Probe J)
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="POS 1 cannot print.",
            span=(0, 19)
        )
        e2 = EvidenceEvent(
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
        res_a = link_events([e1, e2])
        self.assertEqual(res_a.events[1].issue_id, res_a.issues[0].issue_id)
        self.assertEqual(res_a.events[1].link_confidence, LinkConfidence.INFERRED_UNIQUE)

        # Scenario B: Multiple open issues + "All sorted now" -> AMBIGUOUS (Probe J2)
        e_b1 = EvidenceEvent(
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
        e_b2 = EvidenceEvent(
            event_id="t0.c1.e0",
            turn_index=0,
            clause_index=1,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_receipt_printer",
            source_quote="Receipt printer is jammed.",
            span=(20, 46)
        )
        e_b3 = EvidenceEvent(
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
        res_b = link_events([e_b1, e_b2, e_b3])
        self.assertIsNone(res_b.events[2].issue_id)
        self.assertEqual(res_b.events[2].link_confidence, LinkConfidence.AMBIGUOUS)
        self.assertIn("AMBIGUOUS_GLOBAL_RESOLUTION", res_b.events[2].review_reasons)
        self.assertIn("AMBIGUOUS_GLOBAL_RESOLUTION", res_b.review_reasons)

    # 6. New symptom creates a separate issue rather than attaching to existing one
    def test_new_symptom_creates_separate_issue_on_same_device(self):
        # Initial problem: Till 1 offline (CONNECTIVITY_LAN)
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="Till 1 has a socket error.",
            span=(0, 26)
        )
        # Distinct second symptom on Till 1: cashup balancing discrepancy
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_pos_1",
            source_quote="Till 1 also has a cashup float discrepancy.",
            span=(0, 43)
        )
        result = link_events([e1, e2])

        # Exactly 1 target
        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, "target_pos_1")

        # Two distinct operational issues on Till 1
        self.assertEqual(len(result.issues), 2)
        issue_categories = {i.category for i in result.issues}
        self.assertEqual(issue_categories, {ProblemCategory.CONNECTIVITY_LAN, ProblemCategory.CASHUP_BALANCING})

        # Each event linked to its respective distinct issue
        self.assertEqual(result.events[0].issue_id, result.issues[0].issue_id)
        self.assertEqual(result.events[1].issue_id, result.issues[1].issue_id)

    # 7. Unrelated device mention does not alter another issue's association
    def test_unrelated_device_mention_does_not_alter_issue(self):
        # Problem on POS 1
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
        # Mention of healthy/unrelated PED
        e2 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_ped",
            source_quote="The card machine works fine.",
            span=(0, 28)
        )
        result = link_events([e1, e2])

        # POS 1 issue remains alone and untouched
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].target_id, "target_pos_1")
        self.assertEqual(result.issues[0].event_history_ids, ["t0.c0.e0"])

        # e2 does not bind to POS 1 issue
        self.assertIsNone(result.events[1].issue_id)
        self.assertEqual(result.events[1].link_confidence, LinkConfidence.NONE)

    # 8. Ambiguous associations remain flagged instead of guessing
    def test_ambiguous_device_resolution_with_multiple_open_issues(self):
        # Two issues on printer: jam and network
        e1 = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="The printer has a paper jam.",
            span=(0, 28)
        )
        e2 = EvidenceEvent(
            event_id="t0.c1.e0",
            turn_index=0,
            clause_index=1,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="The printer is also showing socket error.",
            span=(30, 71)
        )
        # Ambiguous resolution: "The printer is working now" (does not state which issue)
        e3 = EvidenceEvent(
            event_id="t1.c0.e0",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.RESOLUTION_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer",
            source_quote="The printer is working now.",
            span=(0, 27)
        )
        result = link_events([e1, e2, e3])

        # Must NOT arbitrarily choose one of the two printer issues!
        self.assertIsNone(result.events[2].issue_id)
        self.assertEqual(result.events[2].link_confidence, LinkConfidence.AMBIGUOUS)
        self.assertIn("AMBIGUOUS_ISSUE_SCOPE", result.events[2].review_reasons)
        self.assertIn("AMBIGUOUS_ISSUE_SCOPE", result.review_reasons)


if __name__ == "__main__":
    unittest.main()
