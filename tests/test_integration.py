"""
End-to-end integration tests: upload → convert → download → verify pitches preserved.
"""
import io
import os
import pytest
from fastapi.testclient import TestClient
from music21 import converter as m21conv, note as m21note

from backend.main import app

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), 'rb') as f:
        return f.read()


def get_pitches(score):
    return [(n.pitch.name, n.pitch.octave) for n in score.flatten().notes if isinstance(n, m21note.Note)]


def parse_musicxml_bytes(data: bytes):
    """Parse MusicXML bytes with explicit format hint to avoid format misdetection."""
    return m21conv.parseData(data, format='musicxml')


@pytest.mark.parametrize("src,tgt,expected_clef", [
    ("treble", "alto",  "AltoClef"),
    ("treble", "bass",  "BassClef"),
    ("treble", "tenor", "TenorClef"),
])
def test_roundtrip_pitches_preserved(src, tgt, expected_clef):
    """Upload → convert → download → parse: pitches identical, correct clef present."""
    content = fixture_bytes("basic_treble_scale.musicxml")
    original = get_pitches(parse_musicxml_bytes(content))

    resp = client.post(
        "/convert",
        data={"source_clef": src, "target_clef": tgt, "format": "musicxml"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    result = parse_musicxml_bytes(resp.content)
    converted = get_pitches(result)
    assert original == converted, (
        f"Pitches changed {src}→{tgt}!\nOriginal: {original}\nConverted: {converted}"
    )
    clef_classes = {type(c).__name__ for c in result.recurse().getElementsByClass('Clef')}
    assert expected_clef in clef_classes, f"Expected {expected_clef}, found: {clef_classes}"


def test_health_endpoint_live():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_clefs_endpoint_live():
    resp = client.get("/clefs")
    assert resp.status_code == 200
    assert "treble" in resp.json()
    assert "alto" in resp.json()
