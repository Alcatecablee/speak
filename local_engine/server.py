"""
FastAPI Local Engine Server for Speak V2.
Binds strictly to loopback (127.0.0.1:8765).
Bridges the Speak Web UI to native WASAPI capture and conversation intelligence.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from local_engine.capture_manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [speak.server] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("speak.server")

app = FastAPI(
    title="Speak Local Engine API",
    description="Localhost bridge for native Windows WASAPI call capture and AI analysis",
    version="2.1.0"
)

# Configure CORS for Speak Web App & Localhost
ALLOWED_ORIGINS = [
    "https://speak-plum.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8765",
    "null"  # For file:// execution if tested locally
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_manager = SessionManager(output_dir="recordings")


@app.get("/health")
def get_health():
    """Health check endpoint confirming engine is active on loopback."""
    return {
        "status": "ok",
        "engine": "Speak Localhost Engine",
        "version": "2.1.0",
        "loopback_only": True
    }


@app.get("/status")
def get_status():
    """Returns current engine capture/processing state."""
    return session_manager.get_status()


@app.post("/capture/start")
def start_capture():
    """Starts dual-stream WASAPI recording."""
    try:
        result = session_manager.start_capture()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/capture/stop")
def stop_capture(skip_stt: bool = Query(default=False, description="For fast hackathon demo")):
    """Stops audio capture and begins background transcription + intelligence analysis."""
    try:
        result = session_manager.stop_capture_and_process(skip_stt_demo=skip_stt)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcript")
def get_transcript():
    """Returns transcript JSON and formatted plain text."""
    json_path = session_manager.output_dir / "transcript.json"
    txt_path = session_manager.output_dir / "transcript.txt"

    if not json_path.exists():
        raise HTTPException(status_code=404, detail="No transcript found. Record a call first.")

    with open(json_path, "r", encoding="utf-8") as f:
        transcript_json = json.load(f)

    raw_text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""

    return {
        "status": "success",
        "data": transcript_json,
        "formatted_text": raw_text
    }


@app.get("/analysis")
def get_analysis():
    """Returns structured conversation intelligence JSON."""
    analysis_path = session_manager.output_dir / "analysis.json"
    if not analysis_path.exists():
        raise HTTPException(status_code=404, detail="No analysis found. Record a call first.")

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis_json = json.load(f)

    return {
        "status": "success",
        "data": analysis_json
    }


@app.get("/review")
def get_review():
    """Returns human-reviewable Markdown summary and draft Salesforce payload."""
    review_path = session_manager.output_dir / "analysis_review.md"
    sf_path = session_manager.output_dir / "salesforce_draft_payload.json"

    if not review_path.exists():
        raise HTTPException(status_code=404, detail="No review document found. Record a call first.")

    markdown_text = review_path.read_text(encoding="utf-8")
    
    sf_payload = {}
    if sf_path.exists():
        with open(sf_path, "r", encoding="utf-8") as f:
            sf_payload = json.load(f)

    return {
        "status": "success",
        "markdown": markdown_text,
        "salesforce_draft": sf_payload
    }


@app.post("/demo/load-sample")
def load_sample():
    """Loads pre-analyzed real recording for instant demo."""
    try:
        return session_manager.load_demo_sample()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Starts the FastAPI server strictly on 127.0.0.1."""
    logger.info(f"Starting Speak Local Engine on http://{host}:{port} (Loopback only)...")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
