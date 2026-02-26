import pytest
from backend.clef_map import CLEF_MAP, get_clef_class, CLEF_LABELS

def test_all_clefs_present():
    expected = {'treble', 'alto', 'tenor', 'bass', 'treble_8vb', 'treble_8va', 'bass_8vb'}
    assert expected.issubset(set(CLEF_MAP.keys()))

def test_get_clef_class_treble():
    from music21 import clef
    cls = get_clef_class('treble')
    assert cls == clef.TrebleClef

def test_get_clef_class_alto():
    from music21 import clef
    cls = get_clef_class('alto')
    assert cls == clef.AltoClef

def test_get_clef_class_bass():
    from music21 import clef
    cls = get_clef_class('bass')
    assert cls == clef.BassClef

def test_get_clef_class_tenor():
    from music21 import clef
    cls = get_clef_class('tenor')
    assert cls == clef.TenorClef

def test_get_clef_class_invalid():
    with pytest.raises(ValueError, match="Unknown clef"):
        get_clef_class('oboe')

def test_clef_labels_have_display_names():
    for key in CLEF_MAP:
        assert key in CLEF_LABELS
        assert isinstance(CLEF_LABELS[key], str)
        assert len(CLEF_LABELS[key]) > 0
