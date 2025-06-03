# utils/security.py

import bcrypt
from flask import session, redirect, url_for, request, abort
from functools import wraps

# ==========================
# Password hashing functions
# ==========================
def hash_password(plain_password: str) -> bytes:
    """
    Hash a plaintext password using bcrypt.
    Returns the salt‐appended hash.
    """
    salt = bcrypt.gensalt()  # default cost
    pw_hash = bcrypt.hashpw(plain_password.encode('utf‐8'), salt)
    return pw_hash  # store this in the DB

def check_password(plain_password: str, hashed: bytes) -> bool:
    """
    Compare plaintext password against stored hash.
    """
    return bcrypt.checkpw(plain_password.encode('utf‐8'), hashed)

# ====================================
# Decorators for role‐based access control
# ====================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

def role_required(*allowed_roles):
    """
    Usage:
        @role_required('doctor', 'admin')
        def some_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('login_page'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                # 403 Forbidden
                return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

'''
hash_password: Call before inserting a new user into db.users.

check_password: Call at login.

login_required: Redirects to login if not in session.

role_required('doctor'): Wraps any route to ensure only session['role'] == 'doctor'.

Add a /register route if you want self‐registration. Otherwise, preload admin accounts into the DB.

'''