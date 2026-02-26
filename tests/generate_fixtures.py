"""
Run this script once to generate test fixture MusicXML files.
Usage: python tests/generate_fixtures.py
"""
import os
from music21 import stream, note, chord, clef, key, meter, tempo, dynamics, metadata
from music21 import articulations, expressions, spanner, tie

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


def save(score, name):
    path = os.path.join(FIXTURES_DIR, name)
    score.write('musicxml', fp=path)
    print(f"Saved: {path}")
    return path


def make_basic_treble_scale():
    s = stream.Score()
    p = stream.Part()
    p.id = "Violin"
    p.append(clef.TrebleClef())
    p.append(key.Key('G'))
    p.append(meter.TimeSignature('4/4'))
    p.append(tempo.MetronomeMark(number=120))
    for pitch in ['G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F#5', 'G5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)
    s.metadata = metadata.Metadata()
    s.metadata.title = "Basic Scale Test"
    s.metadata.composer = "ClefSwap Test Suite"
    return save(s, "basic_treble_scale.musicxml")


def make_sharps_key():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('F#'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['F#4', 'G#4', 'A#4', 'B4', 'C#5', 'D#5', 'F#5']:
        p.append(note.Note(pitch, quarterLength=1))
    p.append(note.Note('F#5', quarterLength=1))
    s.insert(0, p)
    return save(s, "sharps_key.musicxml")


def make_flats_key():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('G-'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['G-4', 'A-4', 'B-4', 'C-5', 'D-5', 'E-5', 'F5', 'G-5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)
    return save(s, "flats_key.musicxml")


def make_articulations_test():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))

    n1 = note.Note('C5', quarterLength=1)
    n1.articulations.append(articulations.Staccato())
    p.append(n1)

    n2 = note.Note('D5', quarterLength=1)
    n2.articulations.append(articulations.Accent())
    p.append(n2)

    n3 = note.Note('E5', quarterLength=1)
    n3.articulations.append(articulations.Tenuto())
    p.append(n3)

    n4 = note.Note('F5', quarterLength=1)
    n4.expressions.append(expressions.Fermata())
    p.append(n4)

    n5 = note.Note('G5', quarterLength=1)
    n5.expressions.append(expressions.Trill())
    p.append(n5)

    s.insert(0, p)
    return save(s, "articulations_test.musicxml")


def make_dynamics_test():
    from music21 import dynamics as dyn
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))

    notes = [note.Note('C5', quarterLength=1) for _ in range(8)]
    for n in notes:
        p.append(n)

    p.insert(0, dyn.Dynamic('pp'))
    p.insert(2, dyn.Dynamic('mf'))
    p.insert(4, dyn.Dynamic('ff'))

    s.insert(0, p)
    return save(s, "dynamics_test.musicxml")


def make_slurs_ties_test():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))

    n1 = note.Note('G4', quarterLength=4)
    n1.tie = tie.Tie('start')
    p.append(n1)
    n2 = note.Note('G4', quarterLength=4)
    n2.tie = tie.Tie('stop')
    p.append(n2)

    n3 = note.Note('C5', quarterLength=1)
    n4 = note.Note('D5', quarterLength=1)
    n5 = note.Note('E5', quarterLength=1)
    n6 = note.Note('F5', quarterLength=1)
    for n in [n3, n4, n5, n6]:
        p.append(n)
    sl = spanner.Slur(n3, n6)
    p.insert(0, sl)

    s.insert(0, p)
    return save(s, "slurs_ties_test.musicxml")


def make_multi_clef_score():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('C'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['C5', 'D5', 'E5', 'F5']:
        p.append(note.Note(pitch, quarterLength=1))
    p.append(clef.TenorClef())
    for pitch in ['G3', 'A3', 'B3', 'C4']:
        p.append(note.Note(pitch, quarterLength=1))
    p.append(clef.TrebleClef())
    for pitch in ['E5', 'F5', 'G5', 'A5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)
    return save(s, "multi_clef_score.musicxml")


def make_metadata_test():
    s = stream.Score()
    s.metadata = metadata.Metadata()
    s.metadata.title = "Sonata in G Major"
    s.metadata.composer = "Test Composer"
    s.metadata.copyright = "© 2024 Test"
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('G'))
    p.append(meter.TimeSignature('4/4'))
    for pitch in ['G4', 'A4', 'B4', 'C5']:
        p.append(note.Note(pitch, quarterLength=1))
    s.insert(0, p)
    return save(s, "metadata_test.musicxml")


def make_pickup_measure():
    s = stream.Score()
    p = stream.Part()
    p.append(clef.TrebleClef())
    p.append(key.Key('G'))
    p.append(meter.TimeSignature('4/4'))

    m0 = stream.Measure(number=0)
    m0.append(note.Note('D5', quarterLength=1))
    p.append(m0)

    for _ in range(2):
        m = stream.Measure()
        for pitch in ['G5', 'F#5', 'E5', 'D5']:
            m.append(note.Note(pitch, quarterLength=1))
        p.append(m)
    s.insert(0, p)
    return save(s, "pickup_measure.musicxml")


if __name__ == "__main__":
    print("Generating test fixtures...")
    make_basic_treble_scale()
    make_sharps_key()
    make_flats_key()
    make_articulations_test()
    make_dynamics_test()
    make_slurs_ties_test()
    make_multi_clef_score()
    make_metadata_test()
    make_pickup_measure()
    print(f"Done! Fixtures written to {FIXTURES_DIR}")
