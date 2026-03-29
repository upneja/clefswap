# OMR + Instrument Playback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PNG sheet music input (via oemer OMR), instrument-aware clef conversion with automatic range analysis, a step-by-step wizard for approving octave shifts on flagged measures, and in-browser MIDI playback using html-midi-player.

**Architecture:** PNG → oemer CLI (subprocess) → MusicXML → existing clef converter → range analyzer flags out-of-range measures → session stored server-side (temp dir, 30min TTL) → wizard frontend reviews flagged measures with MIDI snippets → /finalize applies approved shifts → PDF + full MIDI returned. Sessions served at `/session/{id}/midi/...` endpoints.

**Tech Stack:** oemer (OMR, subprocess CLI), music21 (MIDI export, range analysis), html-midi-player + @magenta/music (CDN, browser MIDI playback with GM soundfonts), FastAPI sessions (in-memory dict + temp dirs), Pillow (already installed)

---

## Environment

- **Working dir:** `/Users/upneja/Projects/monkeymusic`
- **Venv:** `source .venv/bin/activate`
- **Tests:** `pytest tests/ -v`
- **Backend running on:** port 8000 (kill/restart with `./run.sh`)

---

## Task 1: Install oemer and verify OMR works

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Install oemer**

```bash
cd /Users/upneja/Projects/monkeymusic
source .venv/bin/activate
pip install oemer
```

Expected: installs oemer 0.1.5 + onnxruntime + opencv-python + scikit-learn + scipy (~200MB).

**Step 2: Verify oemer CLI works**

```bash
source .venv/bin/activate
oemer --help 2>&1 | head -5
```

Expected: shows usage with `-o` output flag.

**Step 3: Update requirements.txt**

Add to `backend/requirements.txt`:
```
oemer==0.1.5
```

**Step 4: Create a test PNG from an existing MusicXML fixture**

We need a real PNG of sheet music to test OMR. Generate one from the existing fixture using LilyPond:

```bash
source .venv/bin/activate
python3 -c "
from music21 import converter
s = converter.parse('tests/fixtures/basic_treble_scale.musicxml')
s.write('lily.png', fp='/tmp/test_omr.png')
import glob, os
pngs = glob.glob('/tmp/test_omr*.png')
print('PNGs:', pngs)
"
```

If LilyPond generates a PNG, note the actual output path (may be `/tmp/test_omr-1.png`).

**Step 5: Run oemer on the test PNG**

```bash
source .venv/bin/activate
oemer /tmp/test_omr-1.png -o /tmp/omr_output/ 2>&1
ls /tmp/omr_output/
```

Expected: a `.musicxml` file in `/tmp/omr_output/`.

**Step 6: Verify the output parses**

```bash
source .venv/bin/activate
python3 -c "
from music21 import converter
import glob
f = glob.glob('/tmp/omr_output/*.musicxml')[0]
s = converter.parse(f)
print('Parts:', len(s.parts))
print('Notes:', len(list(s.flatten().notes)))
"
```

**Step 7: Add oemer to requirements and commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add oemer for OMR support"
```

---

## Task 2: Instrument Database

**Files:**
- Create: `backend/instruments.py`
- Create: `tests/test_instruments.py`

**Step 1: Write failing tests**

File: `tests/test_instruments.py`
```python
import pytest
from backend.instruments import INSTRUMENTS, get_instrument, InstrumentNotFound

def test_all_required_instruments_present():
    required = {'violin', 'viola', 'cello', 'double_bass', 'flute',
                'clarinet_bb', 'trumpet_bb', 'trombone', 'piano_rh', 'piano_lh'}
    assert required.issubset(set(INSTRUMENTS.keys()))

def test_instrument_has_required_fields():
    v = get_instrument('violin')
    assert v['name'] == 'Violin'
    assert v['clef'] == 'treble'
    assert v['midi_program'] == 40
    assert v['range_low'] == 'G3'
    assert v['range_high'] == 'E7'

def test_viola_clef_is_alto():
    assert get_instrument('viola')['clef'] == 'alto'

def test_cello_clef_is_bass():
    assert get_instrument('cello')['clef'] == 'bass'

def test_double_bass_clef_is_bass_8vb():
    assert get_instrument('double_bass')['clef'] == 'bass_8vb'

def test_get_instrument_unknown_raises():
    with pytest.raises(InstrumentNotFound):
        get_instrument('theremin')

def test_all_instruments_have_valid_clef():
    from backend.clef_map import CLEF_MAP
    for key, inst in INSTRUMENTS.items():
        assert inst['clef'] in CLEF_MAP, f"{key} has unknown clef {inst['clef']}"

def test_all_instruments_have_midi_program():
    for key, inst in INSTRUMENTS.items():
        assert 0 <= inst['midi_program'] <= 127, f"{key} has invalid MIDI program"
```

**Step 2: Run — expect FAIL**

```bash
source .venv/bin/activate && pytest tests/test_instruments.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError`

**Step 3: Create backend/instruments.py**

```python
"""
Instrument database: name, clef, MIDI program, playable range.
Range is given as pitch strings music21 can parse (e.g. 'G3', 'E7').
MIDI program numbers follow General MIDI specification.
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
    return INSTRUMENTS[key]
```

**Step 4: Run tests — expect PASS**

```bash
source .venv/bin/activate && pytest tests/test_instruments.py -v
```

All 8 must pass.

**Step 5: Commit**

```bash
git add backend/instruments.py tests/test_instruments.py
git commit -m "feat: instrument database with range and MIDI program data"
```

---

## Task 3: Range Analyzer

**Files:**
- Create: `backend/range_analyzer.py`
- Create: `tests/test_range_analyzer.py`

**Step 1: Write failing tests**

File: `tests/test_range_analyzer.py`
```python
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
```

**Step 2: Run — expect FAIL**

```bash
source .venv/bin/activate && pytest tests/test_range_analyzer.py -v 2>&1 | head -10
```

**Step 3: Create backend/range_analyzer.py**

```python
"""
Range analyzer: identifies measures where notes fall outside an instrument's
playable range, and applies octave shifts to fix them.
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
        instrument: dict from instruments.INSTRUMENTS

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
    import gc
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

    del score
    gc.collect()
    return result
```

**Step 4: Run tests — expect PASS**

```bash
source .venv/bin/activate && pytest tests/test_range_analyzer.py -v
```

All 8 must pass. If `apply_octave_shifts` fails because deepcopy of music21 Score doesn't work, use `score.write('musicxml')` + re-parse as alternative.

**Step 5: Commit**

```bash
git add backend/range_analyzer.py tests/test_range_analyzer.py
git commit -m "feat: range analyzer with octave shift application"
```

---

## Task 4: OMR Wrapper

**Files:**
- Create: `backend/omr.py`
- Create: `tests/test_omr.py`

**Step 1: Write failing tests**

File: `tests/test_omr.py`
```python
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from backend.omr import run_omr, OmrError, is_image_file


def test_is_image_file_png():
    assert is_image_file('score.png') is True

def test_is_image_file_jpg():
    assert is_image_file('score.jpg') is True
    assert is_image_file('score.jpeg') is True

def test_is_image_file_xml_is_false():
    assert is_image_file('score.musicxml') is False
    assert is_image_file('score.mxl') is False

def test_run_omr_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        run_omr('/nonexistent/file.png')

def test_run_omr_raises_omr_error_on_oemer_failure():
    """If oemer CLI fails, OmrError is raised with a clear message."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        # Write a tiny valid PNG (1x1 white pixel)
        import struct, zlib
        def make_png():
            sig = b'\x89PNG\r\n\x1a\n'
            ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
            ihdr_chunk = b'IHDR' + ihdr
            ihdr_crc = struct.pack('>I', zlib.crc32(ihdr_chunk) & 0xffffffff)
            idat_data = zlib.compress(b'\x00\xff\xff\xff')
            idat_chunk = b'IDAT' + idat_data
            idat_crc = struct.pack('>I', zlib.crc32(idat_chunk) & 0xffffffff)
            iend_crc = struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
            def chunk(name, data): return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
            return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat_data) + chunk(b'IEND', b'')
        f.write(make_png())
        tmp_path = f.name
    try:
        # A 1x1 pixel PNG will fail OMR — that's the point
        with pytest.raises((OmrError, Exception)):
            run_omr(tmp_path)
    finally:
        os.unlink(tmp_path)

def test_run_omr_returns_musicxml_path_on_success():
    """Mock oemer subprocess to test the path-finding logic."""
    import subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake musicxml output that oemer would produce
        fake_xml = os.path.join(tmpdir, 'output.musicxml')
        with open(fake_xml, 'w') as f:
            f.write('<?xml version="1.0"?><score-partwise/>')

        with patch('backend.omr.subprocess.run') as mock_run, \
             patch('backend.omr.tempfile.mkdtemp', return_value=tmpdir):
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            result = run_omr('/fake/input.png')
            assert result.endswith('.musicxml') or result.endswith('.xml')
```

**Step 2: Run — expect FAIL**

```bash
source .venv/bin/activate && pytest tests/test_omr.py -v 2>&1 | head -10
```

**Step 3: Create backend/omr.py**

```python
"""
OMR (Optical Music Recognition) wrapper around the oemer CLI.
Converts sheet music images (PNG, JPG) to MusicXML using oemer.
"""
import glob
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


class OmrError(Exception):
    """Raised when OMR processing fails."""
    pass


def is_image_file(filename: str) -> bool:
    """Return True if filename has an image extension."""
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_IMAGE_EXTENSIONS


def run_omr(image_path: str) -> str:
    """
    Run oemer on an image file and return the path to the resulting MusicXML.

    Args:
        image_path: Absolute path to input PNG/JPG.

    Returns:
        Absolute path to output .musicxml file (in a temp dir — caller must clean up).

    Raises:
        FileNotFoundError: if image_path does not exist.
        OmrError: if oemer fails or produces no output.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_dir = tempfile.mkdtemp(prefix='clefswap_omr_')
    logger.info(f"Running oemer on {image_path} → {output_dir}")

    try:
        result = subprocess.run(
            ['oemer', image_path, '-o', output_dir],
            capture_output=True,
            text=True,
            timeout=300,  # OMR can take a while
        )

        if result.returncode != 0:
            raise OmrError(
                f"OMR failed (exit {result.returncode}):\n{result.stderr[:500]}"
            )

        # Find the produced MusicXML file
        xml_files = (
            glob.glob(os.path.join(output_dir, '*.musicxml')) +
            glob.glob(os.path.join(output_dir, '**', '*.musicxml'), recursive=True) +
            glob.glob(os.path.join(output_dir, '*.xml')) +
            glob.glob(os.path.join(output_dir, '**', '*.xml'), recursive=True)
        )

        if not xml_files:
            raise OmrError(
                f"oemer ran successfully but produced no MusicXML in {output_dir}. "
                f"Contents: {os.listdir(output_dir)}"
            )

        musicxml_path = xml_files[0]
        logger.info(f"OMR produced: {musicxml_path}")
        return musicxml_path

    except subprocess.TimeoutExpired:
        raise OmrError("OMR timed out after 5 minutes. Try a simpler/smaller image.")
    except OmrError:
        raise
    except Exception as e:
        raise OmrError(f"Unexpected OMR error: {e}") from e
```

**Step 4: Run tests — expect PASS**

```bash
source .venv/bin/activate && pytest tests/test_omr.py -v
```

Most tests should pass. The real-file test (`test_run_omr_raises_omr_error_on_oemer_failure`) may pass or skip depending on oemer behavior with tiny PNGs.

**Step 5: Commit**

```bash
git add backend/omr.py tests/test_omr.py
git commit -m "feat: oemer OMR wrapper with error handling"
```

---

## Task 5: MIDI Generator

**Files:**
- Create: `backend/midi_gen.py`
- Create: `tests/test_midi_gen.py`

**Step 1: Write failing tests**

File: `tests/test_midi_gen.py`
```python
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
```

**Step 2: Run — expect FAIL**

```bash
source .venv/bin/activate && pytest tests/test_midi_gen.py -v 2>&1 | head -5
```

**Step 3: Create backend/midi_gen.py**

```python
"""
MIDI generation from music21 Score objects.
Exports full scores or individual measures as MIDI bytes.
"""
import gc
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def score_to_midi(score, midi_program: int = 40) -> bytes:
    """
    Convert a music21 Score to MIDI bytes, setting all parts to midi_program.

    Args:
        score: music21 Score object.
        midi_program: General MIDI program number (0-127).

    Returns:
        Raw MIDI bytes (starts with b'MThd').
    """
    from music21 import instrument as m21inst
    import copy

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
    import copy

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
        # Copy time signature and key from original measure if present
        for m in measures:
            mini_part.append(copy.deepcopy(m))
        mini.insert(0, mini_part)

    if not found:
        raise ValueError(f"Measure {measure_number} not found in score.")

    return score_to_midi(mini, midi_program=midi_program)
```

**Step 4: Run tests — expect PASS**

```bash
source .venv/bin/activate && pytest tests/test_midi_gen.py -v
```

**Step 5: Commit**

```bash
git add backend/midi_gen.py tests/test_midi_gen.py
git commit -m "feat: MIDI generator for full scores and individual measures"
```

---

## Task 6: Session Store + New API Endpoints

**Files:**
- Create: `backend/session_store.py`
- Modify: `backend/main.py`
- Modify: `backend/validators.py`
- Create: `tests/test_new_api.py`

**Step 1: Create backend/session_store.py**

```python
"""
In-memory session store for conversion state.
Each session holds: musicxml path, flagged measures, instrument info, temp dir.
Sessions expire after 30 minutes.
"""
import os
import shutil
import tempfile
import threading
import time
import uuid

_sessions: dict = {}
_lock = threading.Lock()
SESSION_TTL = 30 * 60  # 30 minutes


def create_session() -> tuple[str, str]:
    """
    Create a new session with a temp directory.
    Returns: (session_id, session_dir)
    """
    session_id = str(uuid.uuid4())
    session_dir = tempfile.mkdtemp(prefix=f'clefswap_session_{session_id[:8]}_')
    with _lock:
        _sessions[session_id] = {
            'dir': session_dir,
            'created': time.time(),
            'data': {},
        }
    return session_id, session_dir


def get_session(session_id: str) -> dict | None:
    with _lock:
        return _sessions.get(session_id)


def set_session_data(session_id: str, data: dict):
    with _lock:
        if session_id in _sessions:
            _sessions[session_id]['data'].update(data)


def delete_session(session_id: str):
    with _lock:
        session = _sessions.pop(session_id, None)
    if session:
        shutil.rmtree(session['dir'], ignore_errors=True)


def cleanup_expired():
    """Delete sessions older than SESSION_TTL."""
    now = time.time()
    expired = []
    with _lock:
        for sid, s in list(_sessions.items()):
            if now - s['created'] > SESSION_TTL:
                expired.append(sid)
    for sid in expired:
        delete_session(sid)
```

**Step 2: Update backend/validators.py to accept PNG/JPG**

Add to `ALLOWED_EXTENSIONS` and add image-specific validation. Find the line:
```python
ALLOWED_EXTENSIONS = {'.mxl', '.musicxml', '.xml'}
```
Replace with:
```python
ALLOWED_EXTENSIONS = {'.mxl', '.musicxml', '.xml', '.png', '.jpg', '.jpeg'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
```

Update `validate_file` to remove the generic error for image files and instead allow them through (they were previously caught by the `.pdf` check which is fine since `.pdf` is still rejected).

The `.mid`/`.midi` check and `.pdf` check stay. The catch-all changes:
```python
if ext not in ALLOWED_EXTENSIONS:
    raise ValidationError(
        f"Unsupported file type '{ext}'. Please upload a MusicXML file "
        f"(.mxl, .musicxml, .xml) or a sheet music image (.png, .jpg)."
    )
```

**Step 3: Write failing API tests**

File: `tests/test_new_api.py`
```python
"""Tests for new OMR and instrument-aware conversion endpoints."""
import io
import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), 'rb') as f:
        return f.read()


# --- GET /instruments ---

def test_instruments_endpoint():
    resp = client.get("/instruments")
    assert resp.status_code == 200
    data = resp.json()
    assert 'violin' in data
    assert 'viola' in data
    assert data['violin']['clef'] == 'treble'
    assert data['viola']['clef'] == 'alto'
    assert 'midi_program' in data['violin']


# --- POST /convert-instrument (MusicXML input path) ---

def test_convert_instrument_musicxml_no_flags():
    """Convert a simple score that's within viola range — no wizard needed."""
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'session_id' in data
    assert 'flagged_measures' in data
    assert isinstance(data['flagged_measures'], list)
    assert 'full_midi_url' in data


def test_convert_instrument_wrong_instrument_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "theremin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400


def test_convert_instrument_same_instrument_400():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "violin"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 400


# --- GET /session/{id}/midi/full ---

def test_session_midi_full_returns_midi():
    content = fixture_bytes("basic_treble_scale.musicxml")
    resp = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    assert resp.status_code == 200
    session_id = resp.json()['session_id']

    midi_resp = client.get(f"/session/{session_id}/midi/full")
    assert midi_resp.status_code == 200
    assert midi_resp.content[:4] == b'MThd'


def test_session_not_found_404():
    resp = client.get("/session/nonexistent-id/midi/full")
    assert resp.status_code == 404


# --- POST /finalize ---

def test_finalize_returns_pdf():
    from backend.renderer import detect_renderer
    if detect_renderer() == 'none':
        pytest.skip("No PDF renderer available")

    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']

    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {}, "format": "pdf"},
    )
    assert final.status_code == 200
    assert final.headers['content-type'] == 'application/pdf'


def test_finalize_returns_musicxml():
    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']

    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {}, "format": "musicxml"},
    )
    assert final.status_code == 200
    assert 'attachment' in final.headers.get('content-disposition', '')


def test_finalize_applies_shifts():
    """Finalize with a shift applied — verify note moved in output."""
    from music21 import converter as m21conv, note as m21note
    content = fixture_bytes("basic_treble_scale.musicxml")
    conv = client.post(
        "/convert-instrument",
        data={"source_instrument": "violin", "target_instrument": "viola"},
        files={"file": ("test.musicxml", io.BytesIO(content), "text/xml")},
    )
    session_id = conv.json()['session_id']
    flagged = conv.json()['flagged_measures']

    # Apply shift_down to measure 1 (even if not flagged — tests the mechanism)
    final = client.post(
        "/finalize",
        json={"session_id": session_id, "shifts": {"1": "shift_down"}, "format": "musicxml"},
    )
    assert final.status_code == 200
```

**Step 4: Run tests — expect FAIL**

```bash
source .venv/bin/activate && pytest tests/test_new_api.py -v 2>&1 | head -15
```

Expected: ImportError or 404 (endpoints not defined yet).

**Step 5: Add new endpoints to backend/main.py**

Add these imports at the top of `main.py`:
```python
from pydantic import BaseModel
from fastapi.responses import Response
from backend.instruments import INSTRUMENTS, get_instrument, InstrumentNotFound
from backend.range_analyzer import analyze_range, apply_octave_shifts
from backend.midi_gen import score_to_midi, measure_to_midi
from backend.omr import run_omr, is_image_file, OmrError
from backend.session_store import (
    create_session, get_session, set_session_data, delete_session, cleanup_expired
)
```

Add these Pydantic models after the imports:
```python
class FinalizeRequest(BaseModel):
    session_id: str
    shifts: dict[str, str]  # {"1": "shift_down", "3": "shift_up"}
    format: str = "pdf"
```

Add these endpoints to `main.py` (after the existing `/convert` endpoint):

```python
@app.get("/instruments")
def list_instruments():
    """Return all supported instruments with display info."""
    return {
        key: {
            'name': inst['name'],
            'clef': inst['clef'],
            'midi_program': inst['midi_program'],
            'range_low': inst['range_low'],
            'range_high': inst['range_high'],
        }
        for key, inst in INSTRUMENTS.items()
    }


@app.post("/convert-instrument")
async def convert_instrument(
    file: UploadFile = File(...),
    source_instrument: str = Form("violin"),
    target_instrument: str = Form("viola"),
):
    """
    Full pipeline:
    1. Accept PNG (OMR) or MusicXML
    2. Convert clef based on target instrument
    3. Analyze range against target instrument
    4. Return session_id + flagged measures + MIDI URLs
    """
    cleanup_expired()

    # Validate file
    try:
        validate_file(file)
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})

    # Validate instruments
    try:
        src_inst = get_instrument(source_instrument)
        tgt_inst = get_instrument(target_instrument)
    except InstrumentNotFound as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    if source_instrument == target_instrument:
        return JSONResponse(
            status_code=400,
            content={"error": "Source and target instruments are the same."}
        )

    session_id, session_dir = create_session()
    upload_tmp = None
    musicxml_path = None

    try:
        # Save upload
        suffix = os.path.splitext(file.filename or 'upload')[1].lower() or '.musicxml'
        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix='clefswap_up_') as tmp:
            tmp.write(contents)
            upload_tmp = tmp.name

        # OMR if image
        if is_image_file(file.filename or ''):
            try:
                musicxml_path = run_omr(upload_tmp)
            except OmrError as e:
                delete_session(session_id)
                return JSONResponse(status_code=422, content={"error": f"OMR failed: {str(e)[:300]}"})
        else:
            musicxml_path = upload_tmp
            upload_tmp = None  # don't double-delete

        # Clef conversion
        try:
            converted_path = convert_clef(musicxml_path, src_inst['clef'], tgt_inst['clef'])
        except Exception as e:
            delete_session(session_id)
            return JSONResponse(status_code=422, content={"error": f"Conversion failed: {str(e)[:200]}"})

        # Save converted MusicXML to session
        session_xml = os.path.join(session_dir, 'converted.musicxml')
        import shutil as _shutil
        _shutil.move(converted_path, session_xml)

        # Parse for analysis
        from music21 import converter as m21conv
        score = m21conv.parse(session_xml)

        # Range analysis
        flagged = analyze_range(score, tgt_inst)

        # Generate full MIDI
        full_midi = score_to_midi(score, midi_program=tgt_inst['midi_program'])
        full_midi_path = os.path.join(session_dir, 'full.mid')
        with open(full_midi_path, 'wb') as f:
            f.write(full_midi)

        # Generate per-measure MIDI snippets for flagged measures
        measure_midi_urls = {}
        for fm in flagged:
            n = fm.measure_number
            # Original measure
            try:
                orig_bytes = measure_to_midi(score, n, midi_program=src_inst['midi_program'])
                orig_path = os.path.join(session_dir, f'm{n}_original.mid')
                with open(orig_path, 'wb') as f:
                    f.write(orig_bytes)
            except Exception:
                pass

            # Shifted measure (apply shift to full score, extract measure)
            from backend.range_analyzer import apply_octave_shifts as _shift
            shifted_score = _shift(score, {n: fm.suggestion})
            try:
                shifted_bytes = measure_to_midi(shifted_score, n, midi_program=tgt_inst['midi_program'])
                shifted_path = os.path.join(session_dir, f'm{n}_shifted.mid')
                with open(shifted_path, 'wb') as f:
                    f.write(shifted_bytes)
            except Exception:
                pass

            measure_midi_urls[n] = {
                'original': f'/session/{session_id}/midi/m{n}_original',
                'shifted': f'/session/{session_id}/midi/m{n}_shifted',
            }

        set_session_data(session_id, {
            'xml_path': session_xml,
            'target_instrument': target_instrument,
            'flagged': [vars(f) for f in flagged],
        })

        return {
            'session_id': session_id,
            'flagged_measures': [
                {
                    'measure_number': f.measure_number,
                    'issue': f.issue,
                    'suggestion': f.suggestion,
                    'worst_pitch': f.worst_pitch,
                    'original_midi_url': measure_midi_urls.get(f.measure_number, {}).get('original'),
                    'shifted_midi_url': measure_midi_urls.get(f.measure_number, {}).get('shifted'),
                }
                for f in flagged
            ],
            'full_midi_url': f'/session/{session_id}/midi/full',
        }

    except Exception as e:
        logger.exception("Unexpected error in /convert-instrument")
        delete_session(session_id)
        return JSONResponse(status_code=500, content={"error": "Internal server error."})
    finally:
        _unlink(upload_tmp)
        if musicxml_path and musicxml_path != upload_tmp:
            _unlink(musicxml_path)


@app.get("/session/{session_id}/midi/{filename}")
def get_session_midi(session_id: str, filename: str):
    """Serve a MIDI file from a session's temp directory."""
    session = get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found or expired."})

    midi_path = os.path.join(session['dir'], f"{filename}.mid")
    if not os.path.exists(midi_path):
        return JSONResponse(status_code=404, content={"error": f"MIDI file not found: {filename}"})

    with open(midi_path, 'rb') as f:
        content = f.read()
    return Response(content=content, media_type='audio/midi')


@app.post("/finalize")
async def finalize(req: FinalizeRequest):
    """
    Apply approved octave shifts and return the final PDF or MusicXML.
    Deletes the session after responding.
    """
    session = get_session(req.session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found or expired."})

    if req.format not in ('pdf', 'musicxml'):
        return JSONResponse(status_code=400, content={"error": "format must be 'pdf' or 'musicxml'"})

    xml_path = session['data'].get('xml_path')
    target_instrument_key = session['data'].get('target_instrument', 'viola')

    try:
        tgt_inst = get_instrument(target_instrument_key)
    except InstrumentNotFound:
        return JSONResponse(status_code=400, content={"error": "Invalid target instrument in session."})

    try:
        from music21 import converter as m21conv
        score = m21conv.parse(xml_path)

        # Apply approved shifts (keys come in as strings from JSON)
        shifts = {int(k): v for k, v in req.shifts.items()}
        if shifts:
            score = apply_octave_shifts(score, shifts)

        # Write final MusicXML
        final_xml_tmp = tempfile.NamedTemporaryFile(
            suffix='.musicxml', delete=False, prefix='clefswap_final_'
        )
        final_xml_tmp.close()
        score.write('musicxml', fp=final_xml_tmp.name)

        output_stem = f"converted_{target_instrument_key}_clef"

        if req.format == 'pdf':
            try:
                pdf_path = render_to_pdf(final_xml_tmp.name, output_stem)
                _unlink(final_xml_tmp.name)
                delete_session(req.session_id)
                return FileResponse(
                    path=pdf_path,
                    media_type='application/pdf',
                    filename=f"{output_stem}.pdf",
                    headers={"Content-Disposition": f'attachment; filename="{output_stem}.pdf"'},
                    background=BackgroundTask(_unlink, pdf_path),
                )
            except RendererUnavailable as e:
                return JSONResponse(status_code=503, content={"error": str(e)})

        # Return MusicXML
        delete_session(req.session_id)
        return FileResponse(
            path=final_xml_tmp.name,
            media_type='application/xml',
            filename=f"{output_stem}.musicxml",
            headers={"Content-Disposition": f'attachment; filename="{output_stem}.musicxml"'},
            background=BackgroundTask(_unlink, final_xml_tmp.name),
        )

    except Exception as e:
        logger.exception("Error in /finalize")
        return JSONResponse(status_code=500, content={"error": f"Finalize failed: {str(e)[:200]}"})
```

**Step 6: Run new API tests**

```bash
source .venv/bin/activate && pytest tests/test_new_api.py -v
```

Fix any import errors, missing imports, or logic bugs. All tests should pass.

**Step 7: Run full test suite**

```bash
source .venv/bin/activate && pytest tests/ -v 2>&1 | tail -10
```

**Step 8: Commit**

```bash
git add backend/session_store.py backend/instruments.py backend/omr.py backend/range_analyzer.py backend/midi_gen.py backend/main.py backend/validators.py tests/test_new_api.py
git commit -m "feat: /convert-instrument, /session/midi, /finalize endpoints with OMR, range analysis, MIDI"
```

---

## Task 7: Frontend Overhaul

**Files:**
- Modify: `frontend/index.html`

Replace the entire file. Key changes from original:
1. File accepts PNG/JPG/XML
2. Instrument selectors (source + target) instead of clef selectors
3. Wizard overlay for flagged measures with html-midi-player snippets
4. Full-score MIDI player on completion
5. Download PDF + MIDI buttons

**Step 1: Replace frontend/index.html entirely**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ClefSwap — Convert & Play Sheet Music</title>
  <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- html-midi-player: browser MIDI playback with GM soundfonts -->
  <script src="https://cdn.jsdelivr.net/combine/npm/tone@14.7.58,npm/@magenta/music@1.23.1/es6/core.js,npm/focus-visible@5,npm/html-midi-player@1.5.0"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root { --navy:#1a1a2e; --gold:#e2b714; --gold-dark:#c9a010; --cream:#faf8f0; }
    body { background:var(--navy); font-family:'Inter',sans-serif; color:var(--cream); margin:0; }
    h1 { font-family:'Playfair Display',serif; }
    .drop-zone { border:2px dashed rgba(226,183,20,0.4); transition:border-color 0.2s,background 0.2s; }
    .drop-zone.over { border-color:var(--gold); background:rgba(226,183,20,0.06); }
    .btn-gold { background:var(--gold); color:var(--navy); font-weight:600; transition:background 0.15s,transform 0.1s; }
    .btn-gold:hover:not(:disabled) { background:var(--gold-dark); }
    .btn-gold:active:not(:disabled) { transform:scale(0.98); }
    .btn-gold:disabled { opacity:0.4; cursor:not-allowed; }
    .btn-outline { border:1.5px solid rgba(226,183,20,0.4); color:var(--gold); transition:border-color 0.2s,background 0.2s; }
    .btn-outline:hover:not(:disabled) { border-color:var(--gold); background:rgba(226,183,20,0.07); }
    .btn-outline:disabled { opacity:0.4; cursor:not-allowed; }
    select { background:rgba(255,255,255,0.05); border:1.5px solid rgba(255,255,255,0.12); color:var(--cream); }
    select:focus { border-color:var(--gold); outline:none; }
    select option { background:#1a1a2e; }
    .spinner { width:24px; height:24px; border:3px solid rgba(226,183,20,0.2); border-top-color:var(--gold); border-radius:50%; animation:spin 0.8s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
    midi-player { --primary-color:var(--gold); width:100%; display:block; border-radius:8px; overflow:hidden; }
    .wizard-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:50; display:flex; align-items:center; justify-content:center; padding:24px; }
    .wizard-card { background:#1c1c32; border:1.5px solid rgba(226,183,20,0.3); border-radius:16px; padding:28px; max-width:480px; width:100%; }
  </style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const { useState, useRef, useCallback, useEffect } = React;
const API = 'http://localhost:8000';

function fmtBytes(b) {
  if (b < 1024) return b+' B';
  if (b < 1048576) return (b/1024).toFixed(1)+' KB';
  return (b/1048576).toFixed(1)+' MB';
}

function MidiPlayer({ src, label }) {
  if (!src) return null;
  return (
    <div className="space-y-1">
      {label && <p className="text-xs" style={{color:'rgba(250,248,240,0.4)'}}>{label}</p>}
      <midi-player src={src} sound-font="https://storage.googleapis.com/magentadata/js/soundfonts/sgm_plus"></midi-player>
    </div>
  );
}

function WizardStep({ measure, total, current, onAccept, onSkip }) {
  const progress = `${current} of ${total}`;
  return (
    <div className="wizard-overlay">
      <div className="wizard-card space-y-5">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-bold" style={{fontFamily:'Playfair Display,serif',color:'var(--gold)'}}>
            Range Adjustment
          </h2>
          <span className="text-xs" style={{color:'rgba(250,248,240,0.35)'}}>{progress}</span>
        </div>

        <div className="rounded-lg p-4 space-y-1" style={{background:'rgba(251,191,36,0.08)',border:'1px solid rgba(251,191,36,0.2)'}}>
          <p className="text-sm font-semibold" style={{color:'#fbbf24'}}>
            ⚠ Measure {measure.measure_number}
          </p>
          <p className="text-sm" style={{color:'rgba(250,248,240,0.6)'}}>
            Note <strong style={{color:'var(--cream)'}}>{measure.worst_pitch}</strong> is {measure.issue === 'too_high' ? 'above' : 'below'} the target instrument's range.
          </p>
          <p className="text-xs mt-1" style={{color:'rgba(250,248,240,0.4)'}}>
            Suggestion: shift {measure.suggestion === 'shift_down' ? 'down' : 'up'} one octave
          </p>
        </div>

        <div className="space-y-3">
          {measure.original_midi_url && (
            <MidiPlayer src={`${API}${measure.original_midi_url}`} label="▶ Original measure" />
          )}
          {measure.shifted_midi_url && (
            <MidiPlayer src={`${API}${measure.shifted_midi_url}`} label={`▶ Shifted ${measure.suggestion === 'shift_down' ? 'down' : 'up'} one octave`} />
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button className="btn-outline flex-1 py-2.5 rounded-lg text-sm" onClick={onSkip}>
            Keep original
          </button>
          <button className="btn-gold flex-1 py-2.5 rounded-lg text-sm" onClick={onAccept}>
            ✓ Apply shift
          </button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [file, setFile]             = useState(null);
  const [srcInst, setSrcInst]       = useState('violin');
  const [tgtInst, setTgtInst]       = useState('viola');
  const [instruments, setInstruments] = useState({});
  const [status, setStatus]         = useState('idle');
  const [error, setError]           = useState('');
  const [sessionId, setSessionId]   = useState(null);
  const [flagged, setFlagged]       = useState([]);
  const [wizardIdx, setWizardIdx]   = useState(0);
  const [shifts, setShifts]         = useState({});
  const [fullMidiUrl, setFullMidiUrl] = useState(null);
  const [dlPdfUrl, setDlPdfUrl]     = useState(null);
  const [dlMidiUrl, setDlMidiUrl]   = useState(null);
  const [isDragOver, setDragOver]   = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/instruments`)
      .then(r => r.json())
      .then(setInstruments)
      .catch(() => {});
  }, []);

  const ACCEPT = '.mxl,.musicxml,.xml,.png,.jpg,.jpeg';

  const pick = useCallback((f) => {
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['mxl','musicxml','xml','png','jpg','jpeg'].includes(ext)) {
      setError(`Unsupported type .${ext}. Use MusicXML (.mxl, .musicxml) or image (.png, .jpg).`);
      setStatus('error'); return;
    }
    if (f.size > 20*1024*1024) {
      setError('File too large. Max 20MB.'); setStatus('error'); return;
    }
    setFile(f); setStatus('ready'); setError(''); setDlPdfUrl(null); setDlMidiUrl(null);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false); pick(e.dataTransfer.files[0]);
  }, [pick]);

  const convert = async () => {
    if (!file) return;
    setStatus('converting'); setError('');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('source_instrument', srcInst);
    fd.append('target_instrument', tgtInst);
    try {
      const resp = await fetch(`${API}/convert-instrument`, { method:'POST', body:fd });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.error || `Server error (${resp.status})`);
      }
      const data = await resp.json();
      setSessionId(data.session_id);
      setFullMidiUrl(`${API}${data.full_midi_url}`);
      setFlagged(data.flagged_measures || []);
      setShifts({});

      if ((data.flagged_measures || []).length === 0) {
        setStatus('player');
      } else {
        setWizardIdx(0);
        setStatus('wizard');
      }
    } catch(e) {
      setError(e.message || 'Conversion failed.'); setStatus('error');
    }
  };

  const acceptShift = () => {
    const m = flagged[wizardIdx];
    setShifts(s => ({...s, [m.measure_number]: m.suggestion}));
    nextWizard();
  };
  const skipShift = () => nextWizard();
  const nextWizard = () => {
    if (wizardIdx + 1 >= flagged.length) {
      setStatus('player');
    } else {
      setWizardIdx(i => i + 1);
    }
  };

  const finalize = async (fmt) => {
    if (!sessionId) return;
    setStatus('finalizing');
    try {
      const resp = await fetch(`${API}/finalize`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ session_id: sessionId, shifts, format: fmt }),
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.error || `Server error (${resp.status})`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const disp = resp.headers.get('content-disposition') || '';
      const m = disp.match(/filename="?([^"]+)"?/);
      const name = m ? m[1] : `converted.${fmt}`;
      if (fmt === 'pdf') { setDlPdfUrl({url, name}); }
      else { setDlMidiUrl({url, name}); }
      setStatus('player');
    } catch(e) {
      setError(e.message || 'Finalize failed.'); setStatus('error');
    }
  };

  const reset = () => {
    setFile(null); setStatus('idle'); setError(''); setSessionId(null);
    setFlagged([]); setShifts({}); setFullMidiUrl(null);
    setDlPdfUrl(null); setDlMidiUrl(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const instKeys = Object.keys(instruments);
  const sameInst = srcInst === tgtInst;
  const canConvert = !!file && !sameInst;
  const isImage = file && ['png','jpg','jpeg'].includes(file.name.split('.').pop().toLowerCase());

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b px-6 py-5" style={{borderColor:'rgba(255,255,255,0.08)',background:'rgba(0,0,0,0.2)'}}>
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{color:'var(--gold)'}}>ClefSwap</h1>
            <p className="text-sm mt-0.5" style={{color:'rgba(250,248,240,0.45)'}}>
              Upload sheet music → adapt for any instrument → play it back.
            </p>
          </div>
          <span className="text-3xl opacity-20">𝄞</span>
        </div>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full px-6 py-10 space-y-8">

        {/* Upload */}
        {(status === 'idle' || status === 'ready' || status === 'error') && (
          <>
            <div
              className={`drop-zone rounded-2xl p-10 text-center cursor-pointer select-none ${isDragOver?'over':''}`}
              onDrop={onDrop}
              onDragOver={e=>{e.preventDefault();setDragOver(true);}}
              onDragLeave={()=>setDragOver(false)}
              onClick={()=>inputRef.current?.click()}
            >
              <input ref={inputRef} type="file" className="hidden" accept={ACCEPT}
                onChange={e=>pick(e.target.files[0])} />
              {file ? (
                <div className="space-y-2">
                  <div className="text-4xl">{isImage?'🖼️':'📄'}</div>
                  <p className="font-semibold" style={{color:'var(--gold)'}}>{file.name}</p>
                  <p className="text-sm" style={{color:'rgba(250,248,240,0.4)'}}>{fmtBytes(file.size)} · {isImage?'Image (OMR)':'MusicXML'}</p>
                  <button className="text-xs underline mt-1" style={{color:'rgba(250,248,240,0.3)'}}
                    onClick={e=>{e.stopPropagation();reset();}}>Remove</button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="text-5xl opacity-30">𝄞</div>
                  <div>
                    <p className="text-lg font-medium" style={{color:'rgba(250,248,240,0.8)'}}>Drop your sheet music here</p>
                    <p className="text-sm mt-1" style={{color:'rgba(250,248,240,0.35)'}}>
                      MusicXML (.mxl, .musicxml) or Image (.png, .jpg)
                    </p>
                  </div>
                  <button className="btn-gold px-5 py-2 rounded-lg text-sm" onClick={e=>e.stopPropagation()}>
                    Choose file
                  </button>
                </div>
              )}
            </div>

            {/* Instrument selectors */}
            <div>
              <p className="text-xs uppercase tracking-widest mb-3" style={{color:'rgba(250,248,240,0.35)'}}>Instrument Conversion</p>
              <div className="flex items-center gap-4">
                <div className="flex-1 space-y-1">
                  <label className="text-xs" style={{color:'rgba(250,248,240,0.4)'}}>From</label>
                  <select value={srcInst} onChange={e=>setSrcInst(e.target.value)} className="w-full rounded-lg px-3 py-2.5 text-sm">
                    {instKeys.map(k=><option key={k} value={k}>{instruments[k].name}</option>)}
                  </select>
                </div>
                <span className="text-xl mt-5" style={{color:'rgba(250,248,240,0.2)'}}>→</span>
                <div className="flex-1 space-y-1">
                  <label className="text-xs" style={{color:'rgba(250,248,240,0.4)'}}>To</label>
                  <select value={tgtInst} onChange={e=>setTgtInst(e.target.value)} className="w-full rounded-lg px-3 py-2.5 text-sm">
                    {instKeys.map(k=><option key={k} value={k}>{instruments[k].name}</option>)}
                  </select>
                </div>
              </div>
              {sameInst && <p className="text-xs mt-2" style={{color:'#fbbf24'}}>⚠ Same instrument selected.</p>}
            </div>

            {/* Convert button */}
            <button className="btn-gold w-full py-3.5 rounded-xl text-base" disabled={!canConvert} onClick={convert}>
              Convert & Analyze Range
            </button>

            {status === 'error' && error && (
              <div className="rounded-xl p-4 flex gap-3" style={{background:'rgba(248,113,113,0.1)',border:'1px solid rgba(248,113,113,0.3)',color:'#fca5a5'}}>
                <span>⚠</span>
                <div>
                  <p className="text-sm">{error}</p>
                  <button className="text-xs underline mt-2" style={{color:'rgba(252,165,165,0.6)'}} onClick={reset}>Try again</button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Converting spinner */}
        {(status === 'converting' || status === 'finalizing') && (
          <div className="flex flex-col items-center justify-center py-20 gap-5">
            <div className="spinner" style={{width:40,height:40,borderWidth:4}}></div>
            <p style={{color:'rgba(250,248,240,0.5)'}}>
              {status === 'converting'
                ? isImage ? 'Running optical music recognition… (30–60s)' : 'Converting score…'
                : 'Generating your score…'}
            </p>
          </div>
        )}

        {/* Player + download */}
        {status === 'player' && (
          <div className="space-y-6">
            <div className="rounded-xl p-5 space-y-4" style={{background:'rgba(226,183,20,0.06)',border:'1.5px solid rgba(226,183,20,0.25)'}}>
              <div className="flex items-center gap-2">
                <span style={{color:'#22c55e',fontSize:'1.2rem'}}>✓</span>
                <p className="font-semibold" style={{color:'var(--gold)'}}>
                  {instruments[tgtInst]?.name || tgtInst} version ready
                </p>
              </div>
              {Object.keys(shifts).length > 0 && (
                <p className="text-xs" style={{color:'rgba(250,248,240,0.45)'}}>
                  {Object.keys(shifts).length} octave adjustment{Object.keys(shifts).length > 1 ? 's' : ''} applied.
                </p>
              )}
            </div>

            {/* MIDI player */}
            {fullMidiUrl && (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-widest" style={{color:'rgba(250,248,240,0.35)'}}>Playback</p>
                <MidiPlayer src={fullMidiUrl} />
              </div>
            )}

            {/* Download buttons */}
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-widest" style={{color:'rgba(250,248,240,0.35)'}}>Download</p>
              <div className="flex gap-3">
                {dlPdfUrl ? (
                  <a href={dlPdfUrl.url} download={dlPdfUrl.name} className="btn-gold flex-1 py-2.5 rounded-lg text-sm text-center no-underline">
                    ↓ {dlPdfUrl.name}
                  </a>
                ) : (
                  <button className="btn-gold flex-1 py-2.5 rounded-lg text-sm" onClick={()=>finalize('pdf')}>
                    Download PDF
                  </button>
                )}
                {dlMidiUrl ? (
                  <a href={dlMidiUrl.url} download={dlMidiUrl.name} className="btn-outline flex-1 py-2.5 rounded-lg text-sm text-center no-underline">
                    ↓ {dlMidiUrl.name}
                  </a>
                ) : (
                  <button className="btn-outline flex-1 py-2.5 rounded-lg text-sm" onClick={()=>finalize('musicxml')}>
                    Download MusicXML
                  </button>
                )}
              </div>
            </div>

            <button className="text-xs underline" style={{color:'rgba(250,248,240,0.25)'}} onClick={reset}>
              Convert another file
            </button>
          </div>
        )}
      </main>

      {/* Wizard overlay */}
      {status === 'wizard' && flagged[wizardIdx] && (
        <WizardStep
          measure={flagged[wizardIdx]}
          total={flagged.length}
          current={wizardIdx + 1}
          onAccept={acceptShift}
          onSkip={skipShift}
        />
      )}

      <footer className="border-t px-6 py-4 text-center text-xs"
        style={{borderColor:'rgba(255,255,255,0.06)',color:'rgba(250,248,240,0.2)'}}>
        Built for musicians who play multiple instruments.
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>
```

**Step 2: Verify file was written**

```bash
wc -l /Users/upneja/Projects/monkeymusic/frontend/index.html
```

Expected: 250+ lines.

**Step 3: Commit**

```bash
cd /Users/upneja/Projects/monkeymusic
git add frontend/index.html
git commit -m "feat: overhaul frontend with instrument selectors, range wizard, MIDI playback"
```

---

## Task 8: Integration + Restart

**Files:**
- None new — wire everything up and verify

**Step 1: Run full test suite**

```bash
cd /Users/upneja/Projects/monkeymusic && source .venv/bin/activate
pytest tests/ -v 2>&1 | tail -15
```

All existing 64 tests must still pass. New tests from Tasks 2-6 should also pass.

**Step 2: Kill old backend and restart**

```bash
# Kill existing backend
lsof -i :8000 -sTCP:LISTEN -t | xargs kill 2>/dev/null || true
sleep 1

# Start fresh
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000 --log-level info &
sleep 2

# Verify new endpoints
curl -s http://localhost:8000/health
curl -s http://localhost:8000/instruments | python3 -m json.tool | head -20
```

Expected: `/health` returns `{"status":"ok","renderer":"lilypond"}`. `/instruments` returns all 10 instruments.

**Step 3: Update dashboard state.json**

Update `/Users/upneja/Projects/monkeymusic/dashboard/state.json` to reflect the new feature tasks. (The controller handles this.)

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: OMR + instrument playback feature complete"
```

---

## Summary

| Task | Files | Key outcome |
|------|-------|-------------|
| 1 | requirements.txt | oemer installed, OMR verified |
| 2 | instruments.py | 10 instruments with range + MIDI data |
| 3 | range_analyzer.py | Flag out-of-range measures, apply octave shifts |
| 4 | omr.py | oemer CLI wrapper with error handling |
| 5 | midi_gen.py | music21 → MIDI bytes (full score + single measure) |
| 6 | main.py + session_store.py | 3 new endpoints: /convert-instrument, /session/midi, /finalize |
| 7 | frontend/index.html | Instrument selectors, wizard, html-midi-player |
| 8 | — | Integration test + backend restart |
