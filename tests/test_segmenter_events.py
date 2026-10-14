"""
Unit Tests for Discourse-Aware Clause Segmenter and Semantic Event Extractor.

Verifies:
1. Affirmative failure versus negated failure.
2. 'Not only ... but also ...' correlative constructions.
3. Retrospective positive evidence followed by current failure.
4. Contrasting clauses ('terminal works; printer does not').
5. Multiple targets and distinct ordinals ('POS 1' vs 'second till').
6. Accurate source spans matching exact turn slices and event ordering.
7. Ambiguous or unsupported language remaining uncertain rather than forced into a confident claim.
8. Diagnostic and remedial action extraction for consultant utterances.
"""

import unittest

from intelligence.models import (
    ActorRole,
    ClaimType,
    EvidenceEvent,
    LinkConfidence,
    Polarity,
    TemporalScope,
)
from intelligence.segmenter import SegmentedClause, segment_turn
from intelligence.events import (
    extract_events_from_clause,
    extract_turn_events,
)


class TestSegmenterAndEvents(unittest.TestCase):
    """Test suite for clause segmentation and semantic event extraction."""

    # 1. Affirmative failure versus negated failure
    def test_affirmative_failure_vs_negated_failure(self):
        # Affirmative failure
        text_aff = "The printer failed again."
        events_aff = extract_turn_events(text_aff, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events_aff), 1)
        ev_aff = events_aff[0]
        self.assertEqual(ev_aff.claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(ev_aff.polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(ev_aff.temporal_scope, TemporalScope.PRESENT_OR_CURRENT)
        self.assertEqual(ev_aff.target_id, "target_printer")

        # Negated failure ("has not failed")
        text_neg = "The printer has not failed."
        events_neg = extract_turn_events(text_neg, turn_index=1, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events_neg), 1)
        ev_neg = events_neg[0]
        self.assertEqual(ev_neg.claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(ev_neg.polarity, Polarity.NEGATED)
        self.assertEqual(ev_neg.temporal_scope, TemporalScope.PRESENT_OR_CURRENT)
        self.assertEqual(ev_neg.target_id, "target_printer")

        # Colloquial negated failure ("didn't fail")
        text_neg2 = "The terminal didn't fail."
        events_neg2 = extract_turn_events(text_neg2, turn_index=2, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events_neg2), 1)
        self.assertEqual(events_neg2[0].claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(events_neg2[0].polarity, Polarity.NEGATED)

    # 2. Correlative "Not only ... but also ..."
    def test_correlative_not_only_but_also(self):
        text = "Not only does the terminal work, but the printer works too."
        events = extract_turn_events(text, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events), 2)

        ev1, ev2 = events[0], events[1]

        # First clause: "Not only does the terminal work"
        self.assertEqual(ev1.claim_type, ClaimType.RESOLUTION_ASSERTION)
        # Even though "not" is present, "not only" is an emphatic affirmative!
        self.assertEqual(ev1.polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(ev1.target_id, "target_terminal")
        self.assertEqual(ev1.temporal_scope, TemporalScope.PRESENT_OR_CURRENT)

        # Second clause: "but the printer works too"
        self.assertEqual(ev2.claim_type, ClaimType.RESOLUTION_ASSERTION)
        self.assertEqual(ev2.polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(ev2.target_id, "target_printer")
        self.assertEqual(ev2.temporal_scope, TemporalScope.PRESENT_OR_CURRENT)

    # 3. Retrospective positive evidence followed by current failure
    def test_retrospective_positive_followed_by_current_failure(self):
        text = "The printer was working fine earlier, but it has failed again."
        events = extract_turn_events(text, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events), 2)

        ev1, ev2 = events[0], events[1]

        # Clause 1: was working fine earlier -> RETROSPECTIVE_PAST
        self.assertEqual(ev1.claim_type, ClaimType.RESOLUTION_ASSERTION)
        self.assertEqual(ev1.polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(ev1.temporal_scope, TemporalScope.RETROSPECTIVE_PAST)
        self.assertEqual(ev1.target_id, "target_printer")

        # Clause 2: but it has failed again -> PRESENT_OR_CURRENT
        self.assertEqual(ev2.claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(ev2.polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(ev2.temporal_scope, TemporalScope.PRESENT_OR_CURRENT)

    # 4. Contrasting clauses: semicolon and conjunction
    def test_contrasting_clauses_semicolon_and_conjunction(self):
        # Semicolon contrast: "terminal works; printer does not"
        text_semi = "terminal works; printer does not"
        events_semi = extract_turn_events(text_semi, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events_semi), 2)

        self.assertEqual(events_semi[0].target_id, "target_terminal")
        self.assertEqual(events_semi[0].claim_type, ClaimType.RESOLUTION_ASSERTION)
        self.assertEqual(events_semi[0].polarity, Polarity.AFFIRMATIVE)

        self.assertEqual(events_semi[1].target_id, "target_printer")
        self.assertEqual(events_semi[1].polarity, Polarity.NEGATED)

        # Conjunction contrast: "POS1 is online, but POS2 is offline"
        text_conj = "POS1 is online, but POS2 is offline"
        events_conj = extract_turn_events(text_conj, turn_index=1, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events_conj), 2)

        self.assertEqual(events_conj[0].target_id, "target_pos_1")
        self.assertEqual(events_conj[0].claim_type, ClaimType.RESOLUTION_ASSERTION)
        self.assertEqual(events_conj[0].polarity, Polarity.AFFIRMATIVE)

        self.assertEqual(events_conj[1].target_id, "target_pos_2")
        self.assertEqual(events_conj[1].claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(events_conj[1].polarity, Polarity.AFFIRMATIVE)

    # 5. Multiple targets and distinct ordinals
    def test_multiple_targets_and_ordinals(self):
        text = "POS 1 is printing fine, but the second till is crashing."
        events = extract_turn_events(text, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events), 2)

        self.assertEqual(events[0].target_id, "target_pos_1")
        self.assertEqual(events[0].claim_type, ClaimType.RESOLUTION_ASSERTION)
        self.assertEqual(events[0].polarity, Polarity.AFFIRMATIVE)

        self.assertEqual(events[1].target_id, "target_pos_2")
        self.assertEqual(events[1].claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(events[1].polarity, Polarity.AFFIRMATIVE)

    # 6. Accurate source spans matching exact turn slices and event ordering
    def test_accurate_source_spans_and_ordering(self):
        text = "POS1 bill printer is jamming; however the receipt printer is cleared."
        clauses = segment_turn(text, turn_index=3)
        self.assertEqual(len(clauses), 2)

        # Check clause spans match verbatim slices
        for c in clauses:
            start, end = c.span
            self.assertEqual(text[start:end], c.text)

        events = extract_turn_events(text, turn_index=3, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events), 2)

        # Check event spans match verbatim slices
        for ev in events:
            start, end = ev.span
            self.assertEqual(text[start:end], ev.source_quote)

        # Event ordering: event 0 comes before event 1
        self.assertEqual(events[0].event_id, "t3.c0.e0")
        self.assertEqual(events[1].event_id, "t3.c1.e0")
        self.assertTrue(events[0].span[0] < events[1].span[0])

    # 7. Ambiguous and unsupported language remains uncertain
    def test_ambiguous_and_unsupported_language_remains_uncertain(self):
        text1 = "Maybe it's something with the server, I don't know."
        events1 = extract_turn_events(text1, turn_index=0, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events1), 1)
        self.assertEqual(events1[0].polarity, Polarity.UNCERTAIN)
        self.assertIn("UNCERTAIN_PREDICATE_EVIDENCE", events1[0].review_reasons)

        text2 = "Could be the database perhaps, not sure if it is broken."
        events2 = extract_turn_events(text2, turn_index=1, speaker=ActorRole.CLIENT)
        self.assertEqual(len(events2), 1)
        # Not forced into a confident affirmative failure!
        self.assertEqual(events2[0].polarity, Polarity.UNCERTAIN)
        self.assertIn("UNCERTAIN_PREDICATE_EVIDENCE", events2[0].review_reasons)

    # 8. Diagnostic and remedial actions
    def test_diagnostic_and_remedial_actions(self):
        text = "I rebooted the switch and pinged the till."
        events = extract_turn_events(text, turn_index=0, speaker=ActorRole.CONSULTANT)
        self.assertEqual(len(events), 2)

        self.assertEqual(events[0].claim_type, ClaimType.REMEDIAL_ACTION)
        self.assertEqual(events[0].polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(events[0].target_id, "target_network")

        self.assertEqual(events[1].claim_type, ClaimType.DIAGNOSTIC_ACTION)
        self.assertEqual(events[1].polarity, Polarity.AFFIRMATIVE)
        self.assertEqual(events[1].target_id, "target_terminal")


if __name__ == "__main__":
    unittest.main()
