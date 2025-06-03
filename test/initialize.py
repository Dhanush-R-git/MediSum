from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["reportdata"]

# Ensure indexes:
db.users.create_index("username", unique=True)
db.patients.create_index("patient_id", unique=True)
db.summaries.create_index([("patient_id", 1), ("timestamp", -1)])
db.reports_log.create_index([("patient_id", 1), ("timestamp", -1)])

# (Optional) Insert sample experts:
db.experts.insert_many([
    {"name": "Dr. Alice Heart", "email": "alice.heart@hospital.com", "specialty": "Cardiology"},
    {"name": "Dr. Bob Spine", "email": "bob.spine@hospital.com", "specialty": "Orthopedics"},
    {"name": "Dr. Carol Neuro", "email": "carol.neuro@hospital.com", "specialty": "Neurology"},
    {"name": "Dr. Dhanush Ravi", "email": "dhanushravi.rds@gmail.com", "specialty": "Radiology"}
])
