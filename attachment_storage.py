"""Optional ticket file uploads: stored under app-configured upload root."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

KIND_TICKET = "ticket"
KIND_REMARK = "remark"
KIND_RESOLUTION = "resolution"

MAX_BYTES_PER_FILE = 8 * 1024 * 1024
MAX_FILES_PER_REQUEST = 10

ALLOWED_EXT = frozenset(
    {
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "txt",
        "csv",
        "md",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "zip",
        "odt",
        "ods",
    }
)


def _extension(filename: str) -> str | None:
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXT else None


def save_uploaded_files(
    upload_root: Path,
    cursor: Any,
    ticket_id: int,
    user_id: int,
    kind: str,
    comment_id: int | None,
    files: list[FileStorage],
) -> list[str]:
    """
    Persist files and INSERT rows into ticket_attachments.
    Does not commit. Returns human-readable errors (empty list = success).
    """
    errors: list[str] = []
    saved = 0
    dest_dir = upload_root / str(ticket_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        if saved >= MAX_FILES_PER_REQUEST:
            errors.append(f"At most {MAX_FILES_PER_REQUEST} files per upload.")
            break
        if not f or not f.filename or not str(f.filename).strip():
            continue
        ext = _extension(f.filename)
        if not ext:
            errors.append(
                f"File type not allowed (skipped): {secure_filename(f.filename)}"
            )
            continue

        data = f.read()
        if len(data) > MAX_BYTES_PER_FILE:
            errors.append(
                f"File too large (max 8 MB): {secure_filename(f.filename)}"
            )
            continue

        stored_file = f"{uuid.uuid4().hex}.{ext}"
        rel_path = f"{ticket_id}/{stored_file}"
        abs_path = dest_dir / stored_file
        abs_path.write_bytes(data)

        orig = secure_filename(f.filename) or stored_file
        if len(orig) > 200:
            orig = orig[:200]
        mime = (f.content_type or "").strip() or None
        size = len(data)

        cursor.execute(
            """
            INSERT INTO ticket_attachments (
                ticket_id, comment_id, kind, stored_path,
                original_name, content_type, file_size, uploaded_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ticket_id,
                comment_id,
                kind,
                rel_path,
                orig,
                mime,
                size,
                user_id,
            ),
        )
        saved += 1

    return errors


def delete_ticket_files(upload_root: Path, ticket_id: int) -> None:
    """Remove on-disk folder for a ticket (best effort)."""
    path = upload_root / str(ticket_id)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
