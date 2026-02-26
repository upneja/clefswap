import pytest
from music21 import stream, note, clef, key, meter
from backend.range_analyzer import analyze_range, apply_octave_shifts, FlaggedMeasure


def make_score(pitches, clef_obj=None):
    """Helper: build a simple score with one part."""
    from music21 import clef as m21clef
    s = stream.Score()
    p = stream.Part()
    p.append(clef_obj or m21clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    for i, pitch in enumerate(pitches):
        m = stream.Measure(number=i + 1)
        m.append(note.Note(pitch, quarterLength=4))
        p.append(m)
    s.insert(0, p)
    return s


def test_no_flags_when_all_in_range():
    # Viola range: C3–E6. Middle notes should be fine.
    from backend.instruments import get_instrument
    viola = get_instrument('viola')
    score = make_score(['C4', 'G4', 'D5'])
    flagged = analyze_range(score, viola)
    assert flagged == []


def test_flags_note_above_range():
    from backend.instruments import get_instrument
    viola = get_instrument('viola')
    # G6 is above E6 (viola max)
    score = make_score(['C4', 'G6', 'D5'])
    flagged = analyze_range(score, viola)
    assert len(flagged) == 1
    assert flagged[0].measure_number == 2
    assert flagged[0].suggestion == 'shift_down'


def test_flags_note_below_range():
    from backend.instruments import get_instrument
    viola = get_instrument('viola')
    # A1 is below C3 (viola min)
    score = make_score(['C4', 'A1', 'D5'])
    flagged = analyze_range(score, viola)
    assert len(flagged) == 1
    assert flagged[0].measure_number == 2
    assert flagged[0].suggestion == 'shift_up'


def test_flags_multiple_measures():
    from backend.instruments import get_instrument
    viola = get_instrument('viola')
    score = make_score(['G6', 'C4', 'A1'])  # m1 too high, m3 too low
    flagged = analyze_range(score, viola)
    assert len(flagged) == 2
    numbers = [f.measure_number for f in flagged]
    assert 1 in numbers
    assert 3 in numbers


def test_apply_shift_down_moves_notes_one_octave():
    score = make_score(['G6'])
    original_pitch = list(score.flatten().notes)[0].pitch.midi
    shifts = {1: 'shift_down'}
    shifted = apply_octave_shifts(score, shifts)
    new_pitch = list(shifted.flatten().notes)[0].pitch.midi
    assert new_pitch == original_pitch - 12


def test_apply_shift_up_moves_notes_one_octave():
    score = make_score(['A1'])
    original_pitch = list(score.flatten().notes)[0].pitch.midi
    shifts = {1: 'shift_up'}
    shifted = apply_octave_shifts(score, shifts)
    new_pitch = list(shifted.flatten().notes)[0].pitch.midi
    assert new_pitch == original_pitch + 12


def test_apply_shifts_does_not_modify_other_measures():
    score = make_score(['G6', 'C4', 'D5'])
    original_m2 = list(score.parts[0].getElementsByClass('Measure'))[1]
    original_m2_pitch = list(original_m2.notes)[0].pitch.midi
    shifts = {1: 'shift_down'}  # only shift measure 1
    shifted = apply_octave_shifts(score, shifts)
    shifted_m2 = list(shifted.parts[0].getElementsByClass('Measure'))[1]
    shifted_m2_pitch = list(shifted_m2.notes)[0].pitch.midi
    assert shifted_m2_pitch == original_m2_pitch


def test_flagged_measure_has_correct_fields():
    from backend.instruments import get_instrument
    viola = get_instrument('viola')
    score = make_score(['G6'])
    flagged = analyze_range(score, viola)
    f = flagged[0]
    assert hasattr(f, 'measure_number')
    assert hasattr(f, 'suggestion')
    assert hasattr(f, 'issue')
    assert hasattr(f, 'worst_pitch')
