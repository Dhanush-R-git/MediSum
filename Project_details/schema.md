---
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
- **Arrows** show foreign key relationships.
- `generated_by` in summaries references `users._id`.
- `patient_id` in summaries references `patients._id`.
---