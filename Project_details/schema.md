
```text
+---------+      +-----------+      +--------------+
|  users  |      | patients  |      |  summaries   |
+---------+      +-----------+      +--------------+
| _id     |<--+  | _id       |      | _id          |
| username|   |  | patient_id|----->| patient_id   |
| pw_hash |   |  | name      |      | summary_text |
| role    |   +->| dob       |      | pdf_path     |
| email   |      | sex       |      | generated_by |--+
| date    |      | ...       |      | timestamp    |  |
+---------+      +-----------+      +--------------+  |
      ^                                    ^          |
      |                                    |          |
      +------------------------------------+----------+
```
---
- **Arrows** show foreign key relationships.
- `generated_by` in summaries references `users._id`.
- `patient_id` in summaries references `patients._id`.

Notes:

- users._id is referenced in patients.created_by (which doctor created the patient) and in summaries.generated_by.

- To enforce data integrity, use MongoDB’s unique indexes on username and patient_id. In production, also enable validations (e.g. via MongoDB schema validation).

- All user passwords are stored as a bcrypt hash (never plaintext).


---
