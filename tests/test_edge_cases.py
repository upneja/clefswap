"""
Edge case tests for ClefSwap robustness.
"""
import io
import os
import tempfile
import pytest
from music21 import converter as m21conv, stream, note, clef, key, meter, metadata
from fastapi.testclient import TestClient
from backend.main import app
from backend.converter import convert_clef

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), 'rb') as f:
        return f.read()


def test_mxl_compressed_format():
    """.mxl files (ZIP archives) are parsed natively by music21."""
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['C5', 'D5', 'E5', 'F5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)

    with tempfile.NamedTemporaryFile(suffix='.mxl', delete=False) as f:
        mxl_path = f.name
    result_path = s.write('mxl', fp=mxl_path)

    # music21 may return a different path than what we passed
    if result_path and os.path.exists(str(result_path)):
        mxl_path = str(result_path)
    elif not os.path.exists(mxl_path):
        alt = mxl_path + '.mxl'
        if os.path.exists(alt):
            mxl_path = alt

    try:
        out = convert_clef(mxl_path, 'treble', 'alto')
        assert os.path.exists(out)
        result = m21conv.parse(out)
        clef_classes = {type(c).__name__ for c in result.recurse().getElementsByClass('Clef')}
        assert 'AltoClef' in clef_classes
        os.unlink(out)
    finally:
        if os.path.exists(mxl_path):
            os.unlink(mxl_path)


def test_multi_part_score_all_parts_converted():
    """All parts in a multi-part score get the new clef."""
    s = stream.Score()
    for i in range(3):
        p = stream.Part()
        p.id = f"Part{i}"
        p.append(clef.TrebleClef())
        p.append(key.Key('C'))
        p.append(meter.TimeSignature('4/4'))
        for pitch in ['C5', 'D5', 'E5', 'F5']:
            p.append(note.Note(pitch, quarterLength=1))
        s.insert(0, p)

    with tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False) as f:
        path = f.name
    s.write('musicxml', fp=path)

    try:
        out = convert_clef(path, 'treble', 'alto')
        result = m21conv.parse(out)
        for part in result.parts:
            clef_classes = {type(c).__name__ for c in part.recurse().getElementsByClass('Clef')}
            assert 'AltoClef' in clef_classes, f"AltoClef missing in {part.id}"
            assert 'TrebleClef' not in clef_classes, f"TrebleClef remains in {part.id}"
        os.unlink(out)
    finally:
        os.unlink(path)


def test_empty_measure_rest_survives():
    """Full-measure rests survive clef conversion."""
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    from music21 import note as m21note
    p.append(m21note.Rest(quarterLength=4))
    for pitch in ['C5', 'D5', 'E5', 'F5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)

    with tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False) as f:
        path = f.name
    s.write('musicxml', fp=path)

    try:
        out = convert_clef(path, 'treble', 'alto')
        result = m21conv.parse(out)
        rests = list(result.flatten().getElementsByClass('Rest'))
        assert len(rests) >= 1, "Rest not preserved"
        os.unlink(out)
    finally:
        os.unlink(path)


def test_no_clef_in_original_inserts_target():
    """Score with no clef element gets target clef inserted."""
    s = stream.Score()
    p = stream.Part()
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['C5', 'D5', 'E5', 'F5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)

    with tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False) as f:
        path = f.name
    s.write('musicxml', fp=path)

    try:
        out = convert_clef(path, 'treble', 'alto')
        result = m21conv.parse(out)
        clef_classes = {type(c).__name__ for c in result.recurse().getElementsByClass('Clef')}
        assert 'AltoClef' in clef_classes
        os.unlink(out)
    finally:
        os.unlink(path)


def test_api_file_size_limit():
    """Files > 10MB are rejected with 422 and size error."""
    big = b'x' * (10 * 1024 * 1024 + 1)
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("big.musicxml", io.BytesIO(big), "text/xml")},
    )
    assert resp.status_code == 422
    body = resp.json()["error"].lower()
    assert "10mb" in body or "large" in body


def test_api_pdf_extension_rejected():
    """PDF files get a clear error mentioning 'PDF'."""
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "pdf"},
        files={"file": ("score.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 422
    assert "PDF" in resp.json()["error"]


def test_api_midi_extension_rejected():
    """MIDI files get a clear error mentioning 'MIDI'."""
    resp = client.post(
        "/convert",
        data={"source_clef": "treble", "target_clef": "alto", "format": "musicxml"},
        files={"file": ("score.mid", io.BytesIO(b"MThd\x00\x00"), "audio/midi")},
    )
    assert resp.status_code == 422
    assert "MIDI" in resp.json()["error"]
