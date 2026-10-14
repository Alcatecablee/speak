"""
Dedicated Remote ID Safety & Adversarial Regression Suite.
Validates zero false positive extraction across:
  - Phone numbers (SA cell, toll-free, international)
  - Currencies (Rand, Dollar, Euro)
  - Case / Ticket references
  - Security codes and OTPs
  - Verbal self-correction
"""

import unittest
from intelligence.providers import GroundedExtractionProvider


class TestRemoteIDSafetyAndAdversarial(unittest.TestCase):
    """Rigorous adversarial testing of Remote ID extraction guards."""

    def setUp(self):
        self.provider = GroundedExtractionProvider()

    def test_phone_number_exclusion(self):
        """Phone numbers with prefixes or verbal anchors must never be extracted."""
        transcripts = [
            [{"speaker": "CLIENT", "text": "Please call the manager on 083 760 4430."}],
            [{"speaker": "CLIENT", "text": "Dial my cell phone +27 82 555 1234 if you get cut off."}],
            [{"speaker": "CLIENT", "text": "The store number is 0861 422 722 for accounts."}],
            [{"speaker": "CLIENT", "text": "Phone me back on 072 345 6789 later."}],
            [{"speaker": "CLIENT", "text": "Send a WhatsApp to 084 998 1234."}],
        ]
        for t in transcripts:
            analysis = self.provider.analyze({"session_id": "test", "merged_turns": t})
            self.assertEqual(
                analysis.entities.customer_identifiers,
                [],
                f"Phone number hallucinated as remote ID from: {t[0]['text']}"
            )

    def test_currency_exclusion(self):
        """Financial amounts and currency references must never be extracted."""
        transcripts = [
            [{"speaker": "CLIENT", "text": "The batch variance was R1,000 on Departmental Sales."}],
            [{"speaker": "CLIENT", "text": "We had two missing transactions of R 500 and R300."}],
            [{"speaker": "CLIENT", "text": "The total tender amount was $1,200 on till 1."}],
            [{"speaker": "CLIENT", "text": "Entered a float of 500 rand into the drawer."}],
            [{"speaker": "CLIENT", "text": "The refund was 2500 rands yesterday."}],
        ]
        for t in transcripts:
            analysis = self.provider.analyze({"session_id": "test", "merged_turns": t})
            self.assertEqual(
                analysis.entities.customer_identifiers,
                [],
                f"Currency amount hallucinated as remote ID from: {t[0]['text']}"
            )

    def test_case_and_ticket_reference_exclusion(self):
        """Case, ticket, or reference numbers must never be extracted as connection IDs."""
        transcripts = [
            [{"speaker": "CLIENT", "text": "Calling regarding open ticket REF:00569582."}],
            [{"speaker": "CLIENT", "text": "The case number is reference 10928374."}],
            [{"speaker": "CONSULTANT", "text": "I logged this under ticket 9948271 for logistics."}],
        ]
        for t in transcripts:
            analysis = self.provider.analyze({"session_id": "test", "merged_turns": t})
            self.assertEqual(
                analysis.entities.customer_identifiers,
                [],
                f"Case reference hallucinated as remote ID from: {t[0]['text']}"
            )

    def test_otp_and_security_code_exclusion(self):
        """Security PINs and OTP codes must never be extracted as connection IDs."""
        transcripts = [
            [{"speaker": "CONSULTANT", "text": "Please enter the supervisor OTP 449 201 on the screen."}],
            [{"speaker": "CLIENT", "text": "The override pin is 552 109 for manager access."}],
            [{"speaker": "CONSULTANT", "text": "Use authorization code 112 334 to unlock."}],
        ]
        for t in transcripts:
            analysis = self.provider.analyze({"session_id": "test", "merged_turns": t})
            self.assertEqual(
                analysis.entities.customer_identifiers,
                [],
                f"OTP/PIN hallucinated as remote ID from: {t[0]['text']}"
            )

    def test_valid_remote_id_true_positives(self):
        """Legitimate AnyDesk, TeamViewer, and remote portal IDs must be accurately extracted."""
        cases = [
            ("AnyDesk is 419 883 201.", "419 883 201"),
            ("TeamViewer is 501 229 884.", "501 229 884"),
            ("Connecting to your terminal on 20288 2622 2622.", "20288 2622 2622"),
            ("Logged in to 772 109 443.", "772 109 443"),
            ("Connecting on AnyDesk 311 902 445.", "311 902 445"),
            ("Connecting to 719 332 001.", "719 332 001"),
        ]
        for text, expected in cases:
            analysis = self.provider.analyze({
                "session_id": "test",
                "merged_turns": [{"speaker": "CLIENT", "text": text}]
            })
            self.assertIn(
                expected,
                analysis.entities.customer_identifiers,
                f"Failed to extract valid remote ID {expected} from: {text}"
            )

    def test_verbal_correction_overwrites_wrong_id(self):
        """When client corrects a misstated remote ID, the old ID must be discarded."""
        transcript = [
            {"speaker": "CLIENT", "text": "AnyDesk is 419 883 201."},
            {"speaker": "CLIENT", "text": "Wait, sorry, not 419 883 201! Use 991 223 445."},
        ]
        analysis = self.provider.analyze({"session_id": "test", "merged_turns": transcript})
        self.assertNotIn("419 883 201", analysis.entities.customer_identifiers)
        self.assertIn("991 223 445", analysis.entities.customer_identifiers)
        self.assertEqual(len(analysis.entities.customer_identifiers), 1)

    def test_statistical_safety_metrics(self):
        """Computes confusion matrix across 20 synthetic adversarial examples."""
        positives = [
            "AnyDesk 883 992 102",
            "TeamViewer 123 456 789",
            "Connecting to terminal on 334 556 778",
            "Remote ID is 994 221 003",
            "Logged in to 445 112 334",
            "Station on 881 223 994",
            "AnyDesk is 112 334 556",
            "TeamViewer ID: 778 991 223",
            "Remote connection 556 778 990",
            "Connecting to 331 445 667"
        ]
        negatives = [
            "Call store on 083 123 4567",
            "Manager cell +27 82 998 1234",
            "Dial 0861 999 888",
            "Tender variance of R1,500",
            "Drawer float 500 rand",
            "Case REF:00994821",
            "Ticket reference 8847291",
            "Supervisor OTP 334 991",
            "Manager code 778 112",
            "Transaction on 15/08/2026 was R450"
        ]

        tp, fp, tn, fn = 0, 0, 0, 0
        for text in positives:
            res = self.provider.analyze({"session_id": "test", "merged_turns": [{"speaker": "CLIENT", "text": text}]})
            if len(res.entities.customer_identifiers) > 0:
                tp += 1
            else:
                fn += 1

        for text in negatives:
            res = self.provider.analyze({"session_id": "test", "merged_turns": [{"speaker": "CLIENT", "text": text}]})
            if len(res.entities.customer_identifiers) > 0:
                fp += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fn_rate = fn / (tp + fn) if (tp + fn) > 0 else 0.0

        self.assertEqual(fp, 0, f"Found {fp} false positive remote IDs in adversarial traps")
        self.assertEqual(fn, 0, f"Found {fn} false negative remote IDs in valid prompts")
        self.assertEqual(precision, 1.0)
        self.assertEqual(recall, 1.0)
        self.assertEqual(fp_rate, 0.0)
        self.assertEqual(fn_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
