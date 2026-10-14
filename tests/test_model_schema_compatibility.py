"""
Schema Compatibility & Invariance Tests for Phase 3 Model Additions.
Verifies that:
1. Legacy ConversationAnalysis JSON payloads load cleanly with backwards-compatible defaults.
2. Existing fields and enum values remain completely unchanged.
3. technical_resolution_status defaults or syncs from legacy resolution_status.
4. New models (EvidenceEvent, TargetEntity, OperationalIssue, RemoteIdCandidate, ReviewReason)
   serialize and deserialize accurately.
"""

import json
import unittest

from intelligence.models import (
    ActionType,
    ActorRole,
    ClaimType,
    ConfidenceAssessment,
    ConfidenceLevel,
    ConversationAnalysis,
    ConversationSummary,
    ClientIssue,
    ActionsTaken,
    EpistemicType,
    EvidenceEvent,
    EvidenceItem,
    EvidenceSpan,
    ExtractedEntities,
    FollowUp,
    IssueState,
    LinkConfidence,
    OperationalIssue,
    Polarity,
    ProblemCategory,
    RemoteIdAnchor,
    RemoteIdCandidate,
    RemoteIdStatus,
    ResolutionStatus,
    ReviewReason,
    Sentiment,
    SentimentAnalysis,
    TargetEntity,
    TargetKind,
    TemporalScope,
)


class TestModelSchemaCompatibility(unittest.TestCase):
    """Rigorous verification of backward compatibility for additive models."""

    def test_legacy_payload_loading_without_new_fields(self):
        """A legacy v2.1.0 JSON payload missing all Phase 3 fields loads without error."""
        legacy_dict = {
            "schema_version": "2.1.0",
            "call_start_time": "2026-10-06T14:30:00",
            "total_turns_analyzed": 4,
            "summary": {
                "reason_for_contact": "POS1 offline",
                "key_events": ["Client reported issue", "Consultant rebooted switch"],
                "outcome": "Resolved"
            },
            "client_issue": {
                "primary_issue": "POS1 offline",
                "details": ["Terminals not syncing"],
                "evidence": []
            },
            "actions_taken": {
                "structured_actions": [],
                "consultant_actions": ["Rebooted switch"],
                "client_actions": ["Verified lights"]
            },
            "resolution_status": "RESOLVED",
            "resolution_rationale": "Client confirmed sorted.",
            "follow_up": {
                "required": False,
                "action_items": [],
                "owner": "NONE",
                "timeframe": None,
                "evidence": None
            },
            "entities": {
                "normalized_entities": [],
                "customer_identifiers": [],
                "case_or_reference_numbers": [],
                "product_or_system_names": ["POS1"],
                "quantities_or_numbers": [],
                "dates_or_times": [],
                "error_messages": []
            },
            "sentiment": {
                "sentiment": "NEUTRAL",
                "rationale": "Calm dialogue",
                "is_ai_derived": True
            },
            "evidence": [
                {
                    "fact": "All sorted now",
                    "epistemic_type": "DIRECT_FACT",
                    "turn_index": 3,
                    "timestamp": "14:31:00",
                    "speaker": "CLIENT",
                    "source_quote": "All sorted now"
                }
            ],
            "confidence": {
                "level": "HIGH",
                "score": 0.95,
                "review_notes": "Verified",
                "stt_noise_detected": False
            }
        }

        # Deserialize JSON string
        json_str = json.dumps(legacy_dict)
        analysis = ConversationAnalysis.model_validate_json(json_str)

        # Core legacy fields preserved
        self.assertEqual(analysis.schema_version, "2.1.0")
        self.assertEqual(analysis.resolution_status, ResolutionStatus.RESOLVED)
        self.assertEqual(analysis.summary.reason_for_contact, "POS1 offline")
        self.assertFalse(analysis.follow_up.required)

        # New fields receive default backwards-compatible values
        self.assertEqual(analysis.technical_resolution_status, ResolutionStatus.RESOLVED)
        self.assertFalse(analysis.review_required)
        self.assertEqual(analysis.review_reasons, [])
        self.assertEqual(analysis.outcome_reasons, [])
        self.assertEqual(analysis.closure_blockers, [])
        self.assertEqual(analysis.field_flags, {})
        self.assertEqual(analysis.targets, [])
        self.assertEqual(analysis.issues, [])
        self.assertEqual(analysis.events, [])
        self.assertEqual(analysis.remote_id_candidates, [])

        # EvidenceItem spans default to empty list
        self.assertEqual(analysis.evidence[0].spans, [])

    def test_new_additive_models_serialization(self):
        """New models serialize and deserialize completely without loss of structure."""
        event = EvidenceEvent(
            event_id="t0.c0.e0",
            turn_index=0,
            clause_index=0,
            sub_index=0,
            speaker=ActorRole.CLIENT,
            claim_type=ClaimType.FAILURE_ASSERTION,
            polarity=Polarity.AFFIRMATIVE,
            temporal_scope=TemporalScope.PRESENT_OR_CURRENT,
            target_id="target_printer_pos1",
            issue_id="issue_pos1_jam",
            link_confidence=LinkConfidence.EXPLICIT,
            source_quote="The POS1 bill printer is physically damaged.",
            span=(0, 44),
            supersedes_event_id=None,
            review_reasons=[]
        )

        target = TargetEntity(
            target_id="target_printer_pos1",
            canonical_name="POS1 Bill Printer",
            kind=TargetKind.PRINTER,
            ordinal=1,
            location="Front counter"
        )

        issue = OperationalIssue(
            issue_id="issue_pos1_jam",
            target_id="target_printer_pos1",
            category=ProblemCategory.PRINTING_HARDWARE,
            symptom_description="Printer door hinge broken",
            current_state=IssueState.OPEN,
            event_history_ids=["t0.c0.e0"]
        )

        candidate = RemoteIdCandidate(
            candidate_id="cand_01",
            value="419 883 201",
            turn_index=1,
            clause_index=0,
            speaker=ActorRole.CLIENT,
            anchor=RemoteIdAnchor.ANYDESK,
            site_label="Main Branch",
            target_id="target_pos1",
            status=RemoteIdStatus.ACTIVE,
            superseded_by=None,
            consultant_connected=True,
            rejected_reasons=[]
        )

        review = ReviewReason(
            code="AMBIGUOUS_ISSUE_SCOPE",
            message="Global fix statement with multiple open issues.",
            event_ids=["t3.c0.e0"],
            turn_indices=[3],
            field_name="resolution_status"
        )

        span = EvidenceSpan(
            turn_index=0,
            start_char=0,
            end_char=44,
            text="The POS1 bill printer is physically damaged.",
            role="PRIMARY"
        )

        # Roundtrip JSON tests
        event_roundtrip = EvidenceEvent.model_validate_json(event.model_dump_json())
        self.assertEqual(event_roundtrip.event_id, "t0.c0.e0")
        self.assertEqual(event_roundtrip.claim_type, ClaimType.FAILURE_ASSERTION)
        self.assertEqual(event_roundtrip.polarity, Polarity.AFFIRMATIVE)

        target_roundtrip = TargetEntity.model_validate_json(target.model_dump_json())
        self.assertEqual(target_roundtrip.kind, TargetKind.PRINTER)
        self.assertEqual(target_roundtrip.ordinal, 1)

        issue_roundtrip = OperationalIssue.model_validate_json(issue.model_dump_json())
        self.assertEqual(issue_roundtrip.current_state, IssueState.OPEN)
        self.assertEqual(issue_roundtrip.category, ProblemCategory.PRINTING_HARDWARE)

        cand_roundtrip = RemoteIdCandidate.model_validate_json(candidate.model_dump_json())
        self.assertEqual(cand_roundtrip.value, "419 883 201")
        self.assertEqual(cand_roundtrip.anchor, RemoteIdAnchor.ANYDESK)

        review_roundtrip = ReviewReason.model_validate_json(review.model_dump_json())
        self.assertEqual(review_roundtrip.code, "AMBIGUOUS_ISSUE_SCOPE")

        span_roundtrip = EvidenceSpan.model_validate_json(span.model_dump_json())
        self.assertEqual(span_roundtrip.text, "The POS1 bill printer is physically damaged.")

    def test_technical_resolution_status_explicit_separation(self):
        """When technical_resolution_status is provided, it does not get overwritten by resolution_status."""
        payload = {
            "schema_version": "2.1.0",
            "total_turns_analyzed": 2,
            "summary": {"reason_for_contact": "Test", "outcome": "Callback scheduled"},
            "client_issue": {"primary_issue": "Test"},
            "actions_taken": {"structured_actions": []},
            "resolution_status": "FOLLOW_UP_REQUIRED",
            "technical_resolution_status": "UNRESOLVED",
            "follow_up": {"required": True, "action_items": ["Call back"]},
            "entities": {},
            "sentiment": {"sentiment": "NEUTRAL", "rationale": "Test"},
            "confidence": {"level": "HIGH", "score": 1.0, "review_notes": "Test"}
        }
        analysis = ConversationAnalysis.model_validate(payload)
        # Legacy field is FOLLOW_UP_REQUIRED for compatibility
        self.assertEqual(analysis.resolution_status, ResolutionStatus.FOLLOW_UP_REQUIRED)
        # Authoritative technical status remains UNRESOLVED!
        self.assertEqual(analysis.technical_resolution_status, ResolutionStatus.UNRESOLVED)

    def test_legacy_follow_up_required_maps_to_unknown_technical_status(self):
        """A legacy payload with resolution_status=FOLLOW_UP_REQUIRED never maps to canonical technical status."""
        payload = {
            "schema_version": "2.1.0",
            "total_turns_analyzed": 2,
            "summary": {"reason_for_contact": "Test", "outcome": "Callback scheduled"},
            "client_issue": {"primary_issue": "Test"},
            "actions_taken": {"structured_actions": []},
            "resolution_status": "FOLLOW_UP_REQUIRED",
            "follow_up": {"required": True, "action_items": ["Call back tomorrow"]},
            "entities": {},
            "sentiment": {"sentiment": "NEUTRAL", "rationale": "Test"},
            "confidence": {"level": "HIGH", "score": 1.0, "review_notes": "Test"}
        }
        analysis = ConversationAnalysis.model_validate(payload)
        self.assertEqual(analysis.resolution_status, ResolutionStatus.FOLLOW_UP_REQUIRED)
        # Canonical technical status MUST be UNKNOWN
        self.assertEqual(analysis.technical_resolution_status, ResolutionStatus.UNKNOWN)
        # Must record that the legacy payload did not supply sufficient technical outcome information
        self.assertIn("LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS", analysis.outcome_reasons)

    def test_canonical_status_rejects_direct_follow_up_required(self):
        """technical_resolution_status directly passed as FOLLOW_UP_REQUIRED is normalized to UNKNOWN."""
        payload = {
            "total_turns_analyzed": 1,
            "summary": {"reason_for_contact": "Test", "outcome": "Pending"},
            "client_issue": {"primary_issue": "Test"},
            "actions_taken": {"structured_actions": []},
            "resolution_status": "FOLLOW_UP_REQUIRED",
            "technical_resolution_status": "FOLLOW_UP_REQUIRED",
            "follow_up": {"required": True, "action_items": []},
            "entities": {},
            "sentiment": {"sentiment": "NEUTRAL", "rationale": "Test"},
            "confidence": {"level": "HIGH", "score": 1.0, "review_notes": "Test"}
        }
        analysis = ConversationAnalysis.model_validate(payload)
        self.assertEqual(analysis.technical_resolution_status, ResolutionStatus.UNKNOWN)
        self.assertIn("LEGACY_PAYLOAD_INSUFFICIENT_TECHNICAL_STATUS", analysis.outcome_reasons)

    def test_schema_version_contract(self):
        """New models emit schema_version 2.2.0 while older versions (2.0.0, 2.1.0) are preserved."""
        base_payload = {
            "total_turns_analyzed": 1,
            "summary": {"reason_for_contact": "Test", "outcome": "Done"},
            "client_issue": {"primary_issue": "Test"},
            "actions_taken": {"structured_actions": []},
            "resolution_status": "RESOLVED",
            "follow_up": {"required": False, "action_items": []},
            "entities": {},
            "sentiment": {"sentiment": "NEUTRAL", "rationale": "Test"},
            "confidence": {"level": "HIGH", "score": 1.0, "review_notes": "Test"}
        }
        
        # Omitted schema_version defaults to new 2.2.0 contract
        new_analysis = ConversationAnalysis.model_validate(base_payload)
        self.assertEqual(new_analysis.schema_version, "2.2.0")

        # Older schema_version 2.1.0 is preserved
        p_210 = dict(base_payload, schema_version="2.1.0")
        analysis_210 = ConversationAnalysis.model_validate(p_210)
        self.assertEqual(analysis_210.schema_version, "2.1.0")

        # Older schema_version 2.0.0 is preserved
        p_200 = dict(base_payload, schema_version="2.0.0")
        analysis_200 = ConversationAnalysis.model_validate(p_200)
        self.assertEqual(analysis_200.schema_version, "2.0.0")


if __name__ == "__main__":
    unittest.main()

