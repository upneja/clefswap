"""
PDF Renderer: detects available rendering tools and converts MusicXML → PDF.

Priority:
  1. LilyPond (via music21's lily.pdf writer)
  2. MuseScore 4/3 CLI
  3. None (caller receives RendererUnavailable)
"""
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_LILYPOND_CANDIDATES = [
    '/opt/homebrew/bin/lilypond',
    '/usr/local/bin/lilypond',
    '/usr/bin/lilypond',
    shutil.which('lilypond') or '',
]

_MUSESCORE_CANDIDATES = [
    '/usr/bin/musescore4',
    '/usr/bin/musescore',
    '/Applications/MuseScore 4.app/Contents/MacOS/mscore',
    '/Applications/MuseScore 3.app/Contents/MacOS/mscore',
    shutil.which('musescore4') or '',
    shutil.which('musescore') or '',
]


class RendererUnavailable(Exception):
    """No PDF renderer (LilyPond or MuseScore) is available."""
    pass


def _find_executable(candidates: list) -> str | None:
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def detect_renderer() -> str:
    """Return 'lilypond', 'musescore', or 'none'."""
    if _find_executable(_LILYPOND_CANDIDATES):
        return 'lilypond'
    if _find_executable(_MUSESCORE_CANDIDATES):
        return 'musescore'
    return 'none'


def render_to_pdf(musicxml_path: str, stem: str) -> str:
    """
    Convert a MusicXML file to PDF.

    Args:
        musicxml_path: Path to .musicxml input.
        stem: Base name for temp output file.

    Returns:
        Path to rendered PDF temp file. Caller must delete.

    Raises:
        RendererUnavailable: if no renderer found.
        RuntimeError: if rendering fails.
    """
    renderer = detect_renderer()
    if renderer == 'none':
        raise RendererUnavailable(
            "No PDF renderer found. Install LilyPond: brew install lilypond"
        )
    if renderer == 'lilypond':
        return _render_lilypond(musicxml_path, stem)
    return _render_musescore(musicxml_path, stem)


def _render_lilypond(musicxml_path: str, stem: str) -> str:
    """Use music21's LilyPond integration to render MusicXML → PDF."""
    from music21 import converter as m21conv
    from music21 import environment as m21env

    # Tell music21 where LilyPond lives
    lilypond_bin = _find_executable(_LILYPOND_CANDIDATES)
    env = m21env.Environment()
    env['lilypondPath'] = lilypond_bin

    score = m21conv.parse(musicxml_path)
    tmp_dir = tempfile.mkdtemp(prefix='clefswap_render_')

    try:
        # music21 writes a .ly file then calls lilypond to compile
        pdf_path = os.path.join(tmp_dir, f"{stem}.pdf")
        result_path = score.write('lily.pdf', fp=pdf_path)

        # music21 returns the actual output path — use it if provided
        if result_path and os.path.exists(str(result_path)):
            actual_pdf = str(result_path)
        elif os.path.exists(pdf_path):
            actual_pdf = pdf_path
        else:
            # Scan the tmp_dir for any .pdf that appeared
            candidates = [
                os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
                if f.endswith('.pdf')
            ]
            if candidates:
                actual_pdf = candidates[0]
            else:
                raise RuntimeError(f"LilyPond did not produce a PDF in {tmp_dir}")

        # Move to a standalone temp file so cleanup of tmp_dir is safe
        final = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='clefswap_')
        final.close()
        shutil.copy2(actual_pdf, final.name)
        return final.name

    except Exception as e:
        # CLI fallback: write .ly then compile directly
        logger.warning(f"music21 lily.pdf failed ({e}), trying CLI fallback")
        return _render_lilypond_cli(musicxml_path, stem, lilypond_bin, tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _render_lilypond_cli(musicxml_path: str, stem: str, lilypond_bin: str, tmp_dir: str) -> str:
    """Fallback: export .ly via music21, compile with lilypond CLI."""
    from music21 import converter as m21conv
    score = m21conv.parse(musicxml_path)

    ly_dir = tempfile.mkdtemp(prefix='clefswap_ly_')
    try:
        ly_path = os.path.join(ly_dir, f"{stem}.ly")
        result_path = score.write('lilypond', fp=ly_path)

        # Resolve the actual .ly path
        if result_path and os.path.exists(str(result_path)):
            ly_path = str(result_path)
        elif not os.path.exists(ly_path):
            alt = ly_path + '.ly'
            if os.path.exists(alt):
                ly_path = alt
            else:
                # Scan ly_dir for any .ly file
                candidates = [
                    os.path.join(ly_dir, f) for f in os.listdir(ly_dir)
                    if f.endswith('.ly')
                ]
                if candidates:
                    ly_path = candidates[0]
                else:
                    raise RuntimeError(f"music21 did not produce a .ly file in {ly_dir}")

        out_stem = os.path.join(ly_dir, stem)
        result = subprocess.run(
            [lilypond_bin, '--pdf', '-o', out_stem, ly_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"LilyPond CLI failed:\n{result.stderr[:500]}")

        pdf_path = out_stem + '.pdf'
        if not os.path.exists(pdf_path):
            # Scan for any .pdf in ly_dir
            candidates = [
                os.path.join(ly_dir, f) for f in os.listdir(ly_dir)
                if f.endswith('.pdf')
            ]
            if candidates:
                pdf_path = candidates[0]
            else:
                raise RuntimeError(f"LilyPond CLI produced no PDF at {out_stem}.pdf")

        final = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='clefswap_')
        final.close()
        shutil.move(pdf_path, final.name)
        return final.name
    finally:
        shutil.rmtree(ly_dir, ignore_errors=True)


def _render_musescore(musicxml_path: str, stem: str) -> str:
    """MuseScore CLI: MusicXML → PDF."""
    mscore = _find_executable(_MUSESCORE_CANDIDATES)
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='clefswap_')
    tmp.close()
    try:
        result = subprocess.run(
            [mscore, '--export-to', tmp.name, musicxml_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(f"MuseScore failed:\n{result.stderr[:500]}")
        if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
            raise RuntimeError("MuseScore produced no output")
        return tmp.name
    except Exception:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise
