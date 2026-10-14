"""
Adversarial Classification and Resolution Hardening Tests.
Validates robust handling of:
  - Negations in proximity to positive fix keywords
  - False confirmations immediately followed by failure
  - Tentative non-firm proposals vs binding commitments
  - Client abandonment / support resistance
  - Partial outcomes across multiple peripherals
"""

import unittest
from intelligence.models import ResolutionStatus
from intelligence.providers import GroundedExtractionProvider


class TestAdversarialClassification(unittest.TestCase):
    """Rigorous adversarial evaluation of resolution status determination."""

    def setUp(self):
        self.provider = GroundedExtractionProvider()

    def test_negation_window_overrides_fix_keyword(self):
        """Negations preceding fix keywords must prevent false RESOLVED classifications."""
        transcripts = [
            [
                {"speaker": "CONSULTANT", "text": "Can you check the printer status?"},
                {"speaker": "CLIENT", "text": "It beeped once, but wait! It is not working now!"}
            ],
            [
                {"speaker": "CONSULTANT", "text": "Did the reboot help?"},
                {"speaker": "CLIENT", "text": "Never sorted, nothing is fixed here."}
            ],
            [
                {"speaker": "CONSULTANT", "text": "Did the card swipe go through?"},
                {"speaker": "CLIENT", "text": "No, it failed and does not work."}
            ]
        ]
        for t in transcripts:
            analysis = self.provider.analyze({"session_id": "test_neg", "merged_turns": t})
            self.assertEqual(
                analysis.resolution_status,
                ResolutionStatus.UNRESOLVED,
                f"Failed negation protection on: {t[1]['text']}"
            )

    def test_false_confirmation_trap(self):
        """Initial appearance of fix followed by fatal failure must be classified as UNRESOLVED."""
        transcript = [
            {"speaker": "CLIENT", "text": "Kitchen printer stopped working after power cut."},
            {"speaker": "CONSULTANT", "text": "Please check the power supply and reseat the kettle cord."},
            {"speaker": "CLIENT", "text": "It beeped once, but wait! It is not working now! The red error light is flashing and it completely died again."},
            {"speaker": "CONSULTANT", "text": "That indicates a blown power board. Unit is damaged and needs a replacement."}
        ]
        analysis = self.provider.analyze({"session_id": "test_false_conf", "merged_turns": transcript})
        self.assertEqual(analysis.resolution_status, ResolutionStatus.UNRESOLVED)

    def test_tentative_proposal_vs_firm_commitment(self):
        """Tentative ideas without firm timeframes must never create a follow-up commitment."""
        tentative_transcript = [
            {"speaker": "CLIENT", "text": "Our reports take 40 minutes to run."},
            {"speaker": "CONSULTANT", "text": "Maybe someone from dev can look at it sometime next week, but I can't guarantee a time."},
            {"speaker": "CLIENT", "text": "Okay, that is rather vague."}
        ]
        analysis_tentative = self.provider.analyze({"session_id": "test_tent", "merged_turns": tentative_transcript})
        self.assertEqual(analysis_tentative.resolution_status, ResolutionStatus.UNRESOLVED)
        self.assertFalse(analysis_tentative.follow_up.required)

        firm_transcript = [
            {"speaker": "CLIENT", "text": "Our reports take 40 minutes to run."},
            {"speaker": "CONSULTANT", "text": "I will optimize the SQL query and call you back in 15 minutes."},
            {"speaker": "CLIENT", "text": "Thanks, I will wait for your call in 15 minutes."}
        ]
        analysis_firm = self.provider.analyze({"session_id": "test_firm", "merged_turns": firm_transcript})
        self.assertEqual(analysis_firm.resolution_status, ResolutionStatus.FOLLOW_UP_REQUIRED)
        self.assertTrue(analysis_firm.follow_up.required)
        self.assertEqual(analysis_firm.follow_up.timeframe, "Within 15 minutes")

    def test_client_refusal_and_abandonment(self):
        """Client refusal or urgent call abandonment must result in UNRESOLVED."""
        abandon_transcript = [
            {"speaker": "CLIENT", "text": "The bill printer is jamming repeatedly."},
            {"speaker": "CONSULTANT", "text": "Let's check the roller mechanism together."},
            {"speaker": "CLIENT", "text": "I have to leave right now, lunch rush is starting. Nothing is fixed."}
        ]
        analysis_abandon = self.provider.analyze({"session_id": "test_ab", "merged_turns": abandon_transcript})
        self.assertEqual(analysis_abandon.resolution_status, ResolutionStatus.UNRESOLVED)

        refusal_transcript = [
            {"speaker": "CLIENT", "text": "Both card machines are offline."},
            {"speaker": "CONSULTANT", "text": "Can I connect remotely to inspect the comms driver?"},
            {"speaker": "CLIENT", "text": "No, I refuse to troubleshoot remotely again. Send someone onsite."}
        ]
        analysis_refusal = self.provider.analyze({"session_id": "test_ref", "merged_turns": refusal_transcript})
        self.assertEqual(analysis_refusal.resolution_status, ResolutionStatus.UNRESOLVED)

    def test_multi_peripheral_partial_resolution(self):
        """When one peripheral is fixed while another remains broken, status must be PARTIALLY_RESOLVED."""
        partial_transcript = [
            {"speaker": "CLIENT", "text": "Both the slip printer and the bar scanner are down."},
            {"speaker": "CONSULTANT", "text": "Reconnected USB on slip printer. Printed test slip."},
            {"speaker": "CLIENT", "text": "Yes, printer works now! But scanner remains broken for now."}
        ]
        analysis = self.provider.analyze({"session_id": "test_part", "merged_turns": partial_transcript})
        self.assertEqual(analysis.resolution_status, ResolutionStatus.PARTIALLY_RESOLVED)


if __name__ == "__main__":
    unittest.main()
