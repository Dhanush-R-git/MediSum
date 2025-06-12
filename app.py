# app.py imports

from flask import Flask, request, render_template, redirect, url_for, session, jsonify, send_file, abort
from pymongo import MongoClient
from datetime import datetime
import os, logging, smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from utils.security import hash_password, check_password, login_required, role_required
from utils.file_utils import validate_pdf, save_upload
from werkzeug.utils import secure_filename

# from langchain imports libraries to keep the summary‐generation pipeline
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEndpoint
from langchain import PromptTemplate, LLMChain
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from pdf_generator import create_pdf

load_dotenv()  # Load .env

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'CHANGE_ME_IN_PRODUCTION')

# --- Configure MongoDB ---
# Configure MongoDB connection via Cosmos DB for Mongo API
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client["reportdata"]

# Initialize HuggingFace model
os.environ['HUGGINGFACEHUB_API_TOKEN'] = os.getenv('HUGGINGFACEHUB_API_TOKEN')


# Mail config (for sending to experts)
app.config.update(
    MAIL_SERVER   = os.getenv('MAIL_SERVER', 'localhost'),
    MAIL_PORT     = int(os.getenv('MAIL_PORT', 25)),
    MAIL_USERNAME = os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD'),
    MAIL_USE_TLS  = os.getenv('MAIL_USE_TLS', 'False').lower() in ('1','true','yes')
)

ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB per image, for example

# Configure logging
logging.basicConfig(level=logging.DEBUG)

repo_id = "mistralai/Mistral-7B-Instruct-v0.3"
llm = HuggingFaceEndpoint(
    repo_id=repo_id,
    task="summarization",
    #max_length=1024, 
    temperature=0.7, 
    token=os.getenv('HUGGINGFACEHUB_API_TOKEN')
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
# Initialize PromptTemplate and LLMChain
prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["context"]
)
llm_chain = LLMChain(prompt=prompt, llm=llm)

# -----------------------------
# ===== Authentication ========
# -----------------------------
@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template('login.html', error="Username and password required")

    user = db.users.find_one({'username': username})
    if not user:
        return render_template('login.html', error="Invalid credentials")

    if not check_password(password, user['password_hash']):
        return render_template('login.html', error="Invalid credentials")

    # Successful login
    session['logged_in'] = True
    session['username'] = user['username']
    session['user_id'] = str(user['_id'])
    session['role'] = user['role']  # e.g. "doctor", "lab_tech", etc.

    # Redirect based on role
    if user['role'] == 'doctor':
        return redirect(url_for('dashboard'))
    elif user['role'] == 'lab_tech':
        return redirect(url_for('lab_upload_blood_report'))
    elif user['role'] == 'radiologist':
        return redirect(url_for('rad_upload_scan_report'))
    elif user['role'] == 'coordinator':
        return redirect(url_for('coord_upload_progress_report'))
    else:
        # Unknown role
        session.clear()
        return render_template('login.html', error="Invalid role")


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# (Optional) Route to register new users (only for admin, or open sign‐up)
@app.route('/register', methods=['GET', 'POST'])
def register_page():
    # If you want open registration, else protect behind @role_required('admin')
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')
        full_name = request.form.get('full_name').strip()
        role = request.form.get('role')  # doctor, lab_tech, radiologist, coordinator

        # Basic validations
        if not (username and email and password and role and full_name):
            return render_template('register.html', error="All fields are required.")

        if db.users.find_one({'username': username}):
            return render_template('register.html', error="Username already exists.")

        pw_hash = hash_password(password)
        new_user = {
            'username': username,
            'email': email,
            'full_name': full_name,
            'role': role,
            'password_hash': pw_hash,
            'date_created': datetime.utcnow()
        }
        db.users.insert_one(new_user)
        return redirect(url_for('login_page'))

    return render_template('register.html')


# -----------------------------
# ==== Doctor‐Only Routes =====
# -----------------------------
@app.route('/dashboard', methods=['GET'])
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
    # Fetch list of all patients to populate right panel
    all_patients = list(db.patients.find({}, {'_id': 0, 'patient_id': 1, 'name': 1, 'dob': 1}))
    # Format them into: [ { patient_id, display_name }, ... ]
    patient_list = []
    for p in all_patients:
        dob_str = p.get('dob').strftime('%m/%d/%Y') if p.get('dob') else ''
        patient_list.append({
            'patient_id': p['patient_id'],
            'display': f"{p['name']} ({dob_str})"
        })

    # Render with no patient selected initially
    return render_template('dashboard.html', patients=patient_list, selected=None, patient_data=None)


@app.route('/dashboard/<patient_id>', methods=['GET'])
@role_required('doctor')
def load_patient(patient_id):
    """
    When a doctor clicks on a patient in right panel, AJAX or direct link hits this endpoint.
    We load that patient's data (demographics + any static placeholders for timeline, 
    goals, actions, quality measures) and render the same dashboard but with patient_data populated.
    """
    # 1. Lookup patient demographics:
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

    # 3. Fetch expert list for “send to expert” dropdown
    experts = list(db.experts.find({}, {'_id': 0, 'name': 1, 'email': 1}))

    # 4. Fetch recent progress report history
    progress_logs = list(db.reports_log.find(
        {'patient_id': patient_id, 'report_type': 'progress'}
    ).sort('timestamp', -1).limit(5))

    # Format for template
    progress_history = [
        {
            'file_path': entry['file_path'],
            'uploaded_by': entry.get('uploaded_by'),
            'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M')
        }
        for entry in progress_logs
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
    )


@app.route('/create_patient', methods=['GET', 'POST'])
@role_required('doctor')
def create_patient():
    """
    Render a form (GET). On POST, validate inputs, generate new patient_id, insert record.
    Return JSON if AJAX, or redirect back with a success message.
    """
    if request.method == 'POST':
        name = request.form.get('name').strip()
        dob_raw = request.form.get('dob')    # expect "YYYY-MM-DD"
        sex = request.form.get('sex')
        email = request.form.get('email').strip()
        phone = request.form.get('phone').strip()
        address = request.form.get('address').strip()

        # Server‐side validations
        if not (name and dob_raw and sex and email and phone and address):
            return jsonify({'error': 'All fields are required.'}), 400

        try:
            dob = datetime.strptime(dob_raw, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format for DOB.'}), 400

        # Generate a new unique patient_id: “PAT” + zero‐padded count
        count = db.patients.count_documents({}) + 1
        patient_id = f"PAT{count:04d}"
        new_patient = {
            'patient_id': patient_id,
            'name': name,
            'dob': dob,
            'sex': sex,
            'email': email,
            'phone': phone,
            'address': address,
            'date_created': datetime.utcnow(),
            'doctor_report': None,
            'scan_report': None,
            'blood_report': None,
            'created_by': session['user_id']
        }
        db.patients.insert_one(new_patient)
        return jsonify({'message': 'Patient created successfully', 'patient_id': patient_id})

    # GET request → show HTML form
    return render_template('create_patient.html')


@app.route('/upload_doctor_report', methods=['GET', 'POST'])
@role_required('doctor')
def upload_doctor_report():
    """
    Allow the doctor to upload a clinical note/prescription (PDF).
    """
    if request.method == 'POST':
        patient_id = request.form.get('patientId').strip()
        report_file = request.files.get('reportFile')

        if not patient_id or not report_file:
            return jsonify({'error': 'Patient ID and report file are required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        # Validate PDF
        if not validate_pdf(report_file):
            return jsonify({'error': 'Uploaded file must be a valid PDF under 10 MB'}), 400

        # Save to static/uploads/doctor_reports/...
        rel_path = save_upload(report_file, 'doctor_reports')

        # Update patient doc
        db.patients.update_one(
            {'patient_id': patient_id},
            {'$set': {'doctor_report': rel_path}}
        )
        # Log in reports_log (optional)
        db.reports_log.insert_one({
            'patient_id': patient_id,
            'report_type': 'doctor',
            'uploaded_by': session['user_id'],
            'file_path': rel_path,
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'Doctor report uploaded successfully'})

    return render_template('upload_doctor_report.html')


def allowed_image(filename):
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_IMAGE_EXTS

@app.route('/upload_scan_report', methods=['GET', 'POST'])
@role_required('doctor', 'radiologist')
def upload_scan_report():
    """
    Radiologists or doctors can upload a scan PDF, write scan notes,
    and upload multiple scan images.
    """
    if request.method == 'POST':
        patient_id = request.form.get('patientId', '').strip()
        scan_notes = request.form.get('scanNotes', '').strip()
        pdf_file   = request.files.get('reportFile')
        image_files = request.files.getlist('imageFiles')

        # 1) Basic validation
        if not patient_id:
            return jsonify({'error': 'Patient ID is required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        updates = {}
        logs = []

        # 2) Handle PDF upload (if provided)
        if pdf_file and pdf_file.filename:
            if not validate_pdf(pdf_file):
                return jsonify({'error': 'Uploaded file must be a valid PDF'}), 400

            rel_pdf = save_upload(pdf_file, 'scan_reports')
            updates['scan_report'] = rel_pdf
            logs.append({
                'report_type': 'scan_pdf',
                'file_path': rel_pdf
            })

        # 3) Handle scan notes (always update)
        updates['scan_notes'] = scan_notes

        # 4) Handle image uploads
        saved_images = []
        for img in image_files:
            if not img or not img.filename:
                continue
            if not allowed_image(img.filename):
                continue
            # size check
            img.stream.seek(0, os.SEEK_END)
            size = img.stream.tell()
            img.stream.seek(0)
            if size > MAX_IMAGE_SIZE:
                continue

            rel_img = save_upload(img, 'scan_images')
            saved_images.append(rel_img)
            logs.append({
                'report_type': 'scan_image',
                'file_path': rel_img
            })

        if saved_images:
            # push to an array field
            updates.setdefault('scan_image_paths', [])
            # use $each to append multiple
            db.patients.update_one(
                {'patient_id': patient_id},
                {'$push': {'scan_image_paths': {'$each': saved_images}}}
            )

        # 5) Apply all other updates (notes and PDF)
        if updates:
            db.patients.update_one({'patient_id': patient_id}, {'$set': updates})

        # 6) Log all uploads
        for entry in logs:
            db.reports_log.insert_one({
                'patient_id': patient_id,
                'uploaded_by': session['user_id'],
                'timestamp': datetime.utcnow(),
                **entry
            })

        return jsonify({'message': 'Scan data uploaded successfully'})

    # GET
    # Optionally fetch patient_data to pre‐fill patient_id, notes, and existing PDF
    return render_template('upload_scan_report.html', patient_data=None)


@app.route('/upload_blood_report', methods=['GET', 'POST'])
@role_required('doctor', 'lab_tech')
def upload_blood_report():
    """
    Lab technicians or doctors can upload a blood report PDF,
    enter notes, and input multiple test values.
    """
    if request.method == 'POST':
        # 1) Retrieve form fields
        patient_id  = request.form.get('patientId', '').strip()
        blood_notes = request.form.get('bloodNotes', '').strip()
        pdf_file    = request.files.get('reportFile')

        # 2) Basic validation
        if not patient_id:
            return jsonify({'error': 'Patient ID is required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        # Collect updates and logs
        updates = {}
        logs    = []

        # 3) Handle PDF upload
        if not pdf_file or not pdf_file.filename:
            return jsonify({'error': 'Blood report PDF is required'}), 400

        if not validate_pdf(pdf_file):
            return jsonify({'error': 'Uploaded file must be a valid PDF under 10 MB'}), 400

        rel_pdf = save_upload(pdf_file, 'blood_reports')
        updates['blood_report'] = rel_pdf
        logs.append({
            'report_type': 'blood_pdf',
            'file_path': rel_pdf
        })

        # 4) Save notes
        updates['blood_notes'] = blood_notes

        # 5) Gather all test inputs into a dict
        #    We assume any form field not 'patientId', 'bloodNotes', 'reportFile'
        #    is a numeric test value.
        blood_results = {}
        for key, val in request.form.items():
            if key in ('patientId', 'bloodNotes'):
                continue
            # Attempt numeric parse; if fails, skip
            try:
                num = float(val)
                blood_results[key] = num
            except (ValueError, TypeError):
                continue

        if blood_results:
            updates['blood_results'] = blood_results

        # 6) Apply updates to patient document
        if updates:
            db.patients.update_one(
                {'patient_id': patient_id},
                {'$set': updates}
            )

        # 7) Log all actions
        for entry in logs:
            db.reports_log.insert_one({
                'patient_id': patient_id,
                'uploaded_by': session['user_id'],
                'timestamp': datetime.utcnow(),
                **entry
            })

        return jsonify({'message': 'Blood report and data saved successfully'})

    # GET: render form (you may also pass existing patient data for preview)
    return render_template('upload_blood_report.html', patient_data=None)


@app.route('/generate_summary', methods=['POST'])
@role_required('doctor')
def generate_summary():
    """
    Called via AJAX from the dashboard: bundling all existing PDF reports
    (doctor_report, scan_report, blood_report) into a single medical summary PDF
    using the LangChain pipeline, then store in summaries collection.
    """
    patient_id = request.form.get('patientId')
    if not patient_id:
        return jsonify({'error': 'Patient ID is required'}), 400

    patient = db.patients.find_one({'patient_id': patient_id})
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404

    # 1. Collect file paths
    doctor_path = patient.get('doctor_report')
    scan_path = patient.get('scan_report')
    blood_path = patient.get('blood_report')

    documents = []
    def load_pdfs(path):
        from langchain_community.document_loaders import PyPDFLoader
        try:
            loader = PyPDFLoader(path)
            return loader.load_and_split()
        except Exception as e:
            logging.error(f"Error loading {path}: {e}")
            return []

    if doctor_path:
        documents.extend(load_pdfs( os.path.join(app.root_path, doctor_path) ))
    if scan_path:
        documents.extend(load_pdfs( os.path.join(app.root_path, scan_path) ))
    if blood_path:
        documents.extend(load_pdfs( os.path.join(app.root_path, blood_path) ))

    if not documents:
        return jsonify({'error': 'No reports found to summarize.'}), 404

    # 2. Embed, vectorize, run QA chain to generate summary (LangChain boilerplate)
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)

        vectordb = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory="./database_db1"
        )
        vectordb.persist()
        logging.debug("Vector database created and persisted successfully.")
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm_chain,
            retriever=vectordb.as_retriever(),
            chain_type="stuff",
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True
        )
        response = qa_chain("Create a full medical summary that covers the patient's history, diagnosis, treatment, and current status")
        summary_text = response["result"]
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return jsonify({'error': 'Error generating summary.'}), 500

    # 3. Turn into PDF (pdf_generator.create_pdf)
    pdf_filename = f"summary_{patient_id}_{int(datetime.utcnow().timestamp())}.pdf"
    pdf_path = os.path.join(app.root_path, 'static', 'uploads', 'summaries', pdf_filename)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    try:
        create_pdf(summary_text, pdf_path)
    except Exception as e:
        logging.error(f"Error writing PDF: {e}")
        return jsonify({'error': 'Unable to write PDF.'}), 500

    # 4. Persist summary record
    db.summaries.insert_one({
        'patient_id': patient_id,
        'summary_text': summary_text,
        'pdf_path': os.path.join('static', 'uploads', 'summaries', pdf_filename),
        'generated_by': session['user_id'],
        'timestamp': datetime.utcnow()
    })

    return jsonify({'message': 'Summary generated successfully', 'summary_text': summary_text})


@app.route('/medical_summaries', methods=['GET', 'POST'])
@role_required('doctor')
def medical_summaries():
    """
    GET: Show a search form (patientId).  
    POST: Return all summaries for that patient.
    """
    if request.method == 'POST':
        pid = request.form.get('patientId').strip()
        if not pid:
            return render_template('medical_summaries.html', error="Patient ID is required", summaries=[])

        raw = db.summaries.find({'patient_id': pid}).sort('timestamp', -1)
        summaries = []
        for s in raw:
            ts = s.get('timestamp')
            date_str = ts.strftime('%Y-%m-%d %H:%M') if ts else 'N/A'
            excerpt = s.get('summary_text', '')[:100] + ('…' if len(s.get('summary_text','')) > 100 else '')
            summaries.append({
                'date': date_str,
                'excerpt': excerpt,
                'pdf_path': s.get('pdf_path')
            })
        return render_template('medical_summaries.html', summaries=summaries, patient_id=pid)

    # GET
    return render_template('medical_summaries.html', summaries=None, patient_id='')


@app.route('/send_expert_email', methods=['POST'])
@role_required('doctor')
def send_expert_email():
    data = request.json or {}
    patient_id = data.get('patientId')
    expert_email = data.get('expertEmail')
    summary_text = data.get('summaryText')

    if not (patient_id and expert_email and summary_text):
        return jsonify({'error': 'Missing data'}), 400

    msg = EmailMessage()
    msg['Subject'] = f"MediSum: Analysis request for Patient {patient_id}"
    msg['From']    = app.config['MAIL_USERNAME'] or 'no-reply@medisum.com'
    msg['To']      = expert_email
    msg.set_content(
        f"Dear Specialist,\n\n"
        f"You have been requested to review the medical summary for patient {patient_id}.\n\n"
        f"--- Summary ---\n{summary_text}\n\n"
        f"Please reply with your expert analysis.\n\n"
        "Regards,\nMediSum Team"
    )

    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'], timeout=10)
        if app.config['MAIL_USE_TLS']:
            server.starttls()
        if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return jsonify({'message': 'Email sent successfully'})
    except Exception as e:
        logging.error(f"Email error: {e}")
        return jsonify({'error': 'Failed to send email'}), 500


# -----------------------------
# === Lab Technician Routes ===
# -----------------------------
@app.route('/lab/upload_blood_report', methods=['GET', 'POST'])
@role_required('lab_tech')
def lab_upload_blood_report():
    """
    Lab technician only: upload blood/PCR/CBC/etc. 
    (Identical to doctor’s endpoint but restricted to role).
    """
    if request.method == 'POST':
        patient_id = request.form.get('patientId').strip()
        report_file = request.files.get('reportFile')
        if not patient_id or not report_file:
            return jsonify({'error': 'Patient ID and report file required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        if not validate_pdf(report_file):
            return jsonify({'error': 'Uploaded file must be a valid PDF'}), 400

        rel_path = save_upload(report_file, 'blood_reports')
        db.patients.update_one({'patient_id': patient_id}, {'$set': {'blood_report': rel_path}})
        db.reports_log.insert_one({
            'patient_id': patient_id,
            'report_type': 'blood',
            'uploaded_by': session['user_id'],
            'file_path': rel_path,
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'Blood report uploaded successfully'})

    return render_template('upload_blood_report.html')


# -----------------------------
# === Radiologist Routes ======
# -----------------------------
@app.route('/rad/upload_scan_report', methods=['GET', 'POST'])
@role_required('radiologist')
def rad_upload_scan_report():
    """
    Radiologist only: upload scan/radiology report.
    """
    if request.method == 'POST':
        patient_id = request.form.get('patientId').strip()
        report_file = request.files.get('reportFile')
        if not patient_id or not report_file:
            return jsonify({'error': 'Patient ID and report file required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        if not validate_pdf(report_file):
            return jsonify({'error': 'Uploaded file must be a valid PDF'}), 400

        rel_path = save_upload(report_file, 'scan_reports')
        db.patients.update_one({'patient_id': patient_id}, {'$set': {'scan_report': rel_path}})
        db.reports_log.insert_one({
            'patient_id': patient_id,
            'report_type': 'scan',
            'uploaded_by': session['user_id'],
            'file_path': rel_path,
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'Scan report uploaded successfully'})

    return render_template('upload_scan_report.html')


# -----------------------------
# === Coordinator Routes ======
# -----------------------------
@app.route('/coord/upload_progress_report', methods=['GET', 'POST'])
@role_required('coordinator')
def coord_upload_progress_report():
    """
    Coordinator only: upload progress/consultation reports.
    Implementation identical to blood/scan but with a separate folder.
    """
    if request.method == 'POST':
        patient_id = request.form.get('patientId').strip()
        report_file = request.files.get('reportFile')
        if not patient_id or not report_file:
            return jsonify({'error': 'Patient ID and report file required'}), 400

        patient = db.patients.find_one({'patient_id': patient_id})
        if not patient:
            return jsonify({'error': 'Patient ID not found'}), 404

        if not validate_pdf(report_file):
            return jsonify({'error': 'Uploaded file must be a valid PDF'}), 400

        rel_path = save_upload(report_file, 'progress_reports')
        db.patients.update_one({'patient_id': patient_id}, {'$set': {'progress_report': rel_path}})
        db.reports_log.insert_one({
            'patient_id': patient_id,
            'report_type': 'progress',
            'uploaded_by': session['user_id'],
            'file_path': rel_path,
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'Progress report uploaded successfully'})

    return render_template('upload_progress_report.html')


# -----------------------------
# ==== Download Summaries =====
# -----------------------------
@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    """
    Serve static files for download. Make sure to sanitize `filename`
    or only allow downloads from designated folders.
    """
    # Only allow paths under 'static/uploads/'
    safe_base = os.path.join(app.root_path, 'static', 'uploads')
    full_path = os.path.normpath(os.path.join(app.root_path, filename))

    if not full_path.startswith(safe_base):
        abort(403)

    if not os.path.isfile(full_path):
        abort(404)

    return send_file(full_path, as_attachment=True)

# =========================
# ==== Error Handlers =====
# =========================
@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500





if __name__ == '__main__':
    # For development only; in production, use gunicorn/uwsgi + HTTPS
    app.run(debug=True, host='0.0.0.0', port=5000)
