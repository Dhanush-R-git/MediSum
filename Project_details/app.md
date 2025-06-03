# Flask App (`app.py`) – Endpoint Overview

This document provides an overview of the endpoints and main features implemented in `app.py` for the MediSum project.

## Features

- **Environment Variables:**  
  Loads secrets and configuration from a `.env` file.

- **MongoDB Integration:**  
  Connects to MongoDB for storing and retrieving users, patients, summaries, experts, and related data.

- **Authentication:**  
  - `/login` – User login route  
  - `/logout` – User logout route

- **Role-Based Routing:**  
  Endpoints are protected and routed based on user roles.

---

## Endpoints by Role

### Doctors
- `/dashboard`  
  Main patient portal with tabs.

- `/create_patient` (GET/POST)  
  Create a new patient record.

- `/upload_doctor_report` (GET/POST)  
  Upload a doctor's report.

- `/upload_scan_report` (GET/POST)  
  Upload a scan report.

- `/upload_blood_report` (GET/POST)  
  Upload a blood report.

- `/generate_summary` (POST)  
  Generate a medical summary.

- `/medical_summaries` (GET/POST)  
  View or manage medical summaries.

- `/send_expert_email` (POST)  
  Send a summary or report to an expert via email.

---

### Lab Technicians
- `/lab/upload_blood_report` (GET/POST)  
  Upload blood test reports.

---

### Radiologists
- `/rad/upload_scan_report` (GET/POST)  
  Upload scan (e.g., X-ray, MRI) reports.

---

### Coordinators
- `/coord/upload_progress_report` (GET/POST)  
  Upload patient progress reports (if needed).

- `/coord/upload_consultation_report` (GET/POST)  
  Upload consultation reports.

---

## Notes

- All endpoints are protected with authentication and role-based access control.
- File uploads are validated and securely stored.
- Email functionality is available for expert consultations.
- MongoDB is used as the primary data store for all user and medical data.
