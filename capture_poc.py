import pyaudiowpatch as pyaudio
import soundfile as sf
import queue
import time
import sys
import numpy as np
import os
import logging
import argparse
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
    parser = argparse.ArgumentParser(description="Two-stream Audio Capture with Integrated Transcription (Speak V2)")
    parser.add_argument("--transcribe", action="store_true", default=True, help="Automatically transcribe streams after capture (default: True)")
    parser.add_argument("--no-transcribe", dest="transcribe", action="store_false", help="Skip automatic transcription")
    parser.add_argument("--model", default="openai/whisper-tiny", help="Whisper model name (default: openai/whisper-tiny)")
    parser.add_argument("--provider", default="whisper-hf", choices=["whisper-hf", "mock"], help="Transcription provider (default: whisper-hf)")
    parser.add_argument("--output-dir", default="recordings", help="Output directory for session artifacts")
    
    args = parser.parse_args()
    setup_logging()
    logger = logging.getLogger("speak.capture")

    logger.info("==================================================")
    logger.info("Initializing Speak V2 Dual-Stream Audio Capture...")
    logger.info("==================================================")

    p = pyaudio.PyAudio()

    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        default_mic = p.get_device_info_by_index(wasapi_info["defaultInputDevice"])
        default_loopback = p.get_default_wasapi_loopback()
    except OSError as e:
        logger.error(f"Error discovering WASAPI audio hardware: {e}")
        p.terminate()
        sys.exit(1)

    logger.info(f"Target Microphone Device: {default_mic['name']} (Index: {default_mic['index']})")
    logger.info(f"Target Loopback Device:   {default_loopback['name']} (Index: {default_loopback['index']})")

    q_mic = queue.Queue()
    q_loop = queue.Queue()

    def mic_callback(in_data, frame_count, time_info, status):
        q_mic.put(in_data)
        return (in_data, pyaudio.paContinue)

    def loop_callback(in_data, frame_count, time_info, status):
        q_loop.put(in_data)
        return (in_data, pyaudio.paContinue)

    mic_rate = int(default_mic["defaultSampleRate"])
    mic_channels = default_mic["maxInputChannels"]
    
    loop_rate = int(default_loopback["defaultSampleRate"])
    loop_channels = default_loopback["maxInputChannels"]

    mic_file = "consultant_mic.wav"
    loop_file = "client_loopback.wav"

    if os.path.exists(mic_file):
        os.remove(mic_file)
    if os.path.exists(loop_file):
        os.remove(loop_file)

    f_mic = sf.SoundFile(mic_file, mode='x', samplerate=mic_rate, channels=mic_channels, subtype='PCM_16')
    f_loop = sf.SoundFile(loop_file, mode='x', samplerate=loop_rate, channels=loop_channels, subtype='PCM_16')

    call_start_time = datetime.now()
    logger.info(f"Opening capture streams at {call_start_time.strftime('%H:%M:%S')}...")

    try:
        # 1. Open Microphone Stream (Consultant)
        logger.info("[STREAM 1/2 START] Opening CONSULTANT microphone stream...")
        stream_mic = p.open(format=pyaudio.paInt16,
                            channels=mic_channels,
                            rate=mic_rate,
                            input=True,
                            input_device_index=default_mic["index"],
                            stream_callback=mic_callback)

        # 2. Open Loopback Stream (Client)
        logger.info("[STREAM 2/2 START] Opening CLIENT headset loopback stream...")
        stream_loop = p.open(format=pyaudio.paInt16,
                             channels=loop_channels,
                             rate=loop_rate,
                             input=True,
                             input_device_index=default_loopback["index"],
                             stream_callback=loop_callback)
                             
        stream_mic.start_stream()
        stream_loop.start_stream()

        logger.info(">>> LIVE RECORDING ACTIVE <<< (Both channels time-synchronized)")
        logger.info("Speak into microphone or conduct call. Press Ctrl+C when finished.")

        while stream_mic.is_active() and stream_loop.is_active():
            while not q_mic.empty():
                data = q_mic.get()
                audio_data = np.frombuffer(data, dtype=np.int16)
                if mic_channels > 1:
                    audio_data = audio_data.reshape(-1, mic_channels)
                f_mic.write(audio_data)

            while not q_loop.empty():
                data = q_loop.get()
                audio_data = np.frombuffer(data, dtype=np.int16)
                if loop_channels > 1:
                    audio_data = audio_data.reshape(-1, loop_channels)
                f_loop.write(audio_data)
                
            time.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("Stop signal received. Halting audio streams...")
    finally:
        if 'stream_mic' in locals():
            stream_mic.stop_stream()
            stream_mic.close()
            logger.info("[STREAM 1/2 STOP] Consultant microphone stream closed.")
        if 'stream_loop' in locals():
            stream_loop.stop_stream()
            stream_loop.close()
            logger.info("[STREAM 2/2 STOP] Client loopback stream closed.")
        
        f_mic.close()
        f_loop.close()
        p.terminate()
        
        mic_size = os.path.getsize(mic_file) if os.path.exists(mic_file) else 0
        loop_size = os.path.getsize(loop_file) if os.path.exists(loop_file) else 0
        
        logger.info(f"Raw audio safely preserved:")
        logger.info(f"  - {mic_file}  ({mic_size / (1024*1024):.2f} MB)")
        logger.info(f"  - {loop_file} ({loop_size / (1024*1024):.2f} MB)")

    # Execute transcription if requested
    if args.transcribe and mic_size > 5000 and loop_size > 5000:
        logger.info("\n>>> TRANSCRIPTION PIPELINE TRIGGERED <<<")
        provider = get_transcription_provider(args.provider, model_name=args.model)
        pipeline = TranscriptionPipeline(provider=provider)
        
        result = pipeline.process_session(
            consultant_audio_path=mic_file,
            client_audio_path=loop_file,
            call_start_time=call_start_time,
            output_dir=args.output_dir
        )
        
        print("\n" + "="*70)
        print("FINAL SPEAKER-LABELED TRANSCRIPT:")
        print("="*70)
        print(result["transcript_text"])
        print("="*70)
        print(f"Transcript saved to: {args.output_dir}/transcript.txt\n")

if __name__ == '__main__':
    main()
