"""Private storage; no remote link fetching, extraction, or user path resolution."""

import hashlib, io, os, uuid, zipfile
from pathlib import Path
from flask import current_app, send_file
from ..academic.core import need

MIMES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "txt": "text/plain",
    "zip": "application/zip",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def root():
    p = Path(current_app.config["PRIVATE_STORAGE"]).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(f):
    name = Path((f.filename or "").replace("\\", "/")).name
    need(
        name
        and len(name) <= 240
        and not any(ord(c) < 32 or ord(c) == 127 for c in name),
        message="Tên file không hợp lệ",
    )
    ext = name.rsplit(".", 1)[-1].lower()
    need(ext in MIMES, message="Loại file không được hỗ trợ")
    raw = f.read(current_app.config["MAX_FILE_BYTES"] + 1)
    need(
        0 < len(raw) <= current_app.config["MAX_FILE_BYTES"],
        "QUOTA_EXCEEDED",
        "File phải nhỏ hơn hoặc bằng 10 MiB",
        413,
    )
    valid = False
    if ext == "pdf":
        valid = raw.startswith(b"%PDF-")
    elif ext == "png":
        valid = raw.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in ("jpg", "jpeg"):
        valid = raw.startswith(b"\xff\xd8\xff")
    elif ext == "txt":
        try:
            raw.decode("utf-8")
            valid = b"\x00" not in raw
        except UnicodeDecodeError:
            pass
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = z.namelist()
                valid = not any(n.lower().endswith("vbaproject.bin") for n in names)
                if ext != "zip":
                    valid = (
                        valid
                        and "[Content_Types].xml" in names
                        and any(
                            n.startswith(
                                {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}[ext]
                            )
                            for n in names
                        )
                    )
        except (zipfile.BadZipFile, ValueError):
            pass
    need(valid, "FILE_TYPE_MISMATCH", "Nội dung file không khớp định dạng cho phép")
    key = uuid.uuid4().hex
    temp = root() / (key + ".staging")
    final = root() / key
    try:
        with temp.open("xb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        temp.replace(final)
    finally:
        temp.unlink(missing_ok=True)
    return {
        "storage_key": key,
        "original_filename": name,
        "mime_type": MIMES[ext],
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def download(key, name, expected_hash=None):
    need(
        isinstance(key, str)
        and len(key) == 32
        and all(c in "0123456789abcdef" for c in key),
        "NOT_FOUND",
        "Không tìm thấy file",
        404,
    )
    p = root() / key
    need(
        p.is_file() and not p.is_symlink() and p.resolve().parent == root(),
        "NOT_FOUND",
        "Không tìm thấy file",
        404,
    )
    if expected_hash:
        need(
            hashlib.sha256(p.read_bytes()).hexdigest() == expected_hash,
            "FILE_INTEGRITY_ERROR",
            "File không khớp mã kiểm tra",
            409,
        )
    return send_file(
        p,
        as_attachment=True,
        download_name=name,
        mimetype="application/octet-stream",
        conditional=True,
    )
