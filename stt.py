"""Optional speech to text for Talk, via CrispASR's whisper server on STT_PORT (default 5091).

Needs CrispASR plus a whisper ggml model:
    cd <CrispASR>/models && sh download-ggml-model.sh large-v3-turbo-q5_0
"""
import atexit
import glob
import json
import os
import subprocess
import threading
import time

import requests

CRISPASR_DIR = os.environ.get("CRISPASR_DIR", os.path.join(os.path.expanduser("~"), "Documents", "CrispASR"))
CRISPASR_EXE = os.environ.get("CRISPASR_EXE", os.path.join(CRISPASR_DIR, "build-vulkan", "bin", "crispasr.exe"))

CRISPASR_HOST = "127.0.0.1"
STT_PORT = int(os.environ.get("STT_PORT", "5091"))
STT_BASE = f"http://{CRISPASR_HOST}:{STT_PORT}"

# Explicit override wins; otherwise take the best whisper model actually on disk. The for-tests-*
# files are 500KB stubs shipped for CrispASR's own test suite, not usable models — never pick one.
STT_MODEL = os.environ.get("STT_MODEL", "")
# Whisper only keeps the tail of a prompt (224 tokens); a sentence or two is all that is useful.
PROMPT_CHARS = 200
TAKES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stt_takes")

_server_proc = None
_server_lock = threading.Lock()
# One loaded model behind the endpoint: overlapping POSTs queue instead of racing.
_stt_lock = threading.Lock()


def model_path():
    if STT_MODEL:
        return STT_MODEL if os.path.exists(STT_MODEL) else ""
    found = [p for p in glob.glob(os.path.join(CRISPASR_DIR, "models", "ggml-*.bin"))
             if "for-tests" not in os.path.basename(p)]
    # Biggest file = best model of those present. Crude, and right for whisper's size ladder.
    return max(found, key=os.path.getsize) if found else ""


def available() -> bool:
    return os.path.exists(CRISPASR_EXE) and bool(model_path())


def _server_healthy() -> bool:
    try:
        return requests.get(f"{STT_BASE}/health", timeout=1).ok
    except requests.RequestException:
        return False


def _ensure_server():
    global _server_proc
    if _server_healthy():
        return
    with _server_lock:
        if _server_healthy():
            return
        _server_proc = subprocess.Popen(
            [CRISPASR_EXE, "--server", "-m", model_path(),
             "--host", CRISPASR_HOST, "--port", str(STT_PORT)],
            cwd=CRISPASR_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        atexit.register(_stop_server)
        deadline = time.monotonic() + 60   # whisper loads from disk
        while time.monotonic() < deadline:
            if _server_healthy():
                return
            if _server_proc.poll() is not None:
                raise RuntimeError("crispasr ASR server exited during startup")
            time.sleep(0.3)
        raise RuntimeError("crispasr ASR server did not become healthy in time")


def _stop_server():
    if _server_proc is not None and _server_proc.poll() is None:
        _server_proc.terminate()


def warm():
    """Load the ASR model up front: the first thing you say shouldn't pay for it."""
    if not available():
        print(f"[stt] no whisper model in {os.path.join(CRISPASR_DIR, 'models')} — speech input off")
        return
    try:
        _ensure_server()
        print(f"[stt] speech recognition ready on {STT_BASE} ({os.path.basename(model_path())})")
    except Exception as e:
        print(f"[stt] could not start ASR server: {e}")


def transcribe(audio_bytes: bytes, language: str = "sr", filename: str = "speech.wav",
               prompt: str = "") -> str:
    """Spoken audio -> text, or "" when unavailable or the take was unusable.

    Empty string, never a guess: app.js shows "didn't catch that" rather than putting words in the
    learner's mouth.
    prompt: what was said just before (whisper's "previous context"). It steers the recognizer
    toward real words in that register; it is context, never the expected answer.
    """
    if not audio_bytes or not available():
        return ""
    data = {"response_format": "json", "language": language}
    if prompt:
        data["prompt"] = prompt[-PROMPT_CHARS:]
    try:
        _ensure_server()
        with _stt_lock:
            r = requests.post(
                f"{STT_BASE}/v1/audio/transcriptions",
                files={"file": (filename, audio_bytes, "audio/wav")},
                data=data,
                timeout=120,
            )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()
    except Exception as e:
        print(f"[stt] transcription failed: {e}")
        return ""


def save_take(audio_bytes: bytes, text: str, prompt: str = "", keep: int = 20) -> str:
    """Keep the newest recordings beside what was heard, so a mishearing can be replayed and a
    change to the prompt or the model measured on real audio (tools/stt_replay.py)."""
    os.makedirs(TAKES_DIR, exist_ok=True)
    stem = os.path.join(TAKES_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**6:06d}")
    with open(stem + ".wav", "wb") as f:
        f.write(audio_bytes)
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump({"text": text, "prompt": prompt}, f, ensure_ascii=False)
    for old in sorted(glob.glob(os.path.join(TAKES_DIR, "*.wav")))[:-keep]:
        for path in (old, old[:-4] + ".json"):
            if os.path.exists(path):
                os.remove(path)
    return stem + ".wav"


if __name__ == "__main__":
    # Smallest useful check: CrispASR ships samples/jfk.wav. English, but this is a plumbing test —
    # does the server start, take a file and hand back words.
    sample = os.path.join(CRISPASR_DIR, "samples", "jfk.wav")
    print("model:", model_path() or "(none found)")
    if not available():
        raise SystemExit("no whisper model installed — see the module docstring")
    print("transcript:", transcribe(open(sample, "rb").read(), language="en") or "(nothing)")
