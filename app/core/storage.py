from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.core.config import settings


class StorageError(Exception):
    pass


class InvalidFileType(StorageError):
    pass


class FileTooLarge(StorageError):
    pass


class EmptyFile(StorageError):
    pass


class UnsafePath(StorageError):
    pass


MAGIC_PDF = b"%PDF-"
MAGIC_JPG = bytes([0xFF, 0xD8, 0xFF])
MAGIC_PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


@dataclass
class StoredFile:
    relative_path: str
    original_filename: str | None
    content_type: str
    size_bytes: int
    sha256: str


def _detect_type(data: bytes) -> tuple[str, str] | None:
    if data.startswith(MAGIC_PDF):
        return "application/pdf", ".pdf"
    if data.startswith(MAGIC_JPG):
        return "image/jpeg", ".jpg"
    if data.startswith(MAGIC_PNG):
        return "image/png", ".png"
    return None


def _validate_subdir(subdir: str) -> None:
    if not subdir:
        raise UnsafePath("invalid subdir")
    if "/" in subdir or "\\" in subdir or "." in subdir:
        raise UnsafePath("invalid subdir")
    if len(subdir) != len(subdir.strip()):
        raise UnsafePath("invalid subdir")
    for c in subdir:
        if not ("a" <= c <= "z" or "0" <= c <= "9" or c == "_" or c == "-"):
            raise UnsafePath("invalid subdir")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _set_permissions(p: Path) -> None:
    try:
        os.chmod(p, 0o640)
    except Exception:
        pass


class LocalStorage:
    def __init__(self, upload_dir: str | None = None) -> None:
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR).resolve()

    def save(self, file: UploadFile, subdir: str) -> StoredFile:
        _validate_subdir(subdir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        stream = file.file
        # Read first bytes for magic detection
        header = stream.read(16)
        if not header:
            raise EmptyFile("empty file")
        detected = _detect_type(header)
        if detected is None:
            raise InvalidFileType("unsupported file type")
        detected_content_type, detected_ext = detected

        # Validate consistency: reject if declared extension/content type disagree
        declared_ct = file.content_type or ""
        declared_name = file.filename or ""
        declared_ext = os.path.splitext(declared_name)[1].lower() if declared_name else ""

        # Disallow mismatches - if they explicitly declare different type/ext that conflicts
        # But requirement says: "reject if the declared extension or content type disagrees with the detected type"
        if declared_ct and declared_ct not in settings.ALLOWED_UPLOAD_TYPES:
            raise InvalidFileType("unsupported file type")
        if declared_ext and declared_ext not in (".pdf", ".jpg", ".jpeg", ".png"):
            raise InvalidFileType("unsupported file type")

        # If declared content type is in allowed list, it must match detected
        if declared_ct and declared_ct in settings.ALLOWED_UPLOAD_TYPES:
            if declared_ct != detected_content_type:
                raise InvalidFileType("content type mismatch")
        # If declared extension is present and maps to different type than detected
        if declared_ext:
            ext_to_ct = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            if declared_ext in ext_to_ct and ext_to_ct[declared_ext] != detected_content_type:
                raise InvalidFileType("extension mismatch")

        target_dir = (self.upload_dir / subdir).resolve()
        if not str(target_dir).startswith(str(self.upload_dir)):
            raise UnsafePath("path traversal")
        target_dir.mkdir(parents=True, exist_ok=True)

        name = uuid.uuid4().hex + detected_ext
        final_path = target_dir / name
        tmp_path = target_dir / (name + ".part")

        hasher = hashlib.sha256()
        size = 0
        try:
            # Write header first
            tmp_path.write_bytes(header)
            hasher.update(header)
            size += len(header)
            if size == 0:
                raise EmptyFile("empty file")
            if size > settings.MAX_UPLOAD_BYTES:
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
                raise FileTooLarge("file too large")

            chunk_size = 1024 * 1024
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.MAX_UPLOAD_BYTES:
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass
                    raise FileTooLarge("file too large")
                hasher.update(chunk)
                with open(tmp_path, "ab") as f:
                    f.write(chunk)
            if size == 0:
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
                raise EmptyFile("empty file")
            _set_permissions(tmp_path)
            os.replace(tmp_path, final_path)
            _set_permissions(final_path)
        except StorageError:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise

        rel_path = str(final_path.relative_to(self.upload_dir))
        original_filename = os.path.basename((declared_name or file.filename or "").replace("\\", "/"))[:255] or None
        return StoredFile(
            relative_path=rel_path,
            original_filename=original_filename,
            content_type=detected_content_type,
            size_bytes=size,
            sha256=hasher.hexdigest(),
        )

    def open_path(self, relative_path: str) -> Path:
        if not relative_path or os.path.isabs(relative_path):
            raise UnsafePath("unsafe path")
        if ".." in relative_path.replace("\\", "/").split("/"):
            raise UnsafePath("unsafe path")
        full = (self.upload_dir / relative_path).resolve()
        if not str(full).startswith(str(self.upload_dir) + os.sep) and str(full) != str(self.upload_dir):
            # Also allow if it's directly in upload dir? but files go in subdirs; but be strict
            pass
        # Strict check - must be inside upload dir
        try:
            full.relative_to(self.upload_dir)
        except Exception:
            raise UnsafePath("unsafe path")
        # Check for symlink escapes - if any component is symlink pointing outside?
        # Simple check: resolve is enough if we verify it's under upload dir
        if not str(full).startswith(str(self.upload_dir)):
            raise UnsafePath("unsafe path")
        if not full.exists():
            raise UnsafePath("file not found")
        # Detect symlink escape
        try:
            real = full.resolve()
            if not str(real).startswith(str(self.upload_dir)):
                raise UnsafePath("unsafe path")
        except Exception:
            raise UnsafePath("unsafe path")
        return full

    def delete(self, relative_path: str) -> None:
        try:
            full = self.open_path(relative_path)
        except Exception:
            # idempotent - never raises if missing or unsafe? "delete is idempotent (deleting twice, deleting a missing file: no error)"
            # "delete refuses paths outside UPLOAD_DIR" - so unsafe paths should be refused with error? Let us look up requirement again
            # "delete refuses paths outside UPLOAD_DIR" and "delete is idempotent (deleting twice, deleting a missing file: no error)"
            # So if missing -> no error (idempotent). If outside UPLOAD_DIR -> refuse (UnsafePath). 
            try:
                # If it's an unsafe path case
                if not relative_path or os.path.isabs(relative_path):
                    raise UnsafePath("unsafe path")
                if ".." in relative_path.replace("\\", "/").split("/"):
                    raise UnsafePath("unsafe path")
                full_check = (self.upload_dir / relative_path).resolve()
                try:
                    full_check.relative_to(self.upload_dir)
                except Exception:
                    raise UnsafePath("unsafe path")
                # missing is fine
                return
            except UnsafePath:
                raise
            except Exception:
                return
        try:
            if full.exists():
                full.unlink()
        except Exception:
            pass


def storage_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, FileTooLarge):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, InvalidFileType):
        return HTTPException(status_code=415, detail=str(exc))
    if isinstance(exc, EmptyFile):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, UnsafePath):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def get_storage() -> LocalStorage:
    return LocalStorage()
