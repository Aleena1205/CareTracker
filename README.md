# CareTrack — Patient Case Management (MongoDB project)

A small academic prototype inspired by SIH 2026 problem statement **SIH26047: Patient Case-Taking Software**. It demonstrates MongoDB document storage, CRUD operations, indexes, `$lookup`, and aggregation analytics through a lightweight Streamlit interface.

> **Safety:** Use synthetic data only. This is not a clinical product and must not be used to diagnose, treat, or make medical decisions. Do not enter real patient data.

## Features

- Register, edit, and search fictional patients
- Update existing visit records
- Record patient visits and case notes
- Store prescription records (storage only; no medication recommendations)
- View a patient's visit history
- Dashboard metrics and diagnosis/monthly visit charts
- Aggregation reports for visits by doctor, follow-up status, and repeat visits
- Export patient list to CSV
- MongoDB indexes for patient code, name, phone, visit history, doctor, and prescriptions
- Insert sample demo records

## Tech stack

- MongoDB Community Server or MongoDB Atlas
- Python + PyMongo
- Streamlit UI
- Pandas for simple tabular reporting

## 1. Set up MongoDB

Choose one:

### Option A — Local MongoDB
Install and start MongoDB Community Server. The default URI is usually:

`mongodb://localhost:27017/`

### Option B — MongoDB Atlas
Create a database user, allow your current IP in Network Access, and copy the Python driver connection string. Replace the username/password placeholders. Avoid sharing your connection string.

## 2. Install and run

Open a terminal in this project folder.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` in VS Code and set `MONGODB_URI` and `MONGODB_DB`.

Then run:

```powershell
streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, then:

```bash
streamlit run app.py
```

The app opens in your browser, typically at `http://localhost:8501`.

## 3. Recommended demo flow

1. Open **Demo data** and click **Insert demo data**.
2. Open **Dashboard** to view counts and charts.
3. Open **Search & case history** and search `DEMO-1001`.
4. Register another fictional patient.
5. Record a visit and add a prescription record.
6. Open **Analytics & export** and review the aggregation reports.
7. Use MongoDB Compass to inspect the `patients`, `visits`, and `prescriptions` collections.

## MongoDB collections

### `patients`
One document per patient. Stores basic profile fields and an array of allergies.

### `visits`
One document per visit. References a patient with `patient_id`. This supports multiple visits per patient without making the patient document grow indefinitely.

### `prescriptions`
One document per prescription record. References the patient with `patient_id`. The current MVP does not associate prescriptions with a particular visit in the UI, but the schema supports an optional `visit_id`.

## MongoDB concepts to explain in your viva

- **Document model:** patient data is represented as BSON documents.
- **References:** `visits.patient_id` links a visit to a patient.
- **Embedded data:** allergies are stored as an array inside the patient document.
- **Indexes:** unique index on `patient_code`; indexes on fields used in common searches.
- **Aggregation:** `$group`, `$sort`, `$match`, `$lookup`, `$unwind`, `$project`.
- **CRUD:** insert patients/visits/prescriptions; find records; update is available through the MongoDB tools and can be added to the UI as an extension; deletes are intentionally not exposed in this first safe MVP.
- **CSV export:** reports can be exported for demonstration.

## Troubleshooting

- **`MONGODB_URI is missing`:** ensure `.env` exists beside `app.py` and has `MONGODB_URI=...`.
- **Authentication failed:** verify the Atlas database username/password. URL-encode special characters in the password.
- **Server selection timeout:** check that MongoDB is running or that your IP is allowed in Atlas Network Access.
- **`streamlit` not recognized:** activate the virtual environment and run `python -m streamlit run app.py`.
- **Duplicate patient code:** every patient code must be unique.

## Limitations

This is a small academic prototype, not a production medical-record system. It does not provide authentication, encryption policy, regulatory compliance, clinical validation, audit-grade access controls, or backups. Do not use real patient data.
