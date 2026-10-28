#!/usr/bin/env python
import io
import os
import sys
import tempfile
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core import storage, config
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


def make_upload(data: bytes, filename: str = "test.pdf", content_type: str = "application/pdf"):
    file = UploadFile(filename=filename, file=io.BytesIO(data), headers=Headers({"content-type": content_type}))
    return file


def run_tests():
    with tempfile.TemporaryDirectory() as td:
        upload_dir = Path(td) / "uploads"
        config.settings.UPLOAD_DIR = str(upload_dir)
        storage.settings.UPLOAD_DIR = str(upload_dir)
        s = LocalStorage(str(upload_dir))

        # 1. valid PDF
        data = PDF_MAGIC + b"hello"
        up = make_upload(data, "doc.pdf", "application/pdf")
        res = s.save(up, "docs")
        p = Path(s.upload_dir) / res.relative_path
        assert p.exists(), "pdf not saved"
        assert len(p.name) == 32 + 4
        assert p.name.endswith(".pdf")
        assert res.size_bytes == len(data)
        import hashlib
        assert res.sha256 == hashlib.sha256(data).hexdigest()
        print("1 ok")

        # 2. jpg/png
        jpg = JPG_MAGIC + b"123"
        up = make_upload(jpg, "photo.jpg", "image/jpeg")
        res = s.save(up, "photos")
        p = Path(s.upload_dir) / res.relative_path
        assert p.name.endswith(".jpg")
        png = PNG_MAGIC + b"abc"
        up2 = make_upload(png, "img.png", "image/png")
        res2 = s.save(up2, "photos")
        p2 = Path(s.upload_dir) / res2.relative_path
        assert p2.name.endswith(".png")
        print("2 ok")

        # 3. weird names
        data = PDF_MAGIC + b"x"
        up = make_upload(data, "../../etc/passwd.pdf", "application/pdf")
        res = s.save(up, "docs")
        assert ".." not in res.relative_path
        assert "passwd" not in Path(res.relative_path).name
        p = Path(s.upload_dir) / res.relative_path
        assert p.exists()
        up2 = make_upload(data, "résumé final (1).pdf", "application/pdf")
        res2 = s.save(up2, "docs")
        assert "résumé" not in Path(res2.relative_path).name
        p2 = Path(s.upload_dir) / res2.relative_path
        assert p2.exists()
        print("3 ok")

        # 4
        try:
            up = make_upload(b"MZ fake exe", "bad.pdf", "application/pdf")
            s.save(up, "docs")
            assert False
        except InvalidFileType:
            pass
        try:
            up2 = make_upload(b"hello world", "note.pdf", "application/pdf")
            s.save(up2, "docs")
            assert False
        except InvalidFileType:
            pass
        print("4 ok")

        # 5
        png = PNG_MAGIC + b"data"
        up = make_upload(png, "img.pdf", "application/pdf")
        try:
            s.save(up, "docs")
            assert False
        except InvalidFileType:
            pass
        print("5 ok")

        # 6
        config.settings.MAX_UPLOAD_BYTES = 100
        storage.settings.MAX_UPLOAD_BYTES = 100
        data = PDF_MAGIC + b"x" * (100 - len(PDF_MAGIC))
        assert len(data) == 100
        up = make_upload(data, "a.pdf", "application/pdf")
        res = s.save(up, "docs")
        assert res.size_bytes == 100
        data2 = PDF_MAGIC + b"x" * (101 - len(PDF_MAGIC))
        up2 = make_upload(data2, "b.pdf", "application/pdf")
        try:
            s.save(up2, "docs")
            assert False
        except FileTooLarge:
            pass
        docs = Path(s.upload_dir) / "docs"
        for f in docs.glob("*.part"):
            assert False, "partial left"
        assert len(list(docs.glob("*.pdf"))) >= 1
        print("6 ok")

        # 7
        try:
            up = make_upload(b"", "empty.pdf", "application/pdf")
            s.save(up, "docs")
            assert False
        except EmptyFile:
            pass
        print("7 ok")

        # 8
        data = PDF_MAGIC + b"x"
        for bad in ["", "../x", "a/b", "A", "a.b"]:
            try:
                up = make_upload(data, "a.pdf", "application/pdf")
                s.save(up, bad)
                assert False
            except UnsafePath:
                pass
        print("8 ok")

        # 9
        try:
            s.open_path("../../etc/passwd")
            assert False
        except UnsafePath:
            pass
        try:
            s.open_path("/etc/passwd")
            assert False
        except UnsafePath:
            pass
        # symlink
        outside = Path(s.upload_dir).parent / "outside.txt"
        outside.write_text("hi")
        link = Path(s.upload_dir) / "docs" / "link2.txt"
        (Path(s.upload_dir) / "docs").mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(outside, link)
            try:
                s.open_path("docs/link2.txt")
                assert False
            except UnsafePath:
                pass
        except Exception:
            pass
        print("9 ok")

        # 10
        data = PDF_MAGIC + b"x"
        up = make_upload(data, "a.pdf", "application/pdf")
        res = s.save(up, "docs")
        s.delete(res.relative_path)
        s.delete(res.relative_path)
        s.delete("docs/nonexist.pdf")
        print("10 ok")

        # 11
        try:
            s.delete("../../etc/passwd")
            assert False
        except UnsafePath:
            pass
        print("11 ok")

        # 12
        try:
            up = make_upload(b"notpdf", "x.pdf", "application/pdf")
            s.save(up, "docs")
            assert False
        except Exception:
            pass
        docs = Path(s.upload_dir) / "docs"
        if docs.exists():
            for f in docs.glob("*.part"):
                assert False
        print("12 ok")

        # 13
        data = PDF_MAGIC + b"x"
        up1 = make_upload(data, "a.pdf", "application/pdf")
        up2 = make_upload(data, "b.pdf", "application/pdf")
        r1 = s.save(up1, "docs")
        r2 = s.save(up2, "docs")
        assert r1.relative_path != r2.relative_path
        print("13 ok")

        # 14
        assert storage_error_to_http(FileTooLarge()).status_code == 413
        assert storage_error_to_http(InvalidFileType()).status_code == 415
        assert storage_error_to_http(EmptyFile()).status_code == 400
        assert storage_error_to_http(UnsafePath()).status_code == 400
        print("14 ok")

        # 15
        config.settings.MAX_UPLOAD_BYTES = 25 * 1024 * 1024
        storage.settings.MAX_UPLOAD_BYTES = 25 * 1024 * 1024

        class CountingBytesIO(io.BytesIO):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.max_read = 0

            def read(self, size=-1):
                if size > self.max_read:
                    self.max_read = size
                return super().read(size)

        data = PDF_MAGIC + b"x" * (25 * 1024 * 1024 - len(PDF_MAGIC) + 5)
        bio = CountingBytesIO(data)
        up = UploadFile(filename="big.pdf", file=bio, headers=Headers({"content-type": "application/pdf"}))
        try:
            s.save(up, "docs")
            assert False
        except FileTooLarge:
            pass
        assert bio.max_read <= 1024 * 1024 + 32
        print("15 ok")

    print("ALL OK")


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise
