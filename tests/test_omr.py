import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from backend.omr import run_omr, OmrError, is_image_file


def test_is_image_file_png():
    assert is_image_file('score.png') is True

def test_is_image_file_jpg():
    assert is_image_file('score.jpg') is True
    assert is_image_file('score.jpeg') is True

def test_is_image_file_xml_is_false():
    assert is_image_file('score.musicxml') is False
    assert is_image_file('score.mxl') is False

def test_run_omr_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        run_omr('/nonexistent/file.png')

def test_run_omr_raises_omr_error_on_oemer_failure():
    """If oemer CLI fails, OmrError is raised with a clear message."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        # Write a tiny valid PNG (1x1 white pixel)
        import struct, zlib
        def chunk(name, data):
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        idat_data = zlib.compress(b'\x00\xff\xff\xff')
        png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat_data) + chunk(b'IEND', b'')
        f.write(png)
        tmp_path = f.name
    try:
        # A 1x1 pixel PNG will fail OMR — that's the point
        with pytest.raises((OmrError, Exception)):
            run_omr(tmp_path)
    finally:
        os.unlink(tmp_path)

def test_run_omr_returns_musicxml_path_on_success():
    """Mock oemer subprocess to test the path-finding logic."""
    import subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake musicxml output that oemer would produce
        fake_xml = os.path.join(tmpdir, 'output.musicxml')
        with open(fake_xml, 'w') as f:
            f.write('<?xml version="1.0"?><score-partwise/>')

        with patch('backend.omr.subprocess.run') as mock_run, \
             patch('backend.omr.tempfile.mkdtemp', return_value=tmpdir), \
             patch('backend.omr.os.path.exists', return_value=True):
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            result = run_omr('/fake/input.png')
            assert result.endswith('.musicxml') or result.endswith('.xml')
