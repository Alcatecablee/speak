"""
Diverse Conversation Corpus and Ground Truth Annotations for P0.3 Stage 1 Evaluation.
Contains 5 diverse synthetic & de-identified support scenarios designed to benchmark:
  - Supported facts with transcript evidence
  - Ambiguous / conflicting evidence handling
  - Unstated fields (hallucination prevention, e.g. unstated remote IDs)
  - Distinguishing facts vs inferences
"""

import json
from pathlib import Path
from typing import Any, Dict, List

CORPUS_CASES: List[Dict[str, Any]] = [
    {
        "id": "eval_01_printer_offline",
        "scenario": "Hardware / Network Printer Offline (Fully Resolved)",
        "transcript": {
            "session_id": "eval_01_printer_offline",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "09:00:10", "text": "Support desk, Clive speaking. How can I help?"},
                {"speaker": "CLIENT", "timestamp_str": "09:00:18", "text": "Hi Clive, our kitchen printer Epson TM-T88 is completely offline. AnyDesk is 849 102 331."},
                {"speaker": "CONSULTANT", "timestamp_str": "09:00:32", "text": "Connecting to 849 102 331 now. I see the IP address 192.168.1.150 is unreachable on the LAN."},
                {"speaker": "CLIENT", "timestamp_str": "09:01:05", "text": "Let me check the network cable... ah, someone kicked the ethernet switch plug."},
                {"speaker": "CONSULTANT", "timestamp_str": "09:01:45", "text": "Ping is back up. I sent a test docket through the production queue and it printed out."},
                {"speaker": "CLIENT", "timestamp_str": "09:02:10", "text": "Yes, perfect! It just printed the test slip. All sorted now, thanks so much."},
                {"speaker": "CONSULTANT", "timestamp_str": "09:02:20", "text": "Glad to help. No follow-up needed. Have a good service."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Hardware / Printer",
            "expected_remote_id": "849 102 331",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Kitchen printer Epson TM-T88 was unreachable", "evidence": "I see the IP address 192.168.1.150 is unreachable on the LAN"},
                {"fact": "Ethernet cable was loose", "evidence": "someone kicked the ethernet switch plug"},
                {"fact": "Test slip printed successfully", "evidence": "It just printed the test slip. All sorted now"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Software version", "Warranty expiry", "Callback date"]
        }
    },
    {
        "id": "eval_02_recipe_variance",
        "scenario": "Production Variance & Batch Calculation (Firm Callback Commitment)",
        "transcript": {
            "session_id": "eval_02_recipe_variance",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "14:15:00", "text": "Support desk. Connecting to your terminal on 20288 2622 2622."},
                {"speaker": "CLIENT", "timestamp_str": "14:15:20", "text": "Looking at the batch variance for the cheesecake production run."},
                {"speaker": "CONSULTANT", "timestamp_str": "14:16:10", "text": "The unit of measure in recipe setup is set to whole batch instead of slices. Also need butternut puree in 1 KG."},
                {"speaker": "CLIENT", "timestamp_str": "14:17:30", "text": "Can you check if that affects yesterday's stock variance?"},
                {"speaker": "CONSULTANT", "timestamp_str": "14:18:00", "text": "I will investigate the recipe configuration on my side and call you back in 15 minutes."},
                {"speaker": "CLIENT", "timestamp_str": "14:18:15", "text": "Okay, 15 minutes is fine. I'll wait for your call."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "FOLLOW_UP_REQUIRED",
            "expected_category": "Production Configuration",
            "expected_remote_id": "20288 2622 2622",
            "expected_follow_up_required": True,
            "expected_commitment_timeframe": "Within 15 minutes",
            "supported_facts": [
                {"fact": "Cheesecake recipe setup has unit of measure mismatch", "evidence": "unit of measure in recipe setup is set to whole batch instead of slices"},
                {"fact": "Client requested butternut puree set to 1 KG", "evidence": "need butternut puree in 1 KG"},
                {"fact": "Consultant committed to callback within 15 minutes", "evidence": "call you back in 15 minutes"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Total stock variance cost", "Store manager name"]
        }
    },
    {
        "id": "eval_03_ambiguous_commitment",
        "scenario": "Tentative Non-Firm Follow-up (Ambiguous Commitment Calibration)",
        "transcript": {
            "session_id": "eval_03_ambiguous_commitment",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "11:00:00", "text": "Hi, our reporting module runs very slowly at month end. TeamViewer is 491 882 104."},
                {"speaker": "CONSULTANT", "timestamp_str": "11:00:45", "text": "I checked server CPU and it is sitting at 98% during SQL exports."},
                {"speaker": "CLIENT", "timestamp_str": "11:01:20", "text": "When will someone fix the SQL query index?"},
                {"speaker": "CONSULTANT", "timestamp_str": "11:01:50", "text": "I'm not sure, maybe someone from database admin can take a look sometime next week, but I can't guarantee a time."},
                {"speaker": "CLIENT", "timestamp_str": "11:02:10", "text": "That's rather vague, but please log it anyway."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "Database Performance",
            "expected_remote_id": "491 882 104",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Server CPU is 98% during SQL exports", "evidence": "sitting at 98% during SQL exports"}
            ],
            "ambiguous_facts": [
                {"claim": "Callback deadline", "evidence": "maybe someone from database admin can take a look sometime next week, but I can't guarantee a time"}
            ],
            "unstated_fields": ["Specific consultant assignee", "Confirmed resolution SLA"]
        }
    },
    {
        "id": "eval_04_missing_id_hallucination_trap",
        "scenario": "Verbal Remote Assistance Without Remote ID (Zero Hallucination Trap)",
        "transcript": {
            "session_id": "eval_04_missing_id_hallucination_trap",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "16:20:00", "text": "Support desk, how can I help?"},
                {"speaker": "CLIENT", "timestamp_str": "16:20:15", "text": "I need help reconciling the cash drawer on till 2. I don't have remote software installed."},
                {"speaker": "CONSULTANT", "timestamp_str": "16:20:30", "text": "No problem, we can do it over the phone. Press Menu, then Supervisor Cashup."},
                {"speaker": "CLIENT", "timestamp_str": "16:21:05", "text": "Got it. Entered the float of 500 Rand and printed the blind drop slip."},
                {"speaker": "CONSULTANT", "timestamp_str": "16:21:25", "text": "Great, till 2 is reconciled. All balanced."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Cashup / Reconcile",
            "expected_remote_id": None,  # MUST NOT HALLUCINATE ANY ID
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Float entered was 500 Rand", "evidence": "Entered the float of 500 Rand"},
                {"fact": "Till 2 was reconciled", "evidence": "till 2 is reconciled"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Remote Connection ID", "AnyDesk Number", "TeamViewer ID"]
        }
    },
    {
        "id": "eval_05_conflicting_correction",
        "scenario": "Self-Correcting Client Terminal Identification (Entity Grounding)",
        "transcript": {
            "session_id": "eval_05_conflicting_correction",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:10:00", "text": "Hi, Terminal 4 card swipe is failing. AnyDesk 991 223 445."},
                {"speaker": "CLIENT", "timestamp_str": "10:10:25", "text": "Wait, sorry, not Terminal 4! Terminal 4 is working fine. It is Terminal 7 on the second floor."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:10:45", "text": "Got it, checking Terminal 7 on 991 223 445. The Adumo comms driver was stopped."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:11:15", "text": "Restarted the service on Terminal 7. Try a test transaction now."},
                {"speaker": "CLIENT", "timestamp_str": "10:11:40", "text": "Card swipe succeeded on Terminal 7! Thank you."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Payment Terminal / EFT",
            "expected_remote_id": "991 223 445",
            "expected_target_entity": "Terminal 7",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Issue was on Terminal 7, not Terminal 4", "evidence": "not Terminal 4! Terminal 4 is working fine. It is Terminal 7"},
                {"fact": "Adumo comms driver service was restarted", "evidence": "Restarted the service on Terminal 7"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Client surname", "Bank merchant number"]
        }
    },
    {
        "id": "eval_06_multi_issue_partial",
        "scenario": "Multi-Issue Call: One Fixed, One Outstanding (Partially Resolved)",
        "transcript": {
            "session_id": "eval_06_multi_issue_partial",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "13:00:10", "text": "Hello, we have two issues on POS 1. The barcode scanner is jammed and the receipt header logo is corrupted. AnyDesk 552 114 908."},
                {"speaker": "CONSULTANT", "timestamp_str": "13:00:40", "text": "Connected to 552 114 908. Let's look at the scanner first. Unplug the USB cable and plug it into port 3."},
                {"speaker": "CLIENT", "timestamp_str": "13:01:15", "text": "Okay, scanner beeped and test scan read the barcode successfully. Scanner is working fine now."},
                {"speaker": "CONSULTANT", "timestamp_str": "13:01:40", "text": "Great. Regarding the receipt logo corruption, that requires a graphic driver patch from the manufacturer. I'll escalate to dev team."},
                {"speaker": "CLIENT", "timestamp_str": "13:02:00", "text": "Understood. At least scanner works for service. Logo remains broken for now."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "PARTIALLY_RESOLVED",
            "expected_category": "POS Peripherals / Scanner",
            "expected_remote_id": "552 114 908",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Barcode scanner reconnected to port 3 and confirmed working", "evidence": "scanner beeped and test scan read the barcode successfully"},
                {"fact": "Receipt logo remains corrupted pending graphic driver patch", "evidence": "Logo remains broken for now"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Graphic driver version", "Store manager name"]
        }
    },
    {
        "id": "eval_07_unresolved_client_abandon",
        "scenario": "Unresolved Abandoned Call (Client Emergency Exit)",
        "transcript": {
            "session_id": "eval_07_unresolved_client_abandon",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "15:40:00", "text": "Support desk, speaking to who?"},
                {"speaker": "CLIENT", "timestamp_str": "15:40:12", "text": "This is store 14. Our GRV invoice import is crashing with error code 502."},
                {"speaker": "CONSULTANT", "timestamp_str": "15:40:30", "text": "Let me see... can you provide your remote connection number?"},
                {"speaker": "CLIENT", "timestamp_str": "15:40:48", "text": "Wait, our regional director just walked in and the alarm is ringing. I have to leave right now, nothing is fixed. Bye."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "GRV / Inventory",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "GRV invoice import crashed with error code 502", "evidence": "GRV invoice import is crashing with error code 502"},
                {"fact": "Client had to abandon call without resolution", "evidence": "I have to leave right now, nothing is fixed"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Remote Connection ID", "Invoice Number"]
        }
    },
    {
        "id": "eval_08_firm_callback_license",
        "scenario": "License Expiry with Firm Callback Commitment (2 Hours)",
        "transcript": {
            "session_id": "eval_08_firm_callback_license",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "08:15:00", "text": "Morning support. Our back-office server shows License Expired. AnyDesk is 331 884 219."},
                {"speaker": "CONSULTANT", "timestamp_str": "08:15:30", "text": "Logged in to 331 884 219. Yes, the annual workstation certificate lapsed at midnight."},
                {"speaker": "CLIENT", "timestamp_str": "08:16:00", "text": "We need the accounts workstation unblocked before midday."},
                {"speaker": "CONSULTANT", "timestamp_str": "08:16:30", "text": "I will request a renewed digital key from licensing operations and call you back in 2 hours with the new key."},
                {"speaker": "CLIENT", "timestamp_str": "08:16:50", "text": "Thank you, I'll expect your call in 2 hours."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "FOLLOW_UP_REQUIRED",
            "expected_category": "Software Licensing",
            "expected_remote_id": "331 884 219",
            "expected_follow_up_required": True,
            "expected_commitment_timeframe": "Within 2 hours",
            "supported_facts": [
                {"fact": "Workstation certificate lapsed at midnight", "evidence": "annual workstation certificate lapsed at midnight"},
                {"fact": "Consultant committed to callback within 2 hours with renewed key", "evidence": "call you back in 2 hours with the new key"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["Purchase Order Number", "Accountant Name"]
        }
    },
    {
        "id": "eval_09_database_backup_resolved",
        "scenario": "Database Backup Disk Space Exhaustion (Fully Resolved)",
        "transcript": {
            "session_id": "eval_09_database_backup_resolved",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "17:00:00", "text": "Clive on support. Connecting to 719 332 001."},
                {"speaker": "CLIENT", "timestamp_str": "17:00:20", "text": "Our nightly SQL backup failed with Disk Full on volume D."},
                {"speaker": "CONSULTANT", "timestamp_str": "17:01:00", "text": "I purged 6 months of old archived transaction logs, freeing 45 Gigabytes on drive D."},
                {"speaker": "CONSULTANT", "timestamp_str": "17:02:15", "text": "Triggered manual backup job now. Backup completed successfully: pos_db_20261014.bak written."},
                {"speaker": "CLIENT", "timestamp_str": "17:02:40", "text": "I see the fresh .bak file in folder. That fixed it, problem is solved. Thanks!"},
                {"speaker": "CONSULTANT", "timestamp_str": "17:02:55", "text": "Excellent, backup verified. No further action needed."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Database Administration",
            "expected_remote_id": "719 332 001",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Purged archived transaction logs freeing 45 GB", "evidence": "freeing 45 Gigabytes on drive D"},
                {"fact": "Manual backup succeeded creating pos_db_20261014.bak", "evidence": "Backup completed successfully: pos_db_20261014.bak written"}
            ],
            "ambiguous_facts": [],
            "unstated_fields": ["SQL Server version", "Backup encryption key"]
        }
    },
    {
        "id": "eval_10_dropped_call_unknown",
        "scenario": "Disconnected Call After Greeting (Unknown Outcome)",
        "transcript": {
            "session_id": "eval_10_dropped_call_unknown",
            "session_type": "eval",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "09:30:00", "text": "Support desk, Clive here. Hello?"},
                {"speaker": "CLIENT", "timestamp_str": "09:30:08", "text": "Hello, can you hear me? Line is breaking up..."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNKNOWN",
            "expected_category": "Incomplete Interaction",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [],
            "ambiguous_facts": [],
            "unstated_fields": ["Caller Identity", "Issue Description", "Remote Connection ID"]
        }
    }
]


def save_evaluation_corpus(output_dir: Path) -> Path:
    """Saves the corpus files and ground truth manifest to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir = output_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for case in CORPUS_CASES:
        t_path = dataset_dir / f"{case['id']}_transcript.json"
        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(case["transcript"], f, indent=2)

        gt_path = dataset_dir / f"{case['id']}_ground_truth.json"
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(case["ground_truth"], f, indent=2)

        manifest.append({
            "id": case["id"],
            "scenario": case["scenario"],
            "transcript_file": t_path.name,
            "ground_truth_file": gt_path.name
        })

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path
