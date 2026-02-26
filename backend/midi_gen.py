"""
MIDI generation from music21 Score objects.
Exports full scores or individual measures as MIDI bytes.
"""
import copy
import gc
import os
import tempfile

from music21 import instrument as m21inst


def score_to_midi(score, midi_program: int = 40) -> bytes:
    """
    Convert a music21 Score to MIDI bytes, setting all parts to midi_program.

    Args:
        score: music21 Score object.
        midi_program: General MIDI program number (0-127).

    Returns:
        Raw MIDI bytes (starts with b'MThd').
    """
    s = copy.deepcopy(score)

    # Set instrument on every part
    for part in s.parts:
        existing = list(part.getElementsByClass('Instrument'))
        for inst in existing:
            inst.activeSite.remove(inst)
        new_inst = m21inst.instrumentFromMidiProgram(midi_program)
        part.insert(0, new_inst)

    tmp = tempfile.NamedTemporaryFile(suffix='.mid', delete=False, prefix='clefswap_midi_')
    tmp.close()
    try:
        s.write('midi', fp=tmp.name)
        with open(tmp.name, 'rb') as f:
            return f.read()
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        del s
        gc.collect()


def measure_to_midi(score, measure_number: int, midi_program: int = 40) -> bytes:
    """
    Extract a single measure from a Score and return it as MIDI bytes.

    Args:
        score: music21 Score object.
        measure_number: 1-based measure number.
        midi_program: General MIDI program number.

    Returns:
        Raw MIDI bytes for that measure.

    Raises:
        ValueError: if measure_number not found in score.
    """
    from music21 import stream as m21stream

    # Build a mini-score with just the target measure
    mini = m21stream.Score()
    found = False

    for part in score.parts:
        measures = [m for m in part.getElementsByClass('Measure')
                    if m.number == measure_number]
        if not measures:
            continue
        found = True
        mini_part = m21stream.Part()
        for m in measures:
            mini_part.append(copy.deepcopy(m))
        mini.insert(0, mini_part)

    if not found:
        raise ValueError(f"Measure {measure_number} not found in score.")

    return score_to_midi(mini, midi_program=midi_program)
