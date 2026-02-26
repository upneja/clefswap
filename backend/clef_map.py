from music21 import clef as m21clef

CLEF_MAP = {
    'treble':     m21clef.TrebleClef,
    'alto':       m21clef.AltoClef,
    'tenor':      m21clef.TenorClef,
    'bass':       m21clef.BassClef,
    'treble_8vb': m21clef.Treble8vbClef,
    'treble_8va': m21clef.Treble8vaClef,
    'bass_8vb':   m21clef.Bass8vbClef,
}

CLEF_LABELS = {
    'treble':     'Treble Clef (G)',
    'alto':       'Alto Clef (C3)',
    'tenor':      'Tenor Clef (C4)',
    'bass':       'Bass Clef (F)',
    'treble_8vb': 'Treble 8vb (Guitar/Tenor Voice)',
    'treble_8va': 'Treble 8va (Piccolo)',
    'bass_8vb':   'Bass 8vb (Contrabass)',
}


def get_clef_class(clef_name: str):
    """Return the music21 clef class for the given clef name."""
    if clef_name not in CLEF_MAP:
        raise ValueError(f"Unknown clef: '{clef_name}'. Valid options: {list(CLEF_MAP.keys())}")
    return CLEF_MAP[clef_name]
