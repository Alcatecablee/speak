"""
Independent Holdout Benchmark Corpus for P0.3 Stage 2 Validation.
Contains 10 authentic GAAP technical support scenarios completely unseen during development:
  - Hardware breakdown & replacement dispatch (Bill printer door damaged)
  - Network & switch power-cycle recovery
  - Payment terminal EFT Wi-Fi setup with AnyDesk
  - Recipe variance historical calculation lock with TeamViewer
  - Cashup variances with firm morning callback commitment
  - Open tables blocking cashup resolution
  - Adversarial phone, currency, and case reference number trap (Zero Hallucination)
  - Multi-terminal partial resolution (one fixed, one down)
  - False positive negation trap ('not working now')
  - Client refusal of remote support and onsite dispatch
"""

import json
from pathlib import Path
from typing import Any, Dict, List

HOLDOUT_CASES: List[Dict[str, Any]] = [
    {
        "id": "holdout_01_damaged_bill_printer",
        "scenario": "Hardware / Damaged Bill Printer Door (Hardware Replacement Required)",
        "transcript": {
            "session_id": "holdout_01_damaged_bill_printer",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "08:05:00", "text": "GAAP support desk, Clive speaking. How can I assist?"},
                {"speaker": "CLIENT", "timestamp_str": "08:05:15", "text": "Hi Clive, this is Dave. The POS2 bill printer is physically damaged. The printer door does not close properly after replacing paper."},
                {"speaker": "CONSULTANT", "timestamp_str": "08:05:40", "text": "Did you try reseating the paper roll roller latch?"},
                {"speaker": "CLIENT", "timestamp_str": "08:06:05", "text": "We tried everything, but the latch hinge is broken and unit needs a replacement. Store opens at 8am tomorrow."},
                {"speaker": "CONSULTANT", "timestamp_str": "08:06:30", "text": "Understood Dave. I have logged an urgent hardware replacement ticket for logistics. We cannot resolve this over the phone."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "Hardware / Printer",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "POS2 bill printer door latch hinge is physically broken", "evidence": "latch hinge is broken and unit needs a replacement"}
            ]
        }
    },
    {
        "id": "holdout_02_network_switch_reset",
        "scenario": "Network / Netgear Switch & Router Power Cycle (Fully Resolved)",
        "transcript": {
            "session_id": "holdout_02_network_switch_reset",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "11:20:00", "text": "Morning Clive, our terminals and POS1 are offline and not syncing."},
                {"speaker": "CONSULTANT", "timestamp_str": "11:20:30", "text": "Please shut down all terminals, the internet router, and the Netgear switch. Leave them off for two minutes while you double-check the network cables on POS1."},
                {"speaker": "CLIENT", "timestamp_str": "11:22:45", "text": "Okay, switched everything back on now. The network lights are green."},
                {"speaker": "CONSULTANT", "timestamp_str": "11:23:15", "text": "I see POS1 ping is responding. Check your terminal sync status."},
                {"speaker": "CLIENT", "timestamp_str": "11:23:40", "text": "Yes, all devices synced and online now! Everything is sorted, closing case. Thanks Clive!"}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Network Infrastructure",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Network switch and router rebooted and POS1 cable verified", "evidence": "switched everything back on now. The network lights are green"},
                {"fact": "All devices confirmed online and synced", "evidence": "all devices synced and online now! Everything is sorted"}
            ]
        }
    },
    {
        "id": "holdout_03_adumo_ped_wifi",
        "scenario": "Payment EFT / Adumo Base Wi-Fi Reconfiguration (Fully Resolved with AnyDesk)",
        "transcript": {
            "session_id": "holdout_03_adumo_ped_wifi",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "14:10:00", "text": "Our card machine is giving socket error and not taking transactions. AnyDesk is 419 883 201."},
                {"speaker": "CONSULTANT", "timestamp_str": "14:10:30", "text": "Connected to 419 883 201. I see the PAX PED was set to SIM instead of Wi-Fi. Restart the PED and the Adumo Base."},
                {"speaker": "CONSULTANT", "timestamp_str": "14:11:15", "text": "I entered the password for the Adumo_base Wi-Fi network in terminal settings. Try a customer transaction now."},
                {"speaker": "CLIENT", "timestamp_str": "14:12:00", "text": "The transaction went through instantly. Everything is working fine now. Client tested with the customer."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Payment Terminal / EFT",
            "expected_remote_id": "419 883 201",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "PAX PED reconnected to Adumo_base Wi-Fi", "evidence": "entered the password for the Adumo_base Wi-Fi network"},
                {"fact": "Customer card transaction succeeded", "evidence": "transaction went through instantly. Everything is working fine now"}
            ]
        }
    },
    {
        "id": "holdout_04_beefhead_recipe_historical_lock",
        "scenario": "Production / Recipe Variance Historical Data Lock Policy (Fully Resolved with TeamViewer)",
        "transcript": {
            "session_id": "holdout_04_beefhead_recipe_historical_lock",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "15:00:00", "text": "Hi Clive, on Departmental Sales for Beefhead dish there is an R20.01 variance. TeamViewer is 501 229 884."},
                {"speaker": "CONSULTANT", "timestamp_str": "15:00:40", "text": "Connected to 501 229 884. The live recipe totals R38.71, matching the R20.01 Beef Sirloin difference against the locked September snapshot."},
                {"speaker": "CONSULTANT", "timestamp_str": "15:01:20", "text": "Per standard GAAP procedure, historical report data from September is locked and cannot be altered retrospectively."},
                {"speaker": "CLIENT", "timestamp_str": "15:01:50", "text": "Understood, that completely explains the historical variance. Problem is solved, no further action needed."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Production Configuration",
            "expected_remote_id": "501 229 884",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Beefhead dish has R20.01 variance matching Beef Sirloin ingredient", "evidence": "variance on Departmental Sales for Beefhead dish"},
                {"fact": "Historical September data is locked by policy", "evidence": "historical report data from September is locked and cannot be altered"}
            ]
        }
    },
    {
        "id": "holdout_05_cashup_terminals_offline_callback",
        "scenario": "Cashup / Firm Morning Callback Commitment (Follow-up Required)",
        "transcript": {
            "session_id": "holdout_05_cashup_terminals_offline_callback",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "19:45:00", "text": "Good evening Clive, we have cashup variances but POS2 and POS3 are offline so sales cannot sync."},
                {"speaker": "CONSULTANT", "timestamp_str": "19:45:30", "text": "Can we reboot POS2 and POS3 now?"},
                {"speaker": "CLIENT", "timestamp_str": "19:45:50", "text": "The store is closing and the owner will be on site tomorrow morning to power them up."},
                {"speaker": "CONSULTANT", "timestamp_str": "19:46:20", "text": "Understood. I will call you tomorrow morning at 8:30 AM to assist with the cashup once terminals are online."},
                {"speaker": "CLIENT", "timestamp_str": "19:46:40", "text": "Thank you Clive, I will expect your call tomorrow morning at 8:30 AM."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "FOLLOW_UP_REQUIRED",
            "expected_category": "Cashup Balancing",
            "expected_remote_id": None,
            "expected_follow_up_required": True,
            "expected_commitment_timeframe": "Tomorrow morning at 8:30 AM",
            "supported_facts": [
                {"fact": "POS2 and POS3 offline preventing cashup sync", "evidence": "POS2 and POS3 are offline so sales cannot sync"},
                {"fact": "Consultant committed to callback tomorrow morning at 8:30 AM", "evidence": "call you tomorrow morning at 8:30 AM to assist with the cashup"}
            ]
        }
    },
    {
        "id": "holdout_06_open_tables_blocking_cashup",
        "scenario": "Point of Sale / Open Tables Blocking Cash-Up (Fully Resolved)",
        "transcript": {
            "session_id": "holdout_06_open_tables_blocking_cashup",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "21:00:00", "text": "Help, system is blocking cashup. Connecting on AnyDesk 311 902 445."},
                {"speaker": "CONSULTANT", "timestamp_str": "21:00:30", "text": "Connected to 311 902 445. There were three open tables on POS1 preventing cashup."},
                {"speaker": "CONSULTANT", "timestamp_str": "21:01:10", "text": "Assisted the manager to close table 4 and table 9 to correct tender. Now complete the cashup."},
                {"speaker": "CLIENT", "timestamp_str": "21:01:45", "text": "Yes, tables are closed and now she can complete cashup! Cashup finished and balanced. Thanks!"}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "RESOLVED",
            "expected_category": "Cashup Balancing",
            "expected_remote_id": "311 902 445",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Open tables were blocking cashup", "evidence": "There were three open tables on POS1 preventing cashup"},
                {"fact": "Tables closed and cashup completed successfully", "evidence": "now she can complete cashup! Cashup finished and balanced"}
            ]
        }
    },
    {
        "id": "holdout_07_phone_currency_ref_safety_trap",
        "scenario": "Card Terminal / Phone, Currency, Date & Case Ref Number Trap (Zero Hallucination)",
        "transcript": {
            "session_id": "holdout_07_phone_currency_ref_safety_trap",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "10:30:00", "text": "Morning. Regarding our PED printing long slips on case REF:00569582. Please call the store manager on 083 760 4430."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:30:35", "text": "Do you have AnyDesk or remote software so I can inspect the terminal configuration?"},
                {"speaker": "CLIENT", "timestamp_str": "10:30:55", "text": "We don't use remote software. The two transactions on 14/07/2026 were R1,000 and R300 on credit card."},
                {"speaker": "CONSULTANT", "timestamp_str": "10:31:30", "text": "Understood. Because we have no remote software access, I will escalate REF:00569582 to the Adumo team with sample slips."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "Payment Terminal / EFT",
            "expected_remote_id": None,  # MUST NOT HALLUCINATE 083 760 4430 or 00569582 or 14/07/2026 or R1,000
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Client reported long slips on PED under reference REF:00569582", "evidence": "PED printing long slips on case REF:00569582"},
                {"fact": "No remote software access installed on site", "evidence": "We don't use remote software"}
            ]
        }
    },
    {
        "id": "holdout_08_multi_terminal_partial_reboot",
        "scenario": "Hardware / Multi-Device Partial Resolution (One Fixed, One Down)",
        "transcript": {
            "session_id": "holdout_08_multi_terminal_partial_reboot",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "12:15:00", "text": "Hello, we have problems on two terminals. AnyDesk is 772 109 443."},
                {"speaker": "CONSULTANT", "timestamp_str": "12:15:40", "text": "Logged in to 772 109 443. One terminal required an OTP, which we provided to the client. Terminal 1 is working fine now."},
                {"speaker": "CONSULTANT", "timestamp_str": "12:16:15", "text": "However, the second terminal has a corrupt database and needs a senior technician onsite to reimage."},
                {"speaker": "CLIENT", "timestamp_str": "12:16:40", "text": "Okay, at least Terminal 1 is online and sorted, but second terminal remains down pending technician."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "PARTIALLY_RESOLVED",
            "expected_category": "POS Terminals",
            "expected_remote_id": "772 109 443",
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Terminal 1 online following OTP entry", "evidence": "Terminal 1 is working fine now"},
                {"fact": "Second terminal remains down with corrupt database pending onsite visit", "evidence": "second terminal remains down pending technician"}
            ]
        }
    },
    {
        "id": "holdout_09_false_confirmation_negation",
        "scenario": "Hardware / False Confirmation Negation Trap (Unresolved)",
        "transcript": {
            "session_id": "holdout_09_false_confirmation_negation",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CLIENT", "timestamp_str": "16:00:00", "text": "Kitchen printer stopped working after power cut. Can you help?"},
                {"speaker": "CONSULTANT", "timestamp_str": "16:00:25", "text": "Please check the power supply and reseat the kettle cord."},
                {"speaker": "CLIENT", "timestamp_str": "16:01:00", "text": "It beeped once, but wait! It is not working now! The red error light is flashing and it completely died again."},
                {"speaker": "CONSULTANT", "timestamp_str": "16:01:30", "text": "That indicates a blown power board from the surge. We cannot fix this remotely, unit is damaged and needs a replacement."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "Hardware / Printer",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Kitchen printer red error light flashing and power board blown", "evidence": "red error light is flashing and it completely died again"}
            ]
        }
    },
    {
        "id": "holdout_10_client_refusal_onsite_escalation",
        "scenario": "Support Resistance / Client Refuses Remote Troubleshooting (Unresolved)",
        "transcript": {
            "session_id": "holdout_10_client_refusal_onsite_escalation",
            "session_type": "holdout",
            "merged_turns": [
                {"speaker": "CONSULTANT", "timestamp_str": "17:15:00", "text": "Support desk, Clive here. Following up on your card machines."},
                {"speaker": "CLIENT", "timestamp_str": "17:15:20", "text": "They were offline all afternoon. We restarted the router and card machine but it still fails."},
                {"speaker": "CONSULTANT", "timestamp_str": "17:15:50", "text": "Can I connect to Server1 via our remote portal to inspect the comms driver?"},
                {"speaker": "CLIENT", "timestamp_str": "17:16:15", "text": "No, I refuse to troubleshoot remotely again. Nothing is fixed and I need an onsite technician tomorrow morning. Goodbye."}
            ]
        },
        "ground_truth": {
            "expected_resolution_status": "UNRESOLVED",
            "expected_category": "Payment Terminal / EFT",
            "expected_remote_id": None,
            "expected_follow_up_required": False,
            "expected_commitment_timeframe": None,
            "supported_facts": [
                {"fact": "Client refused remote troubleshooting and requested onsite visit", "evidence": "I refuse to troubleshoot remotely again. Nothing is fixed and I need an onsite technician"}
            ]
        }
    }
]
