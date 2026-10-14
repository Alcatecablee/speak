"""
P0.3 known-failure REGRESSION tests (development data, NOT an independent holdout).

These encode the CTO-approved expected semantics for the probes found in the
Stage 2 evidence review. They are written BEFORE the fix. Several are expected
to FAIL against the frozen baseline (tag: baseline-p0.3-rc-flawed). Do not
weaken an assertion to make the suite green; change the engine instead.

Agreed semantics
----------------
* "Latest relevant evidence" = latest evidence about the SAME issue/target.
  A later statement about the receipt printer never changes the card terminal.
* Resolution outcome across issues:
    all issues resolved -> RESOLVED
    some resolved, some not -> PARTIALLY_RESOLVED
    none resolved -> UNRESOLVED
    cannot tell which issue a statement refers to -> UNKNOWN (needs review)
* A fix that is later contradicted for the same issue REOPENS that issue.
* Probe J (agreed definition): a client-attested fix ("all sorted now") counts
  as resolution evidence when it has an unambiguous referent - i.e. exactly one
  open issue. The consultant need not have performed the fix. With two or more
  open issues and no referent, the statement is ambiguous -> UNKNOWN, not
  RESOLVED. (J1 / J2 below.)
* Remote ID: a later ID supersedes an earlier one ONLY if the later statement
  is an explicit correction of the same target. If several IDs exist and the
  intended connection target is not identifiable, the Salesforce
  Remote_Connection_ID__c must be blank (None) - never "the first one".
* A missed ID (e.g. spoken digits) must yield blank, never a guess.
"""

import unittest

from intelligence.formatter import format_draft_salesforce_payload
from intelligence.models import ResolutionStatus as RS
from intelligence.providers import GroundedExtractionProvider


def analyse(turns):
    provider = GroundedExtractionProvider()
    data = {
        "session_id": "regression",
        "merged_turns": [
            {"speaker": s, "timestamp_str": f"10:00:{i:02d}", "text": t}
            for i, (s, t) in enumerate(turns)
        ],
    }
    analysis = provider.analyze(data)
    sf_id = format_draft_salesforce_payload(analysis)["fields"]["Remote_Connection_ID__c"]
    return analysis, sf_id


class TestChronologyAndScope(unittest.TestCase):
    def test_A_earlier_ok_then_failed_is_not_resolved(self):
        a, _ = analyse([
            ("CLIENT", "The printer was working fine now earlier, but it has failed again."),
            ("CONSULTANT", "Let me check the cable."),
        ])
        self.assertNotEqual(a.resolution_status, RS.RESOLVED)

    def test_B_fixed_then_still_offline_reopens_issue(self):
        a, _ = analyse([
            ("CLIENT", "The printer is offline."),
            ("CONSULTANT", "Restarted the service."),
            ("CLIENT", "That fixed it, it is working now."),
            ("CLIENT", "Actually the printer is still offline."),
        ])
        self.assertEqual(a.resolution_status, RS.UNRESOLVED)

    def test_C_terminal_fixed_receipt_printer_not_is_partial(self):
        a, _ = analyse([
            ("CLIENT", "Card terminal and receipt printer have problems."),
            ("CONSULTANT", "Restarted the service."),
            ("CLIENT", "The terminal is working fine now; the receipt printer is not."),
        ])
        self.assertEqual(a.resolution_status, RS.PARTIALLY_RESOLVED)

    def test_D_first_till_fixed_second_broken_is_partial(self):
        a, _ = analyse([
            ("CLIENT", "Both tills are offline."),
            ("CONSULTANT", "Restarted the service on till one."),
            ("CLIENT", "We fixed the first till, all sorted, but the second till remains broken."),
        ])
        self.assertEqual(a.resolution_status, RS.PARTIALLY_RESOLVED)

    def test_E_fix_then_regression_reopens(self):
        a, _ = analyse([
            ("CLIENT", "Printer offline."),
            ("CONSULTANT", "Restarted the service."),
            ("CLIENT", "Printer works now, all sorted."),
            ("CLIENT", "Oh no it just stopped printing again."),
        ])
        self.assertEqual(a.resolution_status, RS.UNRESOLVED)

    def test_J1_client_attested_fix_single_open_issue_is_resolved(self):
        a, _ = analyse([
            ("CLIENT", "Printer is down."),
            ("CLIENT", "All sorted now."),
        ])
        self.assertEqual(a.resolution_status, RS.RESOLVED)

    def test_J2_all_sorted_with_two_open_issues_is_ambiguous(self):
        a, _ = analyse([
            ("CLIENT", "The printer is down and the card machine is offline."),
            ("CLIENT", "All sorted now."),
        ])
        self.assertEqual(a.resolution_status, RS.UNKNOWN)

    def test_later_comment_on_other_device_does_not_overwrite_state(self):
        """Card terminal fixed; later comment is only about the receipt printer."""
        a, _ = analyse([
            ("CLIENT", "The card terminal is offline."),
            ("CONSULTANT", "Restarted the service."),
            ("CLIENT", "The card terminal is working fine now."),
            ("CLIENT", "By the way the receipt printer is slow, but that is normal for us."),
        ])
        self.assertEqual(a.resolution_status, RS.RESOLVED)


class TestRemoteIdSelection(unittest.TestCase):
    def test_F_two_ids_different_sites_leaves_salesforce_blank(self):
        a, sf_id = analyse([
            ("CLIENT", "AnyDesk is 419 883 201."),
            ("CLIENT", "Our other site AnyDesk is 501 229 884."),
        ])
        self.assertIsNone(sf_id, "ambiguous connection target must not pick the first ID")

    def test_G_account_number_is_not_a_remote_id(self):
        a, sf_id = analyse([("CLIENT", "My account is 441 992 108 and the printer is down.")])
        self.assertIsNone(sf_id)
        self.assertEqual(a.entities.customer_identifiers, [])

    def test_H_spoken_digits_missed_but_never_invented(self):
        a, sf_id = analyse([("CLIENT", "AnyDesk is four one nine, eight eight three, two zero one.")])
        self.assertIsNone(sf_id)

    def test_I_corrected_id_supersedes_stale_id(self):
        a, sf_id = analyse([
            ("CLIENT", "AnyDesk is 419 883 201."),
            ("CONSULTANT", "Connected to 419 883 201."),
            ("CLIENT", "Sorry, I misread it. The correct AnyDesk is 419 883 210."),
        ])
        self.assertEqual(sf_id, "419 883 210")
        self.assertNotIn("419 883 201", a.entities.customer_identifiers)

    def test_repeated_same_id_is_not_ambiguous(self):
        a, sf_id = analyse([
            ("CLIENT", "AnyDesk is 419 883 201."),
            ("CONSULTANT", "Connected to 419 883 201."),
        ])
        self.assertEqual(sf_id, "419 883 201")

    def test_two_ids_where_consultant_connected_to_one_is_still_ambiguous_without_correction(self):
        """Connecting to one of two offered IDs is not an explicit correction."""
        a, sf_id = analyse([
            ("CLIENT", "AnyDesk for site one is 419 883 201, site two is 501 229 884."),
            ("CONSULTANT", "Connected to 501 229 884."),
        ])
        # Acceptable outcomes: the connected ID, or blank for review. Never the first-offered ID.
        self.assertIn(sf_id, ("501 229 884", None))


if __name__ == "__main__":
    unittest.main()
