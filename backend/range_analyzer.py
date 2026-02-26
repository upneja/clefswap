"""
Range analyzer: identifies measures where notes fall outside an instrument's
playable range, and applies octave shifts to fix them.

All comparisons use concert (sounding) pitch.
"""
import copy
from dataclasses import dataclass
from typing import Literal

from music21 import note as m21note, pitch as m21pitch


@dataclass
class FlaggedMeasure:
    measure_number: int
    issue: Literal['too_high', 'too_low']
    suggestion: Literal['shift_down', 'shift_up']
    worst_pitch: str  # e.g. 'G6'


def analyze_range(score, instrument: dict) -> list[FlaggedMeasure]:
    """
    Scan every measure in every part of score.
    Return list of FlaggedMeasure for measures where any note exceeds
    the instrument's range_low or range_high.

    Args:
        score: music21 Score object (after clef conversion)
        instrument: dict from instruments.INSTRUMENTS (shallow copy)

    Returns:
        List of FlaggedMeasure, in measure order, deduplicated.
    """
    low = m21pitch.Pitch(instrument['range_low'])
    high = m21pitch.Pitch(instrument['range_high'])

    flagged_map: dict[int, FlaggedMeasure] = {}

    for part in score.parts:
        for measure in part.getElementsByClass('Measure'):
            num = measure.number
            if num in flagged_map:
                continue  # already flagged from another part

            notes = [n for n in measure.flatten().notes if isinstance(n, m21note.Note)]
            if not notes:
                continue

            too_high = [n for n in notes if n.pitch > high]
            too_low = [n for n in notes if n.pitch < low]

            if too_high:
                worst = max(too_high, key=lambda n: n.pitch.midi)
                flagged_map[num] = FlaggedMeasure(
                    measure_number=num,
                    issue='too_high',
                    suggestion='shift_down',
                    worst_pitch=worst.pitch.nameWithOctave,
                )
            elif too_low:
                worst = min(too_low, key=lambda n: n.pitch.midi)
                flagged_map[num] = FlaggedMeasure(
                    measure_number=num,
                    issue='too_low',
                    suggestion='shift_up',
                    worst_pitch=worst.pitch.nameWithOctave,
                )

    return sorted(flagged_map.values(), key=lambda f: f.measure_number)


def apply_octave_shifts(score, shifts: dict[int, str]):
    """
    Apply octave shifts to specific measures.

    Args:
        score: music21 Score object
        shifts: dict of {measure_number: 'shift_up'|'shift_down'}

    Returns:
        New Score object with shifts applied (original not modified).
    """
    result = copy.deepcopy(score)

    for part in result.parts:
        for measure in part.getElementsByClass('Measure'):
            direction = shifts.get(measure.number)
            if not direction:
                continue
            semitones = -12 if direction == 'shift_down' else 12
            for n in measure.flatten().notes:
                if isinstance(n, m21note.Note):
                    n.pitch.midi += semitones
                elif hasattr(n, 'pitches'):  # Chord
                    for p in n.pitches:
                        p.midi += semitones

    return result
