# ClefSwap

Convert sheet music between clefs instantly. Upload a MusicXML file, select source and target clefs, download a PDF or MusicXML.

**V1:** Treble → Alto (violin → viola) and all other standard clef pairs.

## Quick Start

```bash
# 1. Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Install PDF renderer (macOS)
brew install lilypond
# Linux: sudo apt-get install lilypond

# 3. Generate test fixtures and run tests
python tests/generate_fixtures.py
pytest tests/ -v

# 4. Start the backend
./run.sh

# 5. Open the app
open frontend/index.html
```

## How It Works

ClefSwap is a **re-notation** tool — not a transposition tool. Pitches stay identical.

- Middle C (C4) in treble clef → one ledger line below the staff
- Middle C (C4) in alto clef → the middle (3rd) line of the staff

Same pitch. Different visual representation. The clef tells you which line = which pitch.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check + renderer status |
| GET | /clefs | Available clef names and labels |
| POST | /convert | Convert file (multipart: file, source_clef, target_clef, format) |

## Supported Clefs

| Key | Display |
|-----|---------|
| `treble` | Treble Clef (G) — violin, flute, trumpet |
| `alto` | Alto Clef (C3) — viola |
| `tenor` | Tenor Clef (C4) — cello upper range |
| `bass` | Bass Clef (F) — cello, bass, tuba |
| `treble_8vb` | Treble 8vb — guitar, tenor voice |
| `treble_8va` | Treble 8va — piccolo |
| `bass_8vb` | Bass 8vb — contrabass |

## V1 Behavior

- All clef instances in the score are replaced uniformly (including mid-score changes)
- All dynamics, articulations, slurs, ties, tuplets, and text expressions are preserved
- Score metadata (title, composer, copyright) is preserved
- PDF rendering requires LilyPond or MuseScore 4 — MusicXML download always works

## Stack

- **Backend**: Python 3.10+ / FastAPI / music21 9.3
- **PDF**: LilyPond (preferred) or MuseScore 4
- **Frontend**: React 18 + Tailwind CSS (CDN, no build step)
