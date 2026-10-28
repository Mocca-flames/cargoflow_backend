import io
import os
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core import storage
from app.core.storage import (
    EmptyFile,
    FileTooLarge,
    InvalidFileType,
    LocalStorage,
    UnsafePath,
    storage_error_to_http,
)


PDF_MAGIC = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
JPG_MAGIC = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00\x10JFIF"
PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"\x00\x00\x00\rIHDR"


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(storage.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    s = LocalStorage(str(tmp_path / "uploads"))
    return s


def make_upload(data: bytes, filename: str = "test.pdf", content_type: str = "application/pdf"):
    file = UploadFile(filename=filename, file=io.BytesIO(data), headers=Headers({"content-type": content_type}))
    return file


def test_valid_pdf_saved(tmp_storage):
    data = PDF_MAGIC + b"hello"
    up = make_upload(data, "doc.pdf", "application/pdf")
    res = tmp_storage.save(up, "docs")
    p = Path(tmp_storage.upload_dir) / res.relative_path
    assert p.exists()
    assert len(p.name) == 32 + 4  # 32 hex + .pdf
    assert p.name.endswith(".pdf")
    assert res.size_bytes == len(data)
    import hashlib

    assert res.sha256 == hashlib.sha256(data).hexdigest()


def test_valid_jpeg_png(tmp_storage):
    jpg = JPG_MAGIC + b"123"
    up = make_upload(jpg, "photo.jpg", "image/jpeg")
    res = tmp_storage.save(up, "photos")
    p = Path(tmp_storage.upload_dir) / res.relative_path
    assert p.name.endswith(".jpg")

    png = PNG_MAGIC + b"abc"
    up2 = make_upload(png, "img.png", "image/png")
    res2 = tmp_storage.save(up2, "photos")
    p2 = Path(tmp_storage.upload_dir) / res2.relative_path
    assert p2.name.endswith(".png")


def test_weird_original_names_never_on_disk(tmp_storage):
    data = PDF_MAGIC + b"x"
    up = make_upload(data, "../../etc/passwd.pdf", "application/pdf")
    res = tmp_storage.save(up, "docs")
    assert ".." not in res.relative_path
    assert "passwd" not in Path(res.relative_path).name
    p = Path(tmp_storage.upload_dir) / res.relative_path
    assert p.exists()

    up2 = make_upload(data, "résumé final (1).pdf", "application/pdf")
    res2 = tmp_storage.save(up2, "docs")
    assert "résumé" not in Path(res2.relative_path).name
    p2 = Path(tmp_storage.upload_dir) / res2.relative_path
    assert p2.exists()


def test_exe_or_text_renamed_to_pdf_rejected(tmp_storage):
    up = make_upload(b"MZ fake exe", "bad.pdf", "application/pdf")
    with pytest.raises(InvalidFileType):
        tmp_storage.save(up, "docs")
    up2 = make_upload(b"hello world", "note.pdf", "application/pdf")
    with pytest.raises(InvalidFileType):
        tmp_storage.save(up2, "docs")


def test_png_uploaded_as_pdf_rejected(tmp_storage):
    png = PNG_MAGIC + b"data"
    up = make_upload(png, "img.pdf", "application/pdf")
    with pytest.raises(InvalidFileType):
        tmp_storage.save(up, "docs")


def test_exact_max_and_over(tmp_storage, monkeypatch):
    from app.core import config, storage

    monkeypatch.setattr(config.settings, "MAX_UPLOAD_BYTES", 100)
    monkeypatch.setattr(storage.settings, "MAX_UPLOAD_BYTES", 100)
    data = PDF_MAGIC + b"x" * (100 - len(PDF_MAGIC))
    assert len(data) == 100
    up = make_upload(data, "a.pdf", "application/pdf")
    res = tmp_storage.save(up, "docs")
    assert res.size_bytes == 100
    # +1
    data2 = PDF_MAGIC + b"x" * (101 - len(PDF_MAGIC))
    up2 = make_upload(data2, "b.pdf", "application/pdf")
    with pytest.raises(FileTooLarge):
        tmp_storage.save(up2, "docs")
    # no partial left
    docs = Path(tmp_storage.upload_dir) / "docs"
    for f in docs.glob("*.part"):
        assert False, "partial file left"
    assert len(list(docs.glob("*.pdf"))) == 1


def test_empty_rejected(tmp_storage):
    up = make_upload(b"", "empty.pdf", "application/pdf")
    with pytest.raises(EmptyFile):
        tmp_storage.save(up, "docs")


def test_invalid_subdirs(tmp_storage):
    data = PDF_MAGIC + b"x"
    for bad in ["", "../x", "a/b", "A", "a.b"]:
        up = make_upload(data, "a.pdf", "application/pdf")
        with pytest.raises(UnsafePath):
            tmp_storage.save(up, bad)


def test_open_path_rejects(tmp_storage):
    with pytest.raises(UnsafePath):
        tmp_storage.open_path("../../etc/passwd")
    with pytest.raises(UnsafePath):
        tmp_storage.open_path("/etc/passwd")
    # symlink outside
    outside = Path(tmp_storage.upload_dir).parent / "outside.txt"
    outside.write_text("hi")
    link = Path(tmp_storage.upload_dir) / "docs" / "link.txt"
    (Path(tmp_storage.upload_dir) / "docs").mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link)
    except Exception:
        pytest.skip("symlink not supported")
    with pytest.raises(UnsafePath):
        tmp_storage.open_path("docs/link.txt")


def test_delete_idempotent(tmp_storage):
    data = PDF_MAGIC + b"x"
    up = make_upload(data, "a.pdf", "application/pdf")
    res = tmp_storage.save(up, "docs")
    tmp_storage.delete(res.relative_path)
    tmp_storage.delete(res.relative_path)  # second time no error
    tmp_storage.delete("docs/nonexist.pdf")  # missing no error


def test_delete_refuses_outside(tmp_storage):
    with pytest.raises(UnsafePath):
        tmp_storage.delete("../../etc/passwd")


def test_no_temp_files_left(tmp_storage):
    # try bad file
    up = make_upload(b"notpdf", "x.pdf", "application/pdf")
    try:
        tmp_storage.save(up, "docs")
    except Exception:
        pass
    docs = Path(tmp_storage.upload_dir) / "docs"
    if docs.exists():
        for f in docs.glob("*.part"):
            assert False


def test_two_uploads_different_names(tmp_storage):
    data = PDF_MAGIC + b"x"
    up1 = make_upload(data, "a.pdf", "application/pdf")
    up2 = make_upload(data, "b.pdf", "application/pdf")
    r1 = tmp_storage.save(up1, "docs")
    r2 = tmp_storage.save(up2, "docs")
    assert r1.relative_path != r2.relative_path


def test_storage_error_to_http_mapping():
    from fastapi import HTTPException

    assert storage_error_to_http(FileTooLarge()) .status_code == 413
    assert storage_error_to_http(InvalidFileType()) .status_code == 415
    assert storage_error_to_http(EmptyFile()) .status_code == 400
    assert storage_error_to_http(UnsafePath()) .status_code == 400


def test_large_upload_chunked(tmp_storage, monkeypatch):
    from app.core import config, storage

    monkeypatch.setattr(config.settings, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
    monkeypatch.setattr(storage.settings, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)

    class CountingBytesIO(io.BytesIO):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.max_read = 0

        def read(self, size=-1):
            if size > self.max_read:
                self.max_read = size
            return super().read(size)

    data = PDF_MAGIC + b"x" * (25 * 1024 * 1024 - len(PDF_MAGIC) + 5)  # over
    bio = CountingBytesIO(data)
    up = UploadFile(filename="big.pdf", file=bio, headers=Headers({"content-type": "application/pdf"}))
    with pytest.raises(FileTooLarge):
        tmp_storage.save(up, "docs")
    assert bio.max_read <= 1024 * 1024 + 16
