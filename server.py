import os
import io
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId

load_dotenv()

app = Flask(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("MONGODB_DB", "caretrack_db").strip() or "caretrack_db"

# ── DB connection ──────────────────────────────────────────────────────────────
_client = None
_db = None

def get_db():
    global _client, _db
    if _db is not None:
        return _db
    _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")
    _db = _client[DB_NAME]
    _db.patients.create_index([("patient_code", ASCENDING)], unique=True)
    _db.patients.create_index([("full_name", ASCENDING)])
    _db.patients.create_index([("phone", ASCENDING)])
    _db.visits.create_index([("patient_id", ASCENDING), ("visit_date", DESCENDING)])
    _db.visits.create_index([("doctor_name", ASCENDING)])
    _db.prescriptions.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)])
    _db.prescriptions.create_index([("visit_id", ASCENDING)])
    return _db


def jsonify_doc(doc):
    """Recursively convert MongoDB doc to JSON-safe dict."""
    if isinstance(doc, list):
        return [jsonify_doc(d) for d in doc]
    if isinstance(doc, dict):
        return {k: jsonify_doc(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.strftime("%Y-%m-%d")
    return doc


def as_id(value: Any) -> ObjectId:
    return value if isinstance(value, ObjectId) else ObjectId(str(value))


def calculate_age(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", db_name=DB_NAME)


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    db = get_db()
    today_start = datetime.combine(date.today(), datetime.min.time())
    tomorrow_end = datetime.combine(date.today(), datetime.max.time())

    stats = {
        "patients": db.patients.count_documents({}),
        "visits": db.visits.count_documents({}),
        "prescriptions": db.prescriptions.count_documents({}),
        "visits_today": db.visits.count_documents({
            "visit_date": {"$gte": today_start, "$lte": tomorrow_end}
        }),
    }

    diagnoses = list(db.visits.aggregate([
        {"$match": {"diagnosis": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$diagnosis", "visit_count": {"$sum": 1}}},
        {"$sort": {"visit_count": -1}},
        {"$limit": 8},
    ]))

    visits_by_month = list(db.visits.aggregate([
        {"$group": {
            "_id": {"year": {"$year": "$visit_date"}, "month": {"$month": "$visit_date"}},
            "visits": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
    ]))

    recent_visits = list(db.visits.aggregate([
        {"$sort": {"visit_date": -1}},
        {"$limit": 10},
        {"$lookup": {"from": "patients", "localField": "patient_id", "foreignField": "_id", "as": "patient"}},
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "date": "$visit_date",
            "patient": "$patient.full_name",
            "patient_code": "$patient.patient_code",
            "doctor": "$doctor_name",
            "diagnosis": "$diagnosis",
            "status": "$follow_up_status",
        }},
    ]))

    return jsonify({
        "stats": stats,
        "diagnoses": [{"label": r["_id"], "value": r["visit_count"]} for r in diagnoses],
        "visits_by_month": [
            {"month": f"{r['_id']['year']}-{r['_id']['month']:02d}", "visits": r["visits"]}
            for r in visits_by_month
        ],
        "recent_visits": jsonify_doc(recent_visits),
    })


# ── Patients ──────────────────────────────────────────────────────────────────
@app.route("/api/patients", methods=["GET"])
def api_get_patients():
    db = get_db()
    patients = list(db.patients.find({}, {"full_name": 1, "patient_code": 1, "date_of_birth": 1}).sort("full_name", 1))
    return jsonify(jsonify_doc(patients))


@app.route("/api/patients/register", methods=["POST"])
def api_register_patient():
    db = get_db()
    data = request.json
    full_name = (data.get("full_name") or "").strip()
    patient_code = (data.get("patient_code") or "").strip().upper()
    if not full_name or not patient_code:
        return jsonify({"error": "Full name and patient code are required."}), 400
    try:
        dob_str = data.get("date_of_birth", "2000-01-01")
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    allergies_raw = data.get("allergies", "")
    allergies = [x.strip() for x in str(allergies_raw).split(",") if x.strip()]
    patient = {
        "full_name": full_name,
        "patient_code": patient_code,
        "date_of_birth": dob,
        "gender": data.get("gender", "Prefer not to say"),
        "phone": (data.get("phone") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "allergies": allergies,
        "notes": (data.get("notes") or "").strip(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        result = db.patients.insert_one(patient)
        return jsonify({"success": True, "id": str(result.inserted_id), "patient_code": patient_code})
    except PyMongoError as exc:
        return jsonify({"error": f"Could not save patient. Patient codes must be unique. {exc}"}), 409


@app.route("/api/patients/<patient_id>", methods=["GET"])
def api_get_patient(patient_id):
    db = get_db()
    p = db.patients.find_one({"_id": as_id(patient_id)})
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    doc = jsonify_doc(p)
    dob = p.get("date_of_birth")
    doc["age"] = calculate_age(dob)
    doc["visit_count"] = db.visits.count_documents({"patient_id": p["_id"]})

    # Visit history with linked prescriptions
    visits = list(db.visits.aggregate([
        {"$match": {"patient_id": p["_id"]}},
        {"$sort": {"visit_date": -1}},
        {"$lookup": {"from": "prescriptions", "localField": "_id", "foreignField": "visit_id", "as": "prescriptions"}},
    ]))
    doc["visits"] = jsonify_doc(visits)

    # All prescriptions
    prescriptions = list(db.prescriptions.find({"patient_id": p["_id"]}).sort("created_at", -1))
    doc["prescriptions"] = jsonify_doc(prescriptions)
    return jsonify(doc)


@app.route("/api/patients/<patient_id>", methods=["DELETE"])
def api_delete_patient(patient_id):
    db = get_db()
    pid = as_id(patient_id)
    patient = db.patients.find_one({"_id": pid})
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    # Step 1: Find all visit IDs for this patient
    visit_ids = [v["_id"] for v in db.visits.find({"patient_id": pid}, {"_id": 1})]

    # Step 2: Delete prescriptions linked by patient_id OR by visit_id
    db.prescriptions.delete_many({
        "$or": [
            {"patient_id": pid},
            {"visit_id": {"$in": visit_ids}},
        ]
    })

    # Step 3: Delete all visits for this patient
    db.visits.delete_many({"patient_id": pid})

    # Step 4: Delete the patient record
    db.patients.delete_one({"_id": pid})

    return jsonify({"success": True, "deleted_visits": len(visit_ids)})


@app.route("/api/patients/<patient_id>", methods=["PUT"])
def api_update_patient(patient_id):
    db = get_db()
    data = request.json
    full_name = (data.get("full_name") or "").strip()
    patient_code = (data.get("patient_code") or "").strip().upper()
    if not full_name or not patient_code:
        return jsonify({"error": "Full name and patient code are required."}), 400
    try:
        dob_str = data.get("date_of_birth", "2000-01-01")
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    allergies_raw = data.get("allergies", "")
    allergies = [x.strip() for x in str(allergies_raw).split(",") if x.strip()]
    updated = {
        "full_name": full_name,
        "patient_code": patient_code,
        "date_of_birth": dob,
        "gender": data.get("gender", "Prefer not to say"),
        "phone": (data.get("phone") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "allergies": allergies,
        "notes": (data.get("notes") or "").strip(),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        result = db.patients.update_one({"_id": as_id(patient_id)}, {"$set": updated})
        if result.matched_count:
            return jsonify({"success": True})
        return jsonify({"error": "Patient not found."}), 404
    except PyMongoError as exc:
        return jsonify({"error": f"Could not update. Patient codes must be unique. {exc}"}), 409


@app.route("/api/patients/search", methods=["GET"])
def api_search_patients():
    db = get_db()
    query = request.args.get("q", "").strip()
    if query:
        patients = list(db.patients.find({
            "$or": [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"patient_code": {"$regex": query, "$options": "i"}},
                {"phone": {"$regex": query, "$options": "i"}},
            ]
        }).sort("full_name", 1).limit(50))
    else:
        patients = list(db.patients.find({}).sort("created_at", -1).limit(30))
    return jsonify(jsonify_doc(patients))


# ── Visits ────────────────────────────────────────────────────────────────────
@app.route("/api/visits", methods=["POST"])
def api_add_visit():
    db = get_db()
    data = request.json
    patient_id = data.get("patient_id")
    doctor = (data.get("doctor_name") or "").strip()
    symptoms = (data.get("symptoms") or "").strip()
    if not patient_id or not doctor or not symptoms:
        return jsonify({"error": "patient_id, doctor_name, and symptoms are required."}), 400
    try:
        visit_date = datetime.strptime(data.get("visit_date", str(date.today())), "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    follow_up_date = None
    if data.get("follow_up_date"):
        try:
            follow_up_date = datetime.strptime(data["follow_up_date"], "%Y-%m-%d")
        except ValueError:
            pass

    visit = {
        "patient_id": as_id(patient_id),
        "visit_date": visit_date,
        "doctor_name": doctor,
        "symptoms": symptoms,
        "diagnosis": (data.get("diagnosis") or "").strip(),
        "treatment_notes": (data.get("treatment_notes") or "").strip(),
        "follow_up_status": data.get("follow_up_status", "Not required"),
        "follow_up_date": follow_up_date,
        "created_at": datetime.now(timezone.utc),
    }
    result = db.visits.insert_one(visit)
    return jsonify({"success": True, "id": str(result.inserted_id)})


@app.route("/api/visits/list", methods=["GET"])
def api_list_visits():
    db = get_db()
    visits = list(db.visits.aggregate([
        {"$sort": {"visit_date": -1}},
        {"$limit": 200},                    # limit BEFORE lookup for performance
        {"$lookup": {"from": "patients", "localField": "patient_id", "foreignField": "_id", "as": "patient"}},
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
    ]))
    return jsonify(jsonify_doc(visits))


@app.route("/api/visits/<visit_id>", methods=["PUT"])
def api_update_visit(visit_id):
    db = get_db()
    data = request.json
    doctor = (data.get("doctor_name") or "").strip()
    symptoms = (data.get("symptoms") or "").strip()
    if not doctor or not symptoms:
        return jsonify({"error": "doctor_name and symptoms are required."}), 400
    try:
        visit_date = datetime.strptime(data.get("visit_date", str(date.today())), "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    follow_up_date = None
    if data.get("follow_up_date"):
        try:
            follow_up_date = datetime.strptime(data["follow_up_date"], "%Y-%m-%d")
        except ValueError:
            pass

    update_doc = {
        "visit_date": visit_date,
        "doctor_name": doctor,
        "symptoms": symptoms,
        "diagnosis": (data.get("diagnosis") or "").strip(),
        "treatment_notes": (data.get("treatment_notes") or "").strip(),
        "follow_up_status": data.get("follow_up_status", "Not required"),
        "follow_up_date": follow_up_date,
        "updated_at": datetime.now(timezone.utc),
    }
    result = db.visits.update_one({"_id": as_id(visit_id)}, {"$set": update_doc})
    if result.matched_count:
        return jsonify({"success": True})
    return jsonify({"error": "Visit not found."}), 404


# ── Prescriptions ─────────────────────────────────────────────────────────────
@app.route("/api/prescriptions", methods=["POST"])
def api_add_prescription():
    db = get_db()
    data = request.json
    patient_id = data.get("patient_id")
    medicine = (data.get("medicine") or "").strip()
    if not patient_id or not medicine:
        return jsonify({"error": "patient_id and medicine are required."}), 400
    db.prescriptions.insert_one({
        "patient_id": as_id(patient_id),
        "medicine": medicine,
        "dosage": (data.get("dosage") or "").strip(),
        "frequency": (data.get("frequency") or "").strip(),
        "duration": (data.get("duration") or "").strip(),
        "instructions": (data.get("instructions") or "").strip(),
        "created_at": datetime.now(timezone.utc),
    })
    return jsonify({"success": True})


# ── Analytics ─────────────────────────────────────────────────────────────────
@app.route("/api/analytics/medicines")
def api_analytics_medicines():
    db = get_db()
    medicine_stats = list(db.prescriptions.aggregate([
        # Group by medicine name (case-insensitive normalised)
        {"$group": {
            "_id": {"$toLower": "$medicine"},
            "medicine_name": {"$first": "$medicine"},
            "prescription_count": {"$sum": 1},
            "distinct_patients": {"$addToSet": "$patient_id"},
        }},
        # Project clean output and compute distinct patient count
        {"$project": {
            "_id": 0,
            "medicine": "$medicine_name",
            "prescription_count": 1,
            "distinct_patient_count": {"$size": "$distinct_patients"},
        }},
        # Sort highest to lowest by prescription count
        {"$sort": {"prescription_count": -1}},
        {"$limit": 20},
    ]))
    return jsonify(medicine_stats)


@app.route("/api/analytics")
def api_analytics():
    db = get_db()
    by_doctor = list(db.visits.aggregate([
        {"$group": {"_id": "$doctor_name", "visits": {"$sum": 1}}},
        {"$sort": {"visits": -1}},
        {"$limit": 15},
    ]))
    follow_up = list(db.visits.aggregate([
        {"$group": {"_id": "$follow_up_status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]))
    top_patients = list(db.visits.aggregate([
        {"$group": {"_id": "$patient_id", "visit_count": {"$sum": 1}}},
        {"$sort": {"visit_count": -1}},
        {"$limit": 10},
        {"$lookup": {"from": "patients", "localField": "_id", "foreignField": "_id", "as": "patient"}},
        {"$unwind": {"path": "$patient", "preserveNullAndEmptyArrays": True}},
        {"$project": {"_id": 0, "name": "$patient.full_name", "code": "$patient.patient_code", "visits": "$visit_count"}},
    ]))
    return jsonify({
        "by_doctor": [{"label": r["_id"] or "Unknown", "value": r["visits"]} for r in by_doctor],
        "follow_up": [{"label": r["_id"] or "Unknown", "value": r["count"]} for r in follow_up],
        "top_patients": jsonify_doc(top_patients),
    })


@app.route("/api/analytics/export-csv")
def api_export_csv():
    db = get_db()
    rows = list(db.patients.find({}, {"_id": 0, "full_name": 1, "patient_code": 1, "gender": 1, "created_at": 1}))
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="patients_export.csv",
    )


# ── CSV Import ────────────────────────────────────────────────────────────────
@app.route("/api/import-csv", methods=["POST"])
def api_import_csv():
    db = get_db()
    patients_file = request.files.get("patients_csv")
    visits_file = request.files.get("visits_csv")
    prescriptions_file = request.files.get("prescriptions_csv")

    if not patients_file or not visits_file or not prescriptions_file:
        return jsonify({"error": "Please upload all three CSV files."}), 400

    try:
        patients_df = pd.read_csv(patients_file, dtype=str).fillna("")
        visits_df = pd.read_csv(visits_file, dtype=str).fillna("")
        prescriptions_df = pd.read_csv(prescriptions_file, dtype=str).fillna("")
    except Exception as exc:
        return jsonify({"error": f"Could not read CSV files: {exc}"}), 400

    required_columns = {
        "patients.csv": {"patient_code", "full_name", "date_of_birth", "gender", "phone", "email", "allergies", "notes"},
        "visits.csv": {"visit_code", "patient_code", "visit_date", "doctor_name", "symptoms", "diagnosis", "treatment_notes", "follow_up_status", "follow_up_date"},
        "prescriptions.csv": {"prescription_code", "patient_code", "visit_code", "medicine", "dosage", "frequency", "duration", "instructions"},
    }
    frames = {"patients.csv": patients_df, "visits.csv": visits_df, "prescriptions.csv": prescriptions_df}
    for filename, required in required_columns.items():
        missing = required - set(frames[filename].columns)
        if missing:
            return jsonify({"error": f"{filename} is missing columns: {', '.join(sorted(missing))}"}), 400

    def parse_date(value, field, allow_blank=False):
        value = str(value).strip()
        if not value and allow_blank:
            return None
        if not value:
            raise ValueError(f"{field} cannot be blank.")
        return datetime.strptime(value, "%Y-%m-%d")

    patient_ids = {}
    patient_inserted = patient_skipped = 0
    visit_ids = {}
    visit_inserted = visit_skipped = 0
    prescription_inserted = prescription_skipped = 0
    errors = []

    for row_num, row in enumerate(patients_df.to_dict("records"), start=2):
        try:
            code = str(row["patient_code"]).strip().upper()
            name = str(row["full_name"]).strip()
            if not code or not name:
                raise ValueError("patient_code and full_name are required.")
            dob = parse_date(row["date_of_birth"], f"patients.csv row {row_num} date_of_birth")
            existing = db.patients.find_one({"patient_code": code})
            if existing:
                patient_ids[code] = existing["_id"]
                patient_skipped += 1
                continue
            allergies = [x.strip() for x in str(row["allergies"]).split("|") if x.strip()]
            if len(allergies) == 1 and "," in allergies[0]:
                allergies = [x.strip() for x in allergies[0].split(",") if x.strip()]
            doc = {
                "patient_code": code, "full_name": name, "date_of_birth": dob,
                "gender": str(row["gender"]).strip() or "Prefer not to say",
                "phone": str(row["phone"]).strip(), "email": str(row["email"]).strip(),
                "allergies": allergies, "notes": str(row["notes"]).strip(),
                "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
            }
            result = db.patients.insert_one(doc)
            patient_ids[code] = result.inserted_id
            patient_inserted += 1
        except Exception as exc:
            errors.append(f"patients.csv row {row_num}: {exc}")

    for p in db.patients.find({}, {"patient_code": 1}):
        if p.get("patient_code"):
            patient_ids.setdefault(p["patient_code"].upper(), p["_id"])

    for row_num, row in enumerate(visits_df.to_dict("records"), start=2):
        try:
            visit_code = str(row["visit_code"]).strip()
            patient_code = str(row["patient_code"]).strip().upper()
            if not visit_code or not patient_code:
                raise ValueError("visit_code and patient_code are required.")
            if patient_code not in patient_ids:
                raise ValueError(f"patient_code {patient_code} was not found.")
            visit_date = parse_date(row["visit_date"], f"visits.csv row {row_num} visit_date")
            existing = db.visits.find_one({"import_code": visit_code})
            if existing:
                visit_ids[visit_code] = existing["_id"]
                visit_skipped += 1
                continue
            doc = {
                "import_code": visit_code, "patient_id": patient_ids[patient_code],
                "visit_date": visit_date, "doctor_name": str(row["doctor_name"]).strip(),
                "symptoms": str(row["symptoms"]).strip(), "diagnosis": str(row["diagnosis"]).strip(),
                "treatment_notes": str(row["treatment_notes"]).strip(),
                "follow_up_status": str(row["follow_up_status"]).strip() or "Not required",
                "follow_up_date": parse_date(row["follow_up_date"], f"visits.csv row {row_num} follow_up_date", allow_blank=True),
                "created_at": datetime.now(timezone.utc),
            }
            result = db.visits.insert_one(doc)
            visit_ids[visit_code] = result.inserted_id
            visit_inserted += 1
        except Exception as exc:
            errors.append(f"visits.csv row {row_num}: {exc}")

    for v in db.visits.find({"import_code": {"$exists": True}}, {"import_code": 1}):
        if v.get("import_code"):
            visit_ids.setdefault(v["import_code"], v["_id"])

    for row_num, row in enumerate(prescriptions_df.to_dict("records"), start=2):
        try:
            prescription_code = str(row["prescription_code"]).strip()
            patient_code = str(row["patient_code"]).strip().upper()
            visit_code = str(row["visit_code"]).strip()
            if not prescription_code or not patient_code:
                raise ValueError("prescription_code and patient_code are required.")
            if patient_code not in patient_ids:
                raise ValueError(f"patient_code {patient_code} was not found.")
            visit_id = visit_ids.get(visit_code)
            if visit_code and not visit_id:
                raise ValueError(f"visit_code {visit_code} was not found.")
            existing = db.prescriptions.find_one({"import_code": prescription_code})
            if existing:
                prescription_skipped += 1
                continue
            db.prescriptions.insert_one({
                "import_code": prescription_code, "patient_id": patient_ids[patient_code],
                "visit_id": visit_id, "medicine": str(row["medicine"]).strip(),
                "dosage": str(row["dosage"]).strip(), "frequency": str(row["frequency"]).strip(),
                "duration": str(row["duration"]).strip(), "instructions": str(row["instructions"]).strip(),
                "created_at": datetime.now(timezone.utc),
            })
            prescription_inserted += 1
        except Exception as exc:
            errors.append(f"prescriptions.csv row {row_num}: {exc}")

    return jsonify({
        "success": True,
        "patients_inserted": patient_inserted,
        "visits_inserted": visit_inserted,
        "prescriptions_inserted": prescription_inserted,
        "patients_skipped": patient_skipped,
        "visits_skipped": visit_skipped,
        "prescriptions_skipped": prescription_skipped,
        "errors": errors,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
