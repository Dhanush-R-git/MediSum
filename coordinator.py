# coordinator.py

import os
from flask import Blueprint, request, render_template, session, jsonify, current_app
from datetime import datetime
from utils.security import role_required
from utils.file_utils import validate_pdf, save_upload
from pymongo import MongoClient
from pdf_generator import create_pdf

# Import your form‐to‐text builders
from progress_report import builders  

bp = Blueprint('coordinator', __name__, url_prefix='/coord')
db = MongoClient(os.getenv('MONGO_URI'))["reportdata"]

@bp.route('/upload_progress_report', methods=['GET','POST'])
@role_required('coordinator', 'doctor')
def upload_progress():
    if request.method == 'POST':
        pid      = request.form.get('patientId','').strip()
        rpt_type = request.form.get('reportType','').strip()
        attached = request.files.get('reportFile')

        # 1) Validate patient ID
        if not pid:
            return jsonify({'error': 'Patient ID is required'}), 400
        patient = db.patients.find_one({'patient_id': pid})
        if not patient:
            return jsonify({'error':'Patient not found'}), 404

        # 2) Build the note text
        now_dt = datetime.utcnow()
        header = (
            f"Progress Note Type: {rpt_type}\n"
            f"Patient ID: {pid}\n"
            f"Date/Time: {now_dt.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        )
        builder = builders.get(rpt_type)
        if not builder:
            return jsonify({'error':'Unsupported progress note type'}), 400

        body = builder(request.form)
        full_text = header + body

        # 3) If user attached a PDF, validate & save
        rel_attach = None
        if attached and attached.filename:
            if not validate_pdf(attached):
                return jsonify({'error':'Attached file must be a valid PDF'}), 400
            rel_attach = save_upload(attached, 'progress_reports')

        # 4) Generate our own PDF copy of the full note
        out_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'progress_reports')
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{pid}_{rpt_type}_{int(now_dt.timestamp())}.pdf"
        out_path = os.path.join(out_dir, fname)
        create_pdf(full_text, out_path)
        rel_pdf = os.path.join('static','uploads','progress_reports', fname)

        # 5) Build the history entry
        hist_entry = {
            'type': rpt_type,
            'timestamp': now_dt,
            'text': full_text,
            'pdf': rel_pdf
        }
        if rel_attach:
            hist_entry['attachment'] = rel_attach

        # 6) Update patient document:
        #    - push into history array
        #    - update a quick‐access `latest` subdoc
        pd = patient.get('progress_docs')
        if isinstance(pd, list):
            # old style → simple array push
            db.patients.update_one(
                {'patient_id': pid}, 
                {   
                    '$push': {'progress_docs': hist_entry}
                }
                )
        else:
            # nested style → push into history
            db.patients.update_one(
            {'patient_id': pid},
            {
                '$push': {'progress_docs.history': hist_entry},
                '$set':  {'progress_docs.latest': hist_entry}
            }
            )

        # 7) Log in reports_log
        log_entry = {
            'patient_id': pid,
            'report_type': 'progress',
            'progress_type': rpt_type,
            'uploaded_by': session['user_id'],
            'file_path': rel_pdf,
            'timestamp': now_dt
        }
        if rel_attach:
            log_entry['attachment'] = rel_attach

        db.reports_log.insert_one(log_entry)

        return jsonify({'message': 'Progress note saved successfully'}), 200

    # GET
    return render_template('upload_progress_report.html')
