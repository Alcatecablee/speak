"""
Reproducible Synthetic Verification Suite for Remote ID & Action Grounding.

Tests explicit connection-evidence contracts and prevents fabricated actions/resolutions:
1. Client mentions an ID; consultant never connects.
2. Consultant proposes a future connection.
3. Consultant denies or negates a connection.
4. Consultant connects to the second of two candidate IDs.
5. A previously used ID is mentioned historically.
6. A connection is verified, but to an ID other than the first candidate.
7. Future or proposed troubleshooting actions are not marked completed.
8. Remote access is declined without proof of verbal resolution.

Verifies:
- In-memory ConversationAnalysis models.
- Exact serialized salesforce_draft_payload.json on disk (written to isolated tempdir).
- Key events, review notes, narrative summary, and omission of unverified CRM fields.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from intelligence.analyzer import ConversationAnalyzer
from intelligence.formatter import (
    format_draft_salesforce_payload,
    generate_narrative_case_summary,
)
from intelligence.models import (
    ActionType,
    IssueState,
    ResolutionStatus,
)
from intelligence.providers import GroundedExtractionProvider


class TestRemoteIdGroundingReproducible(unittest.TestCase):
    """Reproducible fixture-driven verification suite."""

    def setUp(self):
        self.provider = GroundedExtractionProvider()

    def _run_pipeline(self, scenario_name: str, turns: list) -> tuple:
        """Runs the pipeline hermetically, saving artifacts to an isolated temp directory."""
        temp_dir = tempfile.mkdtemp(prefix=f"speak_repro_{scenario_name}_")
        out_path = Path(temp_dir)
        try:
            transcript_data = {
                "session_id": scenario_name,
                "merged_turns": [
                    {"speaker": s, "timestamp_str": f"10:00:{i:02d}", "text": t}
                    for i, (s, t) in enumerate(turns)
                ],
            }

            # 1. Analyze in memory
            analysis = self.provider.analyze(transcript_data)
            sf_payload = format_draft_salesforce_payload(analysis)

            # 2. Serialize to disk using ConversationAnalyzer
            analyzer = ConversationAnalyzer(provider=self.provider)
            transcript_file = out_path / "transcript.json"
            with open(transcript_file, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, indent=2)

            analyzer.analyze_file(str(transcript_file), output_dir=temp_dir)

            # 3. Read serialized salesforce draft from disk
            disk_payload_file = out_path / "salesforce_draft_payload.json"
            self.assertTrue(disk_payload_file.exists(), "salesforce_draft_payload.json was not created on disk")
            with open(disk_payload_file, "r", encoding="utf-8") as f:
                disk_payload = json.load(f)

            return analysis, sf_payload, disk_payload
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_01_id_mentioned_consultant_never_connects(self):
        """Scenario 1: Client mentions an ID; consultant never connects."""
        turns = [
            ("CLIENT", "Our till is freezing up. AnyDesk is 882 104 991."),
            ("CONSULTANT", "Got it, let me check the physical cable first."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_01_never_connects", turns)

        # 1. Connection evidence contract
        self.assertIsNone(analysis.verified_connected_id)
        self.assertFalse(analysis.has_verified_connection)
        self.assertIn("882 104 991", analysis.entities.customer_identifiers)

        # 2. Salesforce payload omission (both memory and serialized disk JSON)
        self.assertNotIn("Remote_Connection_ID__c", sf_payload["fields"])
        self.assertNotIn("Remote_Connection_ID__c", disk_payload["fields"])

        # 3. Key events must not claim established remote session, but factually state lack of verification
        self.assertFalse(any("established remote session" in ev for ev in analysis.summary.key_events))
        self.assertTrue(any("no remote connection was verified in this recording" in ev.lower() for ev in analysis.summary.key_events))

        # 4. Review notes must not claim verified connection
        self.assertNotIn("Confirmed callback and remote ID verified", analysis.confidence.review_notes)
        self.assertIn("no remote connection was verified in this recording", analysis.confidence.review_notes.lower())

        # 5. Narrative must not claim dial-in
        narrative = sf_payload["fields"]["Description"]
        self.assertNotIn("dialed in", narrative.lower())
        self.assertNotIn("connected remotely", narrative.lower())

    def test_02_consultant_proposes_future_connection(self):
        """Scenario 2: Consultant states they will connect shortly (future promise, no session)."""
        turns = [
            ("CLIENT", "AnyDesk 419 883 201."),
            ("CONSULTANT", "Thanks, I will dial into that in a few minutes after I restart the router."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_02_future_promise", turns)

        self.assertIsNone(analysis.verified_connected_id)
        self.assertFalse(analysis.has_verified_connection)
        self.assertNotIn("Remote_Connection_ID__c", sf_payload["fields"])
        self.assertNotIn("Remote_Connection_ID__c", disk_payload["fields"])
        self.assertFalse(any("established remote session" in ev for ev in analysis.summary.key_events))

    def test_03_consultant_denies_or_negates_connection(self):
        """Scenario 3: Consultant explicitly denies or negates connection."""
        turns = [
            ("CLIENT", "AnyDesk is 551 902 334."),
            ("CONSULTANT", "Thanks, but I won't be remoting in today, we can do this over the phone."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_03_denies_connection", turns)

        self.assertIsNone(analysis.verified_connected_id)
        self.assertFalse(analysis.has_verified_connection)
        self.assertNotIn("Remote_Connection_ID__c", sf_payload["fields"])
        self.assertNotIn("Remote_Connection_ID__c", disk_payload["fields"])
        self.assertFalse(any("established remote session" in ev for ev in analysis.summary.key_events))

    def test_04_consultant_connects_to_second_of_two_ids(self):
        """Scenario 4: Two candidate IDs mentioned; consultant connects specifically to the second ID."""
        turns = [
            ("CLIENT", "AnyDesk for Till 1 is 111 222 333, but Till 2 is 444 555 666."),
            ("CONSULTANT", "Connected to 444 555 666 now."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_04_connects_second_id", turns)

        # Verified connected ID must be specifically the second candidate
        self.assertEqual(analysis.verified_connected_id, "444 555 666")
        self.assertTrue(analysis.has_verified_connection)

        # Field must be populated with exactly the connected ID
        self.assertEqual(sf_payload["fields"]["Remote_Connection_ID__c"], "444 555 666")
        self.assertEqual(disk_payload["fields"]["Remote_Connection_ID__c"], "444 555 666")

        # Key events must reference the verified ID
        self.assertTrue(any("Remote ID: 444 555 666" in ev for ev in analysis.summary.key_events))

        # First candidate must remain unverified
        cand1 = next(c for c in analysis.remote_id_candidates if c.value == "111 222 333")
        self.assertFalse(cand1.consultant_connected)

    def test_05_retrospective_id_mention(self):
        """Scenario 5: Previously used ID mentioned purely in historical context."""
        turns = [
            ("CLIENT", "Last Tuesday we used AnyDesk 771 204 883, but today the screen is totally black."),
            ("CONSULTANT", "Understood, checking the hardware logs."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_05_retrospective_id", turns)

        self.assertIsNone(analysis.verified_connected_id)
        self.assertFalse(analysis.has_verified_connection)
        self.assertNotIn("Remote_Connection_ID__c", sf_payload["fields"])
        self.assertNotIn("Remote_Connection_ID__c", disk_payload["fields"])
        self.assertFalse(any("established remote session" in ev for ev in analysis.summary.key_events))

    def test_06_connection_verified_to_other_than_first_candidate(self):
        """Scenario 6: Three candidate IDs offered; connection verified to the third candidate."""
        turns = [
            ("CLIENT", "Station 1 is 123 456 789, Station 2 is 987 654 321, and Station 3 is 555 666 777."),
            ("CONSULTANT", "Logged in to 555 666 777 now."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_06_third_candidate_connected", turns)

        self.assertEqual(analysis.verified_connected_id, "555 666 777")
        self.assertEqual(sf_payload["fields"]["Remote_Connection_ID__c"], "555 666 777")
        self.assertEqual(disk_payload["fields"]["Remote_Connection_ID__c"], "555 666 777")
        self.assertFalse(any("123 456 789" in ev and "established" in ev for ev in analysis.summary.key_events))

    def test_07_proposed_action_not_marked_completed(self):
        """Scenario 7: Future or proposed troubleshooting actions must not be marked COMPLETED_ACTION."""
        turns = [
            ("CLIENT", "Our card terminal has socket errors."),
            ("CONSULTANT", "Let me check the physical cable and I will inspect the setup."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_07_action_grounding", turns)

        # Consultant actions summary (completed actions) must be empty
        self.assertEqual(analysis.actions_taken.consultant_actions, [])

        # All structured actions from the consultant must be PROPOSED_ACTION
        for act in analysis.actions_taken.structured_actions:
            if act.actor.value == "CONSULTANT":
                self.assertEqual(
                    act.action_type,
                    ActionType.PROPOSED_ACTION,
                    f"Prospective action incorrectly classified as completed: {act}"
                )

        # Narrative must not claim work was already performed
        desc = sf_payload["fields"]["Description"]
        self.assertNotIn("checked the physical cable", desc.lower())
        self.assertNotIn("inspected the setup", desc.lower())

        # Issue state must remain OPEN
        self.assertEqual(len(analysis.issues), 1)
        self.assertEqual(analysis.issues[0].current_state, IssueState.OPEN)

    def test_08_remote_access_declined_not_resolved_verbally(self):
        """Scenario 8: Declining remote access must not cause issue to be marked resolved or resolved verbally."""
        turns = [
            ("CLIENT", "Our printer is jammed and refusing to feed paper. AnyDesk is 551 902 334."),
            ("CONSULTANT", "Thanks, but I won't be remoting in today, we can do this over the phone."),
            ("CLIENT", "Okay, but the paper is still stuck inside."),
        ]
        analysis, sf_payload, disk_payload = self._run_pipeline("scen_08_declined_not_resolved", turns)

        # Resolution status must be UNRESOLVED
        self.assertEqual(analysis.resolution_status, ResolutionStatus.UNRESOLVED)

        # Narrative description must not claim resolved
        desc = sf_payload["fields"]["Description"]
        self.assertNotIn("resolved verbally", desc.lower())
        self.assertNotIn("issue resolved.", desc.lower())
        self.assertIn("issue not resolved", desc.lower())

        # Remote ID must be omitted from payload
        self.assertNotIn("Remote_Connection_ID__c", sf_payload["fields"])
        self.assertNotIn("Remote_Connection_ID__c", disk_payload["fields"])


if __name__ == "__main__":
    unittest.main()
