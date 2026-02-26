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
from fastapi.responses import FileResponse, JSONResponse

from backend.clef_map import CLEF_LABELS
from backend.converter import convert_clef
from backend.renderer import RendererUnavailable, detect_renderer, render_to_pdf
from backend.validators import ValidationError, validate_clef_pair, validate_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        # Wrap with metadata for validate_file (UploadFile may not expose .size)
        class _FileMeta:
            def __init__(self, filename, size):
                self.filename = filename
                self.size = size

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

            return FileResponse(
                path=pdf_tmp,
                media_type='application/pdf',
                filename=f"{output_stem}.pdf",
                headers={"Content-Disposition": f'attachment; filename="{output_stem}.pdf"'},
            )

        # Return MusicXML
        _unlink(upload_tmp)
        upload_tmp = None
        resp_path = converted_tmp
        converted_tmp = None  # Don't clean up — FileResponse needs it

        return FileResponse(
            path=resp_path,
            media_type='application/xml',
            filename=f"{output_stem}.musicxml",
            headers={"Content-Disposition": f'attachment; filename="{output_stem}.musicxml"'},
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


def _unlink(path):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass
