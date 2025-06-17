# auth.py
import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, abort, flash
from datetime import datetime
from pymongo import MongoClient
from utils.security import hash_password, check_password

bp = Blueprint('auth', __name__)

# Share the same DB client
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client["reportdata"]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You must be logged in to access this page.', 'warning')
            return redirect(url_for('auth.login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if user_role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('doctor.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@bp.route('/')
def login_page():
    return render_template('login.html')

@bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        return render_template('login.html', error="Username and password required")
    user = db.users.find_one({'username': username})
    if not user or not check_password(password, user['password_hash']):
        return render_template('login.html', error="Invalid credentials")
    session['logged_in'] = True
    session['username'] = user['username']
    session['user_id']  = str(user['_id'])
    session['role']     = user['role']

    # Redirect by role
    role = user['role']
    if role == 'doctor':
        return redirect(url_for('doctor.dashboard'))
    elif role == 'lab_tech':
        return redirect(url_for('lab.upload_blood'))
    elif role == 'radiologist':
        return redirect(url_for('radiology.upload_scan'))
    elif role == 'coordinator':
        return redirect(url_for('coordinator.upload_progress'))
    else:
        # Unknown role
        session.clear()
        return render_template('login.html', error="Invalid role")

@bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))

@bp.route('/register', methods=['GET','POST'])
#@role_required('admin')
def register_page():
    if request.method=='POST':
        u = request.form
        if db.users.find_one({'username': u['username']}):
            return render_template('register.html', error="Username already exists.")
        pw = hash_password(u['password'])
        db.users.insert_one({
            'username': u['username'],
            'email':    u['email'],
            'full_name':u['full_name'],
            'role':     u['role'],
            'password_hash': pw,
            'created': datetime.utcnow()
        })
        return redirect(url_for('auth.login_page'))
    return render_template('register.html')

@bp.route('/create_patient', methods=['GET','POST'])
@role_required('doctor')
def create_patient():
    if request.method=='POST':
        f = request.form
        # Validate...
        count = db.patients.count_documents({}) + 1
        pid = f"PAT{count:04d}"
        db.patients.insert_one({
            'patient_id': pid,
            'name':       f['name'],
            'dob':        datetime.strptime(f['dob'],'%Y-%m-%d'),
            'sex':        f['sex'],
            'email':      f['email'],
            'phone':      f['phone'],
            'address':    f['address'],
            'date_created': datetime.utcnow(),
            'doctor_docs':   {},
            'scan_docs':     {},
            'blood_docs':    {},
            'progress_docs': [],
            'created_by': session['user_id']
        })
        return jsonify({'message':'Patient created sucessfully','patient_id':pid})
    return render_template('create_patient.html')
