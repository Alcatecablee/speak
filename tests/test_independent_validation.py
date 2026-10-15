"""
Independent Synthetic Validation Benchmark (P0.3 Phase 3 Step 7).

This suite contains 10 fresh, synthetic conversation scenarios that were NOT
used to tune the Step 3-7 components. It evaluates generalization across:
- Multi-issue partial resolutions
- Ambiguous remote IDs
- Verbal remote ID corrections
- Retrospective past claims vs active failures
- Chronological regressions / reopens
- Global resolution ambiguity (Probe J2 variant)
- Client-attested single-issue fixes (Probe J1 variant)
- Confirmed follow-up commitments
- Terminal hardware replacements
- Insufficient evidence / ambiguous dialogues
"""

import unittest
from intelligence.models import ResolutionStatus, RemoteIdStatus
from intelligence.providers import GroundedExtractionProvider
from intelligence.formatter import format_draft_salesforce_payload


INDEPENDENT_SYNTHETIC_CASES = [
    {
        "id": "syn_01_multi_issue_partial",
        "scenario": "Till 1 scanner offline and Till 2 receipt printer jammed; scanner fixed, printer remains jammed",
        "turns": [
            ("CLIENT", "Till 1 barcode scanner is offline and Till 2 receipt printer is jamming."),
            ("CONSULTANT", "Let's work on Till 1 first. Please reseat the USB cable on the scanner."),
            ("CLIENT", "Scanner reconnected, scanned test item and it is working fine now."),
            ("CONSULTANT", "Now for Till 2 printer, open the cover and inspect the gears."),
            ("CLIENT", "The roller gear is completely stripped and jammed, printer remains broken."),
        ],
        "expected_resolution_status": ResolutionStatus.PARTIALLY_RESOLVED,
        "expected_remote_id": None,
        "expected_review_required": False,
    },
    {
        "id": "syn_02_ambiguous_two_remote_ids",
        "scenario": "Two active AnyDesk IDs offered without target differentiation or connection confirmation",
        "turns": [
            ("CLIENT", "Our till is freezing. AnyDesk is 882 104 991."),
            ("CONSULTANT", "Give me a moment to look up your account."),
            ("CLIENT", "Actually or you can try our manager workstation on AnyDesk 334 901 228."),
            ("CONSULTANT", "I see both stations on the network. Let's restart the router first."),
        ],
        "expected_resolution_status": ResolutionStatus.UNRESOLVED,
        "expected_remote_id": None,  # Ambiguous -> canonical must be None, Salesforce field None
        "expected_remote_id_ambiguous": True,
    },
    {
        "id": "syn_03_verbal_remote_id_correction",
        "scenario": "Client misstates remote ID and immediately corrects it; correct ID must be canonical",
        "turns": [
            ("CLIENT", "AnyDesk is 441 220 993."),
            ("CLIENT", "Wait, sorry, not 441 220 993! That is my laptop. Use 819 332 554."),
            ("CONSULTANT", "Logged in to 819 332 554 now. Reconnected comms."),
        ],
        "expected_resolution_status": ResolutionStatus.UNRESOLVED,  # No explicit fix confirmed yet
        "expected_remote_id": "819 332 554",
        "expected_remote_id_ambiguous": False,
    },
    {
        "id": "syn_04_retrospective_claim_active_failure",
        "scenario": "Card machine was working yesterday, but is refusing cards today",
        "turns": [
            ("CLIENT", "The card machine was working fine yesterday, but today it has failed completely."),
            ("CONSULTANT", "Let me check the gateway connection from our side."),
        ],
        "expected_resolution_status": ResolutionStatus.UNRESOLVED,
        "expected_remote_id": None,
    },
    {
        "id": "syn_05_fix_then_regression_reopens",
        "scenario": "Receipt printer fixed with service restart, then fails again later in call",
        "turns": [
            ("CLIENT", "The receipt printer is offline."),
            ("CONSULTANT", "Restarted the service on the terminal."),
            ("CLIENT", "That fixed it, it is printing fine now, all sorted."),
            ("CLIENT", "Oh wait, it just failed again and stopped printing."),
        ],
        "expected_resolution_status": ResolutionStatus.UNRESOLVED,
        "expected_remote_id": None,
    },
    {
        "id": "syn_06_global_resolution_ambiguity_two_issues",
        "scenario": "Two open peripheral issues followed by client-attested 'all sorted now' with no referent",
        "turns": [
            ("CLIENT", "The printer is down and the card machine is offline."),
            ("CLIENT", "All sorted now."),
        ],
        "expected_resolution_status": ResolutionStatus.UNKNOWN,
        "expected_review_required": True,
    },
    {
        "id": "syn_07_client_attested_single_issue_fix",
        "scenario": "Single open issue resolved by client action with explicit confirmation",
        "turns": [
            ("CLIENT", "The kitchen printer is offline."),
            ("CLIENT", "Reconnected the network cable, all sorted now."),
        ],
        "expected_resolution_status": ResolutionStatus.RESOLVED,
        "expected_review_required": False,
    },
    {
        "id": "syn_08_confirmed_callback_commitment",
        "scenario": "Unresolved report with firm consultant commitment to investigate and call back",
        "turns": [
            ("CLIENT", "Our sales totals do not match the end of day report."),
            ("CONSULTANT", "I have captured your transaction logs. I will investigate and call you back tomorrow morning."),
        ],
        "expected_resolution_status": ResolutionStatus.FOLLOW_UP_REQUIRED,
        "expected_follow_up_required": True,
    },
    {
        "id": "syn_09_hardware_replacement_dispatch",
        "scenario": "Hardware peripheral physically broken, replacement ticket dispatched",
        "turns": [
            ("CLIENT", "The cash drawer latch hinge is broken and unit needs a replacement."),
            ("CONSULTANT", "Understood, I have logged urgent replacement ticket for courier dispatch."),
        ],
        "expected_resolution_status": ResolutionStatus.UNRESOLVED,
        "expected_remote_id": None,
    },
    {
        "id": "syn_10_insufficient_evidence_inquiry",
        "scenario": "General dialogue without specific defect, remedial action, or resolution confirmation",
        "turns": [
            ("CLIENT", "Calling to check if there are any scheduled maintenance windows this week."),
            ("CONSULTANT", "No maintenance scheduled for your region this week."),
            ("CLIENT", "Okay, thanks."),
        ],
        "expected_resolution_status": ResolutionStatus.UNKNOWN,
        "expected_remote_id": None,
    },
]


class TestIndependentSyntheticValidation(unittest.TestCase):
    """Executes blind evaluation across 10 un-tuned synthetic scenarios."""

    @classmethod
    def setUpClass(cls):
        cls.provider = GroundedExtractionProvider()

    def test_run_synthetic_validation_suite(self):
        results = []
        status_matches = 0
        remote_id_matches = 0

        for case in INDEPENDENT_SYNTHETIC_CASES:
            data = {
                "session_id": case["id"],
                "merged_turns": [
                    {"speaker": s, "timestamp_str": f"10:00:{i:02d}", "text": t}
                    for i, (s, t) in enumerate(case["turns"])
                ]
            }
            analysis = self.provider.analyze(data)
            sf_payload = format_draft_salesforce_payload(analysis)
            sf_remote_id = sf_payload["fields"]["Remote_Connection_ID__c"]

            # Evaluate Resolution Status
            status_match = (analysis.resolution_status == case["expected_resolution_status"])
            if status_match:
                status_matches += 1

            # Evaluate Remote ID
            if case.get("expected_remote_id_ambiguous"):
                # Must be None in both canonical and Salesforce payload
                id_match = (analysis.entities.customer_identifiers == [] and sf_remote_id is None)
            elif case.get("expected_remote_id"):
                id_match = (
                    len(analysis.entities.customer_identifiers) > 0 and
                    analysis.entities.customer_identifiers[0] == case["expected_remote_id"] and
                    sf_remote_id == case["expected_remote_id"]
                )
            else:
                id_match = (sf_remote_id is None)

            if id_match:
                remote_id_matches += 1

            results.append({
                "case_id": case["id"],
                "scenario": case["scenario"],
                "expected_status": case["expected_resolution_status"].value,
                "actual_status": analysis.resolution_status.value,
                "status_match": status_match,
                "expected_id": case.get("expected_remote_id"),
                "actual_id": sf_remote_id,
                "id_match": id_match,
                "review_required": analysis.review_required,
                "review_reasons": [getattr(r, "code", str(r)) for r in analysis.review_reasons],
                "issues": [(i.issue_id, i.current_state.value) for i in analysis.issues],
            })

        print("\n" + "=" * 70)
        print("INDEPENDENT SYNTHETIC VALIDATION BENCHMARK RESULTS (10 CASI)")
        print("=" * 70)
        for r in results:
            stat_icon = "PASS" if r["status_match"] else "FAIL"
            id_icon = "PASS" if r["id_match"] else "FAIL"
            print(f"[{r['case_id']}] Status: {stat_icon} | Remote-ID: {id_icon}")
            print(f"   Exp Status: {r['expected_status']} | Act Status: {r['actual_status']}")
            print(f"   Exp ID: {r['expected_id']} | Act ID: {r['actual_id']}")
            if not r["status_match"] or not r["id_match"]:
                print(f"   Review Reasons: {r['review_reasons']}")
                print(f"   Issues: {r['issues']}")

        print("-" * 70)
        print(f"Resolution Status Accuracy: {status_matches}/{len(INDEPENDENT_SYNTHETIC_CASES)} ({status_matches / len(INDEPENDENT_SYNTHETIC_CASES):.1%})")
        print(f"Remote Connection ID Accuracy: {remote_id_matches}/{len(INDEPENDENT_SYNTHETIC_CASES)} ({remote_id_matches / len(INDEPENDENT_SYNTHETIC_CASES):.1%})")
        print("=" * 70)

        self.assertGreaterEqual(status_matches, 8, "Expected at least 80% resolution status accuracy on independent batch")
        self.assertEqual(remote_id_matches, 10, "Expected 100% remote-ID accuracy on independent batch")


if __name__ == "__main__":
    unittest.main()
