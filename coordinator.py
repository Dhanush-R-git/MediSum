# coordinator.py
import os
from flask import Blueprint, request, render_template, session, jsonify, current_app
from datetime import datetime
from utils.security import role_required
from utils.file_utils import validate_pdf, save_upload
from pymongo import MongoClient
from pdf_generator import create_pdf

# Import builders directly
from progress_report import builders  

bp = Blueprint('coordinator', __name__)
db = MongoClient(os.getenv('MONGO_URI'))["reportdata"]

@bp.route('/coord/upload_progress_report', methods=['GET','POST'])
@role_required('coordinator')
def upload_progress():
    if request.method == 'POST':
        pid      = request.form.get('patientId','').strip()
        rpt_type = request.form.get('reportType','').strip()
        file_st  = request.files.get('reportFile')

        # Validate patient
        patient = db.patients.find_one({'patient_id':pid})
        if not patient:
            return jsonify({'error':'Patient not found'}),404

        # Build text
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        header = f"Progress ({rpt_type})\nPatient: {pid}\nDate: {now}\n\n"
        builder = builders.get(rpt_type)
        if not builder:
            return jsonify({'error':'Unsupported type'}),400
        body = builder(request.form)
        full = header + body

        # Push raw note for UI
        db.patients.update_one(
            {'patient_id':pid},
            {'$push': {'progress_docs': {
                'type': rpt_type,
                'text': full,
                'timestamp': datetime.utcnow()
            }}}
        )

        # Save optional attachment
        rel = None
        if file_st and file_st.filename:
            if not validate_pdf(file_st):
                return jsonify({'error':'Invalid PDF'}),400
            rel = save_upload(file_st,'progress_reports')

        # Generate PDF
        fname = f"{pid}_{rpt_type}_{int(datetime.utcnow().timestamp())}.pdf"
        outdir = os.path.join(current_app.root_path,'static','uploads','progress_reports')
        os.makedirs(outdir,exist_ok=True)
        outpath= os.path.join(outdir,fname)
        create_pdf(full,outpath)
        rel_pdf = os.path.join('static','uploads','progress_reports',fname)

        # Log and save PDF ref
        db.patients.update_one(
            {'patient_id':pid},
            {'$push': {'progress_docs.$[d].pdf': rel_pdf}},
            array_filters=[{'d.type': rpt_type}]
        )
        entry = {
            'patient_id':pid,'report_type':'progress',
            'progress_type':rpt_type,'uploaded_by':session['user_id'],
            'file_path':rel_pdf,'timestamp':datetime.utcnow()
        }
        if rel: entry['attachment'] = rel
        db.reports_log.insert_one(entry)

        return jsonify({'message':'Progress saved'}),200

    return render_template('upload_progress_report.html')
