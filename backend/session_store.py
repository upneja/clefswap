"""
In-memory session store for conversion state.
Each session holds: musicxml path, flagged measures, instrument info, temp dir.
Sessions expire after 30 minutes.
"""
import os
import shutil
import tempfile
import threading
import time
import uuid

_sessions: dict = {}
_lock = threading.Lock()
SESSION_TTL = 30 * 60  # 30 minutes


def create_session() -> tuple[str, str]:
    """
    Create a new session with a temp directory.
    Returns: (session_id, session_dir)
    """
    session_id = str(uuid.uuid4())
    session_dir = tempfile.mkdtemp(prefix=f'clefswap_session_{session_id[:8]}_')
    with _lock:
        _sessions[session_id] = {
            'dir': session_dir,
            'created': time.time(),
            'data': {},
        }
    return session_id, session_dir


def get_session(session_id: str) -> dict | None:
    with _lock:
        return _sessions.get(session_id)


def set_session_data(session_id: str, data: dict):
    with _lock:
        if session_id in _sessions:
            _sessions[session_id]['data'].update(data)


def delete_session(session_id: str):
    with _lock:
        session = _sessions.pop(session_id, None)
    if session:
        shutil.rmtree(session['dir'], ignore_errors=True)


def cleanup_expired():
    """Delete sessions older than SESSION_TTL."""
    now = time.time()
    expired = []
    with _lock:
        for sid, s in list(_sessions.items()):
            if now - s['created'] > SESSION_TTL:
                expired.append(sid)
    for sid in expired:
        delete_session(sid)
