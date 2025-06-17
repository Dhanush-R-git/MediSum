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
    Lab technicians or doctors can upload a blood report PDF,
    enter notes, and input multiple test values.
    """
    if request.method=='POST':
        # 1) Retrieve form fields
        pid   = request.form['patientId'].strip()
        pdf   = request.files.get('reportFile')
        notes = request.form.get('bloodNotes','').strip()

        # 2) Validate inputs
        if not (pid and pdf):
            return jsonify({'error':'Patient ID is Required'}),400
        patient = db.patients.find_one({'patient_id':pid})

        if not patient:
            return jsonify({'error':'Patient ID Not found'}),404
        if not validate_pdf(pdf):
            return jsonify({'error':'Invalid PDF'}),400

        rel = save_upload(pdf,'blood_reports')
        # collect results
        results = {}
        for key, val in request.form.items():
            if key in ('patientId', 'bloodNotes'):
                continue
            # Attempt numeric parse; if fails, skip
            try:
                num = float(val)
                results[key] = num
            except (ValueError, TypeError):
                continue

        db.patients.update_one(
            {'patient_id':pid},
            {'$set': {
              'blood_docs.blood_report': rel,
              'blood_docs.blood_notes': notes,
              'blood_docs.blood_results': results
            }}
        )
        db.reports_log.insert_one({
            'patient_id':pid,
            'report_type':'blood',
            'uploaded_by':session['user_id'],
            'file_path':rel,
            'timestamp':datetime.utcnow()
        })
        return jsonify({'message':'Blood report and data saved successfully'})
    return render_template('upload_blood_report.html', patient_data=None)
