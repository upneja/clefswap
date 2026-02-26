"""
OMR (Optical Music Recognition) wrapper around the oemer CLI.
Converts sheet music images (PNG, JPG) to MusicXML using oemer.
"""
import glob
import logging
import os
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
