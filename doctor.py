# doctor.py

import os
import logging
import smtplib
from datetime import datetime
from flask import Blueprint, render_template, request, session, jsonify, send_file, abort, current_app
from email.message import EmailMessage
from pymongo import MongoClient
from dotenv import load_dotenv

from utils.security import role_required, login_required
from utils.file_utils import validate_pdf, save_upload
from pdf_generator import create_pdf

# LangChain imports for summary generation
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEndpoint
#from langchain import PromptTemplate, LLMChain
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain.embeddings import HuggingFaceEmbeddings
#from langchain.vectorstores import Chroma

from langchain_core.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

bp = Blueprint('doctor', __name__, url_prefix='/doctor')

load_dotenv()
# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
db = MongoClient(mongo_uri)["reportdata"]

# Configure LLM for summaries
os.environ['HUGGINGFACEHUB_API_TOKEN'] = os.getenv('HUGGINGFACEHUB_API_TOKEN')
repo_id = "mistralai/Mistral-7B-Instruct-v0.3"
llm = HuggingFaceEndpoint(
    repo_id=repo_id,
    task="text-generation",
    temperature=0.7,
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN"),
    provider="hf-inference",
)

# Define the prompt template
prompt_template = """
You are a medical report generator AI.Your task is to create comprehensive medical reports based on the provided patient details and medical history.Follow this structured format for each patient report:
**Patient Details:* - Patient Name:[Insert Patient Name here]-
Patient ID: [Insert Patient ID here]
Joining Date (Reg.Date & Time): [Insert Reg.Date & Time here] 
Test Report: [Insert Test Report details here]
Age/Sex: [Insert Age/Sex here] Impression:
[Insert Impression here]
**Medical History:*
     - Summary: 
           - Relevant past illnesses: [Summarize relevant past illnesses]
             Chronic conditions: [List any chronic conditions]
             Significant medical events: [Mention surgeries or other significant medical events]
**Symptoms and Diagnosis:* - Symptoms: 
Primary symptoms: [Summarize primary symptoms]
Onset and progression: [Mention onset and progression of symptoms]
Diagnosis: - [Provide diagnosis made by healthcare professionals]
**Treatment and Recommendations:* - Treatment: -
Medications:[List medications administered]- Therapies or procedures: [Summarize therapies or procedures performed]- Recommendations: - Follow-up care: [Mention any follow-up care]- Lifestyle adjustments: [Include lifestyle adjustments advised]*Lab Reports:* - Key findings: [Summarize key findings from blood tests, urine analysis, etc. mentioned here]
Significant results: [Highlight significant results or abnormalities]
**Current Status:* - Status: - Current condition:[Describe current condition]- Progress or ongoing issues: [Mention progress or ongoing issues]
above mentioned heading must be in the output and also the summary should be structed and readable way words within 1500 words
Note: if suppose the content not there in the given input i want to show not content is specified in the input file"{context}"
"""

prompt = PromptTemplate(
    template=prompt_template, 
    input_variables=["context"]
    )
#llm_chain = LLMChain(prompt=prompt, llm=llm)
llm_chain = prompt | llm


@bp.route('/dashboard', methods=['GET'])
@role_required('doctor')
def dashboard():
    """
    Main portal page that shows:
    - Sidebar with icons
    - Top bar with patient name, MRN, acuity, etc.
    - Tabs: Overview, Care Management, Documents, Scheduling, Encounters
    - Patient Timeline (for a selected year)
    - Goals & Activities, Actions, Quality Measures & Documentation
    - Right panel: Recent patients list & search box
    """
    # Fetch all patients for right panel
    patients = list(db.patients.find({}, {'_id': 0, 'patient_id': 1, 'name': 1, 'dob': 1}))
    formatted = []
    for p in patients:
        dob = p.get('dob').strftime('%m/%d/%Y') if p.get('dob') else ''
        formatted.append({
            'patient_id': p['patient_id'], 
            'display': f"{p['name']} ({dob})"
            })
    return render_template('dashboard.html', patients=formatted, selected=None, patient_data=None)


@bp.route('/dashboard/<patient_id>', methods=['GET'])
@role_required('doctor')
def load_patient(patient_id):
    """
    When a doctor clicks on a patient in right panel, AJAX or direct link hits this endpoint.
    We load that patient's data (demographics + any static placeholders for timeline, 
    goals, actions, quality measures) and render the same dashboard but with patient_data populated.
    """
    # Load patient demographics
    patient = db.patients.find_one({'patient_id': patient_id}, {'_id': 0})
    if not patient:
        abort(404)

    # 2. (Optional) Pre‐compute timeline events, goals, actions, quality measures.
    # For now, supply placeholder arrays:
    timeline = [
        {'date': 'Jan 01 2024', 'title': 'Treatment', 'desc': 'The health system provides on‐site ...'},
        {'date': 'Jan 05 2024', 'title': 'Care', 'desc': 'The patient is assessed at a medical facility ...'},
        {'date': 'Jan 07 2024', 'title': 'Initial contact', 'desc': 'The patient makes initial contact via call center ...'},
        {'date': 'Jan 23 2024', 'title': 'Pre‐visit awareness', 'desc': "Patient's journey starts when they arrive ..."}
    ]
    goals_activities = [
        {'label': 'Test blood sugar every day', 'percent': 65},
        {'label': 'Take medication as directed', 'percent': 40},
        {'label': 'Maintain normal BP level', 'percent': 10}
    ]
    actions = [
        {'label': 'Brief medical history, allergies, and medications', 'checked': True},
        {'label': 'Surgical history to include all invasive procedures', 'checked': False},
        {'label': 'Prepare medical history document', 'checked': False}
    ]
    quality_measures = [
        {'label': 'Optimization of sepsis care & reduced hospital readmissions', 'status': 'Pending'},
        {'label': 'Reduction in medication‐related adverse events', 'status': 'Pending'},
        {'label': 'Missed Appointment Policy (Patient Financial Responsibility Waiver)', 'status': 'Completed'},
        {'label': 'Improved electronic medical record documentation & patient instructions', 'status': 'Completed'}
    ]
    experts = list(db.experts.find({}, {'_id': 0, 'name': 1, 'email': 1}))

    # Progress & Daily logs
    progress_logs = list(db.reports_log.find(
        {'patient_id': patient_id, 'report_type': 'progress'}
    ).sort('timestamp', -1).limit(5))
    
    progress_history = [
        {'file_path': entry['file_path'],
         'uploaded_by': entry['uploaded_by'],
         'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M'),
         'progress_type': entry.get('progress_type')}
        for entry in progress_logs
    ]
    
    # Collect history entries for doctor, scan, and blood reports
    # 3. Collect all reports (doctor, scan, blood) and progress notes
    reports = []
    for kind, label, sub in [
        ('doctor',   'Doctor Report',   'doctor_docs'),
        ('scan',     'Scan Report',     'scan_docs'),
        ('blood',    'Blood Report',    'blood_docs'),
    ]:
        doc_obj = patient.get(sub, {})
        # 1) collect history entries
        history = doc_obj.get('history', [])
        paths = [e.get(f"{kind}_report") for e in history if e.get(f"{kind}_report")]
        # 2) only include latest if you *also* want a “latest” separate (but see below)
        latest = doc_obj.get(f"{kind}_report")
        # push a single report descriptor
        if paths:
            reports.append({
                'type':      kind,
                'label':     f"{label} (history)",
                'paths':     paths,
                'is_history': True,
            })
        if latest:
            reports.append({
                'type':      kind,
                'label':     f"{label} (latest)",
                'paths':     [latest],
                'is_history': False,
            })

    # progress notes
    for entry in patient.get('progress_docs', []):
        p = entry.get('pdf')
        if not p: continue
        reports.append({
            'type':      'progress',
            'label':     f"Progress Note ({entry.get('type')})",
            'paths':     [p],
            'is_history': True,     # treat progress as “latest only”
        })

    daily_logs = list(db.reports_log.find(
        {'patient_id': patient_id, 'progress_type': 'daily'}
    ).sort('timestamp', -1).limit(5))
    daily_history = [
        {
         'file': d['file_path'],
         'uploaded_by': d['uploaded_by'],
         'timestamp': d['timestamp'].strftime('%Y-%m-%d %H:%M')
         }
        for d in daily_logs
    ]

    # 4. Prepare patient list for the right panel (same as before)
    all_patients = list(db.patients.find({}, {'_id': 0, 'patient_id': 1, 'name': 1, 'dob': 1}))
    patient_list = []
    for p in all_patients:
        dob_str = p.get('dob').strftime('%m/%d/%Y') if p.get('dob') else ''
        patient_list.append({
            'patient_id': p['patient_id'],
            'display': f"{p['name']} ({dob_str})"
        })

    return render_template(
        'dashboard.html',
        patients=patient_list,
        selected=patient_id,
        patient_data=patient,
        timeline=timeline,
        goals_activities=goals_activities,
        actions_list=actions,
        quality_measures=quality_measures,
        experts=experts,
        progress_history=progress_history,
        daily_history=daily_history,
        #doctor_history=doctor_history,
        #scan_history=scan_history,
        #blood_history=blood_history,
        reports=reports,
    )

@bp.route('/upload_doctor_report', methods=['GET', 'POST'])
@role_required('doctor')
def upload_doctor_report():
    """
    Allow the doctor to upload a clinical note/prescription (PDF).
    """
    if request.method == 'POST':
        pid = request.form.get('patientId', '').strip()
        f = request.files.get('reportFile')
        if not pid or not f:
            return jsonify({'error': 'Patient ID and report file are required'}), 400

        patient = db.patients.find_one({'patient_id': pid})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        if not validate_pdf(f):
            return jsonify({'error': 'Uploaded file must be a valid PDF under 10 MB'}), 400

        rel = save_upload(f, pid, 'doctor_docs')
        # update sub‑doc
        db.patients.update_one(
            {'patient_id': pid},
            {'$set': {'doctor_docs.doctor_report': rel}}
        )
        db.reports_log.insert_one({
            'patient_id': pid,
            'report_type': 'doctor',
            'uploaded_by': session['user_id'],
            'file_path': rel,
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'Doctor report uploaded successfully'})

    return render_template('upload_doctor_report.html')


@bp.route('/generate_summary', methods=['POST'])
@role_required('doctor')
def generate_summary():
    """
    Called via AJAX from the dashboard: bundling all existing PDF reports
    (doctor_report, scan_report, blood_report) into a single medical summary PDF
    using the LangChain pipeline, then store in summaries collection.
    """
    payload = request.get_json(force=True) or {}
    pid     = payload.get('patientId')
    paths   = payload.get('paths', [])
    if not pid:
        return jsonify({'error': 'Patient ID required'}), 400
    
    logging.info(f"Generating summary for patient {pid}. PDF paths used: {paths}")

    if not paths:
        return jsonify({'error': 'No reports found to summarize'}), 404

    docs = []
    try:
        for rel in paths:
            full = os.path.join(current_app.root_path, rel)
            if os.path.isfile(full):
                loader = PyPDFLoader(full)
                docs.extend(loader.load_and_split())
    except Exception as e:
        logging.exception("Failed to load PDF documents:")
        return jsonify({'error': 'Error loading PDF files'}), 500
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        chunks = splitter.split_documents(docs)

        vectordb = Chroma.from_documents(
            documents=chunks, 
            embedding=embeddings, 
            persist_directory=os.path.join(current_app.root_path, "chroma_db", pid)
            )
        #vectordb.persist()
        logging.debug("Vector database created and persisted successfully at chroma_db/%s", pid)

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm_chain,
            retriever=vectordb.as_retriever(),
            chain_type="stuff",
            #chain_type_kwargs={"prompt": prompt},
            return_source_documents=True
        )
        response = qa_chain.invoke({
            "query": "Create a full medical summary that covers the patient's history, diagnosis, treatment, and current status"
            })
        #result = qa_chain.invoke({"query": response})
        summary_text = response["result"]
        logging.info("Summary generated")

    except Exception as e:
        logging.exception(f"Error during LangChain processing: {e}")
        return jsonify({'error': 'Error generating summary.'}), 500

    # Create PDF
    now_ts = int(datetime.utcnow().timestamp())
    out_dir = os.path.join(current_app.root_path, 'static', 'uploads', pid, 'summaries')
    os.makedirs(out_dir, exist_ok=True)
    fname   = f"summary_{pid}_{now_ts}.pdf"
    out_path = os.path.join(out_dir, fname)
    try:
        create_pdf(summary_text, out_path)
    except Exception as e:
        logging.error(f"Failed to write summary PDF: {e}")
        return jsonify({'error': 'Error creating summary PDF.'}), 500

    db.summaries.insert_one({
        'patient_id': pid,
        'summary_text': summary_text,
        'pdf_path': os.path.join('static', 'uploads', pid, 'summaries', fname),
        'generated_by': session['user_id'],
        'timestamp': datetime.utcnow()
    })

    return jsonify(
        {
            'message': 'Summary generated successfully',
            'summary_text': summary_text
        })


@bp.route('/medical_summaries', methods=['GET', 'POST'])
@role_required('doctor')
def medical_summaries():
    """
    GET: Show a search form (patientId).  
    POST: Return all summaries for that patient.
    """
    if request.method == 'POST':
        pid = request.form.get('patientId','').strip()
        if not pid:
            return render_template('medical_summaries.html', error="Patient ID required", summaries=[])
        
        raw = db.summaries.find({'patient_id': pid}).sort('timestamp', -1)
        summaries = []
        for s in raw:
            date = s['timestamp'].strftime('%Y-%m-%d %H:%M')
            excerpt = s['summary_text'][:100] + ('…' if len(s['summary_text'])>100 else '')
            summaries.append({
                'date': date, 
                'excerpt': excerpt, 
                'pdf_path': s['pdf_path']
                })
        return render_template('medical_summaries.html', summaries=summaries, patient_id=pid)
    return render_template('medical_summaries.html', summaries=None, patient_id='')


@bp.route('/send_expert_email', methods=['POST'])
@role_required('doctor')
def send_expert_email():
    data = request.json or {}
    pid = data.get('patientId')
    expert_email = data.get('expertEmail')
    summary_text = data.get('summaryText')
    if not (pid and expert_email and summary_text):
        return jsonify({'error': 'Missing data'}), 400

    msg = EmailMessage()
    msg['Subject'] = f"Analysis request for Patient {pid}"
    msg['From'] = current_app.config['MAIL_USERNAME'] or 'no-reply@example.com'
    msg['To'] = expert_email
    msg.set_content(
        f"Dear Specialist,\n\n"
        f"You have been requested to review the medical summary for patient {pid}.\n\n"
        f"--- Summary ---\n{summary_text}\n\n"
        f"Please reply with your expert analysis.\n\n"
        "Regards,\nMediSum Team"
    )

    try:
        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        if current_app.config['MAIL_USE_TLS']:
            server.starttls()
        if current_app.config['MAIL_USERNAME']:
            server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return jsonify({'message': 'Email sent successfully'})
    except Exception as e:
        logging.error(f"Email error: {e}")
        return jsonify({'error': 'Failed to send email'}), 500


@bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    """
    Serve static files for download. Make sure to sanitize `filename`
    or only allow downloads from designated folders.
    """
    safe_base = os.path.join(current_app.root_path, 'static', 'uploads')
    full_path = os.path.normpath(os.path.join(current_app.root_path, filename))
    if not full_path.startswith(safe_base):
        abort(403)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, as_attachment=True)
