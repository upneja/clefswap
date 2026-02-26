import os
import pytest
from music21 import stream, note, clef, key, meter
from backend.midi_gen import score_to_midi, measure_to_midi


def make_score(pitches):
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    for i, pitch in enumerate(pitches):
        m = stream.Measure(number=i + 1)
        m.append(note.Note(pitch, quarterLength=4))
        p.append(m)
    s.insert(0, p)
    return s


def test_score_to_midi_returns_bytes():
    score = make_score(['C4', 'D4', 'E4'])
    midi_bytes = score_to_midi(score, midi_program=41)
    assert isinstance(midi_bytes, bytes)
    assert len(midi_bytes) > 10
    assert midi_bytes[:4] == b'MThd'  # MIDI header magic


def test_score_to_midi_default_program():
    score = make_score(['C4'])
    midi_bytes = score_to_midi(score)
    assert midi_bytes[:4] == b'MThd'


def test_measure_to_midi_returns_bytes():
    score = make_score(['C4', 'D4', 'E4'])
    midi_bytes = measure_to_midi(score, measure_number=2, midi_program=41)
    assert isinstance(midi_bytes, bytes)
    assert midi_bytes[:4] == b'MThd'


def test_measure_to_midi_invalid_measure_raises():
    score = make_score(['C4'])
    with pytest.raises(ValueError, match="Measure"):
        measure_to_midi(score, measure_number=99, midi_program=41)
