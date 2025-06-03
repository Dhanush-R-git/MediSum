from datetime import datetime
from utils.security import hash_password
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["reportdata"]

admin = {
    "username": "admin",
    "email": "admin@hospital.com",
    "full_name": "Admin User",
    "role": "doctor",  # or a special 'admin' role you define
    "password_hash": hash_password("AdminPass123!"),
    "date_created": datetime.utcnow()
}
db.users.insert_one(admin)
print("Admin user created successfully.")