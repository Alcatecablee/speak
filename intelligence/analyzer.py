"""
Pipeline orchestrator for Speak V2 AI Conversation Intelligence.
Loads structured transcript, executes extraction, validates output schema, and exports review artifacts.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type

from intelligence.formatter import format_draft_salesforce_payload, format_markdown_review
from intelligence.models import ConversationAnalysis
from intelligence.providers import BaseAnalysisProvider, GroundedExtractionProvider, LLMAnalysisProvider

logger = logging.getLogger("speak.intelligence")


class ConversationAnalyzer:
    """Orchestrates structured conversation intelligence analysis."""

    def __init__(self, provider: Optional[BaseAnalysisProvider] = None):
        self.provider = provider or GroundedExtractionProvider()

    def analyze_file(
        self,
        transcript_path: str,
        output_dir: Optional[str] = None
    ) -> ConversationAnalysis:
        """
        Reads a transcript.json file, processes it through the provider, and writes outputs.
        
        Args:
            transcript_path: Path to transcript.json file.
            output_dir: Optional directory to save analysis.json and review.md.
            
        Returns:
            ConversationAnalysis validated object.
        """
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        logger.info(f"Loading transcript from {transcript_path}...")
        with open(path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)

        logger.info("Executing conversation analysis...")
        analysis = self.provider.analyze(transcript_data)

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            # 1. Save validated JSON
            json_file = out_path / "analysis.json"
            with open(json_file, "w", encoding="utf-8") as f:
                f.write(analysis.model_dump_json(indent=2))
            logger.info(f"Saved analysis JSON to {json_file}")

            # 2. Save Markdown review document
            md_file = out_path / "analysis_review.md"
            md_content = format_markdown_review(analysis)
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"Saved Markdown review to {md_file}")

            # 3. Save draft Salesforce payload (without transmitting)
            sf_file = out_path / "salesforce_draft_payload.json"
            sf_payload = format_draft_salesforce_payload(analysis)
            with open(sf_file, "w", encoding="utf-8") as f:
                json.dump(sf_payload, f, indent=2)
            logger.info(f"Saved draft Salesforce payload to {sf_file}")

        return analysis
