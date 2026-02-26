"""
Core clef conversion tests. Validates: pitches preserved, new clef present,
non-pitch elements preserved.
"""
import os
import pytest
from music21 import converter, clef as m21clef, note as m21note

from backend.converter import convert_clef

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def get_all_pitches(score):
    return [
        (n.pitch.name, n.pitch.octave)
        for n in score.flatten().notes
        if isinstance(n, m21note.Note)
    ]


def get_clef_classes(score):
    return {type(c).__name__ for c in score.recurse().getElementsByClass('Clef')}


def test_basic_treble_to_alto_pitches_preserved():
    input_path = fixture("basic_treble_scale.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    out = convert_clef(input_path, 'treble', 'alto')
    try:
        assert get_all_pitches(converter.parse(out)) == original
    finally:
        if os.path.exists(out): os.unlink(out)


def test_basic_treble_to_alto_clef_present():
    out = convert_clef(fixture("basic_treble_scale.musicxml"), 'treble', 'alto')
    try:
        clefs = get_clef_classes(converter.parse(out))
        assert 'AltoClef' in clefs
        assert 'TrebleClef' not in clefs
    finally:
        if os.path.exists(out): os.unlink(out)


def test_treble_to_bass_conversion():
    input_path = fixture("basic_treble_scale.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    out = convert_clef(input_path, 'treble', 'bass')
    try:
        assert get_all_pitches(converter.parse(out)) == original
        assert 'BassClef' in get_clef_classes(converter.parse(out))
    finally:
        if os.path.exists(out): os.unlink(out)


def test_treble_to_tenor_conversion():
    input_path = fixture("basic_treble_scale.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    out = convert_clef(input_path, 'treble', 'tenor')
    try:
        assert get_all_pitches(converter.parse(out)) == original
    finally:
        if os.path.exists(out): os.unlink(out)


def test_sharps_key_pitches_preserved():
    input_path = fixture("sharps_key.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    out = convert_clef(input_path, 'treble', 'alto')
    try:
        assert get_all_pitches(converter.parse(out)) == original
    finally:
        if os.path.exists(out): os.unlink(out)


def test_flats_key_pitches_preserved():
    input_path = fixture("flats_key.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    out = convert_clef(input_path, 'treble', 'alto')
    try:
        assert get_all_pitches(converter.parse(out)) == original
    finally:
        if os.path.exists(out): os.unlink(out)


def test_multi_clef_score_all_clefs_replaced():
    input_path = fixture("multi_clef_score.musicxml")
    original = get_all_pitches(converter.parse(input_path))
    # None source = replace ALL clefs
    out = convert_clef(input_path, None, 'alto')
    try:
        result = converter.parse(out)
        clefs = get_clef_classes(result)
        assert 'AltoClef' in clefs
        assert 'TrebleClef' not in clefs
        assert 'TenorClef' not in clefs
        assert get_all_pitches(result) == original
    finally:
        if os.path.exists(out): os.unlink(out)


def test_articulations_preserved():
    out = convert_clef(fixture("articulations_test.musicxml"), 'treble', 'alto')
    try:
        result = converter.parse(out)
        arts = []
        exps = []
        for n in result.flatten().notes:
            arts.extend(type(a).__name__ for a in n.articulations)
            exps.extend(type(e).__name__ for e in n.expressions)
        assert 'Staccato' in arts
        assert 'Accent' in arts
        assert 'Tenuto' in arts
        assert 'Fermata' in exps
        assert 'Trill' in exps
    finally:
        if os.path.exists(out): os.unlink(out)


def test_dynamics_preserved():
    out = convert_clef(fixture("dynamics_test.musicxml"), 'treble', 'alto')
    try:
        result = converter.parse(out)
        dyn_values = [d.value for d in result.flatten().getElementsByClass('Dynamic')]
        assert 'pp' in dyn_values
        assert 'mf' in dyn_values
        assert 'ff' in dyn_values
    finally:
        if os.path.exists(out): os.unlink(out)


def test_ties_survive():
    out = convert_clef(fixture("slurs_ties_test.musicxml"), 'treble', 'alto')
    try:
        result = converter.parse(out)
        tied = [n for n in result.flatten().notes if hasattr(n, 'tie') and n.tie is not None]
        assert len(tied) >= 2, "Tied notes were dropped"
        slurs = list(result.recurse().getElementsByClass('Slur'))
        assert len(slurs) >= 1, "Slurs were dropped during conversion"
    finally:
        if os.path.exists(out): os.unlink(out)


def test_metadata_preserved():
    out = convert_clef(fixture("metadata_test.musicxml"), 'treble', 'alto')
    try:
        result = converter.parse(out)
        # In music21 9.3, MusicXML work-title is parsed into movementName, not title.
        # bestTitle returns movementName as fallback when title is None.
        assert result.metadata.bestTitle == "Sonata in G Major"
        assert result.metadata.composer == "Test Composer"
    finally:
        if os.path.exists(out): os.unlink(out)


def test_pickup_measure_clef_at_start():
    out = convert_clef(fixture("pickup_measure.musicxml"), 'treble', 'alto')
    try:
        result = converter.parse(out)
        first_clef = list(result.recurse().getElementsByClass('Clef'))[0]
        assert isinstance(first_clef, m21clef.AltoClef)
    finally:
        if os.path.exists(out): os.unlink(out)


def test_returns_temp_file_path():
    out = convert_clef(fixture("basic_treble_scale.musicxml"), 'treble', 'alto')
    assert os.path.exists(out)
    assert out.endswith('.musicxml')
    os.unlink(out)


def test_invalid_file_raises():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.musicxml', mode='w', delete=False) as f:
        f.write("this is not musicxml")
        tmp = f.name
    try:
        with pytest.raises(Exception):
            convert_clef(tmp, 'treble', 'alto')
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
