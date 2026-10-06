"""
Speak V2 — Unified Hackathon Demo Runner.
Executes the complete pipeline:
  [Capture/Load Audio] -> [Whisper STT] -> [Speaker-Attributed Transcript] -> [AI Intelligence] -> [Review & Draft CRM]
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from transcription.pipeline import TranscriptionPipeline
from intelligence.analyzer import ConversationAnalyzer
from intelligence.providers import GroundedExtractionProvider


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def print_banner(text: str):
    print("\n" + "=" * 76)
    print(f"  {text.upper()}")
    print("=" * 76)


def print_section(title: str):
    print("\n" + "-" * 50)
    print(f">> {title}")
    print("-" * 50)


def run_demo(
    mic_path: str,
    loopback_path: str,
    output_dir: str = "recordings",
    whisper_model: str = "openai/whisper-tiny",
    skip_stt: bool = False
):
    print_banner("Speak V2 - Hackathon Live Demo Pipeline")
    print(f"Consultant Audio (Mic):      {mic_path}")
    print(f"Client Audio (Loopback):     {loopback_path}")
    print(f"Output Artifacts Directory:  {output_dir}/")
    print(f"Speech-to-Text Model:        {whisper_model}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_json_path = out_dir / "transcript.json"

    # Step 1: Transcription (or skip if transcript.json already exists and requested)
    if not skip_stt or not transcript_json_path.exists():
        print_section("STEP 1: TWO-STREAM TRANSCRIPTION & SPEAKER ATTRIBUTION")
        pipeline = TranscriptionPipeline(model_name=whisper_model)
        print("Transcribing Consultant Mic and Client Loopback independently...")
        start_t = time.time()
        result = pipeline.process_session(
            consultant_audio_path=mic_path,
            client_audio_path=loopback_path,
            output_dir=output_dir
        )
        elapsed = time.time() - start_t
        print(f"Transcription finished in {elapsed:.1f}s.")
        print(f"Status: {result['status'].upper()} | Total Merged Turns: {len(result['merged_turns'])}")
        print(f"Saved: {output_dir}/transcript.txt & {output_dir}/transcript.json")
    else:
        print_section("STEP 1: USING EXISTING SPEAKER-ATTRIBUTED TRANSCRIPT")
        print(f"Loaded existing: {transcript_json_path}")

    # Step 2: AI Conversation Intelligence
    print_section("STEP 2: AI CONVERSATION INTELLIGENCE (GROUNDED EXTRACTION)")
    analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
    analysis = analyzer.analyze_file(
        transcript_path=str(transcript_json_path),
        output_dir=output_dir
    )

    # Step 3: Present Human-Reviewable Summary
    print_section("STEP 3: CONSULTANT CASE REVIEW & SUMMARY")
    print(f"Status:              [{analysis.resolution_status.value}]")
    print(f"Resolution Basis:    {analysis.resolution_rationale}")
    print(f"Confidence:          {analysis.confidence.level.value} ({int(analysis.confidence.score * 100)}%)")
    print(f"Reason for Contact:  {analysis.summary.reason_for_contact}")
    print(f"Primary Issue:       {analysis.client_issue.primary_issue}")

    print("\nActions Taken & Commitments:")
    for act in analysis.actions_taken.structured_actions:
        tf = f" (Timeframe: {act.timeframe})" if act.timeframe else ""
        print(f"  * [{act.action_type.value}] {act.description}{tf}")

    print(f"\nFollow-up Required:  {'YES' if analysis.follow_up.required else 'NO'}")
    if analysis.follow_up.required:
        print(f"  * Owner:     {analysis.follow_up.owner.value}")
        print(f"  * Timeframe: {analysis.follow_up.timeframe or 'Not specified'}")
        for item in analysis.follow_up.action_items:
            print(f"  * Task:      {item}")

    print("\nNormalized Domain Entities:")
    if analysis.entities.customer_identifiers:
        print(f"  * Customer / AnyDesk ID:  {', '.join(analysis.entities.customer_identifiers)}")
    for ent in analysis.entities.normalized_entities:
        print(f"  * {ent.normalized_value:<32} (Raw: '{ent.raw_text}', Conf: {int(ent.confidence*100)}%)")

    # Step 4: Salesforce Draft Boundary
    print_section("STEP 4: DRAFT SALESFORCE CASE RECORD (REVIEW BOUNDARY)")
    salesforce_file = out_dir / "salesforce_draft_payload.json"
    if salesforce_file.exists():
        with open(salesforce_file, "r", encoding="utf-8") as f:
            sf_data = json.load(f)
        print(f"Action:                     {sf_data.get('action')}")
        print(f"Human Review Status:        {sf_data.get('human_review_status')}")
        print(f"Requires Consultant Signoff:{sf_data.get('requires_consultant_confirmation')}")
        print(f"Draft Subject:              {sf_data['fields'].get('Subject')}")
        print(f"Assigned Case Status:       {sf_data['fields'].get('Status')}")

    # Summary
    print_banner("DEMO EXECUTION COMPLETE - ALL ARTIFACTS READY")
    print("Generated Artifacts:")
    print(f"  1. {output_dir}/transcript.txt               (Human-readable speaker dialogue)")
    print(f"  2. {output_dir}/transcript.json              (Raw timestamped speaker turns)")
    print(f"  3. {output_dir}/analysis.json                (Validated schema v2.1.0 data)")
    print(f"  4. {output_dir}/analysis_review.md           (Full Markdown consultant report)")
    print(f"  5. {output_dir}/salesforce_draft_payload.json (Draft CRM payload for signoff)")
    print("=" * 76 + "\n")


def main():
    setup_logger()
    parser = argparse.ArgumentParser(description="Speak V2 - Hackathon Demo Runner")
    parser.add_argument("--mic", type=str, default="consultant_mic.wav", help="Path to consultant microphone WAV")
    parser.add_argument("--loopback", type=str, default="client_loopback.wav", help="Path to client loopback WAV")
    parser.add_argument("--output-dir", type=str, default="recordings", help="Output directory for all artifacts")
    parser.add_argument("--model", type=str, default="openai/whisper-tiny", help="Whisper model name")
    parser.add_argument("--skip-stt", action="store_true", help="Skip STT and use existing transcript.json if available")

    args = parser.parse_args()

    run_demo(
        mic_path=args.mic,
        loopback_path=args.loopback,
        output_dir=args.output_dir,
        whisper_model=args.model,
        skip_stt=args.skip_stt
    )


if __name__ == "__main__":
    main()
