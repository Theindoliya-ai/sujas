import os
import uuid
from fastapi import UploadFile, HTTPException
import cloudinary
import cloudinary.uploader

# ── Cloudinary config ─────────────────────────────────────────────────────────
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# PDF magic bytes: every valid PDF starts with %PDF
_PDF_MAGIC = b"%PDF"


def _is_pdf_content(data: bytes) -> bool:
    return data[:4] == _PDF_MAGIC


async def save_pdf(file: UploadFile) -> str:
    """
    Validate and upload a PDF to Cloudinary.
    Returns the Cloudinary secure URL (stored in DB).
    Raises HTTP 400 on invalid file type, bad magic bytes, or size exceeded.
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

    public_id = f"sujas_pdfs/{uuid.uuid4().hex}"

    result = cloudinary.uploader.upload(
        contents,
        public_id=public_id,
        resource_type="raw",
        format="pdf",
    )

    return result["secure_url"]  # full https URL saved in DB


def delete_file(pdf_url: str) -> None:
    """
    Delete a PDF from Cloudinary using its secure URL.
    Also handles legacy local file paths gracefully.
    No-op if pdf_url is empty or deletion fails.
    """
    if not pdf_url:
        return

    try:
        if "cloudinary.com" in pdf_url:
            # Extract public_id from URL:
            # https://res.cloudinary.com/{cloud}/raw/upload/v{ver}/{folder}/{name}.pdf
            url_path = pdf_url.split("?")[0]          # strip query params
            parts = url_path.split("/upload/")
            if len(parts) == 2:
                after_upload = parts[1]
                # Strip optional version segment  v1234567890/
                if after_upload.startswith("v") and "/" in after_upload:
                    after_upload = after_upload.split("/", 1)[1]
                # Strip file extension
                public_id = after_upload.rsplit(".", 1)[0] if "." in after_upload else after_upload
                cloudinary.uploader.destroy(public_id, resource_type="raw")
        else:
            # Legacy: bare filename or full local path
            upload_dir = os.getenv("UPLOAD_DIR", "uploads")
            filepath = (
                pdf_url
                if os.sep in pdf_url
                else os.path.join(upload_dir, pdf_url)
            )
            if os.path.exists(filepath):
                os.remove(filepath)
    except Exception:
        pass  # deletion failure is non-fatal; log in production if needed
