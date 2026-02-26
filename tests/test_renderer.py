import os
import pytest
from backend.renderer import detect_renderer, render_to_pdf, RendererUnavailable

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def test_detect_renderer_returns_valid_string():
    result = detect_renderer()
    assert result in ('lilypond', 'musescore', 'none')


def test_detect_renderer_finds_lilypond():
    """LilyPond is installed at /opt/homebrew/bin/lilypond."""
    result = detect_renderer()
    assert result == 'lilypond'


def test_render_to_pdf_produces_file():
    renderer = detect_renderer()
    if renderer == 'none':
        pytest.skip("No PDF renderer available")

    input_path = os.path.join(FIXTURES, "basic_treble_scale.musicxml")
    assert os.path.exists(input_path), f"Fixture missing: {input_path}"

    pdf_path = render_to_pdf(input_path, "test_basic_scale")
    try:
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith('.pdf')
        assert os.path.getsize(pdf_path) > 1000, "PDF too small, likely empty"
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def test_render_returns_pdf_extension():
    if detect_renderer() == 'none':
        pytest.skip("No PDF renderer available")
    input_path = os.path.join(FIXTURES, "basic_treble_scale.musicxml")
    pdf_path = render_to_pdf(input_path, "ext_test")
    assert pdf_path.endswith('.pdf')
    if os.path.exists(pdf_path):
        os.unlink(pdf_path)


def test_renderer_unavailable_raises():
    from unittest.mock import patch
    with patch('backend.renderer.detect_renderer', return_value='none'):
        with pytest.raises(RendererUnavailable):
            render_to_pdf("/fake/path.musicxml", "test")
