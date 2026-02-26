"""
Instrument database: name, clef, MIDI program, playable range.

All range values (range_low, range_high) represent concert (sounding) pitch
as pitch strings that music21 can parse (e.g. 'G3', 'E7').
MIDI program numbers follow General MIDI 0-indexed specification.
"""

INSTRUMENTS = {
    'violin': {
        'name': 'Violin',
        'clef': 'treble',
        'midi_program': 40,
        'range_low': 'G3',
        'range_high': 'E7',
    },
    'viola': {
        'name': 'Viola',
        'clef': 'alto',
        'midi_program': 41,
        'range_low': 'C3',
        'range_high': 'E6',
    },
    'cello': {
        'name': 'Cello',
        'clef': 'bass',
        'midi_program': 42,
        'range_low': 'C2',
        'range_high': 'A5',
    },
    'double_bass': {
        'name': 'Double Bass',
        'clef': 'bass_8vb',
        'midi_program': 43,
        'range_low': 'E1',
        'range_high': 'G4',
    },
    'flute': {
        'name': 'Flute',
        'clef': 'treble',
        'midi_program': 73,
        'range_low': 'C4',
        'range_high': 'D7',
    },
    'clarinet_bb': {
        'name': 'Clarinet (Bb)',
        'clef': 'treble',
        'midi_program': 71,
        'range_low': 'D3',
        'range_high': 'B-6',
    },
    'trumpet_bb': {
        'name': 'Trumpet (Bb)',
        'clef': 'treble',
        'midi_program': 56,
        'range_low': 'E3',
        'range_high': 'C6',
    },
    'trombone': {
        'name': 'Trombone',
        'clef': 'bass',
        'midi_program': 57,
        'range_low': 'E2',
        'range_high': 'F5',
    },
    'piano_rh': {
        'name': 'Piano (Right Hand)',
        'clef': 'treble',
        'midi_program': 0,
        'range_low': 'A0',
        'range_high': 'C8',
    },
    'piano_lh': {
        'name': 'Piano (Left Hand)',
        'clef': 'bass',
        'midi_program': 0,
        'range_low': 'A0',
        'range_high': 'C8',
    },
}


class InstrumentNotFound(Exception):
    pass


def get_instrument(key: str) -> dict:
    if key not in INSTRUMENTS:
        raise InstrumentNotFound(f"Unknown instrument: '{key}'. Valid: {list(INSTRUMENTS.keys())}")
    return dict(INSTRUMENTS[key])  # shallow copy prevents external mutation
