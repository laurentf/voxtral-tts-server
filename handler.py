"""RunPod serverless handler for Voxtral TTS.

Starts vLLM-omni as a background subprocess, waits for readiness,
then forwards incoming jobs to the local /v1/audio/speech endpoint.
Returns audio as base64-encoded string.
"""

import base64
import os
import subprocess
import time

import httpx
import runpod

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------

MODEL_ID = os.getenv("VOXTRAL_MODEL", "mistralai/Voxtral-4B-TTS-2603")
PORT = int(os.getenv("VOXTRAL_PORT", "8000"))
MAX_MODEL_LEN = int(os.getenv("VOXTRAL_MAX_MODEL_LEN", "8192"))
QUANTIZATION = os.getenv("VOXTRAL_QUANTIZATION", "")
BASE_URL = f"http://localhost:{PORT}"

# ---------------------------------------------------------------------------
# vLLM subprocess management
# ---------------------------------------------------------------------------

_vllm_process: subprocess.Popen | None = None


def _start_vllm() -> subprocess.Popen:
    """Launch vLLM serve as a background process."""
    cmd = [
        "vllm", "serve", MODEL_ID,
        "--omni",
        "--port", str(PORT),
        "--max-model-len", str(MAX_MODEL_LEN),
        "--dtype", "bfloat16",
        "--gpu-memory-utilization", "0.9",
    ]
    if QUANTIZATION:
        cmd.extend(["--quantization", QUANTIZATION])

    print(f"[handler] Starting vLLM: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def _wait_for_vllm(timeout: int = 600) -> None:
    """Block until vLLM health endpoint responds or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
            if resp.status_code == 200:
                print(f"[handler] vLLM ready after {int(time.time() - start)}s")
                return
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    raise TimeoutError(f"vLLM did not start within {timeout}s")


# ---------------------------------------------------------------------------
# RunPod handler
# ---------------------------------------------------------------------------

def handler(job: dict) -> dict:
    """Process a TTS job.

    Input schema (all fields from /v1/audio/speech):
        {
            "text": "Hello world",              # required
            "voice": "neutral_male",            # preset voice (ignored if ref_audio set)
            "ref_audio": "data:audio/wav;...",   # voice cloning (base64 data URL)
            "ref_text": "transcript",            # transcript of reference audio
            "response_format": "wav",            # wav, mp3, flac, pcm, aac, opus
            "speed": 1.0,                        # 0.25–4.0
            "language": "Auto",                  # en, fr, es, de, it, pt, nl, ar, hi
            "max_new_tokens": 2048               # max generation tokens (~2 min)
        }

    Returns:
        {
            "audio_base64": "UklGRi...",
            "format": "wav",
            "model": "mistralai/Voxtral-4B-TTS-2603"
        }
    """
    job_input = job["input"]

    text = job_input.get("text")
    if not text:
        return {"error": "Missing required field: 'text'"}

    # Build payload for vLLM /v1/audio/speech
    payload: dict = {
        "input": text,
        "model": MODEL_ID,
        "response_format": job_input.get("response_format", "wav"),
    }

    # Voice: cloning or preset (mutually exclusive)
    ref_audio = job_input.get("ref_audio")
    if ref_audio:
        payload["ref_audio"] = ref_audio
        ref_text = job_input.get("ref_text")
        if ref_text:
            payload["ref_text"] = ref_text
    else:
        payload["voice"] = job_input.get("voice", "neutral_male")

    # Optional params
    for key in ("speed", "language", "max_new_tokens"):
        if key in job_input:
            payload[key] = job_input[key]

    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/audio/speech",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return {"error": f"vLLM error: {exc.response.status_code} {exc.response.text[:500]}"}
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return {"error": f"vLLM connection error: {exc}"}

    audio_b64 = base64.b64encode(resp.content).decode("ascii")

    return {
        "audio_base64": audio_b64,
        "format": payload["response_format"],
        "model": MODEL_ID,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

print("[handler] Initializing Voxtral TTS worker...")
_vllm_process = _start_vllm()
_wait_for_vllm()

runpod.serverless.start({"handler": handler})
