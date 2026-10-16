# CareTrack — Patient Case and Follow-Up Management System

CareTrack is an academic web application demonstrating how MongoDB can support patient profiles, visit histories, prescription records, follow-up workflows, and analytics. The final application uses a **Flask backend**, an HTML/CSS/JavaScript frontend, **PyMongo**, and MongoDB.

> **Academic prototype only.** Use synthetic/fictional data only. Do not enter real patient information or use this project for diagnosis, treatment, or medical decision-making.

## Features

- Register, view, search, update, and delete fictional patient records
- Record visits, list visits with patient details, and update visit records
- Create prescription records and review them in patient case history
- View a patient's visit history
- Dashboard counts for patients, visits, prescriptions, and today's visits
- Analytics for common diagnoses, monthly visits, recent visits, medicine frequency, visits by doctor, follow-up status, and patients with the most visits
- Import patient, visit, and prescription records from CSV
- Export the patient list to CSV
- MongoDB indexes for common lookups and history queries
- Aggregation stages including `$match`, `$group`, `$sort`, `$limit`, `$lookup`, `$unwind`, `$project`, `$toLower`, `$addToSet`, and `$size`

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, Flask
- **Database:** MongoDB Community Server or MongoDB Atlas
- **Database driver:** PyMongo
- **CSV handling:** Pandas
- **Configuration:** `python-dotenv`

## Project Structure

```text
CareTrack/
├── server.py              # Flask routes, validation, PyMongo queries and aggregations
├── templates/
│   └── index.html         # Website layout and forms
├── static/
│   ├── app.js             # API requests and dynamic UI updates
│   └── style.css          # Website styling
├── schema_examples.js     # Example MongoDB shell queries
├── requirements.txt       # Python dependencies

```

The exact files in your copy may vary. Keep credentials in `.env`; do not commit secrets to version control.

## Database Design

The default database is `caretrack_db`. It can be changed with the `MONGODB_DB` environment variable. The application uses three collections.

### `patients`

One document per patient, with fields such as `_id`, `full_name`, `patient_code`, `date_of_birth`, `gender`, `phone`, `email`, `allergies`, `notes`, `created_at`, and `updated_at`. Allergies are stored as an embedded array. `patient_code` is normalized to uppercase and has a unique index.

### `visits`

One document per visit, with fields such as `_id`, `patient_id`, `visit_date`, `doctor_name`, `symptoms`, `diagnosis`, `treatment_notes`, `follow_up_status`, `follow_up_date`, and timestamps. `patient_id` stores an ObjectId reference to `patients._id`.

### `prescriptions`

One document per prescription, with fields such as `_id`, `patient_id`, optional `visit_id`, `medicine`, `dosage`, `frequency`, `duration`, `instructions`, and `created_at`.

Visits and prescriptions are separate collections so their records can grow and be queried independently. MongoDB does not automatically enforce relational foreign-key constraints; the application stores ObjectId references and uses query logic or `$lookup` to retrieve related information.

The normal website prescription form stores `patient_id` but does not set `visit_id`; the CSV import path can associate a prescription with a visit when the supplied data allows it.

## Indexes

The backend creates these seven index definitions:

| Collection | Index | Purpose |
|---|---|---|
| `patients` | `patient_code` ascending, unique | Prevent duplicate patient codes and support exact lookups |
| `patients` | `full_name` ascending | Support name-oriented queries and sorting |
| `patients` | `phone` ascending | Support phone lookups |
| `visits` | `patient_id` ascending + `visit_date` descending | Support patient visit history |
| `visits` | `doctor_name` ascending | Support doctor-oriented queries |
| `prescriptions` | `patient_id` ascending + `created_at` descending | Support patient prescription history |
| `prescriptions` | `visit_id` ascending | Support visit-linked prescription lookups |

Indexes can improve suitable queries, but flexible regular-expression searches may not use them efficiently.

## Requirements

- Python 3.12 is recommended for the setup below
- MongoDB Community Server running locally or a MongoDB Atlas cluster
- A terminal and a code editor such as VS Code

## Setup

### 1. Configure MongoDB

**Option A — Local MongoDB**

Install and start MongoDB Community Server. A common local connection URI is:

```text
mongodb://localhost:27017/
```

**Option B — MongoDB Atlas**

Create an Atlas database user, allow your current IP address in Network Access, and copy the Python driver connection string. Replace the username and password placeholders. Do not share or commit the connection string.

### 2. Create a virtual environment and install dependencies

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root. If `.env.example` is included, copy it and edit the values.

```dotenv
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=caretrack_db
```

For Atlas, set `MONGODB_URI` to your Atlas connection string instead. Keep `.env` private and out of Git.

### 4. Run the application

From the project root, run:

```bash
python server.py
```

The Flask application runs locally on port `5000` when started directly. Open `http://localhost:5000` in your browser.

If the application cannot connect, verify that MongoDB is running, the URI and database name are correct, and Atlas Network Access allows your connection.

## Suggested Demo Flow

1. Start MongoDB and launch the Flask application.
2. Review the dashboard.
3. Register a fictional patient with a unique patient code.
4. Search for the patient and open their case history.
5. Add a visit and review it in the visit list/history.
6. Add a prescription record.
7. Review diagnosis, monthly visit, medicine, doctor, follow-up, and repeat-visit analytics.
8. If using the supplied CSV files, test import with synthetic records and export the patient list.
9. Use MongoDB Compass or the MongoDB shell to inspect `patients`, `visits`, and `prescriptions`.

Use only fictional data during the demonstration.

## MongoDB Concepts Demonstrated

- **Document model:** records are stored as BSON documents.
- **Embedded data:** allergies are stored as an array in a patient document.
- **References:** `visits.patient_id` and `prescriptions.patient_id` reference `patients._id`.
- **CRUD:** PyMongo methods include `insert_one()`, `find()`, `find_one()`, `update_one()`, `delete_one()`, and `delete_many()`.
- **Filtering and searching:** operators include `$or`, `$regex`, `$exists`, `$ne`, `$gte`, and `$lte`.
- **Aggregation:** pipelines group, count, sort, limit, join, and reshape records.
- **Indexes:** a unique patient-code index plus indexes for common lookups and history queries.
- **CSV transfer:** Pandas reads and writes CSV data while PyMongo inserts or retrieves documents.

### Aggregation Examples

- **Common diagnoses:** `$match` → `$group` → `$sort` → `$limit`
- **Monthly visits:** `$group` using `$year` and `$month` → chronological `$sort`
- **Recent visits:** `$sort` → `$limit` → `$lookup` → `$unwind` → `$project`
- **Medicine analytics:** `$group` using `$toLower`, `$sum`, and `$addToSet` → `$project` using `$size` → `$sort` → `$limit`
- **Visits by doctor and follow-up status:** `$group` → `$sort`
- **Patients with the most visits:** `$group` → `$sort` → `$limit` → `$lookup` → `$unwind` → `$project`

The frontend requests data from Flask and displays the responses; MongoDB performs the aggregation calculations through PyMongo.

## Validation and Data Integrity

The backend checks required patient name/code, required doctor/symptoms for visits, required patient/medicine for prescriptions, date formats, patient-code normalization, and CSV columns/references. A unique MongoDB index enforces uniqueness for `patient_code`.

The current implementation does **not** configure MongoDB JSON Schema validators. References are not foreign-key constraints, and some visit/prescription paths do not consistently verify that the referenced patient exists before insertion.

## Troubleshooting

- **`MONGODB_URI is missing`:** create `.env` beside `server.py` and set `MONGODB_URI`.
- **Atlas authentication failed:** verify the database username and password; URL-encode special characters in the password if needed.
- **Server selection timeout:** check that MongoDB is running or that your IP is allowed in Atlas Network Access.
- **Module not found:** activate the virtual environment and run `pip install -r requirements.txt`.
- **Duplicate patient code:** use a unique patient code; the database has a unique index on this field.
- **CSV import errors:** verify expected columns, patient codes, and any visit references required by the import format.

## Limitations and Future Improvements

CareTrack is a small academic prototype with these limitations:

- Synthetic demonstration data only; not suitable for real clinical records.
- No authentication, user roles, or access-control checks.
- No MongoDB JSON Schema validator configured.
- Patient deletion uses sequential database writes rather than one transaction.
- The regular prescription form does not attach a prescription to a specific visit.
- Referenced patient documents are not consistently verified before visit or prescription insertion.
- No production-grade audit logging, backups, privacy controls, or regulatory compliance.

Possible improvements include stronger reference validation, visit-linked prescription creation in the website, consistent medicine-name normalization, automated tests, pagination, authentication/authorization, audit logs, secure secret management, and backup/recovery planning.

## Responsible Use

Patient information is sensitive. Keep this project restricted to fictional sample data. Do not use it to store real patient records or make medical decisions. Any real-world deployment would require extensive security, privacy, legal, regulatory, operational, and clinical review.

## Academic Context

CareTrack was developed for **CSE494 — Intelligent NoSQL Databases**. It demonstrates MongoDB document design, PyMongo integration, CRUD operations, indexes, application-level validation, aggregation pipelines, and CSV import/export in a web application.
