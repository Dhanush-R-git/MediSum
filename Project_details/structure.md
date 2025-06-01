```bash
/patient‐portal/
├── app.py
├── .env
├── requirements.txt
├── tailwind.config.js
├── postcss.config.js
├── static/
│   ├── css/
│   │   └── main.css          # compiled Tailwind CSS
│   ├── js/
│   │   ├── dashboard.js      # JS for dashboard interactivity
│   │   └── auth.js           # JS for login/signup
│   └── uploads/              # (subfolders created automatically)
│       ├── doctor_reports/
│       ├── scan_reports/
│       ├── blood_reports/
│       └── summaries/
├── templates/
│   ├── base.html             # Base template (navbar, sidebar)
│   ├── login.html
│   ├── register.html         # (optional) if you allow user registration
│   ├── create_patient.html
│   ├── upload_doctor_report.html
│   ├── upload_scan_report.html
│   ├── upload_blood_report.html
│   ├── dashboard.html        # main portal dashboard (patients list + overview)
│   ├── medical_summaries.html
│   └── partials/
│       ├── sidebar.html
│       ├── navbar.html
│       └── patient_card.html # reusable component for patient list
└── utils/
    ├── security.py           # password hashing / session helpers / role decorators
    └── file_utils.py         # file‐upload validation helpers
```