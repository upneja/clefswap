import os
from backend.clef_map import CLEF_MAP

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.mxl', '.musicxml', '.xml', '.png', '.jpg', '.jpeg'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


class ValidationError(Exception):
    """User-facing validation error."""
    pass


def validate_file(file) -> None:
    """
    Validate uploaded file object.
    Expects: file.filename (str), file.size (int bytes).
    Raises: ValidationError with user-facing message.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename.lower())[1]

    if ext == '.pdf':
        raise ValidationError(
            "PDF files are not supported. Please upload a MusicXML file "
            "(.mxl, .musicxml, .xml) or a sheet music image (.png, .jpg)."
        )
    if ext in ('.mid', '.midi'):
        raise ValidationError(
            "MIDI files are not supported. Please use a MusicXML file "
            "(.mxl or .musicxml). You can export this from MuseScore, Sibelius, or Finale."
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Please upload a MusicXML file "
            f"(.mxl, .musicxml, .xml) or a sheet music image (.png, .jpg)."
        )

    size = getattr(file, 'size', None)
    if size is not None and size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File is too large ({size / 1024 / 1024:.1f}MB). Maximum file size is 10MB."
        )


def validate_clef_pair(source_clef: str, target_clef: str) -> None:
    """
    Validate source and target clef names.
    Raises: ValidationError with user-facing message.
    """
    if source_clef not in CLEF_MAP:
        raise ValidationError(f"Unknown source clef: '{source_clef}'.")
    if target_clef not in CLEF_MAP:
        raise ValidationError(f"Unknown target clef: '{target_clef}'.")
    if source_clef == target_clef:
        raise ValidationError(
            "Source and target clefs are the same. Please choose different clefs."
        )
