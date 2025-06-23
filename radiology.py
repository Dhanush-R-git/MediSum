# radiology.py
import os
from flask import Blueprint, render_template, request, session, jsonify, current_app
from utils.security import role_required
from utils.file_utils import validate_pdf, save_upload
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from datetime import datetime

bp = Blueprint('radiology', __name__)
db = MongoClient(os.getenv('MONGO_URI'))["reportdata"]

@bp.route('/rad/upload_scan_report', methods=['GET','POST'])
@role_required('radiologist')
def upload_scan():
    """
    Radiologist only: upload scan/radiology report.
    Maintains scan_docs.history as an array of timestamped entries
    containing the PDF path, notes, and image paths.
    """
    if request.method=='POST':
        pid   = request.form['patientId'].strip()
        pdf   = request.files.get('reportFile')
        notes = request.form.get('scanNotes','').strip()
        images = request.files.getlist('imageFiles')

        if not pid:
            return jsonify({'error': 'Patient ID is required'}), 400

        patient = db.patients.find_one({'patient_id':pid})

        if not patient:
            return jsonify({'error':'patient_id is Not found'}),404
        
        # 2) Prepare per-patient scan_docs folder
        base_dir = os.path.join(current_app.root_path, 'static', 'uploads', pid, 'scan_docs')
        os.makedirs(base_dir, exist_ok=True)
        
        # Prepare this run's record
        entry = {
            'timestamp': datetime.utcnow(),
            'scan_notes': notes,
            'scan_report': None,
            'image_paths': []
        }
        logs = []

        # 4) Handle PDF upload
        if pdf and pdf.filename:
            if not validate_pdf(pdf):
                return jsonify({'error': 'Invalid PDF'}), 400

            filename = secure_filename(pdf.filename)
            pdf_path = os.path.join(base_dir, filename)
            pdf.save(pdf_path)
            rel_pdf = os.path.join('static', 'uploads', pid, 'scan_docs', filename)

            entry['scan_report'] = rel_pdf
            logs.append({
                'report_type': 'scan_pdf',
                'file_path': rel_pdf
            })

        # 5) Handle image uploads
        for img in images:
            if not img or not img.filename:
                continue
            ext = os.path.splitext(img.filename)[1].lower()
            img.stream.seek(0, os.SEEK_END)
            size = img.stream.tell()
            img.stream.seek(0)

            if ext not in ('.jpg', '.jpeg', '.png') or size > 5 * 1024 * 1024:
                continue

            filename = secure_filename(img.filename)
            img_path = os.path.join(base_dir, filename)
            img.save(img_path)
            rel_img = os.path.join('static', 'uploads', pid, 'scan_docs', filename)

            entry['image_paths'].append(rel_img)
            logs.append({
                'report_type': 'scan_image',
                'file_path': rel_img
            })
            
        # 3) Push to history and update “current” fields
        db.patients.update_one(
            {'patient_id': pid},
            {
                '$push': {'scan_docs.history': entry},
                '$set': {
                    'scan_docs.scan_notes': notes,
                    # only set if we actually uploaded a PDF:
                    **({'scan_docs.scan_report': entry['scan_report']} if entry['scan_report'] else {}),
                    **({'scan_docs.image_paths': entry['image_paths']} if entry['image_paths'] else {})
                }
            }
        )
        # 5) Log to reports_log
        for log in logs:
            db.reports_log.insert_one({
                'patient_id': pid,
                'uploaded_by': session['user_id'],
                'timestamp': entry['timestamp'],
                **log
            })
        return jsonify({'message':'Scan data saved successfully'}), 200
    return render_template('upload_scan_report.html', patient_data=None)
