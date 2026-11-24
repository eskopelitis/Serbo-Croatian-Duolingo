"""Local-only setup for optional AI and speech dependencies."""
import ctypes
from ctypes import wintypes
import importlib.util
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit

from flask import jsonify, request
import sc_piper
import stt

_job_lock = threading.Lock()
_job = 'idle'


def _config_dir():
    root = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.environ.get('XDG_CONFIG_HOME')
    directory = Path(root) / 'NasJezik' if root else Path.home() / '.config' / 'NasJezik'
    if directory.resolve().is_relative_to(Path(__file__).resolve().parent):
        raise OSError('The credential directory must be outside the project')
    return directory


def _crypt(data, decrypt=False):
    """On Windows bind the saved credential to the current Windows account."""
    if os.name != 'nt':
        return data
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]
    source = ctypes.create_string_buffer(data)
    inp = Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    out = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out))
    if not ok:
        raise OSError('Credential protection failed')
    try:
        return ctypes.string_at(out.data, out.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.data, ctypes.c_void_p))


def load_saved_key():
    try:
        path = _config_dir() / 'ai-credential.bin'
        value = _crypt(path.read_bytes(), decrypt=True).decode('utf-8')
        if value:
            os.environ['DEEPSEEK_API_KEY'] = value
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        # Keep any existing environment configuration if the saved credential is unavailable.
        pass


def _save_key(value):
    directory = _config_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        os.chmod(directory, 0o700)
    payload = _crypt(value.encode('utf-8'))
    fd, name = tempfile.mkstemp(prefix='.ai-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as f:
            if os.name != 'nt':
                os.fchmod(f.fileno(), 0o600)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, directory / 'ai-credential.bin')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _local_request():
    try:
        remote = ipaddress.ip_address(request.remote_addr)
        host = urlsplit(request.host_url)
        origin = urlsplit(request.headers.get('Origin', ''))
        return (remote.is_loopback and host.hostname in ('localhost', '127.0.0.1', '::1')
                and origin.scheme in ('http', 'https') and origin.netloc == host.netloc
                and origin.scheme == host.scheme and not origin.path and not origin.query
                and request.headers.get('X-Local-Setup') == '1')
    except (ValueError, TypeError):
        return False


# ponytail: byte sizes of the pinned Marko model + config; update together with the hashes in sc_piper.
_VOICE_BYTES = 63516051 + 4855


def _install_progress():
    """Percent downloaded, from the installer's temp files and finished files on disk."""
    total = 0
    for path in sc_piper.default_model_path().parent.glob('*'):
        if path.name.startswith(('.marko-', 'sr_Marko_medium.onnx')):
            try:
                total += path.stat().st_size
            except OSError:  # a temp file was renamed away mid-scan
                pass
    return min(99, 100 * total // _VOICE_BYTES)


def _install_worker():
    global _job
    script = Path(__file__).resolve().parent / 'tools' / 'setup_sc_voice.py'
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run([sys.executable, str(script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=flags, timeout=1800)
        status = 'done' if result.returncode == 0 and sc_piper.status()['available'] else 'failed'
    except (OSError, subprocess.SubprocessError):
        status = 'failed'
    with _job_lock:
        _job = status


def register(app):
    @app.before_request
    def setup_boundary():
        if request.path.startswith('/api/setup/') and not _local_request():
            return jsonify(error='Open the app on the server computer at localhost to change setup.'), 403

    @app.after_request
    def setup_no_cache(response):
        if request.path.startswith('/api/setup/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/setup/status')
    def setup_status():
        import llm
        with _job_lock:
            job = _job
        return jsonify(ai_configured=bool(os.environ.get('DEEPSEEK_API_KEY', '').strip()),
                       local_ai_available=llm._local_model_id() == llm.BACKUP_MODEL,
                       voice_available=sc_piper.status()['available'],
                       recognition_available=stt.available(), install=job,
                       progress=_install_progress() if job == 'running' else None,
                       voice_install_supported=(not os.environ.get('SC_PIPER_MODEL') and
                           not os.environ.get('SC_PIPER_CONFIG') and importlib.util.find_spec('piper') is not None))

    @app.post('/api/setup/key')
    def setup_key():
        import llm
        if not request.is_json:
            return jsonify(error='Enter a valid API key.'), 400
        body = request.get_json(silent=True)
        value = body.get('key') if isinstance(body, dict) else None
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', value):
            return jsonify(error='Enter a valid API key without spaces.'), 400
        try:
            _save_key(value)
        except OSError:
            return jsonify(error='Could not save the key on this computer. Try again.'), 503
        with llm._client_lock:
            os.environ['DEEPSEEK_API_KEY'] = value
            llm._client = None
            llm.MODEL = None
        return jsonify(configured=True)

    @app.post('/api/setup/voice')
    def setup_voice():
        global _job
        if (os.environ.get('SC_PIPER_MODEL') or os.environ.get('SC_PIPER_CONFIG') or
                importlib.util.find_spec('piper') is None):
            return jsonify(error='Use the voice setup instructions for your custom configuration.'), 400
        with _job_lock:
            if _job != 'running':
                _job = 'running'
                threading.Thread(target=_install_worker, daemon=True).start()
        return jsonify(install='running'), 202
