import os
from datetime import datetime
from flask import current_app, session
from pdf_generator import create_pdf
from utils.file_utils import validate_pdf, save_upload

# Map report types to builder functions
def build_soap(form):
    # Subjective
    lines = ["Subjective (S):"]
    lines.append(f"  - CC: {form.get('soap_cc', '')}")
    lines.append(f"  - Onset: {form.get('soap_onset', '')}")
    dur_val = form.get('soap_duration_value', '')
    dur_unit = form.get('soap_duration_unit', '')
    lines.append(f"  - Duration: {dur_val} {dur_unit}")
    lines.append(f"  - Quality: {form.get('soap_quality', '')}")
    lines.append(f"  - Severity: {form.get('soap_severity', '')}/10")
    lines.append(f"  - Location: {form.get('soap_location', '')}")
    lines.append(f"  - History: {form.get('soap_history', '')}")
    lines.append("  - Medications:")
    meds = form.getlist('soap_meds[]') if hasattr(form, 'getlist') else form.get('soap_meds[]', [])
    if meds:
        for med in meds:
            if med.strip():
                lines.append(f"      • {med.strip()}")
    lines.append("  - Allergies:")
    allergies = form.getlist('soap_allergies[]') if hasattr(form, 'getlist') else form.get('soap_allergies[]', [])
    if allergies:
        for allergy in allergies:
            if allergy.strip():
                lines.append(f"      • {allergy.strip()}")
    lines.append(f"  - ROS: {form.get('soap_ros', '')}\n")
    # Objective
    lines.append("Objective (O):")
    lines.append(f"  - Temp: {form.get('soap_temp', '')} °C")
    lines.append(f"  - BP: {form.get('soap_bp', '')} mmHg")
    lines.append(f"  - Pulse: {form.get('soap_pulse', '')} bpm")
    lines.append(f"  - Resp: {form.get('soap_resp', '')} rpm")
    lines.append(f"  - SpO2: {form.get('soap_spo2', '')} %")
    lines.append(f"  - Weight: {form.get('soap_weight', '')} kg")
    lines.append(f"  - Exam: {form.get('soap_exam', '')}")
    lines.append(f"  - Labs: {form.get('soap_diagnostics', '')}\n")
    # Assessment
    lines.append("Assessment (A):")
    lines.append(f"  {form.get('soap_assessment', '')}\n")
    # Plan
    lines.append("Plan (P):")
    lines.append(f"  - Diagnostic: {form.get('soap_plan_diag', '')}")
    lines.append(f"  - Therapeutic: {form.get('soap_plan_tx', '')}")
    lines.append(f"  - Edu: {form.get('soap_plan_edu', '')}")
    lines.append(f"  - Follow-Up: {form.get('soap_plan_fu', '')}")
    return "\n".join(lines)

def build_dap(form):
    lines = []
    lines.append("Data:")
    lines.append(form.get('dap_data', '') + "\n")
    lines.append("Assessment:")
    lines.append(form.get('dap_assessment', '') + "\n")
    lines.append("Plan:")
    lines.append(form.get('dap_plan', '') + "\n")
    return "\n".join(lines)

def build_birp(form):
    lines = []
    for fld in ('behavioral', 'intervention', 'response', 'plan'):
        lines.append(f"{fld.capitalize()}:")
        lines.append(form.get(f"birp_{fld}", "") + "\n")
    return "\n".join(lines)

def build_narrative(form):
    return form.get('narrative_text', '') + "\n"

def build_session(form):
    lines = []
    lines.append(f"Date/Time: {form.get('session_datetime')}")
    lines.append(form.get('session_notes', '') + "\n")
    return "\n".join(lines)

def build_summary(form):
    return form.get('summary_text', '') + "\n"

def build_daily(form):
    lines = []
    lines.append(f"Date: {form.get('daily_date')}")
    lines.append(form.get('daily_notes', '') + "\n")
    return "\n".join(lines)

def build_shift(form):
    lines = []
    lines.append(f"From Shift: {form.get('shift_from')} → To Shift: {form.get('shift_to')}\n")
    lines.append(form.get('shift_notes', '') + "\n")
    return "\n".join(lines)

def build_admission(form):
    lines = []
    lines.append(f"Admission Date: {form.get('admission_date')}\n")
    lines.append(form.get('admission_assessment', '') + "\n")
    return "\n".join(lines)

def build_case(form):
    lines = []
    for fld in ('background', 'presentation', 'management', 'conclusion'):
        lines.append(f"{fld.capitalize()}:")
        lines.append(form.get(f"case_{fld}", "") + "\n")
    return "\n".join(lines)

def build_supervision(form):
    lines = []
    lines.append(f"Date: {form.get('supervision_date')}")
    lines.append(f"Supervisor: {form.get('supervisor_name')}\n")
    lines.append(form.get('supervision_notes', '') + "\n")
    return "\n".join(lines)

# Extend with other builders: build_dap, build_birp, etc.
builders = {
    'soap': build_soap,
    'dap': build_dap,
    'birp': build_birp,
    'narrative': build_narrative,
    'session': build_session,
    'summary': build_summary,
    'daily': build_daily,
    'shift': build_shift,
    'admission': build_admission,
    'case': build_case,
    'supervision': build_supervision,
}

def generate_progress_report(pid, rpt_type, form, file_storage):
    """
    Builds report text, generates a PDF, saves it (and optional attachment), updates DB, and logs.
    Returns JSON dict with message or error.
    Assume `db` is imported globally.
    """
    # Validate patient
    from app import db  # avoid circular
    patient = db.patients.find_one({'patient_id': pid})
    if not patient:
        return {'error': 'Patient not found'}, 404

    # Header
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    header = f"Patient Progress Report ({rpt_type.upper()})\nPatient ID: {pid}\nDate: {now}\n\n"

    # Body
    builder = builders.get(rpt_type)
    if not builder:
        return {'error': 'Unsupported report type'}, 400
    body = builder(form)
    full_text = header + body

    # Optional PDF attachment save
    rel_attach = None
    if file_storage and file_storage.filename:
        if not validate_pdf(file_storage):
            return {'error': 'Invalid attached PDF'}, 400
        rel_attach = save_upload(file_storage, 'progress_reports')

    # Generate PDF
    timestamp = int(datetime.utcnow().timestamp())
    fname = f"{pid}_{rpt_type}_{timestamp}.pdf"
    out_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'progress_reports')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, fname)
    create_pdf(full_text, out_path)

    rel_path = os.path.join('static', 'uploads', 'progress_reports', fname)
    # Update DB
    db.patients.update_one(
        {'patient_id': pid},
        {'$push': {'progress_reports': rel_path}}
    )
    # Log
    log = {
        'patient_id': pid,
        'report_type': 'progress',
        'progress_type': rpt_type,
        'uploaded_by': session['user_id'],
        'file_path': rel_path,
        'timestamp': datetime.utcnow()
    }
    if rel_attach:
        log['attachment'] = rel_attach
    db.reports_log.insert_one(log)

    return {'message': 'Report generated & uploaded successfully.'}, 200
