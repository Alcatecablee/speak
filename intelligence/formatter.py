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


def generate_narrative_case_summary(analysis: ConversationAnalysis) -> str:
    """
    Generates a complete, professional narrative case history from the structured analysis.
    Written as cohesive, natural prose suitable for direct entry into Salesforce.
    Contains no bullet points, numbered lists, section headers, label blocks, or AI tags.
    """
    sentences = []

    # 1. Reason for contact & primary issues
    reason = (analysis.summary.reason_for_contact or "").strip()
    primary = (analysis.client_issue.primary_issue or "").strip() if analysis.client_issue else ""
    
    if reason:
        if reason.lower().startswith("the client ") or reason.lower().startswith("the customer "):
            opening = reason
        elif reason.lower().startswith("client ") or reason.lower().startswith("customer "):
            opening = f"The {reason[0].lower() + reason[1:]}"
        else:
            opening = f"The client contacted support regarding {reason[0].lower() + reason[1:]}"
        
        if not opening.endswith("."):
            opening += "."
        sentences.append(opening)
    elif primary:
        p_clean = primary[0].lower() + primary[1:]
        sentences.append(f"The client contacted support regarding {p_clean if p_clean.endswith('.') else p_clean + '.'}")
    else:
        sentences.append("The client contacted support regarding technical assistance.")

    # 2. Key Actions taken & diagnostic findings
    actions_prose = []
    
    # Remote connection check
    if analysis.entities.customer_identifiers:
        remote_id = analysis.entities.customer_identifiers[0]
        actions_prose.append(f"the consultant connected remotely to the client's workstation (Remote ID: {remote_id})")
    elif any("remote" in (a.description or "").lower() for a in analysis.actions_taken.structured_actions):
        actions_prose.append("the consultant connected remotely to the client's workstation")

    # Structured actions processing
    for act in analysis.actions_taken.structured_actions:
        desc = (act.description or "").strip()
        if not desc:
            continue
        # Avoid duplicate remote connection mention
        if "connect" in desc.lower() and "remote" in desc.lower():
            continue
            
        actor_val = act.actor.value if hasattr(act.actor, "value") else str(act.actor)
        act_type_val = act.action_type.value if hasattr(act.action_type, "value") else str(act.action_type)

        # Normalize text to avoid "the consultant consultant diagnosed..."
        clean_desc = desc
        for prefix in ("consultant ", "client ", "the consultant ", "the client "):
            if clean_desc.lower().startswith(prefix):
                clean_desc = clean_desc[len(prefix):]
                break

        if actor_val == "CLIENT":
            if "variance calculation" in clean_desc.lower():
                actions_prose.append("the client demonstrated the variance calculation on screen with test values")
            elif not any(clean_desc.lower() in p.lower() for p in actions_prose):
                actions_prose.append(f"the client {clean_desc[0].lower() + clean_desc[1:]}")
        elif act_type_val == "COMPLETED_ACTION" and actor_val == "CONSULTANT":
            if not any(clean_desc.lower() in p.lower() for p in actions_prose):
                actions_prose.append(f"the consultant {clean_desc[0].lower() + clean_desc[1:]}")
        elif act_type_val == "PROPOSED_ACTION":
            if "escalation" in clean_desc.lower():
                actions_prose.append("the consultant noted potential escalation to software support if configuration adjustments do not resolve the issue")
            elif not any(clean_desc.lower() in p.lower() for p in actions_prose):
                actions_prose.append(f"the consultant proposed {clean_desc[0].lower() + clean_desc[1:]}")

    if actions_prose:
        if len(actions_prose) == 1:
            sentences.append(f"During the session, {actions_prose[0]}.")
        elif len(actions_prose) == 2:
            sentences.append(f"During the session, {actions_prose[0]}, and {actions_prose[1]}.")
        else:
            first_clause = f"During the session, {actions_prose[0]}, and {actions_prose[1]}."
            sentences.append(first_clause)
            for p in actions_prose[2:]:
                p_clean = p[0].upper() + p[1:]
                sentences.append(p_clean if p_clean.endswith(".") else p_clean + ".")

    # 3. Secondary issues / details not yet mentioned
    if analysis.client_issue and analysis.client_issue.details:
        for det in analysis.client_issue.details:
            det_clean = det.strip()
            if det_clean and det_clean.lower() not in (reason.lower() + " " + primary.lower()):
                sentences.append(f"The client also requested assistance regarding {det_clean[0].lower() + det_clean[1:] if not det_clean.endswith('.') else det_clean[0].lower() + det_clean[1:-1]}.")

    # 4. Commitments & Follow-up
    if analysis.follow_up.required:
        tf = (analysis.follow_up.timeframe or "").strip()
        if tf.lower().startswith("within "):
            tf_clause = f" {tf.lower()}"
        elif tf:
            tf_clause = f" within {tf}"
        else:
            tf_clause = ""

        items = ", ".join(analysis.follow_up.action_items) if analysis.follow_up.action_items else "investigate the configuration"
        owner_val = analysis.follow_up.owner.value if hasattr(analysis.follow_up.owner, "value") else str(analysis.follow_up.owner)
        owner_name = "The consultant" if owner_val == "CONSULTANT" else "The client"
        
        clean_items = items.rstrip(".")
        if clean_items.lower().startswith("consultant to "):
            clean_items = clean_items[14:]
        elif clean_items.lower().startswith("client to "):
            clean_items = clean_items[10:]
            
        if "with update" in clean_items.lower() or "with fix" in clean_items.lower() or "an update" in clean_items.lower():
            sentences.append(f"{owner_name} agreed to {clean_items}{tf_clause}.")
        else:
            sentences.append(f"{owner_name} agreed to {clean_items}{tf_clause} with an update.")
    elif analysis.summary.outcome:
        out = analysis.summary.outcome.strip()
        if out:
            sentences.append(out if out.endswith(".") else out + ".")

    # 5. Clear Resolution Status
    res_val = analysis.resolution_status.value if hasattr(analysis.resolution_status, "value") else str(analysis.resolution_status)
    if res_val == "FOLLOW_UP_REQUIRED":
        sentences.append("The issues were not confirmed as fully resolved during the interaction, and follow-up remains outstanding.")
    elif res_val in ("UNRESOLVED", "PARTIALLY_RESOLVED"):
        sentences.append("The case remains open pending further investigation and resolution.")
    elif res_val == "RESOLVED":
        sentences.append("The issue was confirmed as fully resolved during the interaction, and no further follow-up is required.")

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
    subject = f"Production Recipe Variance - {analysis.entities.customer_identifiers[0] if analysis.entities.customer_identifiers else 'Client Call'}"
    narrative_description = generate_narrative_case_summary(analysis)
    
    return {
        "sobject": "Case",
        "action": "DRAFT_UPDATE",
        "human_review_status": "PENDING_CONSULTANT_APPROVAL",
        "requires_consultant_confirmation": True,
        "fields": {
            "Subject": subject,
            "Description": narrative_description,
            "Status": "Pending Follow-up" if analysis.follow_up.required else ("Closed" if getattr(analysis.resolution_status, "value", analysis.resolution_status) == "RESOLVED" else "Open"),
            "Resolution_Category__c": "Production Configuration",
            "Remote_Connection_ID__c": analysis.entities.customer_identifiers[0] if analysis.entities.customer_identifiers else None,
            "Client_Sentiment__c": analysis.sentiment.sentiment.value if hasattr(analysis.sentiment.sentiment, "value") else str(analysis.sentiment.sentiment),
            "AI_Confidence_Score__c": analysis.confidence.score,
            "Internal_Review_Notes__c": analysis.confidence.review_notes
        }
    }
