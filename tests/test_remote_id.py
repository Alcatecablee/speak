"""
Unit Tests for Remote-ID Candidate Resolver (Step 6).

Verifies:
1. Exact preservation of digits and formatting.
2. Exclusion of phone numbers, currencies, account numbers, and OTPs.
3. Separation of non-connection identifiers (case references, serial numbers).
4. Verbal self-correction strictly supersedes earlier stale candidates.
5. Multiple distinct active IDs leave canonical field blank with MULTIPLE_ACTIVE_REMOTE_IDS flag.
6. Spoken digits are never fabricated or guessed (REMOTE_ID_UNPARSEABLE flag).
7. Repeated confirmation of the same ID resolves without false ambiguity.
8. Consultant connecting to one of two IDs without verbal correction never picks the first ID.
"""

import unittest

from intelligence.models import (
    ActorRole,
    RemoteIdAnchor,
    RemoteIdCandidate,
    RemoteIdStatus,
)
from intelligence.remote_id import (
    OtherIdentifier,
    RemoteIdResolver,
    RemoteIdResolutionResult,
    resolve_remote_ids,
)


class TestRemoteIdCandidateResolver(unittest.TestCase):
    """Rigorous unit test suite for Remote ID extraction, validation, and safety."""

    # 1. Exact preservation of valid remote IDs
    def test_valid_remote_id_extraction_and_preservation(self):
        dialogue = [
            ("CLIENT", "AnyDesk is 419 883 201."),
        ]
        res = resolve_remote_ids(dialogue)
        self.assertEqual(res.canonical_remote_id, "419 883 201")
        self.assertEqual(len(res.candidates), 1)
        self.assertEqual(res.candidates[0].value, "419 883 201")
        self.assertEqual(res.candidates[0].anchor, RemoteIdAnchor.ANYDESK)
        self.assertEqual(res.candidates[0].status, RemoteIdStatus.ACTIVE)
        self.assertFalse(res.review_required)

    # 2. Strict exclusion of phone numbers, currencies, and account numbers
    def test_strict_exclusion_filters(self):
        dialogue = [
            ("CLIENT", "Please call the manager on 083 760 4430."),
            ("CLIENT", "The batch variance was R1,500 on sales."),
            ("CLIENT", "My account is 441 992 108 and the machine is broken."),
            ("CONSULTANT", "Please enter the supervisor OTP 449 201 on the screen."),
        ]
        res = resolve_remote_ids(dialogue)
        # None of these may ever be extracted as a remote ID!
        self.assertIsNone(res.canonical_remote_id)
        self.assertEqual(len(res.candidates), 0)

    # 3. Separation of non-connection identifiers (case references, serial numbers)
    def test_identifier_type_separation(self):
        dialogue = [
            ("CLIENT", "Calling regarding open ticket REF:00569582."),
            ("CLIENT", "The machine serial number is SN-99882200."),
            ("CLIENT", "AnyDesk is 419 883 201."),
        ]
        res = resolve_remote_ids(dialogue)
        
        # Canonical remote ID must be strictly the AnyDesk ID
        self.assertEqual(res.canonical_remote_id, "419 883 201")

        # Other identifiers captured in structured list
        other_kinds = {oi.kind for oi in res.other_identifiers}
        self.assertIn("CASE_REFERENCE", other_kinds)
        self.assertIn("SERIAL_NUMBER", other_kinds)

        case_ref = next(oi for oi in res.other_identifiers if oi.kind == "CASE_REFERENCE")
        self.assertIn("00569582", case_ref.value)

    # 4. Verbal self-correction strictly supersedes earlier stale candidates
    def test_verbal_correction_supersedes_stale_id(self):
        dialogue = [
            ("CLIENT", "AnyDesk is 419 883 201."),
            ("CONSULTANT", "Connected to 419 883 201."),
            ("CLIENT", "Sorry, I misread it. The correct AnyDesk is 419 883 210."),
        ]
        res = resolve_remote_ids(dialogue)

        # Stale ID must NOT be the canonical ID!
        self.assertEqual(res.canonical_remote_id, "419 883 210")
        self.assertEqual(len(res.candidates), 2)

        cand_old = next(c for c in res.candidates if c.value == "419 883 201")
        cand_new = next(c for c in res.candidates if c.value == "419 883 210")

        self.assertEqual(cand_old.status, RemoteIdStatus.SUPERSEDED)
        self.assertEqual(cand_old.superseded_by, cand_new.candidate_id)
        self.assertEqual(cand_new.status, RemoteIdStatus.ACTIVE)

    # 5. Multiple distinct active IDs leave field blank for review (Probe F)
    def test_multiple_distinct_active_ids_leaves_canonical_blank(self):
        dialogue = [
            ("CLIENT", "AnyDesk for site one is 419 883 201."),
            ("CLIENT", "Our other site AnyDesk is 501 229 884."),
        ]
        res = resolve_remote_ids(dialogue)

        # Ambiguous remote connection target must NEVER pick the first ID arbitrarily!
        self.assertIsNone(res.canonical_remote_id, "Must leave canonical ID blank when ambiguous")
        self.assertEqual(len(res.candidates), 2)
        self.assertTrue(res.review_required)
        self.assertIn("MULTIPLE_ACTIVE_REMOTE_IDS", res.review_reasons)
        self.assertEqual(res.field_flags.get("Remote_Connection_ID__c"), "MULTIPLE_ACTIVE_REMOTE_IDS")

    # 6. Spoken digits are never fabricated (Probe H)
    def test_spoken_digits_never_fabricated(self):
        dialogue = [
            ("CLIENT", "AnyDesk is four one nine, eight eight three, two zero one."),
        ]
        res = resolve_remote_ids(dialogue)

        # Must not fabricate digits or guess
        self.assertIsNone(res.canonical_remote_id)
        self.assertEqual(len(res.candidates), 1)
        self.assertIsNone(res.candidates[0].value)
        self.assertEqual(res.candidates[0].status, RemoteIdStatus.REJECTED)
        self.assertIn("REMOTE_ID_UNPARSEABLE", res.candidates[0].rejected_reasons)
        self.assertEqual(res.field_flags.get("Remote_Connection_ID__c"), "REMOTE_ID_UNPARSEABLE")

    # 7. Repeated confirmation of same ID is not ambiguous
    def test_repeated_confirmation_of_same_id(self):
        dialogue = [
            ("CLIENT", "AnyDesk is 419 883 201."),
            ("CONSULTANT", "Connected to 419 883 201."),
        ]
        res = resolve_remote_ids(dialogue)

        # Repeated confirmation is NOT an ambiguity
        self.assertEqual(res.canonical_remote_id, "419 883 201")
        self.assertEqual(len(res.candidates), 1)
        self.assertTrue(res.candidates[0].consultant_connected)
        self.assertFalse(res.review_required)

    # 8. Consultant connected to one of two IDs without verbal correction
    def test_consultant_connected_to_one_of_two_ids(self):
        dialogue = [
            ("CLIENT", "AnyDesk for site one is 419 883 201, site two is 501 229 884."),
            ("CONSULTANT", "Connected to 501 229 884."),
        ]
        res = resolve_remote_ids(dialogue)

        # Connecting to one without client correction must never pick the first-offered ID!
        self.assertNotEqual(res.canonical_remote_id, "419 883 201")
        # Safe options: either None (safest) or the connected ID 501 229 884
        self.assertIn(res.canonical_remote_id, ("501 229 884", None))


if __name__ == "__main__":
    unittest.main()
