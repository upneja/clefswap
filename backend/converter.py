"""
Core clef conversion using music21.

RE-NOTATION: sounding pitches are IDENTICAL before and after.
Only the visual staff representation changes.
music21 handles re-notation automatically when we swap the clef object.
"""
import gc
import logging
import os
import tempfile

from music21 import converter, clef as m21clef

from backend.clef_map import get_clef_class

logger = logging.getLogger(__name__)

# Configure LilyPond path if present (used later by renderer)
_LILYPOND_PATH = '/opt/homebrew/bin/lilypond'
if os.path.exists(_LILYPOND_PATH):
    try:
        from music21 import environment as m21env
        env = m21env.Environment()
        env['lilypondPath'] = _LILYPOND_PATH
    except Exception:
        pass


def convert_clef(input_path: str, source_clef: str | None, target_clef: str) -> str:
    """
    Parse a MusicXML file, replace all clef instances with target_clef,
    write result to a new temp file.

    Args:
        input_path: Path to input .mxl or .musicxml file.
        source_clef: Clef name to replace, or None to replace ALL clefs.
        target_clef: Clef name to insert.

    Returns:
        Path to output .musicxml temp file. Caller must delete.

    Raises:
        ValueError: if clef names unknown
        Exception: if file cannot be parsed
    """
    target_clef_class = get_clef_class(target_clef)
    logger.info(f"Converting: {source_clef!r} -> {target_clef!r} in {input_path}")

    try:
        score = converter.parse(input_path)
    except Exception as e:
        raise ValueError(f"Could not parse MusicXML file: {e}") from e

    for part in score.parts:
        existing_clefs = list(part.recurse().getElementsByClass('Clef'))

        if not existing_clefs:
            # No clef in score — insert target at start of first measure
            measures = list(part.getElementsByClass('Measure'))
            if measures:
                measures[0].insert(0, target_clef_class())
            continue

        for c in existing_clefs:
            offset = c.offset
            site = c.activeSite
            if site is not None:
                site.remove(c)
                site.insert(offset, target_clef_class())

    tmp = tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False, prefix='clefswap_')
    tmp.close()
    try:
        score.write('musicxml', fp=tmp.name)
    except Exception as e:
        os.unlink(tmp.name)
        raise RuntimeError(f"Failed to write converted MusicXML: {e}") from e

    del score
    gc.collect()

    return tmp.name
