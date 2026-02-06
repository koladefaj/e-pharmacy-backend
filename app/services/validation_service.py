import logging

import magic
from fastapi import HTTPException, UploadFile, status

# Initialize logger for security events
logger = logging.getLogger(__name__)

# CONFIGURATION
# Allowed MIME types mapped to valid extensions
ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
}

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def validate_file_content(file: UploadFile):
    """
    Validates uploaded files:
    1. Size Check
    2. MIME type check via magic bytes
    3. Extension consistency check
    """

    # SIZE VALIDATION
    file_size = 0
    if hasattr(file, "size") and file.size:
        file_size = file.size
    else:
        # Fallback for clients without size headers
        await file.seek(0, 2)  # move to end
        file_size = await file.tell()
        await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"Security: Blocked oversized file ({file_size} bytes)")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large.",
        )

    # CONTENT VALIDATION

    try:
        header = await file.read(2048)  # first 2KB is enough
        file_mime_type = magic.from_buffer(header, mime=True)
        await file.seek(0)  # reset for next service

    except Exception as e:
        logger.error(f"Magic bytes read error: {e}")
        raise HTTPException(status_code=400, detail="Could not read file headers.")

    if file_mime_type not in ALLOWED_MIME_TYPES:

        logger.warning(
            "File validation failed",
            extra={
                "mime_type": file_mime_type,
                "filename": file.filename,
                "reason": "unsupported_mime",
                "client_ip": getattr(file, "client", "unknown"),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        )

    # EXTENSION CONSISTENCY
    file_ext = "." + file.filename.split(".")[-1].lower() if file.filename else ""
    if file_ext not in ALLOWED_MIME_TYPES[file_mime_type]:
        logger.error(f"Extension mismatch: {file_ext} vs {file_mime_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match the actual file content.",
        )

    # Final cursor reset for downstream processing
    await file.seek(0)
    logger.info(f"Security: File {file.filename} passed validation ({file_mime_type})")
    return True
