import os
import uuid
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# PDF magic bytes: every valid PDF starts with %PDF
_PDF_MAGIC = b"%PDF"


def _ensure_upload_dir() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _is_pdf_content(data: bytes) -> bool:
    return data[:4] == _PDF_MAGIC


async def save_pdf(file: UploadFile) -> str:
    """
    Validate and persist an uploaded PDF.
    Returns the stored filename (not the full path).
    Raises HTTP 400 on invalid file type or size.
    """
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")

    contents = await file.read()

    if not _is_pdf_content(contents):
        raise HTTPException(
            status_code=400,
            detail="File content does not appear to be a valid PDF.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the {MAX_FILE_SIZE_MB} MB limit.",
        )

    _ensure_upload_dir()
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    return filename  # store only the filename in DB


def delete_file(filename: str) -> None:
    """Remove a stored PDF by filename.  No-op if file is absent."""
    if not filename:
        return
    # Accept both bare filename and legacy full-path values
    filepath = filename if os.sep in filename else os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
