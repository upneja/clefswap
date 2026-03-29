# ClefSwap

**Sheet music clef converter with OMR, range analysis, and MIDI playback.**

Upload a MusicXML file or a scanned sheet music image — ClefSwap re-notates it for a different instrument, checks whether any notes fall outside the target's playable range, lets you preview each problem measure via in-browser MIDI, and downloads a clean PDF.

---

## What It Does

Classical arrangers constantly copy parts between instruments that read different clefs: violin (treble) to viola (alto), cello (bass) to tenor voice (tenor clef), and so on. ClefSwap automates that tedious step.

**Re-notation, not transposition.** Pitches are identical before and after. Only the visual representation changes — middle C stays middle C, it just moves to a different staff position.

---

## Features

### Clef Conversion
- Converts between any pair of 7 standard clefs: Treble, Alto, Tenor, Bass, Treble 8vb, Treble 8va, Bass 8vb
- All mid-score clef changes are replaced uniformly
- All dynamics, articulations, slurs, ties, tuplets, and text expressions are preserved
- Score metadata (title, composer, copyright) is preserved

### OMR Pipeline (Image Input)
- Upload a PNG or JPG scan of sheet music
- [oemer](https://github.com/BreezeWhite/oemer) performs Optical Music Recognition to produce MusicXML
- The MusicXML is then passed through the full conversion pipeline

### Range Analysis & Octave-Shift Wizard
- After conversion, each measure is checked against the target instrument's playable range
- Flagged measures are presented one-by-one in an interactive wizard
- Each flagged measure plays back both the original and the suggested octave-shifted version via in-browser MIDI
- Accept or skip each suggestion independently before finalizing

### MIDI Generation
- Full-score MIDI generated at the correct General MIDI program for the target instrument
- Per-measure MIDI snippets for each flagged measure (original + shifted versions)
- In-browser playback via [html-midi-player](https://github.com/cifkao/html-midi-player) with GM soundfonts

### Export
- PDF via LilyPond or MuseScore 4
- MusicXML (always available, no renderer required)
- MIDI download

---

## Supported Instruments

| Key | Name | Clef | Range |
|-----|------|------|-------|
| `violin` | Violin | Treble | G3 – E7 |
| `viola` | Viola | Alto | C3 – E6 |
| `cello` | Cello | Bass | C2 – A5 |
| `double_bass` | Double Bass | Bass 8vb | E1 – G4 |
| `flute` | Flute | Treble | C4 – D7 |
| `clarinet_bb` | Clarinet (Bb) | Treble | D3 – Bb6 |
| `trumpet_bb` | Trumpet (Bb) | Treble | E3 – C6 |
| `trombone` | Trombone | Bass | E2 – F5 |
| `piano_rh` | Piano (Right Hand) | Treble | A0 – C8 |
| `piano_lh` | Piano (Left Hand) | Bass | A0 – C8 |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.10+, FastAPI, Uvicorn |
| Music processing | [music21](https://web.mit.edu/music21/) 9.3 |
| OMR | [oemer](https://github.com/BreezeWhite/oemer) |
| PDF rendering | LilyPond (preferred) or MuseScore 4 |
| Frontend | React 18 (CDN, no build step), Tailwind CSS |
| MIDI playback | html-midi-player + Magenta.js |

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + renderer status |
| `GET` | `/clefs` | Available clef names and display labels |
| `GET` | `/instruments` | Supported instruments with ranges |
| `POST` | `/convert` | Simple clef conversion (MusicXML in, PDF/MusicXML out) |
| `POST` | `/convert-instrument` | Full pipeline: OMR → convert → range analysis → session + MIDI URLs |
| `POST` | `/finalize` | Apply approved octave shifts and return final PDF/MusicXML |
| `GET` | `/session/{id}/midi/{file}` | Serve per-measure MIDI from a session |

### Quick convert (no range analysis)
```http
POST /convert
Content-Type: multipart/form-data

file=<MusicXML>
source_clef=treble
target_clef=alto
format=pdf          # or musicxml
```

### Full instrument pipeline
```http
POST /convert-instrument
Content-Type: multipart/form-data

file=<MusicXML or PNG/JPG>
source_instrument=violin
target_instrument=viola
```

---

## How to Run

### Prerequisites
- Python 3.10+
- LilyPond (`brew install lilypond` on macOS, `sudo apt-get install lilypond` on Linux) **or** MuseScore 4 for PDF output

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/upneja/monkeymusic.git
cd monkeymusic

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r backend/requirements.txt

# 4. Generate test fixtures and run the test suite
python tests/generate_fixtures.py
pytest tests/ -v

# 5. Start the backend
./run.sh
# Backend is now at http://localhost:8000

# 6. Open the frontend
open frontend/index.html        # macOS
# Or just open frontend/index.html in any browser
```

The frontend talks to `http://localhost:8000` by default. No build step needed — React and Tailwind are loaded from CDN.

### OMR (image input)

OMR support requires `oemer`, which is listed in `requirements.txt`. It uses a deep learning model that downloads automatically on first use (~200 MB). A GPU is not required but significantly speeds up processing.

---

## Project Structure

```
monkeymusic/
├── backend/
│   ├── main.py           # FastAPI app and all endpoints
│   ├── converter.py      # Core clef re-notation (music21)
│   ├── clef_map.py       # Clef name → music21 class mapping
│   ├── instruments.py    # Instrument database (range, clef, MIDI program)
│   ├── omr.py            # oemer OMR wrapper
│   ├── midi_gen.py       # Full-score and per-measure MIDI generation
│   ├── range_analyzer.py # Playable range checking + octave shift application
│   ├── renderer.py       # LilyPond / MuseScore PDF rendering
│   ├── session_store.py  # Temp session management for wizard flow
│   ├── validators.py     # File and clef pair validation
│   └── requirements.txt
├── frontend/
│   └── index.html        # Single-file React app
├── tests/                # pytest suite (~14 test files)
├── run.sh                # Start script
└── pytest.ini
```

---

## License

MIT
