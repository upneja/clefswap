"""
ClefSwap FastAPI backend.

Endpoints:
  GET  /health    — health check + renderer status
  GET  /clefs     — list available clefs with display labels
  POST /convert   — upload MusicXML, convert clef, download PDF or MusicXML
"""
import gc
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.background import BackgroundTask

from backend.clef_map import CLEF_LABELS
from backend.converter import convert_clef
from backend.instruments import INSTRUMENTS, get_instrument, InstrumentNotFound
from backend.midi_gen import score_to_midi, measure_to_midi
from backend.omr import run_omr, is_image_file, OmrError
from backend.range_analyzer import analyze_range, apply_octave_shifts
from backend.renderer import RendererUnavailable, detect_renderer, render_to_pdf
from backend.session_store import (
    create_session, get_session, set_session_data, delete_session, cleanup_expired
)
from backend.validators import ValidationError, validate_clef_pair, validate_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _FileMeta:
    def __init__(self, filename, size):
        self.filename = filename
        self.size = size


class FinalizeRequest(BaseModel):
    session_id: str
    shifts: dict[str, str]  # {"1": "shift_down", "3": "shift_up"}
    format: str = "pdf"

app = FastAPI(
    title="ClefSwap API",
    description="Convert sheet music between clefs. Pitches are preserved exactly.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "renderer": detect_renderer()}


@app.get("/clefs")
def list_clefs():
    return CLEF_LABELS


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    source_clef: str = Form("treble"),
    target_clef: str = Form("alto"),
    format: str = Form("pdf"),
):
    upload_tmp = None
    converted_tmp = None
    pdf_tmp = None

    try:
        # Read file contents first so we have the size
        contents = await file.read()

        # Validate file
        try:
            validate_file(_FileMeta(file.filename, len(contents)))
        except ValidationError as e:
            return JSONResponse(status_code=422, content={"error": str(e)})

        # Validate clef pair
        try:
            validate_clef_pair(source_clef, target_clef)
        except ValidationError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

        # Validate format
        if format not in ('pdf', 'musicxml'):
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown format '{format}'. Use 'pdf' or 'musicxml'."}
            )

        # Save upload to temp file
        suffix = Path(file.filename or 'upload.musicxml').suffix.lower() or '.musicxml'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix='clefswap_upload_') as tmp:
            tmp.write(contents)
            upload_tmp = tmp.name

        # Convert clef
        try:
            converted_tmp = convert_clef(upload_tmp, source_clef, target_clef)
        except Exception as e:
            logger.exception("Conversion failed")
            return JSONResponse(
                status_code=422,
                content={"error": f"Could not parse MusicXML: {str(e)[:200]}"}
            )

        # Build output filename
        original_stem = Path(file.filename or 'score').stem
        output_stem = f"{original_stem}_{target_clef}_clef"

        # Render or return MusicXML
        if format == 'pdf':
            try:
                pdf_tmp = render_to_pdf(converted_tmp, output_stem)
            except RendererUnavailable as e:
                return JSONResponse(
                    status_code=503,
                    content={"error": f"PDF renderer unavailable: {str(e)}"}
                )
            except Exception as e:
                logger.exception("PDF rendering failed")
                return JSONResponse(
                    status_code=500,
                    content={"error": f"PDF rendering failed: {str(e)[:200]}"}
                )

            # Clean up non-PDF temps before returning
            _unlink(upload_tmp)
            _unlink(converted_tmp)
            upload_tmp = converted_tmp = None

            pdf_path_to_delete = pdf_tmp
            pdf_tmp = None  # Don't delete in finally
            return FileResponse(
                path=pdf_path_to_delete,
                media_type='application/pdf',
                filename=f"{output_stem}.pdf",
                headers={"Content-Disposition": f'attachment; filename="{output_stem}.pdf"'},
                background=BackgroundTask(_unlink, pdf_path_to_delete),
            )

        # Return MusicXML
        _unlink(upload_tmp)
        upload_tmp = None
        resp_path = converted_tmp
        converted_tmp = None
        return FileResponse(
            path=resp_path,
            media_type='application/xml',
            filename=f"{output_stem}.musicxml",
            headers={"Content-Disposition": f'attachment; filename="{output_stem}.musicxml"'},
            background=BackgroundTask(_unlink, resp_path),
        )

    except Exception as e:
        logger.exception("Unexpected error in /convert")
        return JSONResponse(status_code=500, content={"error": "Internal server error."})
    finally:
        # Clean up any temps not consumed by FileResponse
        _unlink(upload_tmp)
        _unlink(converted_tmp)
        # Note: pdf_tmp / resp_path are owned by FileResponse — do NOT delete here
        gc.collect()


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
    Full pipeline: accept PNG (OMR) or MusicXML, convert clef, analyze range,
    return session_id + flagged measures + MIDI URLs.
    """
    import shutil as _shutil
    from music21 import converter as m21conv

    cleanup_expired()

    # Validate file
    contents = await file.read()
    try:
        validate_file(_FileMeta(file.filename, len(contents)))
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
        # Save upload to temp file
        suffix = os.path.splitext(file.filename or 'upload')[1].lower() or '.musicxml'
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

        # Move converted XML to session dir
        session_xml = os.path.join(session_dir, 'converted.musicxml')
        _shutil.move(converted_path, session_xml)

        # Parse and analyze
        score = m21conv.parse(session_xml)
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
            try:
                orig_bytes = measure_to_midi(score, n, midi_program=src_inst['midi_program'])
                with open(os.path.join(session_dir, f'm{n}_original.mid'), 'wb') as f:
                    f.write(orig_bytes)
            except Exception:
                pass

            try:
                shifted_score = apply_octave_shifts(score, {n: fm.suggestion})
                shifted_bytes = measure_to_midi(shifted_score, n, midi_program=tgt_inst['midi_program'])
                with open(os.path.join(session_dir, f'm{n}_shifted.mid'), 'wb') as f:
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
        import shutil as _shutil2
        _unlink(upload_tmp)
        if musicxml_path and musicxml_path != upload_tmp:
            omr_dir = os.path.dirname(musicxml_path)
            _unlink(musicxml_path)
            # Clean up entire OMR output dir (created by run_omr)
            if os.path.basename(omr_dir).startswith('clefswap_omr_'):
                _shutil2.rmtree(omr_dir, ignore_errors=True)


@app.get("/session/{session_id}/midi/{filename}")
def get_session_midi(session_id: str, filename: str):
    """Serve a MIDI file from a session's temp directory."""
    import re
    session = get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found or expired."})

    # Whitelist valid filenames (only server-generated names allowed)
    if not re.match(r'^[a-zA-Z0-9_]+$', filename):
        return JSONResponse(status_code=400, content={"error": "Invalid filename."})

    midi_path = os.path.realpath(os.path.join(session['dir'], f"{filename}.mid"))
    session_dir = os.path.realpath(session['dir'])
    if not midi_path.startswith(session_dir + os.sep):
        return JSONResponse(status_code=400, content={"error": "Invalid filename."})

    if not os.path.exists(midi_path):
        return JSONResponse(status_code=404, content={"error": f"MIDI file not found: {filename}"})

    with open(midi_path, 'rb') as f:
        content = f.read()
    return Response(content=content, media_type='audio/midi')


@app.post("/finalize")
async def finalize(req: FinalizeRequest):
    """Apply approved octave shifts and return the final PDF or MusicXML."""
    from music21 import converter as m21conv

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
        score = m21conv.parse(xml_path)

        # Apply approved shifts (JSON keys come in as strings)
        try:
            shifts = {int(k): v for k, v in req.shifts.items()}
        except (ValueError, TypeError):
            return JSONResponse(status_code=400, content={"error": "Shift keys must be integer measure numbers."})
        if shifts:
            score = apply_octave_shifts(score, shifts)

        # Write final MusicXML to temp file
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
        delete_session(req.session_id)
        return JSONResponse(status_code=500, content={"error": f"Finalize failed: {str(e)[:200]}"})


def _unlink(path):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass
