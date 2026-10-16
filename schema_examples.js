// Run these examples in mongosh after connecting to your caretrack_db database.
// The app automatically creates the main indexes when it connects.

// Example patient document
db.patients.insertOne({
  full_name: "Demo Patient",
  patient_code: "MONGO-DEMO-001",
  date_of_birth: ISODate("2000-01-01T00:00:00Z"),
  gender: "Prefer not to say",
  phone: "0000000000",
  email: "demo@example.test",
  allergies: ["Example allergy"],
  notes: "Fictional sample only",
  created_at: new Date(),
  updated_at: new Date()
});

// Example visit document (patient_id should be the _id of a patient document)
const patient = db.patients.findOne({ patient_code: "MONGO-DEMO-001" });
if (patient) {
  db.visits.insertOne({
    patient_id: patient._id,
    visit_date: new Date(),
    doctor_name: "Dr. Example",
    symptoms: "Fictional sample symptom",
    diagnosis: "Example diagnosis",
    treatment_notes: "Sample only",
    follow_up_status: "Recommended",
    follow_up_date: null,
    created_at: new Date()
  });
}

// Aggregation: count visits by diagnosis
db.visits.aggregate([
  { $match: { diagnosis: { $exists: true, $ne: "" } } },
  { $group: { _id: "$diagnosis", visit_count: { $sum: 1 } } },
  { $sort: { visit_count: -1 } }
]);

// Aggregation: join visits with patient names
db.visits.aggregate([
  { $lookup: {
      from: "patients",
      localField: "patient_id",
      foreignField: "_id",
      as: "patient"
  }},
  { $unwind: "$patient" },
  { $project: {
      _id: 0,
      patient_code: "$patient.patient_code",
      patient_name: "$patient.full_name",
      visit_date: 1,
      diagnosis: 1,
      doctor_name: 1
  }}
]);

// Inspect whether a query uses an index
db.patients.find({ patient_code: "MONGO-DEMO-001" }).explain("executionStats");
