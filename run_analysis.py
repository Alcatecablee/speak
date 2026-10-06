"""
CLI entrypoint for Speak V2 AI Conversation Intelligence Layer.
Usage:
    python run_analysis.py --transcript recordings/transcript.json --output-dir recordings/
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.analyzer import ConversationAnalyzer
from intelligence.providers import GroundedExtractionProvider, LLMAnalysisProvider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("speak.run_analysis")


def main():
    parser = argparse.ArgumentParser(description="Speak V2 - AI Conversation Intelligence Layer")
    parser.add_argument(
        "--transcript",
        type=str,
        default="recordings/transcript.json",
        help="Path to structured transcript.json file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="recordings",
        help="Directory to save analysis.json, analysis_review.md, and draft Salesforce payload"
    )
    parser.add_argument(
        "--provider",
        choices=["grounded", "llm"],
        default="grounded",
        help="Analysis provider engine (default: grounded)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Model name for LLM provider"
    )

    args = parser.parse_args()

    logger.info(f"Initializing AI Conversation Intelligence (Provider: {args.provider})...")
    
    if args.provider == "llm":
        provider = LLMAnalysisProvider(model_name=args.model)
    else:
        provider = GroundedExtractionProvider()

    analyzer = ConversationAnalyzer(provider=provider)

    try:
        analysis = analyzer.analyze_file(
            transcript_path=args.transcript,
            output_dir=args.output_dir
        )
        print("\n" + "=" * 70)
        print("CONVERSATION INTELLIGENCE ANALYSIS COMPLETED")
        print("=" * 70)
        print(f"Status:             {analysis.resolution_status.value}")
        print(f"Confidence:         {analysis.confidence.level.value} ({int(analysis.confidence.score * 100)}%)")
        print(f"Reason for Contact: {analysis.summary.reason_for_contact}")
        print(f"Primary Issue:      {analysis.client_issue.primary_issue}")
        print(f"Follow-up:          {'YES' if analysis.follow_up.required else 'NO'} - {', '.join(analysis.follow_up.action_items)}")
        print(f"Evidence Items:     {len(analysis.evidence)} grounded facts linked to dialogue turns")
        print(f"Outputs written to: {args.output_dir}/analysis.json, {args.output_dir}/analysis_review.md")
        print("=" * 70 + "\n")
        return 0
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
