import argparse
import logging
import sys
import os
from datetime import datetime
from transcription.pipeline import TranscriptionPipeline
from transcription.providers import get_transcription_provider

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )

def main():
    parser = argparse.ArgumentParser(description="Transcribe and merge two-stream call recordings (Speak V2).")
    parser.add_argument("--mic", default="consultant_mic.wav", help="Path to consultant mic WAV file")
    parser.add_argument("--loopback", default="client_loopback.wav", help="Path to client loopback WAV file")
    parser.add_argument("--provider", default="whisper-hf", choices=["whisper-hf", "mock"], help="Transcription provider")
    parser.add_argument("--model", default="openai/whisper-tiny", help="Whisper model name (e.g. openai/whisper-tiny, openai/whisper-base)")
    parser.add_argument("--output-dir", default="recordings", help="Output directory for transcript.txt and transcript.json")
    
    args = parser.parse_args()
    setup_logging()
    logger = logging.getLogger("speak.cli")
    
    logger.info("Initializing Speak V2 Transcription CLI...")
    logger.info(f"Using Provider: {args.provider} (Model: {args.model})")
    
    if not os.path.exists(args.mic):
        logger.error(f"Consultant mic file not found: {args.mic}")
        sys.exit(1)
        
    if not os.path.exists(args.loopback):
        logger.error(f"Client loopback file not found: {args.loopback}")
        sys.exit(1)
        
    provider = get_transcription_provider(args.provider, model_name=args.model)
    pipeline = TranscriptionPipeline(provider=provider)
    
    result = pipeline.process_session(
        consultant_audio_path=args.mic,
        client_audio_path=args.loopback,
        call_start_time=datetime.now(),
        output_dir=args.output_dir
    )
    
    print("\n" + "="*70)
    print("FINAL SPEAKER-LABELED TRANSCRIPT:")
    print("="*70)
    print(result["transcript_text"])
    print("="*70)
    print(f"Status: {result['status'].upper()} | Total Turns: {result['total_dialogue_turns']} | Output: {args.output_dir}/transcript.txt\n")

if __name__ == "__main__":
    main()
