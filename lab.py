# lab.py
import os
from flask import Blueprint, render_template, request, session, jsonify
from utils.security import role_required
from utils.file_utils import validate_pdf, save_upload
from pymongo import MongoClient
from datetime import datetime

bp = Blueprint('lab', __name__)
db = MongoClient(os.getenv('MONGO_URI'))["reportdata"]

@bp.route('/lab/upload_blood_report', methods=['GET','POST'])
@role_required('lab_tech')
def upload_blood():
    """
    Lab technicians can upload a blood report PDF, 
    enter notes, and input multiple test values.

    Maintains blood_docs.history as an array of timestamped entries.
    """
    if request.method=='POST':
        # 1) Retrieve form fields
        pid   = request.form['patientId'].strip()
        pdf   = request.files.get('reportFile')
        notes = request.form.get('bloodNotes','').strip()

        # 2) Validate inputs
        if not pid:
            return jsonify({'error': 'Patient ID is required'}), 400
        if not pdf or not pdf.filename:
            return jsonify({'error': 'Blood report PDF is required'}), 400
        
        patient = db.patients.find_one({'patient_id':pid})

        if not patient:
            return jsonify({'error':'Patient ID Not found'}),404
        if not validate_pdf(pdf):
            return jsonify({'error':'Invalid PDF'}),400

        # 1) Save PDF
        rel_pdf = save_upload(pdf, 'blood_reports')

        # 2) Parse numeric results
        results = {}
        for key, val in request.form.items():
            if key in ('patientId', 'bloodNotes'):
                continue
            try:
                num = float(val)
                results[key] = num
            except (ValueError, TypeError):
                # skip non‐numeric fields
                pass

        # 3) Build a new history entry
        entry = {
            'timestamp': datetime.utcnow(),
            'blood_report': rel_pdf,
            'blood_notes': notes,
            'blood_results': results
        }

        # 4) Update patient document:
        #     - push to history
        #     - set current top‐level fields
        db.patients.update_one(
            {'patient_id': pid},
            {
                '$push': {'blood_docs.history': entry},
                '$set': {
                    'blood_docs.blood_report': rel_pdf,
                    'blood_docs.blood_notes': notes,
                    'blood_docs.blood_results': results
                }
            }
        )
        # 5) Log the upload of the PDF
        db.reports_log.insert_one({
            'patient_id': pid,
            'report_type': 'blood_pdf',
            'uploaded_by': session['user_id'],
            'file_path': rel_pdf,
            'timestamp': entry['timestamp']
        })
        return jsonify({'message':'Blood report and data saved successfully'}), 200
    return render_template('upload_blood_report.html', patient_data=None)
