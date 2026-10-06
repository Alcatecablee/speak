"""
Hardened formatters for Speak V2 AI Conversation Intelligence Layer.
Renders reviewable Markdown documents with explicit fact vs interpretation distinctions,
and generates draft Salesforce case payloads explicitly marked for human review.
"""

import json
from typing import Any, Dict
from intelligence.models import ConversationAnalysis, EpistemicType


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


def format_draft_salesforce_payload(analysis: ConversationAnalysis) -> Dict[str, Any]:
    """
    Builds a Salesforce-ready Case update payload strictly designated as a DRAFT.
    No automatic CRM mutation will occur without explicit consultant review and approval.
    """
    subject = f"Production Recipe Variance - {analysis.entities.customer_identifiers[0] if analysis.entities.customer_identifiers else 'Client Call'}"
    
    description_parts = [
        "[DRAFT CASE RECORD - GENERATED BY SPEAK V2 - REVIEW REQUIRED]",
        f"REASON FOR CONTACT:\n{analysis.summary.reason_for_contact}\n",
        f"PRIMARY ISSUE:\n{analysis.client_issue.primary_issue}\n",
        "CONFIRMED ACTIONS & COMMITMENTS:\n" + "\n".join(
            f"- [{act.action_type.value}] {act.description} (Owner: {act.actor.value})"
            for act in analysis.actions_taken.structured_actions
        ) + "\n",
        f"FOLLOW UP REQUIRED: {'YES' if analysis.follow_up.required else 'NO'}",
        f"FOLLOW UP DETAILS: {', '.join(analysis.follow_up.action_items)} (Timeframe: {analysis.follow_up.timeframe or 'N/A'})\n",
        f"RESOLUTION STATUS: {analysis.resolution_status.value}",
        f"RESOLUTION BASIS: {analysis.resolution_rationale}"
    ]
    
    return {
        "sobject": "Case",
        "action": "DRAFT_UPDATE",
        "human_review_status": "PENDING_CONSULTANT_APPROVAL",
        "requires_consultant_confirmation": True,
        "fields": {
            "Subject": subject,
            "Description": "\n".join(description_parts),
            "Status": "Pending Follow-up" if analysis.follow_up.required else "Closed",
            "Resolution_Category__c": "Production Configuration",
            "Remote_Connection_ID__c": analysis.entities.customer_identifiers[0] if analysis.entities.customer_identifiers else None,
            "Client_Sentiment__c": analysis.sentiment.sentiment.value,
            "AI_Confidence_Score__c": analysis.confidence.score,
            "Internal_Review_Notes__c": analysis.confidence.review_notes
        }
    }
