from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import Flask, Response, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pediasense_local.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "pediasense-dev-secret")

db = SQLAlchemy(app)


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False, default="Anonymous Student")
    topic = db.Column(db.String(100), nullable=False)
    age = db.Column(db.String(50), nullable=True)
    sex = db.Column(db.String(30), nullable=True)
    chief_complaint = db.Column(db.Text, nullable=True)
    vitals = db.Column(db.Text, nullable=True)
    assessment = db.Column(db.Text, nullable=True)
    labs = db.Column(db.Text, nullable=True)
    predicted_diagnosis = db.Column(db.Text, nullable=True)
    priority_level = db.Column(db.String(50), nullable=True)
    score = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CaseLibrary(db.Model):
    __tablename__ = "cases"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    expected_diagnosis = db.Column(db.String(200), nullable=False)


def iso_now() -> datetime:
    return datetime.utcnow()


def normalize_text(payload: Dict[str, Any]) -> str:
    parts = [
        str(payload.get("chiefComplaint", "")),
        str(payload.get("assessment", "")),
        str(payload.get("vitals", "")),
        str(payload.get("labs", "")),
    ]
    return " ".join(parts).lower()


def contains_all(text: str, keywords: List[str]) -> bool:
    return all(keyword in text for keyword in keywords)


def score_case(text: str, matched_rule: str) -> Tuple[float, str]:
    completeness_bonus = 10 if len(text) > 50 else 0
    base_scores = {
        "dehydration": 78,
        "asthma": 68,
        "pneumonia": 74,
        "fever": 85,
        "malnutrition": 71,
        "seizure": 76,
        "default": 65,
    }
    score = min(base_scores.get(matched_rule, 65) + completeness_bonus, 98)
    if score >= 85:
        band = "Excellent"
    elif score >= 75:
        band = "Good"
    elif score >= 65:
        band = "Developing"
    else:
        band = "Needs Support"
    return score, band


def analyze_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = normalize_text(payload)

    if contains_all(text, ["diarrhea", "vomiting"]) or (
        "decreased urine" in text and ("dry lips" in text or "dry mucosa" in text)
    ):
        rule = "dehydration"
        topic = "Dehydration"
        diagnoses = [
            "Deficient Fluid Volume related to excessive fluid loss secondary to vomiting and diarrhea",
            "Risk for Electrolyte Imbalance related to gastrointestinal fluid loss",
        ]
        interventions = [
            "Monitor intake and output accurately.",
            "Assess mucous membranes, skin turgor, and urine output regularly.",
            "Monitor vital signs and level of consciousness.",
            "Encourage oral rehydration solution as ordered and tolerated.",
        ]
        outcomes = [
            "Child will demonstrate improved hydration status within the shift.",
            "Urine output and mucous membrane moisture will improve.",
        ]
        rationale = "Young children are highly vulnerable to dehydration because they have smaller fluid reserves and faster fluid turnover."
        errors = ["Rationale", "Documentation"]
        priority = "High"

    elif any(term in text for term in ["wheezing", "retractions", "dyspnea"]):
        rule = "asthma"
        topic = "Asthma"
        diagnoses = [
            "Ineffective Airway Clearance related to bronchospasm and increased mucus production",
            "Impaired Gas Exchange related to ventilation-perfusion imbalance",
        ]
        interventions = [
            "Assess respiratory rate, depth, effort, and breath sounds.",
            "Position the child in semi-Fowler's or high-Fowler's position.",
            "Administer oxygen or nebulization as ordered.",
            "Monitor for signs of worsening respiratory distress.",
        ]
        outcomes = [
            "Child will demonstrate easier breathing and reduced retractions.",
            "Oxygenation status will remain adequate.",
        ]
        rationale = "Breathing problems must be prioritized in pediatric asthma because airway narrowing can worsen quickly."
        errors = ["Prioritization", "Dx selection"]
        priority = "High"

    elif "crackles" in text or ("cough" in text and "fever" in text and "tachypnea" in text):
        rule = "pneumonia"
        topic = "Pneumonia"
        diagnoses = [
            "Ineffective Airway Clearance related to increased tracheobronchial secretions",
            "Hyperthermia related to infectious process",
        ]
        interventions = [
            "Monitor respiratory status and auscultate lung sounds regularly.",
            "Encourage fluids as appropriate and assist secretion clearance.",
            "Administer medications as ordered and monitor temperature.",
            "Promote rest and observe for increased work of breathing.",
        ]
        outcomes = [
            "Child will maintain clearer breath sounds and effective airway clearance.",
            "Temperature will move toward normal range.",
        ]
        rationale = "Secretions and inflammation in pneumonia can impair airway clearance, making respiratory assessment a priority."
        errors = ["Dx selection"]
        priority = "High"

    elif "fever" in text:
        rule = "fever"
        topic = "Fever"
        diagnoses = [
            "Hyperthermia related to infectious process",
            "Risk for Deficient Fluid Volume related to increased insensible loss",
        ]
        interventions = [
            "Monitor temperature and vital signs.",
            "Encourage fluid intake as tolerated.",
            "Provide comfort measures and medication as ordered.",
            "Observe for signs of febrile complications.",
        ]
        outcomes = [
            "Child will maintain temperature within acceptable range.",
            "Child will remain adequately hydrated.",
        ]
        rationale = "Fever increases metabolic demand and fluid loss, so both temperature control and hydration matter."
        errors = ["Documentation"]
        priority = "Moderate"

    elif any(term in text for term in ["underweight", "poor appetite", "low bmi"]):
        rule = "malnutrition"
        topic = "Malnutrition"
        diagnoses = [
            "Imbalanced Nutrition: Less Than Body Requirements related to inadequate intake",
            "Delayed Growth and Development related to chronic poor nutritional status",
        ]
        interventions = [
            "Assess dietary intake and daily weight trends.",
            "Provide small frequent nutrient-dense meals as appropriate.",
            "Coordinate with caregiver regarding affordable food choices.",
            "Monitor energy level and signs of weakness.",
        ]
        outcomes = [
            "Child will demonstrate improved nutritional intake.",
            "Weight trend and activity level will improve over time.",
        ]
        rationale = "Children need adequate nutrition for growth, immune support, and development, making early intervention important."
        errors = ["Rationale"]
        priority = "Moderate"

    elif any(term in text for term in ["seizure", "convulsion", "staring spell"]):
        rule = "seizure"
        topic = "Seizure Episodes"
        diagnoses = [
            "Risk for Injury related to seizure activity",
            "Ineffective Breathing Pattern related to neuromuscular impairment during seizure episode",
        ]
        interventions = [
            "Maintain airway patency and position child safely during and after seizure.",
            "Time seizure duration and document characteristics.",
            "Avoid restraining the child and remove nearby hazards.",
            "Monitor oxygenation and level of consciousness after the episode.",
        ]
        outcomes = [
            "Child will remain free from injury during seizure activity.",
            "Child will maintain adequate airway and oxygenation after the episode.",
        ]
        rationale = "The immediate priority during seizure activity is protecting the child from injury while supporting airway and oxygenation."
        errors = ["Prioritization"]
        priority = "High"

    else:
        rule = "default"
        topic = "General Pediatrics"
        diagnoses = ["Further assessment needed to determine the priority pediatric nursing diagnosis"]
        interventions = [
            "Collect more complete pediatric assessment data.",
            "Reassess vital signs and focused symptoms.",
            "Review developmental and caregiver-related information.",
        ]
        outcomes = ["A clearer priority nursing problem will be identified after additional assessment."]
        rationale = "Clinical decision support is only as strong as the assessment data entered into the system."
        errors = ["Dx selection", "Prioritization"]
        priority = "Needs More Data"

    score, band = score_case(text, rule)
    return {
        "topic": topic,
        "diagnoses": diagnoses,
        "interventions": interventions,
        "outcomes": outcomes,
        "rationale": rationale,
        "priority": priority,
        "score": score,
        "scoreBand": band,
        "commonErrorTags": errors,
    }


def seed_database() -> None:
    if CaseLibrary.query.count() == 0:
        db.session.add_all(
            [
                CaseLibrary(title="Toddler with dehydration", topic="Dehydration", symptoms="diarrhea, vomiting, dry lips, decreased urine output, lethargy", expected_diagnosis="Deficient Fluid Volume"),
                CaseLibrary(title="Child with asthma exacerbation", topic="Asthma", symptoms="wheezing, dyspnea, retractions, cough", expected_diagnosis="Ineffective Airway Clearance"),
                CaseLibrary(title="Child with pneumonia", topic="Pneumonia", symptoms="fever, cough, crackles, tachypnea", expected_diagnosis="Ineffective Airway Clearance"),
                CaseLibrary(title="Child with persistent fever", topic="Fever", symptoms="fever, warm skin, poor appetite, irritability", expected_diagnosis="Hyperthermia"),
                CaseLibrary(title="Underweight preschooler", topic="Malnutrition", symptoms="underweight, poor intake, weakness, low bmi", expected_diagnosis="Imbalanced Nutrition: Less Than Body Requirements"),
                CaseLibrary(title="School-age child with seizures", topic="Seizure Episodes", symptoms="seizure, altered consciousness, postictal drowsiness", expected_diagnosis="Risk for Injury"),
            ]
        )
        db.session.commit()

    if Attempt.query.count() == 0:
        samples = [
            Attempt(student_name="Arcilla, Kim", topic="Dehydration", age="2 years", sex="Male", chief_complaint="Diarrhea and vomiting", vitals="T 38.4 | HR 128 | RR 28", assessment="Dry lips, decreased urine output, lethargy", predicted_diagnosis="Deficient Fluid Volume", priority_level="High", score=78),
            Attempt(student_name="Ciron, Riza", topic="Pneumonia", age="4 years", sex="Female", chief_complaint="Cough and fever", vitals="T 38.8 | HR 122 | RR 34", assessment="Crackles, productive cough, tachypnea", predicted_diagnosis="Ineffective Airway Clearance", priority_level="High", score=74),
            Attempt(student_name="Gomez, Jho", topic="Asthma", age="6 years", sex="Male", chief_complaint="Shortness of breath", vitals="HR 120 | RR 36", assessment="Wheezing, retractions, dyspnea", predicted_diagnosis="Ineffective Airway Clearance", priority_level="High", score=61),
            Attempt(student_name="Oliva, Karylle", topic="Fever", age="3 years", sex="Female", chief_complaint="Fever", vitals="T 39.0 | HR 118", assessment="Warm skin, irritability", predicted_diagnosis="Hyperthermia", priority_level="Moderate", score=86),
            Attempt(student_name="Tabayag, Angela", topic="Malnutrition", age="5 years", sex="Male", chief_complaint="Poor appetite", vitals="HR 102 | RR 24", assessment="Underweight, weakness", predicted_diagnosis="Imbalanced Nutrition: Less Than Body Requirements", priority_level="Moderate", score=70),
        ]
        db.session.add_all(samples)
        db.session.commit()


def fetch_topic_scores() -> List[Dict[str, Any]]:
    rows = (
        db.session.query(Attempt.topic, func.round(func.avg(Attempt.score), 1).label("avg_score"), func.count(Attempt.id).label("attempts"))
        .group_by(Attempt.topic)
        .order_by(Attempt.topic)
        .all()
    )
    return [{"topic": r.topic, "avg_score": float(r.avg_score or 0), "attempts": int(r.attempts)} for r in rows]


def fetch_error_distribution() -> List[Dict[str, Any]]:
    topic_scores = fetch_topic_scores()
    lookup = {row["topic"]: row["avg_score"] for row in topic_scores}
    asthma = lookup.get("Asthma", 0)
    dehydration = lookup.get("Dehydration", 0)
    pneumonia = lookup.get("Pneumonia", 0)
    fever = lookup.get("Fever", 0)
    return [
        {"name": "Dx selection", "value": max(20, int((100 - pneumonia) / 2 + 20))},
        {"name": "Prioritization", "value": max(20, int((100 - asthma) / 2 + 20))},
        {"name": "Rationale", "value": max(10, int((100 - dehydration) / 3 + 10))},
        {"name": "Documentation", "value": max(8, int((100 - fever) / 4 + 8))},
    ]


def fetch_summary() -> Dict[str, Any]:
    avg_score, total_attempts = db.session.query(func.round(func.avg(Attempt.score), 1), func.count(Attempt.id)).one()
    low_row = (
        db.session.query(Attempt.topic, func.round(func.avg(Attempt.score), 1).label("avg_score"))
        .group_by(Attempt.topic)
        .order_by(func.avg(Attempt.score).asc())
        .first()
    )
    support_count = db.session.query(func.count(Attempt.id)).filter(Attempt.score < 70).scalar() or 0
    recent = Attempt.query.order_by(Attempt.id.desc()).limit(6).all()
    return {
        "classAverage": float(avg_score or 0),
        "totalAttempts": int(total_attempts or 0),
        "lowestTopic": low_row.topic if low_row else "N/A",
        "lowestTopicAverage": float(low_row.avg_score or 0) if low_row else 0,
        "studentsNeedingSupport": int(support_count),
        "recentAttempts": [
            {
                "student_name": item.student_name,
                "topic": item.topic,
                "score": float(item.score),
                "created_at": item.created_at.isoformat(timespec="seconds"),
            }
            for item in recent
        ],
    }


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/health")
def health() -> Response:
    return jsonify({"status": "ok"})


@app.route("/api/analyze-case", methods=["POST"])
def api_analyze_case() -> Response:
    payload = request.get_json(silent=True) or {}
    return jsonify(analyze_case(payload))


@app.route("/api/save-attempt", methods=["POST"])
def api_save_attempt() -> Response:
    payload = request.get_json(silent=True) or {}
    analysis = analyze_case(payload)
    student_name = str(payload.get("studentName", "Anonymous Student")).strip() or "Anonymous Student"
    attempt = Attempt(
        student_name=student_name,
        topic=analysis["topic"],
        age=str(payload.get("age", "")),
        sex=str(payload.get("sex", "")),
        chief_complaint=str(payload.get("chiefComplaint", "")),
        vitals=str(payload.get("vitals", "")),
        assessment=str(payload.get("assessment", "")),
        labs=str(payload.get("labs", "")),
        predicted_diagnosis=analysis["diagnoses"][0],
        priority_level=analysis["priority"],
        score=float(analysis["score"]),
        created_at=iso_now(),
    )
    db.session.add(attempt)
    db.session.commit()
    return jsonify({"message": "Attempt saved successfully.", "analysis": analysis})


@app.route("/api/dashboard/summary")
def api_dashboard_summary() -> Response:
    return jsonify(fetch_summary())


@app.route("/api/analytics/topics")
def api_analytics_topics() -> Response:
    return jsonify(fetch_topic_scores())


@app.route("/api/analytics/errors")
def api_analytics_errors() -> Response:
    return jsonify(fetch_error_distribution())


@app.route("/api/cases")
def api_cases() -> Response:
    return jsonify(
        [
            {
                "id": row.id,
                "title": row.title,
                "topic": row.topic,
                "symptoms": row.symptoms,
                "expected_diagnosis": row.expected_diagnosis,
            }
            for row in CaseLibrary.query.order_by(CaseLibrary.id).all()
        ]
    )


with app.app_context():
    db.create_all()
    seed_database()


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
