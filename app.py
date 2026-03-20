import csv
import io
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    section = db.Column(db.String(50), nullable=True)
    program = db.Column(db.String(100), nullable=True)
    specialization = db.Column(db.String(150), nullable=True)
    post_nominals = db.Column(db.String(100), nullable=True)
    contact_number = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(150), default="PediaSense AI")
    logo_url = db.Column(db.String(255), nullable=True)

class ImportLog(db.Model):
    __tablename__ = "import_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuizQuestion(db.Model):
    __tablename__ = "quiz_questions"
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(120), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    rationale = db.Column(db.Text, nullable=True)
    difficulty_level = db.Column(db.String(20), nullable=True)
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_questions.id"), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=True)
    is_correct = db.Column(db.Boolean, default=False)
    score = db.Column(db.Float, default=0)
    attempt_date = db.Column(db.DateTime, default=datetime.utcnow)

class CaseLibrary(db.Model):
    __tablename__ = "case_library"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    symptoms = db.Column(db.Text, nullable=True)
    assessment_findings = db.Column(db.Text, nullable=True)
    expected_diagnosis = db.Column(db.String(200), nullable=True)
    recommended_interventions = db.Column(db.Text, nullable=True)
    expected_outcomes = db.Column(db.Text, nullable=True)
    rationale = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CaseAttempt(db.Model):
    __tablename__ = "case_attempts"
    id = db.Column(db.Integer, primary_key=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey("case_library.id"), nullable=True)
    input_data = db.Column(db.Text, nullable=False)
    selected_diagnosis = db.Column(db.Text, nullable=True)
    interventions = db.Column(db.Text, nullable=True)
    outcomes = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    attempt_date = db.Column(db.DateTime, default=datetime.utcnow)

class ReferenceDocument(db.Model):
    __tablename__ = "reference_documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    edition = db.Column(db.String(50), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

def normalize_email(email):
    return (email or "").strip().lower()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    database_url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapper

    def role_required(*roles):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if session.get("user_role") not in roles:
                    flash("Unauthorized access.", "danger")
                    return redirect(url_for("home"))
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def current_user():
        if "user_id" not in session:
            return None
        return db.session.get(User, session["user_id"])

    def seed():
        if not SystemSetting.query.first():
            db.session.add(SystemSetting(site_name="PediaSense AI"))
        if not User.query.filter_by(email="manager@pediasense.ai").first():
            u = User(name="System Manager", email="manager@pediasense.ai", role="manager")
            u.set_password("Manager123!")
            db.session.add(u)
        if not User.query.filter_by(email="faculty@pediasense.ai").first():
            u = User(name="Faculty User", email="faculty@pediasense.ai", role="faculty", specialization="Pediatrics", post_nominals="RN, MAN")
            u.set_password("Faculty123!")
            db.session.add(u)
        if not User.query.filter_by(email="student@pediasense.ai").first():
            u = User(name="Student User", email="student@pediasense.ai", role="student", section="4A", program="BSN")
            u.set_password("Student123!")
            db.session.add(u)
        if QuizQuestion.query.count() == 0:
            db.session.add(QuizQuestion(
                topic="Pediatric Dehydration",
                question_text="Which finding most strongly suggests dehydration in a child?",
                option_a="Moist mucous membranes",
                option_b="Decreased urine output",
                option_c="Bounding pulse",
                option_d="Warm flushed skin",
                correct_answer="B",
                rationale="Decreased urine output suggests fluid deficit.",
                difficulty_level="Easy",
                published=True
            ))
        if CaseLibrary.query.count() == 0:
            db.session.add(CaseLibrary(
                title="Toddler with diarrhea and vomiting",
                topic="Fluid and Electrolytes",
                symptoms="Diarrhea, vomiting, lethargy",
                assessment_findings="Dry lips, low urine output",
                expected_diagnosis="Deficient Fluid Volume",
                recommended_interventions="Monitor intake/output; encourage ORS as ordered",
                expected_outcomes="Improved hydration",
                rationale="Children lose fluid rapidly."
            ))
        db.session.commit()

    with app.app_context():
        db.create_all()
        seed()

    @app.context_processor
    def inject_settings():
        return {
            "settings": SystemSetting.query.first(),
            "session_user_name": session.get("user_name"),
            "session_user_role": session.get("user_role"),
        }

    @app.route("/")
    def home():
        role = session.get("user_role")
        if role == "manager":
            return redirect(url_for("manager_dashboard"))
        if role == "faculty":
            return redirect(url_for("faculty_dashboard"))
        if role == "student":
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = normalize_email(request.form.get("email"))
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email, status="active").first()
            if user and user.check_password(password):
                session["user_id"] = user.id
                session["user_name"] = user.name
                session["user_role"] = user.role
                flash("Login successful.", "success")
                return redirect(url_for("home"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/manager")
    @login_required
    @role_required("manager")
    def manager_dashboard():
        return render_template("manager/dashboard.html",
            total_users=User.query.count(),
            total_students=User.query.filter_by(role="student").count(),
            total_faculty=User.query.filter_by(role="faculty").count(),
            total_quizzes=QuizQuestion.query.count(),
            total_cases=CaseLibrary.query.count(),
            total_docs=ReferenceDocument.query.count(),
        )

    @app.route("/manager/import-users", methods=["GET", "POST"])
    @login_required
    @role_required("manager")
    def manager_import_users():
        preview_rows = session.get("import_preview_rows", [])
        preview_mode = bool(preview_rows)
        selected_type = session.get("import_user_type")

        if request.method == "POST":
            user_type = request.form.get("user_type", "").strip().lower()
            uploaded_file = request.files.get("file")
            if user_type not in {"student", "faculty"}:
                flash("Please select a valid user type.", "danger")
                return redirect(url_for("manager_import_users"))
            if not uploaded_file or uploaded_file.filename == "":
                flash("Please upload a CSV file.", "danger")
                return redirect(url_for("manager_import_users"))
            if not uploaded_file.filename.lower().endswith(".csv"):
                flash("Only CSV files are supported.", "danger")
                return redirect(url_for("manager_import_users"))

            rows = list(csv.DictReader(io.StringIO(uploaded_file.read().decode("utf-8-sig"))))
            if not rows:
                flash("The uploaded file is empty.", "warning")
                return redirect(url_for("manager_import_users"))

            required = {
                "student": ["name", "section", "program", "contact_number", "email"],
                "faculty": ["name", "email", "specialization", "post_nominals", "contact_number"],
            }
            missing_cols = [c for c in required[user_type] if c not in rows[0].keys()]
            if missing_cols:
                flash(f"Missing required columns: {', '.join(missing_cols)}", "danger")
                return redirect(url_for("manager_import_users"))

            seen = set()
            preview_rows = []
            for idx, row in enumerate(rows, start=1):
                item = {
                    "row_number": idx,
                    "name": (row.get("name") or "").strip(),
                    "email": normalize_email(row.get("email")),
                    "role": user_type,
                    "section": (row.get("section") or "").strip() if user_type == "student" else None,
                    "program": (row.get("program") or "").strip() if user_type == "student" else None,
                    "specialization": (row.get("specialization") or "").strip() if user_type == "faculty" else None,
                    "post_nominals": (row.get("post_nominals") or "").strip() if user_type == "faculty" else None,
                    "contact_number": (row.get("contact_number") or "").strip(),
                    "errors": [],
                }
                if not item["name"]:
                    item["errors"].append("Missing name")
                if not item["email"]:
                    item["errors"].append("Missing email")
                elif "@" not in item["email"]:
                    item["errors"].append("Invalid email")
                if item["email"] in seen:
                    item["errors"].append("Duplicate email in file")
                if item["email"]:
                    seen.add(item["email"])
                if item["email"] and User.query.filter_by(email=item["email"]).first():
                    item["errors"].append("Email already exists")
                if user_type == "student":
                    if not item["section"]:
                        item["errors"].append("Missing section")
                    if not item["program"]:
                        item["errors"].append("Missing program")
                else:
                    if not item["specialization"]:
                        item["errors"].append("Missing specialization")
                preview_rows.append(item)

            session["import_preview_rows"] = preview_rows
            session["import_user_type"] = user_type
            session["import_file_name"] = secure_filename(uploaded_file.filename)
            return redirect(url_for("manager_import_users"))

        return render_template("manager/import_users.html", preview_rows=preview_rows, preview_mode=preview_mode, selected_type=selected_type)

    @app.route("/manager/import-users/confirm", methods=["POST"])
    @login_required
    @role_required("manager")
    def manager_import_users_confirm():
        rows = session.get("import_preview_rows", [])
        user_type = session.get("import_user_type")
        file_name = session.get("import_file_name", "uploaded.csv")
        if not rows:
            flash("No pending import found.", "warning")
            return redirect(url_for("manager_import_users"))
        success_count = 0
        error_count = 0
        for row in rows:
            if row["errors"]:
                error_count += 1
                continue
            if User.query.filter_by(email=row["email"]).first():
                error_count += 1
                continue
            user = User(
                name=row["name"], email=row["email"], role=row["role"],
                section=row.get("section"), program=row.get("program"),
                specialization=row.get("specialization"), post_nominals=row.get("post_nominals"),
                contact_number=row.get("contact_number"), status="active"
            )
            user.set_password("Student123!" if row["role"] == "student" else "Faculty123!")
            db.session.add(user)
            success_count += 1
        db.session.commit()
        db.session.add(ImportLog(user_type=user_type, file_name=file_name, success_count=success_count, error_count=error_count))
        db.session.commit()
        session.pop("import_preview_rows", None)
        session.pop("import_user_type", None)
        session.pop("import_file_name", None)
        flash(f"Import completed. Added {success_count} users; skipped {error_count}.", "success")
        return redirect(url_for("manager_users"))

    @app.route("/manager/import-users/cancel", methods=["POST"])
    @login_required
    @role_required("manager")
    def manager_import_users_cancel():
        for k in ["import_preview_rows", "import_user_type", "import_file_name"]:
            session.pop(k, None)
        flash("Pending import cleared.", "info")
        return redirect(url_for("manager_import_users"))

    @app.route("/manager/users")
    @login_required
    @role_required("manager")
    def manager_users():
        users = User.query.order_by(User.role.asc(), User.name.asc()).all()
        return render_template("manager/users.html", users=users)

    @app.route("/manager/users/create", methods=["GET", "POST"])
    @login_required
    @role_required("manager")
    def manager_user_create():
        if request.method == "POST":
            email = normalize_email(request.form.get("email"))
            if User.query.filter_by(email=email).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("manager_user_create"))
            user = User(
                name=request.form.get("name", "").strip(),
                email=email,
                role=request.form.get("role"),
                section=request.form.get("section") or None,
                program=request.form.get("program") or None,
                specialization=request.form.get("specialization") or None,
                post_nominals=request.form.get("post_nominals") or None,
                contact_number=request.form.get("contact_number") or None,
                status=request.form.get("status", "active"),
            )
            user.set_password(request.form.get("password", "Password123!"))
            db.session.add(user)
            db.session.commit()
            flash("User created successfully.", "success")
            return redirect(url_for("manager_users"))
        return render_template("manager/user_form.html", mode="create", user=None)

    @app.route("/manager/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("manager")
    def manager_user_edit(user_id):
        user = db.session.get(User, user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("manager_users"))
        if request.method == "POST":
            email = normalize_email(request.form.get("email"))
            existing = User.query.filter(User.email == email, User.id != user.id).first()
            if existing:
                flash("Email already exists.", "danger")
                return redirect(url_for("manager_user_edit", user_id=user.id))
            user.name = request.form.get("name", "").strip()
            user.email = email
            user.role = request.form.get("role")
            user.section = request.form.get("section") or None
            user.program = request.form.get("program") or None
            user.specialization = request.form.get("specialization") or None
            user.post_nominals = request.form.get("post_nominals") or None
            user.contact_number = request.form.get("contact_number") or None
            user.status = request.form.get("status", "active")
            if request.form.get("password"):
                user.set_password(request.form.get("password"))
            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("manager_users"))
        return render_template("manager/user_form.html", mode="edit", user=user)

    @app.route("/manager/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    @role_required("manager")
    def manager_user_delete(user_id):
        user = db.session.get(User, user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("manager_users"))
        if user.id == session.get("user_id"):
            flash("You cannot delete your own logged-in account.", "warning")
            return redirect(url_for("manager_users"))
        db.session.delete(user)
        db.session.commit()
        flash("User deleted.", "info")
        return redirect(url_for("manager_users"))

    @app.route("/manager/import-logs")
    @login_required
    @role_required("manager")
    def manager_import_logs():
        return render_template("manager/import_logs.html", logs=ImportLog.query.order_by(ImportLog.created_at.desc()).all())

    @app.route("/manager/branding", methods=["GET", "POST"])
    @login_required
    @role_required("manager")
    def manager_branding():
        settings = SystemSetting.query.first()
        if request.method == "POST":
            settings.site_name = request.form.get("site_name", settings.site_name)
            settings.logo_url = request.form.get("logo_url", settings.logo_url)
            db.session.commit()
            flash("Branding updated.", "success")
            return redirect(url_for("manager_branding"))
        return render_template("manager/branding.html", settings=settings)

    @app.route("/manager/reference-docs", methods=["GET", "POST"])
    @login_required
    @role_required("manager")
    def manager_reference_docs():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if title:
                file_path = request.form.get("file_path", "").strip() or "uploads/nanda.pdf"
                db.session.add(ReferenceDocument(title=title, edition=request.form.get("edition") or None, file_name=os.path.basename(file_path), file_path=file_path))
                db.session.commit()
                flash("Reference document saved.", "success")
                return redirect(url_for("manager_reference_docs"))
        return render_template("manager/reference_docs.html", docs=ReferenceDocument.query.order_by(ReferenceDocument.uploaded_at.desc()).all())

    @app.route("/student")
    @login_required
    @role_required("student")
    def student_dashboard():
        user = current_user()
        quiz_attempts = QuizAttempt.query.filter_by(student_user_id=user.id).order_by(QuizAttempt.attempt_date.desc()).all()
        case_attempts = CaseAttempt.query.filter_by(student_user_id=user.id).order_by(CaseAttempt.attempt_date.desc()).all()
        avg_score = round(sum(a.score for a in quiz_attempts)/len(quiz_attempts), 2) if quiz_attempts else 0
        return render_template("student/dashboard.html", user=user, quiz_attempts=quiz_attempts[:5], case_attempts=case_attempts[:5], avg_score=avg_score)

    @app.route("/student/profile", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_profile():
        user = current_user()
        if request.method == "POST":
            user.name = request.form.get("name", user.name)
            user.contact_number = request.form.get("contact_number", user.contact_number)
            user.section = request.form.get("section", user.section)
            user.program = request.form.get("program", user.program)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("student_profile"))
        return render_template("student/profile.html", user=user)

    @app.route("/student/quiz", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_quiz():
        user = current_user()
        questions = QuizQuestion.query.filter_by(published=True).all()
        if request.method == "POST":
            for q in questions:
                selected = request.form.get(f"question_{q.id}")
                if not selected:
                    continue
                db.session.add(QuizAttempt(student_user_id=user.id, question_id=q.id, selected_answer=selected, is_correct=(selected == q.correct_answer), score=(100 if selected == q.correct_answer else 0)))
            db.session.commit()
            flash("Quiz submitted.", "success")
            return redirect(url_for("student_quiz_results"))
        return render_template("student/quiz.html", questions=questions)

    @app.route("/student/quiz-results")
    @login_required
    @role_required("student")
    def student_quiz_results():
        user = current_user()
        attempts = db.session.query(QuizAttempt, QuizQuestion).join(QuizQuestion, QuizQuestion.id == QuizAttempt.question_id).filter(QuizAttempt.student_user_id == user.id).order_by(QuizAttempt.attempt_date.desc()).all()
        return render_template("student/quiz_results.html", attempts=attempts)

    @app.route("/student/case-analyzer", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_case_analyzer():
        user = current_user()
        cases = CaseLibrary.query.all()
        if request.method == "POST":
            case = db.session.get(CaseLibrary, int(request.form.get("case_id")))
            selected_diagnosis = request.form.get("selected_diagnosis", "").strip()
            score = 85.0 if case and case.expected_diagnosis and case.expected_diagnosis.lower() in selected_diagnosis.lower() else 75.0
            db.session.add(CaseAttempt(
                student_user_id=user.id,
                case_id=case.id if case else None,
                input_data=request.form.get("input_data", "").strip(),
                selected_diagnosis=selected_diagnosis,
                interventions=request.form.get("interventions", "").strip(),
                outcomes=request.form.get("outcomes", "").strip(),
                score=score,
                feedback="Good attempt. Review alignment with the expected diagnosis."
            ))
            db.session.commit()
            flash("Case attempt saved.", "success")
            return redirect(url_for("student_case_history"))
        return render_template("student/case_analyzer.html", cases=cases)

    @app.route("/student/case-history")
    @login_required
    @role_required("student")
    def student_case_history():
        user = current_user()
        attempts = CaseAttempt.query.filter_by(student_user_id=user.id).order_by(CaseAttempt.attempt_date.desc()).all()
        return render_template("student/case_history.html", attempts=attempts)

    @app.route("/faculty")
    @login_required
    @role_required("faculty")
    def faculty_dashboard():
        return render_template("faculty/dashboard.html",
            total_students=User.query.filter_by(role="student").count(),
            total_quiz_attempts=QuizAttempt.query.count(),
            total_case_attempts=CaseAttempt.query.count()
        )

    @app.route("/faculty/profile", methods=["GET", "POST"])
    @login_required
    @role_required("faculty")
    def faculty_profile():
        user = current_user()
        if request.method == "POST":
            user.name = request.form.get("name", user.name)
            user.contact_number = request.form.get("contact_number", user.contact_number)
            user.specialization = request.form.get("specialization", user.specialization)
            user.post_nominals = request.form.get("post_nominals", user.post_nominals)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("faculty_profile"))
        return render_template("faculty/profile.html", user=user)

    @app.route("/faculty/students")
    @login_required
    @role_required("faculty")
    def faculty_students():
        return render_template("faculty/students.html", students=User.query.filter_by(role="student").order_by(User.name.asc()).all())

    @app.route("/faculty/quiz-generator", methods=["GET", "POST"])
    @login_required
    @role_required("faculty")
    def faculty_quiz_generator():
        generated_questions = session.get("generated_quiz", [])
        if request.method == "POST":
            topic = request.form.get("topic", "").strip() or "Pediatric Nursing"
            difficulty = request.form.get("difficulty", "Moderate")
            num_items = max(1, min(int(request.form.get("num_items", 5)), 20))
            source_mode = request.form.get("source_mode", "NANDA only")
            generated_questions = []
            for i in range(1, num_items + 1):
                generated_questions.append({
                    "topic": topic,
                    "question_text": f"[Draft {i}] {topic}: Which nursing action is most appropriate first?",
                    "option_a": "Assess airway and breathing",
                    "option_b": "Document immediately",
                    "option_c": "Reassure family only",
                    "option_d": "Delay intervention",
                    "correct_answer": "A",
                    "rationale": f"Draft generated from {source_mode}. Faculty review required before publishing.",
                    "difficulty_level": difficulty,
                })
            session["generated_quiz"] = generated_questions
            flash(f"Generated {num_items} draft items.", "success")
            return redirect(url_for("faculty_quiz_generator"))
        return render_template("faculty/quiz_generator.html", generated_questions=generated_questions)

    @app.route("/faculty/quiz-generator/publish", methods=["POST"])
    @login_required
    @role_required("faculty")
    def faculty_quiz_publish():
        generated = session.get("generated_quiz", [])
        if not generated:
            flash("No generated quiz draft found.", "warning")
            return redirect(url_for("faculty_quiz_generator"))
        for q in generated:
            db.session.add(QuizQuestion(
                topic=q["topic"],
                question_text=q["question_text"],
                option_a=q["option_a"], option_b=q["option_b"], option_c=q["option_c"], option_d=q["option_d"],
                correct_answer=q["correct_answer"],
                rationale=q["rationale"],
                difficulty_level=q["difficulty_level"],
                published=True
            ))
        db.session.commit()
        session.pop("generated_quiz", None)
        flash("Generated quiz published.", "success")
        return redirect(url_for("faculty_quiz_bank"))

    @app.route("/faculty/quiz-bank")
    @login_required
    @role_required("faculty")
    def faculty_quiz_bank():
        return render_template("faculty/quiz_bank.html", questions=QuizQuestion.query.order_by(QuizQuestion.created_at.desc()).all())

    @app.route("/faculty/analytics")
    @login_required
    @role_required("faculty")
    def faculty_analytics():
        total_students = User.query.filter_by(role="student").count()
        total_quiz_attempts = QuizAttempt.query.count()
        correct_count = QuizAttempt.query.filter_by(is_correct=True).count()
        avg_accuracy = round((correct_count / total_quiz_attempts) * 100, 2) if total_quiz_attempts else 0
        total_case_attempts = CaseAttempt.query.count()
        avg_case_score = db.session.query(db.func.avg(CaseAttempt.score)).scalar() or 0
        return render_template("faculty/analytics.html", total_students=total_students, total_quiz_attempts=total_quiz_attempts, avg_accuracy=avg_accuracy, total_case_attempts=total_case_attempts, avg_case_score=round(avg_case_score, 2))

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
