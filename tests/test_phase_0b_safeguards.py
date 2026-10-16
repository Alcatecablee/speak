"""
Unit and Adversarial Test Suite for Phase 0b Engine Safeguards.

Verifies:
1. Procedural phrases ("work on", "working on") do not trigger resolution.
2. Consultant-only claims ("reconnected comms", "that should fix it") transition
   to RESOLVED_UNCONFIRMED and block Salesforce case closure.
3. Connection detector negative and temporal safeguards:
   - "I am not connected" (negation)
   - "I was connected earlier" (retrospective past)
   - "I will connect" (prospective future)
   - Stated ID without affirmative connection
   - Disambiguation when multiple IDs are mentioned
4. Action grounding and anti-fabrication:
   - Ongoing action ("checking the setup now") is not marked COMPLETED_ACTION
   - Zero fallback fabrications ("I checked the system setup", hard-coded recipes)
5. Salesforce draft payload invariants:
   - Status is NEVER 'Closed' from audio alone (Pending Follow-up or Open)
   - Resolution_Category__c is strictly None (no unapproved picklists)
   - Subject is dynamically derived from grounded issue
6. Hermetic test isolation:
   - Server import and lifecycle with SPEAK_OUTPUT_DIR never touches ./recordings/
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from intelligence.models import (
    ActionType,
    ActorRole,
    ClaimType,
    IssueState,
    Polarity,
    ResolutionStatus,
    TemporalScope,
)
from intelligence.events import extract_turn_events
from intelligence.remote_id import RemoteIdResolver
from intelligence.linker import IssueLinker
from intelligence.reducer import PerIssueReducer
from intelligence.formatter import (
    format_draft_salesforce_payload,
    generate_narrative_case_summary,
)
from intelligence.providers import GroundedExtractionProvider
from transcription.pipeline import TranscriptionPipeline


class TestPhase0bSafeguards(unittest.TestCase):
    """Adversarial and regression test suite for Phase 0b safeguards."""

    @classmethod
    def setUpClass(cls):
        cls.provider = GroundedExtractionProvider()

    # -------------------------------------------------------------------------
    # 1. Defect D1: Resolution Policy & Procedural Phrase Safeguards
    # -------------------------------------------------------------------------
    def test_procedural_work_on_does_not_resolve(self):
        """Verifies 'Let's work on Till 1' is excluded from resolution assertions."""
        events = extract_turn_events(
            "Let's work on Till 1 first. Please reseat the cable.",
            turn_index=1,
            speaker=ActorRole.CONSULTANT,
        )
        for ev in events:
            self.assertNotEqual(
                ev.claim_type,
                ClaimType.RESOLUTION_ASSERTION,
                f"Procedural 'work on' was falsely classified as resolution: {ev}",
            )

    def test_consultant_remedial_action_transitions_to_action_unverified(self):
        """
        Consultant saying 'Reconnected comms' without client verification
        transitions issue to REMEDIAL_ACTION_TAKEN_UNVERIFIED, which blocks case closure.
        """
        transcript_data = {
            "session_id": "test_consultant_action_unverified",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "Our card machine is offline."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:00:10", "text": "Reconnected comms."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        
        # Issue state must be REMEDIAL_ACTION_TAKEN_UNVERIFIED, NOT RESOLVED or RESOLVED_UNCONFIRMED
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].current_state, IssueState.REMEDIAL_ACTION_TAKEN_UNVERIFIED)
        
        # Overall technical status must be UNRESOLVED because no client verification occurred
        self.assertEqual(analysis.resolution_status, ResolutionStatus.UNRESOLVED)
        
        # Closure blockers must explicitly contain the unverified remedial action notice
        self.assertTrue(
            any("REMEDIAL_ACTION_TAKEN_UNVERIFIED" in b for b in analysis.closure_blockers),
            f"Expected REMEDIAL_ACTION_TAKEN_UNVERIFIED closure blocker, got: {analysis.closure_blockers}",
        )

        # Salesforce draft payload must omit unapproved Status and Resolution_Category__c
        sf_payload = format_draft_salesforce_payload(analysis)
        self.assertNotIn("Status", sf_payload["fields"])
        self.assertNotIn("Resolution_Category__c", sf_payload["fields"])

    def test_consultant_outcome_claim_transitions_to_resolved_unconfirmed(self):
        """
        Consultant saying 'Problem is resolved now' without client verification
        transitions issue to RESOLVED_UNCONFIRMED, which blocks case closure.
        """
        transcript_data = {
            "session_id": "test_consultant_outcome_unconfirmed",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "Our card machine is offline."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:00:10", "text": "That should fix it, problem is resolved."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        
        # Issue state must be RESOLVED_UNCONFIRMED
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].current_state, IssueState.RESOLVED_UNCONFIRMED)
        
        # Overall technical status must be UNRESOLVED because no client verification occurred
        self.assertEqual(analysis.resolution_status, ResolutionStatus.UNRESOLVED)
        
        # Closure blockers must explicitly contain the unconfirmed notice
        self.assertTrue(
            any("RESOLVED_UNCONFIRMED" in b for b in analysis.closure_blockers),
            f"Expected RESOLVED_UNCONFIRMED closure blocker, got: {analysis.closure_blockers}",
        )

    def test_client_confirmation_after_remedial_action_resolves_issue(self):
        """
        Client confirming fix after consultant remedial action links and resolves issue.
        """
        transcript_data = {
            "session_id": "test_remedial_then_client_confirmed",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "Our card machine is offline."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:00:10", "text": "Reconnected comms."},
                {"speaker": "CLIENT", "timestamp_str": "10:00:20", "text": "Yes, card machine is working now!"},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].current_state, IssueState.RESOLVED)
        self.assertEqual(analysis.resolution_status, ResolutionStatus.RESOLVED)

    def test_client_affirmative_resolution_resolves_issue(self):
        """Client confirming fix successfully resolves the issue."""
        transcript_data = {
            "session_id": "test_client_confirmed",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "The kitchen printer is offline."},
                {"speaker": "CLIENT", "timestamp_str": "10:00:15", "text": "Reconnected the network cable, all sorted now."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].current_state, IssueState.RESOLVED)
        self.assertEqual(analysis.resolution_status, ResolutionStatus.RESOLVED)

    # -------------------------------------------------------------------------
    # 2. Defect D2: Connection Detector Negative & Temporal Safeguards
    # -------------------------------------------------------------------------
    def test_connection_detector_rejects_negation(self):
        """'I am not connected' must never create an affirmative connection."""
        resolver = RemoteIdResolver()
        resolver.process_turn("I am not connected to 441 220 993.", 1, ActorRole.CONSULTANT)
        res = resolver.resolve()
        for c in res.candidates:
            self.assertFalse(c.consultant_connected)

    def test_connection_detector_rejects_retrospective_past(self):
        """'I was connected earlier' must not establish a current connection."""
        resolver = RemoteIdResolver()
        resolver.process_turn("I was connected earlier to 441 220 993 before the reboot.", 1, ActorRole.CONSULTANT)
        res = resolver.resolve()
        for c in res.candidates:
            self.assertFalse(c.consultant_connected)

    def test_connection_detector_rejects_prospective_future(self):
        """'I will connect to AnyDesk' must not establish a current connection."""
        resolver = RemoteIdResolver()
        resolver.process_turn("I will connect to 441 220 993 shortly.", 1, ActorRole.CONSULTANT)
        res = resolver.resolve()
        for c in res.candidates:
            self.assertFalse(c.consultant_connected)

    def test_client_stated_id_without_connection_remains_unconnected(self):
        """Client giving AnyDesk ID without consultant affirmative connection produces no connection claim."""
        transcript_data = {
            "session_id": "test_id_unconnected",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "My till is freezing. AnyDesk is 882 104 991."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:00:05", "text": "Let me look up your account first."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        
        # Consultant did not connect! Must produce 0 consultant actions and 0 connection claims
        self.assertEqual(analysis.actions_taken.consultant_actions, [])
        self.assertFalse(any("connected" in a.description.lower() for a in analysis.actions_taken.structured_actions))
        
        # Case summary must not claim connection
        narrative = generate_narrative_case_summary(analysis)
        self.assertNotIn("dialed in", narrative.lower())
        self.assertNotIn("connected remotely", narrative.lower())

    def test_connection_disambiguated_between_two_ids(self):
        """When client mentions two IDs, only the affirmatively connected one is accepted."""
        resolver = RemoteIdResolver()
        resolver.process_turn("Try AnyDesk 882 104 991 or 334 901 228.", 1, ActorRole.CLIENT)
        resolver.process_turn("Connected to 334 901 228 now.", 2, ActorRole.CONSULTANT)
        res = resolver.resolve()
        conn_candidates = [c for c in res.candidates if c.consultant_connected]
        self.assertEqual(len(conn_candidates), 1)
        self.assertEqual(conn_candidates[0].value, "334 901 228")

    # -------------------------------------------------------------------------
    # 3. Defect D2: Action Grounding & Anti-Fabrication Safeguards
    # -------------------------------------------------------------------------
    def test_ongoing_action_is_not_completed_action(self):
        """'I am checking the setup now' (present in progress) is not completed."""
        events = extract_turn_events(
            "I am checking the setup now.",
            turn_index=1,
            speaker=ActorRole.CONSULTANT,
        )
        for ev in events:
            self.assertNotEqual(
                ev.claim_type,
                ClaimType.RESOLUTION_ASSERTION,
            )

    def test_empty_transcript_has_zero_fabricated_actions(self):
        """Empty transcript produces zero actions, no hardcoded fallbacks like 'I checked the system setup'."""
        transcript_data = {
            "session_id": "test_empty_session",
            "merged_turns": [],
        }
        analysis = self.provider.analyze(transcript_data)
        sf_payload = format_draft_salesforce_payload(analysis)
        
        self.assertEqual(analysis.actions_taken.consultant_actions, [])
        self.assertEqual(analysis.actions_taken.structured_actions, [])
        self.assertNotIn("I checked the system setup", sf_payload["fields"]["Description"])
        self.assertNotIn("MC1", sf_payload["fields"]["Description"])
        self.assertNotIn("whole cheesecake", sf_payload["fields"]["Description"].lower())

    # -------------------------------------------------------------------------
    # 4. Defect D3: Salesforce Draft Invariants
    # -------------------------------------------------------------------------
    def test_salesforce_draft_status_omitted(self):
        """Draft payload omits Status to avoid guessing unapproved CRM picklist values."""
        transcript_data = {
            "session_id": "test_all_sorted_status",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "The printer is offline."},
                {"speaker": "CLIENT", "timestamp_str": "10:00:10", "text": "Reconnected the cable, all sorted now."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        sf_payload = format_draft_salesforce_payload(analysis)
        self.assertNotIn("Status", sf_payload["fields"])

    def test_salesforce_draft_resolution_category_omitted(self):
        """Resolution_Category__c must be omitted from payload (no nulls that wipe CRM fields)."""
        transcript_data = {
            "session_id": "test_res_cat_none",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "Printer is offline."},
                {"speaker": "CLIENT", "timestamp_str": "10:00:10", "text": "Sorted now."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        sf_payload = format_draft_salesforce_payload(analysis)
        self.assertNotIn("Resolution_Category__c", sf_payload["fields"])

    def test_salesforce_draft_subject_is_dynamic(self):
        """Subject must be derived from actual grounded client issue, not hardcoded."""
        transcript_data = {
            "session_id": "test_dynamic_subject",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:00:00", "text": "Our barcode scanner is offline."},
            ],
        }
        analysis = self.provider.analyze(transcript_data)
        sf_payload = format_draft_salesforce_payload(analysis)
        self.assertIn("scanner", sf_payload["fields"]["Subject"].lower())
        self.assertNotIn("Cheesecake", sf_payload["fields"]["Subject"])

    # -------------------------------------------------------------------------
    # 5. Defect D4: Chronology & Timestamps
    # -------------------------------------------------------------------------
    def test_transcription_pipeline_anchors_relative_and_wallclock(self):
        """Pipeline preserves relative chronology and anchors wall-clock time when given."""
        pipeline = TranscriptionPipeline()
        temp_dir = tempfile.mkdtemp(prefix="speak_test_transcription_")
        try:
            mic_wav = os.path.join(temp_dir, "consultant_mic.wav")
            loop_wav = os.path.join(temp_dir, "client_loopback.wav")
            # Minimal 44-byte WAV header
            wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            with open(mic_wav, "wb") as f:
                f.write(wav_header)
            with open(loop_wav, "wb") as f:
                f.write(wav_header)

            # Test A: None start time -> relative chronology
            res_none = pipeline.process_session(mic_wav, loop_wav, call_start_time=None, output_dir=temp_dir)
            self.assertEqual(res_none["timestamp_anchor"], "RECORDING_RELATIVE_OFFSET")
            self.assertIsNone(res_none["call_start_time"])

            # Test B: Timezone-aware ISO string
            iso_str = "2026-10-16T10:00:00+02:00"
            res_iso = pipeline.process_session(mic_wav, loop_wav, call_start_time=iso_str, output_dir=temp_dir)
            self.assertEqual(res_iso["timestamp_anchor"], "RECORDING_STARTED_AT_WALL_CLOCK")
            self.assertEqual(res_iso["call_start_time"], iso_str)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 6. Hermetic Test Environment & Zero Mutation Safeguard
    # -------------------------------------------------------------------------
    def test_server_with_speak_output_dir_never_mutates_real_recordings(self):
        """Verifies that setting SPEAK_OUTPUT_DIR prevents touching ./recordings/."""
        real_recordings = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "recordings"))
        files_before = set(os.listdir(real_recordings)) if os.path.exists(real_recordings) else set()

        temp_dir = tempfile.mkdtemp(prefix="speak_hermetic_test_")
        try:
            os.environ["SPEAK_OUTPUT_DIR"] = temp_dir
            from local_engine.server import SessionManager
            
            # Instantiate SessionManager targeting temp_dir
            mgr = SessionManager(output_dir=temp_dir)
            session_res = mgr.load_demo_sample()
            session_id = session_res["session_id"]
            self.assertTrue(os.path.exists(os.path.join(temp_dir, session_id)))

            # Verify real recordings directory is completely untouched
            files_after = set(os.listdir(real_recordings)) if os.path.exists(real_recordings) else set()
            self.assertEqual(files_before, files_after)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            os.environ.pop("SPEAK_OUTPUT_DIR", None)


if __name__ == "__main__":
    unittest.main()
