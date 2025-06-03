# utils/file_utils.py

import os
import magic  # If python‐magic is available; else rely on extension + minimal checks
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'.pdf'}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS

def validate_pdf(file_storage) -> bool:
    """
    Ensures the uploaded file is indeed a PDF (by extension and file header).
    """
    filename = file_storage.filename
    if not allowed_file(filename):
        return False

    # Check magic bytes ("%PDF" at start)
    file_storage.stream.seek(0)
    start_bytes = file_storage.stream.read(4)
    file_storage.stream.seek(0)
    if start_bytes != b'%PDF':
        return False

    # Check file size
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_FILE_SIZE_BYTES:
        return False

    return True

def save_upload(file_storage, subfolder: str) -> str:
    """
    Saves the file under static/uploads/<subfolder>/secure_filename.
    Returns the relative path (e.g. "static/uploads/doctor_reports/abc.pdf").
    """
    filename = secure_filename(file_storage.filename)
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file_storage.save(file_path)
    # Return the relative path (we will store this in DB for retrieval)
    rel_path = os.path.join('static', 'uploads', subfolder, filename)
    return rel_path
