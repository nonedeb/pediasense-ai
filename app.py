
import os
import json
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

database_url = os.environ.get("DATABASE_URL", "sqlite:///pediasense.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student, faculty, manager
    section = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attempts = db.relationship("CaseAttempt", backref="user", lazy=True)
    quiz_attempts = db.relationship("QuizAttempt", backref="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class CaseAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    age = db.Column(db.String(50), nullable=False)
    sex = db.Column(db.String(20), nullable=True)
    chief_complaint = db.Column(db.String(255), nullable=False)
    vitals = db.Column(db.Text, nullable=True)
    assessment = db.Column(db.Text, nullable=False)
    labs = db.Column(db.Text, nullable=True)
    ai_mode = db.Column(db.String(20), default="rule-based")
    top_diagnosis = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(80), nullable=True)
    confidence = db.Column(db.Integer, default=0)
    result_json = db.Column(db.Text, nullable=False)
    self_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(80), nullable=False)
    stem = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    rationale = db.Column(db.Text, nullable=False)


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    details_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


NANDA_LIBRARY = [
    {
        "topic": "Dehydration",
        "keywords": ["diarrhea", "vomiting", "dry lips", "decreased urine", "sunken eyes", "poor skin turgor", "lethargy"],
        "diagnosis": "Deficient Fluid Volume related to excessive fluid loss secondary to vomiting and diarrhea",
        "priority": "high",
        "confidence": 92,
        "interventions": [
            "Monitor intake and output accurately.",
            "Assess mucous membranes, skin turgor, capillary refill, and urine output.",
            "Monitor vital signs and signs of worsening dehydration.",
            "Encourage or administer oral rehydration solution as ordered.",
            "Educate caregiver on warning signs of dehydration and when to seek help."
        ],
        "outcomes": [
            "Child will demonstrate improved hydration status within 8 hours.",
            "Urine output will improve and mucous membranes will remain moist."
        ],
        "rationale": "Young children are more vulnerable to rapid fluid loss because of smaller fluid reserves and faster fluid turnover.",
        "related_diagnoses": [
            "Risk for Electrolyte Imbalance related to gastrointestinal fluid loss"
        ]
    },
    {
        "topic": "Asthma",
        "keywords": ["wheezing", "dyspnea", "retractions", "shortness of breath", "accessory muscles", "tight chest", "cough"],
        "diagnosis": "Ineffective Airway Clearance related to bronchospasm and increased mucus production",
        "priority": "high",
        "confidence": 91,
        "interventions": [
            "Assess respiratory rate, depth, effort, and breath sounds frequently.",
            "Position the child to maximize ventilation.",
            "Administer bronchodilator therapy as ordered.",
            "Monitor oxygen saturation and signs of respiratory fatigue.",
            "Teach trigger avoidance and inhaler/spacer technique."
        ],
        "outcomes": [
            "Child will maintain a patent airway and improved breath sounds.",
            "Respiratory effort and oxygen saturation will improve."
        ],
        "rationale": "Bronchospasm and mucus narrowing increase work of breathing and reduce effective airflow.",
        "related_diagnoses": [
            "Impaired Gas Exchange related to ventilation-perfusion imbalance"
        ]
    },
    {
        "topic": "Pneumonia",
        "keywords": ["fever", "cough", "crackles", "tachypnea", "chest retractions", "nasal flaring", "low oxygen"],
        "diagnosis": "Ineffective Airway Clearance related to tracheobronchial secretions and inflammation",
        "priority": "high",
        "confidence": 88,
        "interventions": [
            "Monitor breath sounds, respiratory effort, and oxygen saturation.",
            "Encourage fluids as appropriate to thin secretions.",
            "Promote rest and cluster nursing care.",
            "Administer prescribed medications and oxygen therapy.",
            "Educate caregiver about medication adherence and red-flag signs."
        ],
        "outcomes": [
            "Child will demonstrate improved airway clearance and easier breathing.",
            "Temperature and respiratory status will stabilize."
        ],
        "rationale": "Inflammation and secretions in the airways impair normal gas movement and increase work of breathing.",
        "related_diagnoses": [
            "Hyperthermia related to infectious process"
        ]
    },
    {
        "topic": "Malnutrition",
        "keywords": ["underweight", "poor appetite", "weight loss", "thin", "low bmi", "stunting", "wasting"],
        "diagnosis": "Imbalanced Nutrition: Less Than Body Requirements related to inadequate intake",
        "priority": "moderate",
        "confidence": 84,
        "interventions": [
            "Assess current weight, dietary intake, and feeding pattern.",
            "Collaborate on a calorie- and protein-appropriate feeding plan.",
            "Monitor weight trends regularly.",
            "Teach caregiver practical low-cost nutrient-dense food options.",
            "Observe for signs of micronutrient deficiency."
        ],
        "outcomes": [
            "Child will demonstrate gradual weight gain or improved nutritional indicators.",
            "Caregiver will verbalize an appropriate nutrition plan."
        ],
        "rationale": "Inadequate intake affects growth, immune function, and recovery.",
        "related_diagnoses": [
            "Risk for Delayed Growth and Development"
        ]
    },
    {
        "topic": "Seizure",
        "keywords": ["seizure", "convulsion", "tonic", "clonic", "postictal", "unresponsive"],
        "diagnosis": "Risk for Injury related to seizure activity",
        "priority": "high",
        "confidence": 86,
        "interventions": [
            "Maintain a safe environment during seizure activity.",
            "Position the child side-lying if possible after seizure to protect airway.",
            "Document duration, triggers, and characteristics of seizure.",
            "Monitor neurologic status and postictal recovery.",
            "Teach caregiver seizure first-aid and emergency warning signs."
        ],
        "outcomes": [
            "Child will remain free from injury during and after seizure activity.",
            "Caregiver will verbalize appropriate seizure precautions."
        ],
        "rationale": "Seizures increase the risk of falls, aspiration, and trauma if safety measures are not maintained.",
        "related_diagnoses": [
            "Risk for Aspiration related to altered consciousness"
        ]
    }
]


def seed_defaults():
    if not User.query.filter_by(email="manager@pediasense.ai").first():
        manager = User(full_name="System Manager", email="manager@pediasense.ai", role="manager")
        manager.set_password("Manager123!")
        db.session.add(manager)

    if not User.query.filter_by(email="faculty@pediasense.ai").first():
        faculty = User(full_name="Faculty Demo", email="faculty@pediasense.ai", role="faculty")
        faculty.set_password("Faculty123!")
        db.session.add(faculty)

    if not User.query.filter_by(email="student@pediasense.ai").first():
        student = User(full_name="Student Demo", email="student@pediasense.ai", role="student", section="BSN 4A")
        student.set_password("Student123!")
        db.session.add(student)

    if QuizQuestion.query.count() == 0:
        questions = [
            QuizQuestion(
                topic="Dehydration",
                stem="A 2-year-old with diarrhea, vomiting, dry lips, and low urine output is most at risk for which nursing priority?",
                option_a="Deficient Fluid Volume",
                option_b="Impaired Social Interaction",
                option_c="Disturbed Body Image",
                option_d="Sleep Pattern Disturbance",
                correct_option="A",
                rationale="Gastrointestinal losses and dehydration signs point to fluid volume deficit as the priority."
            ),
            QuizQuestion(
                topic="Asthma",
                stem="Which assessment finding most strongly supports ineffective airway clearance in a pediatric asthma exacerbation?",
                option_a="Wheezing with retractions",
                option_b="Mild rash on the arm",
                option_c="Occasional hiccups",
                option_d="Increased appetite",
                correct_option="A",
                rationale="Wheezing and retractions indicate airway obstruction and increased work of breathing."
            ),
            QuizQuestion(
                topic="Pneumonia",
                stem="A child with pneumonia and crackles should have which nursing outcome prioritized?",
                option_a="Child will maintain improved airway clearance",
                option_b="Child will choose favorite toys",
                option_c="Child will avoid all movement",
                option_d="Child will sleep 12 hours immediately",
                correct_option="A",
                rationale="Pneumonia primarily affects airway clearance and respiratory effort."
            ),
            QuizQuestion(
                topic="Malnutrition",
                stem="Which caregiver teaching is most appropriate for pediatric malnutrition in a low-resource setting?",
                option_a="Offer nutrient-dense, affordable local foods regularly",
                option_b="Skip meals if the child refuses once",
                option_c="Limit protein entirely",
                option_d="Give only sugary drinks",
                correct_option="A",
                rationale="Affordable nutrient-dense food planning is realistic and supports recovery."
            ),
        ]
        db.session.add_all(questions)
    db.session.commit()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)


@app.context_processor
def inject_globals():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if user.role not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def match_rules(text: str):
    text = (text or "").lower()
    scored = []
    for item in NANDA_LIBRARY:
        hits = sum(1 for kw in item["keywords"] if kw in text)
        if hits:
            scored.append((hits, item))
    scored.sort(key=lambda x: (-x[0], -x[1]["confidence"]))
    return [item for _, item in scored]


def openai_explanation(case_summary: str, matched):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None or not matched:
        return None
    try:
        client = OpenAI(api_key=api_key)
        top = matched[0]
        prompt = f"""
You are helping a pediatric nursing education tool.
Use ONLY the provided diagnosis and case information.
Do not invent diagnoses outside the provided list.

Case:
{case_summary}

Primary NANDA-aligned diagnosis:
{top['diagnosis']}

Related diagnoses:
{", ".join(top.get('related_diagnoses', []))}

Return a concise JSON object with keys:
explanation, caregiver_teaching, safety_notes
"""
        response = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt
        )
        text = getattr(response, "output_text", None)
        if not text:
            return None
        m = text.strip()
        if m.startswith("```"):
            m = m.strip("`")
        try:
            return json.loads(m)
        except Exception:
            return {"explanation": text, "caregiver_teaching": "", "safety_notes": ""}
    except Exception:
        return None


def analyze_case_data(age, sex, chief_complaint, vitals, assessment, labs):
    case_summary = f"Age: {age}\nSex: {sex}\nChief complaint: {chief_complaint}\nVitals: {vitals}\nAssessment: {assessment}\nLabs: {labs}"
    matched = match_rules(" ".join([chief_complaint or "", assessment or "", vitals or "", labs or ""]))
    if not matched:
        fallback = {
            "topic": "General Pediatric Assessment",
            "diagnosis": "Further Assessment Required",
            "priority": "moderate",
            "confidence": 50,
            "interventions": [
                "Complete focused pediatric assessment.",
                "Review vital signs, hydration, respiratory status, and caregiver concerns.",
                "Escalate to faculty review for complex or unclear findings."
            ],
            "outcomes": [
                "A clearer nursing problem list will be identified after additional assessment."
            ],
            "rationale": "Incomplete or non-specific findings may require more data before selecting an appropriate priority diagnosis.",
            "related_diagnoses": []
        }
        matched = [fallback]

    top = matched[0]
    explanation = openai_explanation(case_summary, matched)

    return {
        "topic": top["topic"],
        "mode": "openai-assisted" if explanation else "rule-based",
        "top_diagnosis": top["diagnosis"],
        "related_diagnoses": top.get("related_diagnoses", []),
        "priority": top["priority"],
        "confidence": top["confidence"],
        "interventions": top["interventions"],
        "outcomes": top["outcomes"],
        "rationale": top["rationale"],
        "ai_explanation": explanation,
        "case_summary": case_summary
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        section = request.form.get("section", "").strip()
        role = request.form.get("role", "student")

        if role not in {"student", "faculty"}:
            role = "student"

        if not full_name or not email or not password:
            flash("Please fill out all required fields.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("register"))

        user = User(full_name=full_name, email=email, role=role, section=section)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash(f"Welcome, {user.full_name}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "student":
        attempts = CaseAttempt.query.filter_by(user_id=user.id).order_by(CaseAttempt.created_at.desc()).limit(5).all()
        quiz = QuizAttempt.query.filter_by(user_id=user.id).order_by(QuizAttempt.created_at.desc()).first()
        return render_template("student_dashboard.html", attempts=attempts, latest_quiz=quiz)
    if user.role == "faculty":
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("manager_dashboard"))


@app.route("/student/case", methods=["GET", "POST"])
@role_required("student")
def student_case():
    result = None
    if request.method == "POST":
        age = request.form.get("age", "")
        sex = request.form.get("sex", "")
        chief_complaint = request.form.get("chief_complaint", "")
        vitals = request.form.get("vitals", "")
        assessment = request.form.get("assessment", "")
        labs = request.form.get("labs", "")
        self_score = int(request.form.get("self_score", "0") or 0)

        result = analyze_case_data(age, sex, chief_complaint, vitals, assessment, labs)

        attempt = CaseAttempt(
            user_id=current_user().id,
            age=age,
            sex=sex,
            chief_complaint=chief_complaint,
            vitals=vitals,
            assessment=assessment,
            labs=labs,
            ai_mode=result["mode"],
            top_diagnosis=result["top_diagnosis"],
            topic=result["topic"],
            confidence=result["confidence"],
            self_score=self_score,
            result_json=json.dumps(result)
        )
        db.session.add(attempt)
        db.session.commit()
        flash("Case analyzed and saved.", "success")

    return render_template("student_case.html", result=result)


@app.route("/student/quiz", methods=["GET", "POST"])
@role_required("student")
def student_quiz():
    questions = QuizQuestion.query.order_by(QuizQuestion.id.asc()).all()
    result = None

    if request.method == "POST":
        correct = 0
        details = []
        for q in questions:
            chosen = request.form.get(f"q_{q.id}", "")
            is_correct = chosen == q.correct_option
            if is_correct:
                correct += 1
            details.append({
                "id": q.id,
                "topic": q.topic,
                "chosen": chosen,
                "correct": q.correct_option,
                "is_correct": is_correct,
                "rationale": q.rationale,
                "stem": q.stem
            })
        attempt = QuizAttempt(
            user_id=current_user().id,
            score=correct,
            total=len(questions),
            details_json=json.dumps(details)
        )
        db.session.add(attempt)
        db.session.commit()
        result = details
        flash(f"Quiz submitted. Score: {correct}/{len(questions)}", "success")

    return render_template("student_quiz.html", questions=questions, result=result)


@app.route("/faculty")
@role_required("faculty", "manager")
def faculty_dashboard():
    total_students = db.session.query(func.count(User.id)).filter(User.role == "student").scalar() or 0
    total_attempts = db.session.query(func.count(CaseAttempt.id)).scalar() or 0
    avg_self_score = db.session.query(func.avg(CaseAttempt.self_score)).scalar() or 0

    topic_rows = db.session.query(CaseAttempt.topic, func.count(CaseAttempt.id)).group_by(CaseAttempt.topic).all()
    topic_counts = [{"topic": t or "Uncategorized", "count": c} for t, c in topic_rows]

    low_students = []
    student_rows = db.session.query(User.full_name, func.avg(CaseAttempt.self_score)).join(CaseAttempt, CaseAttempt.user_id == User.id).filter(User.role=="student").group_by(User.id).all()
    for name, avg_score in student_rows:
        if (avg_score or 0) < 75:
            low_students.append({"name": name, "avg": round(avg_score or 0, 1)})

    recent_attempts = CaseAttempt.query.order_by(CaseAttempt.created_at.desc()).limit(10).all()
    quiz_rows = db.session.query(func.avg(QuizAttempt.score * 100.0 / QuizAttempt.total)).scalar() or 0

    return render_template(
        "faculty_dashboard.html",
        total_students=total_students,
        total_attempts=total_attempts,
        avg_self_score=round(avg_self_score, 1),
        topic_counts=topic_counts,
        low_students=low_students,
        recent_attempts=recent_attempts,
        quiz_average=round(quiz_rows, 1),
    )


@app.route("/manager")
@role_required("manager")
def manager_dashboard():
    users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
    questions = QuizQuestion.query.order_by(QuizQuestion.id.asc()).all()
    return render_template("manager_dashboard.html", users=users, questions=questions)


@app.route("/manager/user", methods=["POST"])
@role_required("manager")
def manager_add_user():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "student")
    password = request.form.get("password", "Password123!")
    section = request.form.get("section", "").strip()

    if not full_name or not email or role not in {"student", "faculty", "manager"}:
        flash("Invalid user details.", "danger")
        return redirect(url_for("manager_dashboard"))

    if User.query.filter_by(email=email).first():
        flash("Email already exists.", "warning")
        return redirect(url_for("manager_dashboard"))

    user = User(full_name=full_name, email=email, role=role, section=section)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("User created.", "success")
    return redirect(url_for("manager_dashboard"))




@app.route("/manager/user/<int:user_id>/edit", methods=["POST"])
@role_required("manager")
def manager_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "student")
    section = request.form.get("section", "").strip()
    password = request.form.get("password", "").strip()

    if not full_name or not email or role not in {"student", "faculty", "manager"}:
        flash("Invalid user details.", "danger")
        return redirect(url_for("manager_dashboard"))

    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        flash("Another account already uses that email.", "warning")
        return redirect(url_for("manager_dashboard"))

    if user.id == current_user().id and role != "manager":
        flash("You cannot remove your own manager role while logged in.", "warning")
        return redirect(url_for("manager_dashboard"))

    user.full_name = full_name
    user.email = email
    user.role = role
    user.section = section
    if password:
        user.set_password(password)
    db.session.commit()
    flash("User updated.", "success")
    return redirect(url_for("manager_dashboard"))


@app.route("/manager/user/<int:user_id>/delete", methods=["POST"])
@role_required("manager")
def manager_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user().id:
        flash("You cannot delete your own logged-in manager account.", "warning")
        return redirect(url_for("manager_dashboard"))

    CaseAttempt.query.filter_by(user_id=user.id).delete()
    QuizAttempt.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("manager_dashboard"))


@app.route("/manager/question", methods=["POST"])
@role_required("manager")
def manager_add_question():
    q = QuizQuestion(
        topic=request.form.get("topic", "").strip(),
        stem=request.form.get("stem", "").strip(),
        option_a=request.form.get("option_a", "").strip(),
        option_b=request.form.get("option_b", "").strip(),
        option_c=request.form.get("option_c", "").strip(),
        option_d=request.form.get("option_d", "").strip(),
        correct_option=request.form.get("correct_option", "A").strip().upper(),
        rationale=request.form.get("rationale", "").strip(),
    )
    if not q.topic or not q.stem or q.correct_option not in {"A", "B", "C", "D"}:
        flash("Please complete the quiz question form.", "danger")
        return redirect(url_for("manager_dashboard"))
    db.session.add(q)
    db.session.commit()
    flash("Quiz question added.", "success")
    return redirect(url_for("manager_dashboard"))


@app.route("/api/analytics")
@role_required("faculty", "manager")
def api_analytics():
    topic_rows = db.session.query(CaseAttempt.topic, func.count(CaseAttempt.id)).group_by(CaseAttempt.topic).all()
    return jsonify({"topics": [{"topic": t or "Uncategorized", "count": c} for t, c in topic_rows]})


with app.app_context():
    db.create_all()
    seed_defaults()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
