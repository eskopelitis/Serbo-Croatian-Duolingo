"""Local Serbian Marko voice, with a separately installed Piper model.

By default the model is read from the user's NasJezik data directory. Set
SC_PIPER_MODEL to override the downloaded sr_Marko_medium.onnx file. Its matching
configuration defaults to the model path plus ".json"; SC_PIPER_CONFIG can
override that path. The model is not downloaded or distributed by this module.
Piper and the voice model have separate licenses and must be reviewed separately.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
import importlib.util
import io
import os
from pathlib import Path
import threading
import wave


# Pin the reviewed Marko release and config so another model is not presented
# as this Serbian voice. Update both hashes only after reviewing a new release.
_MODEL_SHA256 = "2d009fe6d43e25b9516b23f5e64f65af202e76f0e6940e452dfb45852a412a68"
_CONFIG_SHA256 = "f3ce50b11c799b0134e678cccecfb8751a4990de32dd710625139c728a1714fb"
_MAX_TEXT_LENGTH = 300
_lock = threading.RLock()
_cached_voice = None
_cached_paths = None


class VoiceUnavailable(RuntimeError):
    """The optional Serbian voice is not configured or could not synthesize."""


class VoiceInputError(ValueError):
    """The supplied text is empty, invalid, or too long for this adapter."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def default_model_path() -> Path:
    """Keep the separately obtained model outside the project and source control."""
    data_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(data_dir).expanduser() if data_dir else Path.home() / ".local" / "share"
    return root / "NasJezik" / "voices" / "sr_Marko_medium.onnx"


def _fingerprint(path: Path) -> tuple:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=8)
def _verified_hash(path: Path, fingerprint: tuple) -> str:
    # Fingerprints invalidate cached verification when the on-disk file changes.
    return _sha256(path)


def _configuration() -> tuple[Path | None, Path | None, str]:
    model_setting = os.environ.get("SC_PIPER_MODEL", "").strip()
    model = (Path(model_setting).expanduser() if model_setting else default_model_path()).resolve()
    config_setting = os.environ.get("SC_PIPER_CONFIG", "").strip()
    config = Path(config_setting).expanduser().resolve() if config_setting else Path(str(model) + ".json")
    if not model.is_file() or not config.is_file():
        return None, None, "The Serbian model or its configuration is missing. Run tools/setup_sc_voice.py or set SC_PIPER_MODEL."
    if importlib.util.find_spec("piper") is None:
        return None, None, "The optional piper-tts package is not installed."
    try:
        if (_verified_hash(model, _fingerprint(model)) != _MODEL_SHA256 or
                _verified_hash(config, _fingerprint(config)) != _CONFIG_SHA256):
            return None, None, "The model or configuration does not match the reviewed Serbian Marko release."
    except OSError:
        return None, None, "The configured Serbian model or configuration cannot be read."
    return model, config, ""


def status() -> dict:
    """Describe configuration; available means the checked files and package exist.

    This does not claim that synthesis, pronunciation, or model rights were
    verified on the current device. No model is loaded by this check.
    """
    _, _, reason = _configuration()
    return {
        "available": not reason,
        "provider": "piper",
        "voice": "Marko",
        "language": "sr",
        "label": "Serbian - Marko (Piper)",
        "reason": reason,
    }


def synthesize(text: str) -> bytes:
    """Return an in-memory WAV for Serbian text, or raise a typed error.

    The caller must identify the voice as Serbian even when the learner has
    selected another standard. Calls are serialized for the shared model.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > _MAX_TEXT_LENGTH or "\x00" in text:
        raise VoiceInputError("Enter 1 to 300 characters of text.")
    global _cached_voice, _cached_paths
    with _lock:
        model, config, reason = _configuration()
        if reason:
            raise VoiceUnavailable(reason)
        # Reload if either reviewed file was replaced after the voice was loaded.
        try:
            paths = (model, config, _fingerprint(model), _fingerprint(config))
        except OSError as exc:
            raise VoiceUnavailable("The configured Serbian model or configuration cannot be read.") from exc
        try:
            if _cached_voice is None or _cached_paths != paths:
                from piper.voice import PiperVoice

                _cached_voice = PiperVoice.load(model, config_path=config)
                _cached_paths = paths
            output = io.BytesIO()
            with wave.open(output, "wb") as wav:
                _cached_voice.synthesize_wav(text.strip(), wav)
            audio = output.getvalue()
            if len(audio) <= 44:
                raise ValueError("empty audio")
            return audio
        except Exception as exc:
            _cached_voice = None
            _cached_paths = None
            raise VoiceUnavailable("The Serbian Piper voice could not synthesize this text.") from exc


def start_warmup() -> threading.Thread:
    """Warm the local model in the background without delaying the web server."""
    def warm():
        try:
            synthesize("Dobar dan.")
        except (VoiceUnavailable, VoiceInputError):
            pass  # The normal voice-status and fallback paths report failures.
    worker = threading.Thread(target=warm, name="serbian-piper-warmup", daemon=True)
    worker.start()
    return worker
