# radiology.py
import os
from flask import Blueprint, render_template, request, session, jsonify
from utils.security import role_required
from utils.file_utils import validate_pdf, save_upload
from pymongo import MongoClient
from datetime import datetime

bp = Blueprint('radiology', __name__)
db = MongoClient(os.getenv('MONGO_URI'))["reportdata"]

@bp.route('/rad/upload_scan_report', methods=['GET','POST'])
@role_required('radiologist')
def upload_scan():
    """
    Radiologist only: upload scan/radiology report.
    """
    if request.method=='POST':
        pid   = request.form['patientId'].strip()
        pdf   = request.files.get('reportFile')
        notes = request.form.get('scanNotes','').strip()
        images = request.files.getlist('imageFiles')

        patient = db.patients.find_one({'patient_id':pid})
        if not pid:
            return jsonify({'error': 'Patient ID is required'}), 400
        if not patient:
            return jsonify({'error':'patient_id is Not found'}),404

        updates = {'scan_docs.scan_notes': notes}
        logs = []

        if pdf and pdf.filename:
            if not validate_pdf(pdf):
                return jsonify({'error':'Invalid PDF'}),400
            rel = save_upload(pdf,'scan_reports')
            updates['scan_docs.scan_report'] = rel
            logs.append({
                'report_type':'scan_pdf',
                'file_path':rel
                })

        img_paths = []
        for img in images:
            ext = os.path.splitext(img.filename)[1].lower()
            if ext not in ('.jpg','.jpeg','.png'):
                continue
            if img.content_length > 5e6:
                continue
            rel = save_upload(img,'scan_images')
            img_paths.append(rel)
            logs.append({
                'report_type':'scan_image',
                'file_path':rel
                })
        if img_paths:
            updates['scan_docs.image_paths'] = img_paths

        db.patients.update_one({'patient_id':pid},{'$set':updates})
        for l in logs:
            db.reports_log.insert_one({
                'patient_id':pid,
                'uploaded_by':session['user_id'],
                'timestamp':datetime.utcnow(),**l
            })
        return jsonify({'message':'Saved'})
    return render_template('upload_scan_report.html', patient_data=None)
