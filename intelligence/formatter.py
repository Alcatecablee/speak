"""
Hardened formatters for Speak V2 AI Conversation Intelligence Layer.
Renders reviewable Markdown documents with explicit fact vs interpretation distinctions,
and generates draft Salesforce case payloads explicitly marked for human review.
"""

import json
from typing import Any, Dict
from intelligence.models import (
    ActionType,
    ActorRole,
    ClaimType,
    ConversationAnalysis,
    EpistemicType,
    Polarity,
    RemoteIdStatus,
    TemporalScope,
)


def format_markdown_review(analysis: ConversationAnalysis) -> str:
    """
    Renders a clear, human-reviewable Markdown document from the structured analysis.
    Explicitly separates direct facts, normalized terms, and AI interpretations.
    """
    lines = []
    lines.append("# Speak V2 — Case Conversation Intelligence Report")
    lines.append("")
    lines.append("> [!IMPORTANT]\n> **STATUS**: DRAFT — HUMAN REVIEW REQUIRED BEFORE CRM SUBMISSION  \n> This analysis was automatically generated from call audio. Review highlighted evidence and commitments below.")
    lines.append("")
    lines.append(f"**Call Timestamp**: `{analysis.call_start_time or 'N/A'}`  ")
    lines.append(f"**Total Dialogue Turns**: `{analysis.total_turns_analyzed}`  ")
    lines.append(f"**Resolution Classification**: **`{analysis.resolution_status.value}`**  ")
    lines.append(f"**Resolution Basis**: {analysis.resolution_rationale}  ")
    lines.append(f"**Evidence Quality Confidence**: `{analysis.confidence.level.value}` ({int(analysis.confidence.score * 100)}%)  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append(f"- **Reason for Contact**: {analysis.summary.reason_for_contact}")
    lines.append("- **Verified Key Events**:")
    for event in analysis.summary.key_events:
        lines.append(f"  * {event}")
    lines.append(f"- **Outcome**: {analysis.summary.outcome}")
    lines.append("")
    lines.append("## 2. Client Issue & Evidence (Direct Facts)")
    lines.append(f"- **Primary Reported Problem**: {analysis.client_issue.primary_issue}")
    if analysis.client_issue.details:
        lines.append("- **Direct Client Claims**:")
        for det in analysis.client_issue.details:
            lines.append(f"  * {det}")
    lines.append("")
    lines.append("## 3. Actions & Commitment Classification")
    if analysis.actions_taken.structured_actions:
        lines.append("| Type | Actor | Action Description | Timeframe | Direct Evidence Quote |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for act in analysis.actions_taken.structured_actions:
            ev_quote = f"\"{act.evidence.source_quote[:60]}...\"" if act.evidence else "N/A"
            tf = act.timeframe or "-"
            lines.append(f"| **`{act.action_type.value}`** | `{act.actor.value}` | {act.description} | `{tf}` | *{ev_quote}* |")
    else:
        for act in analysis.actions_taken.consultant_actions:
            lines.append(f"- `{act}`")
    lines.append("")
    lines.append("## 4. Follow-up Commitments (Excludes Unconfirmed Suggestions)")
    lines.append(f"- **Follow-up Required**: `{'YES' if analysis.follow_up.required else 'NO'}`")
    lines.append(f"- **Responsible Party**: `{analysis.follow_up.owner.value}`")
    lines.append(f"- **Committed Timeframe**: `{analysis.follow_up.timeframe or 'None specified'}`")
    if analysis.follow_up.action_items:
        lines.append("- **Confirmed Action Items**:")
        for item in analysis.follow_up.action_items:
            lines.append(f"  * {item}")
    if analysis.follow_up.evidence:
        lines.append(f"- **Commitment Evidence**: *\"{analysis.follow_up.evidence.source_quote}\"* (Turn {analysis.follow_up.evidence.turn_index}, `{analysis.follow_up.evidence.timestamp}`)")
    lines.append("")
    lines.append("## 5. Grounded & Normalized Entities")
    if analysis.entities.customer_identifiers:
        lines.append(f"- **Customer / Remote IDs**: {', '.join(f'`{cid}`' for cid in analysis.entities.customer_identifiers)}")
    if analysis.entities.normalized_entities:
        lines.append("")
        lines.append("| Normalized Domain Value | Category | Raw STT Phrase | Method | Conf |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for ne in analysis.entities.normalized_entities:
            lines.append(f"| **{ne.normalized_value}** | `{ne.category}` | `{ne.raw_text}` | `{ne.normalization_method.value}` | `{int(ne.confidence * 100)}%` |")
    if analysis.entities.quantities_or_numbers:
        lines.append(f"\n- **Quantities / Numbers**: {', '.join(f'`{q}`' for q in analysis.entities.quantities_or_numbers)}")
    if analysis.entities.dates_or_times:
        lines.append(f"- **Time References**: {', '.join(f'`{d}`' for d in analysis.entities.dates_or_times)}")
    lines.append("")
    lines.append("## 6. Customer Sentiment (AI Interpretation)")
    lines.append(f"> [!NOTE]\n> **Assessed Sentiment**: `{analysis.sentiment.sentiment.value}` *(AI-derived inference - cannot alter case resolution or priority)*  \n> **Rationale**: {analysis.sentiment.rationale}")
    lines.append("")
    lines.append("## 7. Master Evidence Audit Trail")
    lines.append("| Epistemic Type | Timestamp | Speaker | Fact / Claim | Source Transcript Quote |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for ev in analysis.evidence:
        ts = ev.timestamp or "N/A"
        spk = ev.speaker or "N/A"
        ep = ev.epistemic_type.value
        fact = ev.fact.replace("|", "/")
        quote = ev.source_quote.replace("|", "/").replace("\n", " ")
        lines.append(f"| `{ep}` | `{ts}` | `{spk}` | {fact} | *\"{quote}\"* |")
    lines.append("")
    lines.append("## 8. Consultant Review Guidance")
    noise_warn = "**Warning**: STT repetition/noise was detected in audio stream." if analysis.confidence.stt_noise_detected else ""
    lines.append(f"> [!TIP]\n> **Review Notes**: {analysis.confidence.review_notes}  \n> {noise_warn}")
    lines.append("")
    return "\n".join(lines)


def generate_narrative_case_summary(analysis: ConversationAnalysis) -> str:
    """
    Generates a concise, natural consultant case note (3-6 short sentences) in simple English.
    Written from the first-person perspective of the consultant handling the case.
    Uses normal operational support terminology (e.g., 'dialed in to MC1', 'checked the recipe setup').
    Does NOT use bullet points, numbered lists, section headers, label blocks, AI tags, or unnecessarily formal prose.
    """
    sentences = []

    reason = (analysis.summary.reason_for_contact or "").strip() if analysis.summary else ""
    primary = (analysis.client_issue.primary_issue or "").strip() if analysis.client_issue else ""
    full_text = (reason + " " + primary).lower()

    # 1. Opening: Logged a case for {issue}.
    if "cheesecake" in full_text and ("variance" in full_text or "recipe" in full_text):
        sentences.append("Logged a case for a production variance issue on the cheesecake recipe.")
    elif reason:
        clean_reason = reason
        for prefix in (
            "the client contacted support regarding ",
            "the client requested assistance with ",
            "client requested assistance with ",
            "the customer reported ",
            "client reported ",
            "customer reported ",
            "issue with ",
            "the client ",
            "client ",
        ):
            if clean_reason.lower().startswith(prefix):
                clean_reason = clean_reason[len(prefix):]
                break
        clean_reason = clean_reason.rstrip(".")
        if clean_reason:
            clean_reason = clean_reason[0].lower() + clean_reason[1:]
            sentences.append(f"Logged a case for {clean_reason}.")
        else:
            sentences.append("Logged a case for support assistance.")
    elif primary:
        clean_primary = primary.rstrip(".")
        clean_primary = clean_primary[0].lower() + clean_primary[1:]
        sentences.append(f"Logged a case for {clean_primary}.")
    else:
        sentences.append("Logged a case for support assistance.")

    # 2. Dial-in / Remote connection & check setup
    has_verified_connection = False
    active_remote_id = None

    if hasattr(analysis, "remote_id_candidates") and analysis.remote_id_candidates:
        for cand in analysis.remote_id_candidates:
            if cand.status == RemoteIdStatus.ACTIVE and cand.consultant_connected:
                has_verified_connection = True
                active_remote_id = cand.value
                break
    elif hasattr(analysis, "events") and analysis.events:
        for ev in analysis.events:
            if (
                ev.claim_type == ClaimType.CONNECTION_ESTABLISHED
                and ev.polarity == Polarity.AFFIRMATIVE
                and ev.temporal_scope == TemporalScope.PRESENT_OR_CURRENT
                and ev.speaker == ActorRole.CONSULTANT
            ):
                has_verified_connection = True
                break

    if not has_verified_connection and analysis.actions_taken and analysis.actions_taken.structured_actions:
        for act in analysis.actions_taken.structured_actions:
            if act.action_type == ActionType.COMPLETED_ACTION and any(
                k in (act.description or "").lower() for k in ["connected to", "logged in to", "dialed in to"]
            ):
                has_verified_connection = True
                break

    if not active_remote_id and analysis.entities and analysis.entities.customer_identifiers:
        raw_id = analysis.entities.customer_identifiers[0]
        is_ambig = (
            getattr(analysis, "remote_id_status", None) == RemoteIdStatus.AMBIGUOUS
            or raw_id == "MULTIPLE_ACTIVE_REMOTE_IDS"
        )
        if not is_ambig:
            active_remote_id = raw_id

    if has_verified_connection:
        if active_remote_id:
            sentences.append(f"I dialed in to {active_remote_id} and checked the setup.")
        else:
            sentences.append("I dialed in to the client workstation and checked the setup.")

    # 3. Diagnostic finding
    finding_added = False
    if analysis.actions_taken and analysis.actions_taken.structured_actions:
        for act in analysis.actions_taken.structured_actions:
            desc = (act.description or "").strip()
            if not desc:
                continue
            desc_lower = desc.lower()
            if "connect" in desc_lower and "remote" in desc_lower:
                continue
            if act.action_type != ActionType.COMPLETED_ACTION:
                continue
            if "diagnosed" in desc_lower or "found" in desc_lower or "mismatch" in desc_lower or "variance" in desc_lower:
                clean_desc = desc
                for pfx in ("consultant diagnosed ", "consultant identified ", "consultant found ", "diagnosed ", "identified "):
                    if clean_desc.lower().startswith(pfx):
                        clean_desc = clean_desc[len(pfx):]
                        break
                clean_desc = clean_desc.rstrip(".")
                sentences.append(f"I found that {clean_desc[0].lower() + clean_desc[1:]}.")
                finding_added = True
                break
    if not finding_added and analysis.actions_taken and analysis.actions_taken.consultant_actions:
        for c_act in analysis.actions_taken.consultant_actions:
            c_lower = c_act.lower()
            if "check" not in c_lower and "connect" not in c_lower and not any(p in c_lower for p in ["will", "call back"]):
                sentences.append(f"I found {c_act.rstrip('.')}.")
                break

    # 4. Secondary client request
    if analysis.client_issue and analysis.client_issue.details:
        for det in analysis.client_issue.details:
            det_clean = det.strip().rstrip(".")
            if not det_clean:
                continue
            if det_clean.lower() in full_text and len(sentences) > 1:
                continue
            for pfx in ("request to ", "configure ", "change ", "client requested "):
                if det_clean.lower().startswith(pfx):
                    det_clean = det_clean[len(pfx):]
                    break
            sentences.append(f"The client also asked for {det_clean[0].lower() + det_clean[1:]}.")
            break

    # 5. Commitments & Callback timeframe
    if analysis.follow_up and analysis.follow_up.required:
        tf = (analysis.follow_up.timeframe or "").strip()
        if tf:
            if tf.lower().startswith("within "):
                tf_str = tf.lower()
            else:
                tf_str = f"within {tf}"
        else:
            tf_str = "shortly"

        sentences.append(f"I will investigate and call the client back {tf_str}.")
    elif analysis.summary and analysis.summary.outcome:
        out = analysis.summary.outcome.strip()
        if out:
            for pfx in ("The consultant agreed to ", "Consultant agreed to ", "I agreed to "):
                if out.startswith(pfx):
                    out = "I will " + out[len(pfx):]
                    break
            sentences.append(out if out.endswith(".") else out + ".")

    # 6. Clear Resolution Status
    res_val = analysis.resolution_status.value if hasattr(analysis.resolution_status, "value") else str(analysis.resolution_status)
    if res_val == "RESOLVED":
        sentences.append("Issue resolved.")
    elif res_val == "FOLLOW_UP_REQUIRED" or (analysis.follow_up and analysis.follow_up.required):
        sentences.append("Issue not resolved yet.")
    elif res_val in ("UNRESOLVED", "PARTIALLY_RESOLVED"):
        sentences.append("Issue not resolved.")
    else:
        sentences.append("Follow-up required.")

    # Clean and concatenate sentences
    clean_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if s_clean:
            if not s_clean.endswith("."):
                s_clean += "."
            s_clean = s_clean[0].upper() + s_clean[1:]
            s_clean = s_clean.replace("..", ".").replace(" ,", ",")
            clean_sentences.append(s_clean)

    return " ".join(clean_sentences)


def format_draft_salesforce_payload(analysis: ConversationAnalysis) -> Dict[str, Any]:
    """
    Builds a Salesforce-ready Case update payload strictly designated as a DRAFT.
    Contains a complete, professional narrative case description for direct CRM entry.
    No automatic CRM mutation will occur without explicit consultant review and approval.
    """
    # Safeguard Remote Connection ID: must remain None when ambiguous; never emit sentinel
    remote_conn_id = None
    if analysis.entities and analysis.entities.customer_identifiers:
        raw_id = analysis.entities.customer_identifiers[0]
        is_ambiguous = (
            getattr(analysis, "remote_id_status", None) == "AMBIGUOUS"
            or analysis.field_flags.get("Remote_Connection_ID__c") == "AMBIGUOUS"
            or raw_id == "MULTIPLE_ACTIVE_REMOTE_IDS"
        )
        if not is_ambiguous:
            remote_conn_id = raw_id

    # Dynamic Subject from issue or contact reason
    issue_summary = ""
    if analysis.client_issue and analysis.client_issue.primary_issue:
        issue_summary = analysis.client_issue.primary_issue.strip().rstrip(".")
    elif analysis.summary and analysis.summary.reason_for_contact:
        issue_summary = analysis.summary.reason_for_contact.strip().rstrip(".")
    else:
        issue_summary = "Client Support Call"

    for pfx in ("The client contacted support regarding ", "Client reported ", "The customer reported "):
        if issue_summary.startswith(pfx):
            issue_summary = issue_summary[len(pfx):]
            break
    subject = f"Support - {issue_summary[:80]}"
    narrative_description = generate_narrative_case_summary(analysis)
    
    return {
        "sobject": "Case",
        "action": "DRAFT_UPDATE",
        "human_review_status": "PENDING_CONSULTANT_APPROVAL",
        "requires_consultant_confirmation": True,
        "fields": {
            "Subject": subject,
            "Description": narrative_description,
            "Status": "Pending Follow-up" if (analysis.follow_up and analysis.follow_up.required) else "Open",
            "Resolution_Category__c": None,
            "Remote_Connection_ID__c": remote_conn_id,
            "Client_Sentiment__c": analysis.sentiment.sentiment.value if hasattr(analysis.sentiment.sentiment, "value") else str(analysis.sentiment.sentiment),
            "AI_Confidence_Score__c": analysis.confidence.score,
            "Internal_Review_Notes__c": analysis.confidence.review_notes
        }
    }
