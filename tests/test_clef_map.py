import pytest
from backend.clef_map import CLEF_MAP, get_clef_class, CLEF_LABELS

def test_all_clefs_present():
    expected = {'treble', 'alto', 'tenor', 'bass', 'treble_8vb', 'treble_8va', 'bass_8vb'}
    assert expected.issubset(set(CLEF_MAP.keys()))

@pytest.mark.parametrize("clef_name,expected_cls", [
    ("treble",     "TrebleClef"),
    ("alto",       "AltoClef"),
    ("tenor",      "TenorClef"),
    ("bass",       "BassClef"),
    ("treble_8vb", "Treble8vbClef"),
    ("treble_8va", "Treble8vaClef"),
    ("bass_8vb",   "Bass8vbClef"),
])
def test_get_clef_class_all(clef_name, expected_cls):
    from music21 import clef as m21clef
    result = get_clef_class(clef_name)
    assert result.__name__ == expected_cls

def test_get_clef_class_invalid():
    with pytest.raises(ValueError, match="Unknown clef"):
        get_clef_class('oboe')

def test_clef_labels_have_display_names():
    for key in CLEF_MAP:
        assert key in CLEF_LABELS
        assert isinstance(CLEF_LABELS[key], str)
        assert len(CLEF_LABELS[key]) > 0
