"""API integration tests using FastAPI TestClient."""
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


# --- /health ---

def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["renderer"] in ("lilypond", "musescore", "none")


# --- /clefs ---

def test_clefs_returns_all():
    resp = client.get("/clefs")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("treble", "alto", "tenor", "bass"):
        assert key in data


# --- /convert ---

def test_convert_treble_to_alto_musicxml():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    assert 'attachment' in resp.headers.get('content-disposition', '')
    assert len(resp.content) > 100


def test_convert_returns_pdf():
    from backend.renderer import detect_renderer
    if detect_renderer() == 'none':
        pytest.skip("No PDF renderer available")

    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "pdf"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'application/pdf'
    assert len(resp.content) > 1000


def test_convert_same_clef_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "treble", "format": "musicxml"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400
    assert "same" in resp.json()["error"].lower()


def test_convert_unknown_clef_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert",
        data={"source_clef": "oboe", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400


def test_convert_pdf_extension_422():
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "pdf"},
        files={"file": ("score.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")},
    )
    assert resp.status_code == 422
    assert "PDF" in resp.json()["error"]


def test_convert_midi_extension_422():
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("score.mid", io.BytesIO(b"MThd"), "audio/midi")},
    )
    assert resp.status_code == 422
    assert "MIDI" in resp.json()["error"]


def test_convert_garbage_xml_422():
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("test.musicxml", io.BytesIO(b"this is not xml"), "text/xml")},
    )
    assert resp.status_code == 422


def test_convert_no_renderer_503():
    from unittest.mock import patch
    content = fixture_bytes("basic_treble_scale.musicxml")
    with patch('backend.renderer.detect_renderer', return_value='none'):
        resp = client.post(
            "/convert",
            data={"source_clef": "treble", "target_clef": "alto", "format": "pdf"},
            files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
        )
    assert resp.status_code == 503
    assert "renderer" in resp.json()["error"].lower() or "lilypond" in resp.json()["error"].lower()


def test_convert_output_filename_has_target_clef():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("my_piece.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    disposition = resp.headers.get('content-disposition', '')
    assert 'alto' in disposition.lower() or 'my_piece' in disposition.lower()
