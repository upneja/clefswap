"""Tests for new OMR and instrument-aware conversion endpoints."""
import io
import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), 'rb') as f:
        return f.read()


# --- GET /instruments ---

def test_instruments_endpoint():
    resp = client.get("/instruments")
    assert resp.status_code == 200
    data = resp.json()
    assert 'violin' in data
    assert 'viola' in data
    assert data['violin']['clef'] == 'treble'
    assert data['viola']['clef'] == 'alto'
    assert 'midi_program' in data['violin']


# --- POST /convert-instrument (MusicXML input) ---

def test_convert_instrument_musicxml_no_flags():
    """Convert a simple score that's within viola range — no wizard needed."""
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'session_id' in data
    assert 'flagged_measures' in data
    assert isinstance(data['flagged_measures'], list)
    assert 'full_midi_url' in data


def test_convert_instrument_wrong_instrument_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "theremin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400


def test_convert_instrument_same_instrument_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "violin"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400


# --- GET /session/{id}/midi/full ---

def test_session_midi_full_returns_midi():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    session_id = resp.json()['session_id']

    midi_resp = client.get(f"/session/{session_id}/midi/full")
    assert midi_resp.status_code == 200
    assert midi_resp.content[:4] == b'MThd'


def test_session_not_found_404():
    resp = client.get("/session/nonexistent-id/midi/full")
    assert resp.status_code == 404


# --- POST /finalize ---

def test_finalize_returns_pdf():
    from backend.renderer import detect_renderer
    if detect_renderer() == 'none':
        pytest.skip("No PDF renderer available")

    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']

    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {}, "format": "pdf"},
    )
    assert final.status_code == 200
    assert final.headers['content-type'] == 'application/pdf'


def test_finalize_returns_musicxml():
    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']

    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {}, "format": "musicxml"},
    )
    assert final.status_code == 200
    assert 'attachment' in final.headers.get('content-disposition', '')


def test_finalize_applies_shifts():
    """Finalize with a shift applied — verify it doesn't error."""
    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']

    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {"1": "shift_down"}, "format": "musicxml"},
    )
    assert final.status_code == 200
