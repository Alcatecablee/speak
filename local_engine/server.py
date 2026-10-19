"""
FastAPI Local Engine Server for Speak V2.
Binds strictly to loopback (127.0.0.1:8765).
Bridges the Speak Web UI to native WASAPI capture and conversation intelligence.
Secured via ephemeral 256-bit token authentication, pairing code bootstrap,
strict Origin allowlist, and log secret redaction (P0.2).
"""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from local_engine.auth import AuthManager, AuthSecretRedactionFilter
from local_engine.capture_manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [speak.server] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("speak.server")

# Instantiate security manager
auth_manager = AuthManager()

# SessionManager is lazy-initialized and respects SPEAK_OUTPUT_DIR
_session_manager: Optional[SessionManager] = None


def get_default_output_dir() -> str:
    return os.environ.get("SPEAK_OUTPUT_DIR", "recordings")


def get_session_manager() -> SessionManager:
    """Dependency provider for SessionManager, overridable in tests."""
    if "app" in globals() and app and hasattr(app, "dependency_overrides"):
        override = app.dependency_overrides.get(get_session_manager)
        if override is not None:
            return override()
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(output_dir=get_default_output_dir())
    return _session_manager


class _LazySessionManagerProxy:
    """Lazy proxy ensuring legacy module-level attribute access defers initialization."""
    def __getattr__(self, name: str) -> Any:
        return getattr(get_session_manager(), name)


session_manager = _LazySessionManagerProxy()

# Apply credential redaction filter to loggers to prevent token leakage
redaction_filter = AuthSecretRedactionFilter(auth_manager)
logging.getLogger().addFilter(redaction_filter)
for handler in logging.getLogger().handlers:
    handler.addFilter(redaction_filter)
logger.addFilter(redaction_filter)


def get_auth_manager() -> AuthManager:
    """Dependency provider for AuthManager, overridable in tests."""
    return auth_manager


def verify_auth_token(
    request: Request,
    auth_header: Optional[str] = Header(None, alias="X-Speak-Engine-Auth"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    auth_mgr: AuthManager = Depends(get_auth_manager)
) -> bool:
    """
    Verifies request authenticity using constant-time 256-bit session token comparison.
    Accepts token via 'X-Speak-Engine-Auth' custom header or 'Authorization: Bearer <token>'.
    Validates Origin header against strict allowlist (no wildcard).
    """
    origin = request.headers.get("origin")
    if origin and not auth_mgr.is_origin_allowed(origin):
        logger.warning(f"Rejected request with disallowed Origin: {origin}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Origin not in allowed origin list."
        )

    token = auth_header
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token or not auth_mgr.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: missing or invalid engine authentication token."
        )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages background processing worker startup and graceful shutdown."""
    logger.info("Initializing Speak Local Engine lifespan...")
    mgr = get_session_manager()
    mgr.start_worker()
    yield
    logger.info("Shutting down Speak Local Engine lifespan...")
    mgr.shutdown_worker()


app = FastAPI(
    title="Speak Local Engine API",
    description="Localhost bridge for native Windows WASAPI call capture and AI analysis",
    version="2.2.0",
    lifespan=lifespan
)

# Configure CORS with strict Origin allowlist (Wildcards disallowed per CTO mandate)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(auth_manager.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class PairRequest(BaseModel):
    pairing_code: str = Field(..., description="6-digit pairing code displayed in the engine console")


@app.get("/health")
def get_health():
    """Health check endpoint confirming engine is active on loopback. Unauthenticated."""
    return {
        "status": "ok",
        "engine": "Speak Localhost Engine",
        "version": "2.2.0",
        "loopback_only": True
    }


@app.post("/auth/pair")
def pair_client(
    req: PairRequest,
    request: Request,
    auth_mgr: AuthManager = Depends(get_auth_manager)
):
    """
    Bootstrap pairing endpoint.
    Exchanges single-use 6-digit pairing code for an ephemeral session auth token.
    Rate-limited: 5 failed attempts triggers a 60s cooldown (HTTP 429).
    Code expires after 5 minutes TTL (HTTP 403). Single-use: consumed on success.
    """
    origin = request.headers.get("origin")
    if origin and not auth_mgr.is_origin_allowed(origin):
        logger.warning(f"Pairing attempt from disallowed Origin: {origin}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Origin not in allowed origin list."
        )

    if auth_mgr.is_in_cooldown():
        cooldown = auth_mgr.get_remaining_cooldown()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Pairing locked in cooldown. Please wait {cooldown} seconds before retrying."
        )

    if auth_mgr.is_code_expired():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pairing code has expired. Please check console for a fresh code."
        )

    token = auth_mgr.pair_with_code(req.pairing_code)
    if not token:
        if auth_mgr.is_in_cooldown():
            cooldown = auth_mgr.get_remaining_cooldown()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed pairing attempts. Locked for {cooldown} seconds cooldown."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid pairing code."
        )

    return {
        "status": "paired",
        "auth_token": token
    }


@app.get("/status")
def get_status(
    session_id: Optional[str] = Query(default=None, description="Optional specific session ID to inspect"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Returns current engine capture hardware state and optional session-specific status."""
    return manager.get_status(session_id=session_id)


@app.get("/sessions")
def list_sessions(
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
) -> List[Dict[str, Any]]:
    """Returns catalog of all historical and active sessions."""
    return manager.list_sessions()


@app.post("/capture/start")
def start_capture(
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Starts dual-stream WASAPI recording in an isolated session folder."""
    try:
        result = manager.start_capture()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/capture/stop")
def stop_capture(
    session_id: str = Query(..., description="Active session ID being stopped (required)"),
    skip_stt: bool = Query(default=False, description="For fast demo without Whisper"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Stops audio capture for session_id, frees audio devices, and queues processing."""
    try:
        result = manager.stop_capture_and_process(session_id=session_id, skip_stt_demo=skip_stt)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/capture/cancel")
def cancel_capture(
    session_id: Optional[str] = Query(default=None, description="Session ID to cancel (optional)"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Cancels active recording or queued processing and resets engine to idle."""
    try:
        return manager.cancel_session(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcript")
def get_transcript(
    session_id: str = Query(..., description="Unique session ID (required)"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Returns transcript JSON and formatted plain text for session_id."""
    try:
        return manager.get_transcript_data(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/analysis")
def get_analysis(
    session_id: str = Query(..., description="Unique session ID (required)"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Returns structured conversation intelligence JSON for session_id."""
    try:
        return manager.get_analysis_data(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/review")
def get_review(
    session_id: str = Query(..., description="Unique session ID (required)"),
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Returns human-reviewable Markdown summary and draft Salesforce payload for session_id."""
    try:
        return manager.get_review_data(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/demo/load-sample")
def load_sample(
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Loads benchmark sample into a new, unique isolated demo session folder."""
    try:
        return manager.load_demo_sample()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/retry")
def retry_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    _auth: bool = Depends(verify_auth_token)
):
    """Manually re-enqueues an interrupted, errored, or backpressured session for processing."""
    try:
        return manager.retry_session(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Starts the FastAPI server strictly on 127.0.0.1 and displays pairing instructions."""
    code = auth_manager.pairing_code
    formatted_code = f"{code[:3]}-{code[3:]}" if len(code) == 6 else code
    print("\n" + "=" * 64)
    print("  SPEAK LOCAL ENGINE v2.2.0")
    print(f"  Bound strictly to loopback: http://{host}:{port}")
    print("  " + "-" * 60)
    print(f"  PAIRING CODE:  {formatted_code}")
    print("  Enter this 6-digit code in the Speak Web UI to authenticate.")
    print("=" * 64 + "\n", flush=True)

    logger.info(f"Starting Speak Local Engine on http://{host}:{port} (Loopback only)...")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
