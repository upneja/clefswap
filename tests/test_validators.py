import pytest
from backend.validators import validate_file, validate_clef_pair, ValidationError

MAX_SIZE = 10 * 1024 * 1024  # 10MB

class FakeFile:
    def __init__(self, filename, size):
        self.filename = filename
        self.size = size

def test_valid_mxl_file():
    validate_file(FakeFile("piece.mxl", 1024))

def test_valid_musicxml_file():
    validate_file(FakeFile("piece.musicxml", 500))

def test_valid_xml_file():
    validate_file(FakeFile("piece.xml", 500))

def test_invalid_extension_pdf():
    with pytest.raises(ValidationError, match="PDF"):
        validate_file(FakeFile("piece.pdf", 500))

def test_invalid_extension_midi():
    with pytest.raises(ValidationError, match="MIDI"):
        validate_file(FakeFile("piece.mid", 500))

def test_invalid_extension_generic():
    with pytest.raises(ValidationError, match="MusicXML"):
        validate_file(FakeFile("piece.docx", 500))

def test_file_too_large():
    with pytest.raises(ValidationError, match="10MB"):
        validate_file(FakeFile("piece.mxl", MAX_SIZE + 1))

def test_file_at_limit():
    validate_file(FakeFile("piece.mxl", MAX_SIZE))  # exactly 10MB: should pass

def test_same_clef_raises():
    with pytest.raises(ValidationError, match="same"):
        validate_clef_pair("treble", "treble")

def test_different_clefs_ok():
    validate_clef_pair("treble", "alto")  # must not raise

def test_unknown_source_clef():
    with pytest.raises(ValidationError, match="Unknown"):
        validate_clef_pair("oboe", "alto")

def test_unknown_target_clef():
    with pytest.raises(ValidationError, match="Unknown"):
        validate_clef_pair("treble", "cello")
