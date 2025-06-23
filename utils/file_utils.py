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

def save_upload(file_storage, patient_id: str, doc_type: str) -> str:
    """
    Saves the uploaded file under:
        static/uploads/<patient_id>/<doc_type>/<secure_filename>
    Returns the relative path, e.g.
        "static/uploads/PAT0001/doctor_docs/myreport.pdf"
    """
    # sanitize the filename
    filename = secure_filename(file_storage.filename)

    # build the directory: static/uploads/<patient_id>/<doc_type>
    upload_dir = os.path.join(
        current_app.root_path,
        'static', 'uploads',
        patient_id,
        doc_type
    )
    os.makedirs(upload_dir, exist_ok=True)

    # save the file
    file_path = os.path.join(upload_dir, filename)
    file_storage.save(file_path)

    # return the relative path for storing in the DB
    return os.path.join('static', 'uploads', patient_id, doc_type, filename)
