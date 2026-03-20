import csv
import io
import json
from flask import render_template, request, redirect, url_for, flash, session
from models import db, User, ImportLog

ALLOWED_EXTENSIONS = {"csv"}

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_row(row, user_type):
    errors = []
    cleaned = {
        "name": (row.get("name") or "").strip(),
        "email": normalize_email(row.get("email")),
        "role": user_type,
        "section": None,
        "program": None,
        "specialization": None,
        "post_nominals": None,
        "contact_number": (row.get("contact_number") or "").strip(),
    }

    if not cleaned["name"]:
        errors.append("Missing name")
    if not cleaned["email"]:
        errors.append("Missing email")
    elif "@" not in cleaned["email"]:
        errors.append("Invalid email format")

    if user_type == "student":
        cleaned["section"] = (row.get("section") or "").strip()
        cleaned["program"] = (row.get("program") or "").strip()
        if not cleaned["section"]:
            errors.append("Missing section")
        if not cleaned["program"]:
            errors.append("Missing program")
    elif user_type == "faculty":
        cleaned["specialization"] = (row.get("specialization") or "").strip()
        cleaned["post_nominals"] = (row.get("post_nominals") or "").strip()
        if not cleaned["specialization"]:
            errors.append("Missing specialization")

    return cleaned, errors

def register_routes(app):

    @app.route("/")
    def home():
        return redirect(url_for("manager_import_users"))

    @app.route("/manager/import-users", methods=["GET", "POST"])
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

            if not allowed_file(uploaded_file.filename):
                flash("Only CSV files are allowed in this production-ready version.", "danger")
                return redirect(url_for("manager_import_users"))

            try:
                content = uploaded_file.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
            except Exception as exc:
                flash(f"Unable to read file: {exc}", "danger")
                return redirect(url_for("manager_import_users"))

            if not rows:
                flash("The uploaded file is empty.", "warning")
                return redirect(url_for("manager_import_users"))

            required = {
                "student": ["name", "section", "program", "contact_number", "email"],
                "faculty": ["name", "email", "specialization", "post_nominals", "contact_number"],
            }

            uploaded_columns = [str(col).strip() for col in rows[0].keys()]
            missing_columns = [col for col in required[user_type] if col not in uploaded_columns]
            if missing_columns:
                flash(f"Missing required columns: {', '.join(missing_columns)}", "danger")
                return redirect(url_for("manager_import_users"))

            seen_emails = set()
            preview_rows = []

            for idx, row in enumerate(rows, start=1):
                cleaned, row_errors = validate_row(row, user_type)

                if cleaned["email"]:
                    if cleaned["email"] in seen_emails:
                        row_errors.append("Duplicate email in uploaded file")
                    seen_emails.add(cleaned["email"])

                    if User.query.filter_by(email=cleaned["email"]).first():
                        row_errors.append("Email already exists in database")

                preview_rows.append({
                    "row_number": idx,
                    "name": cleaned["name"],
                    "email": cleaned["email"],
                    "role": cleaned["role"],
                    "section": cleaned["section"],
                    "program": cleaned["program"],
                    "specialization": cleaned["specialization"],
                    "post_nominals": cleaned["post_nominals"],
                    "contact_number": cleaned["contact_number"],
                    "errors": row_errors,
                })

            session["import_preview_rows"] = preview_rows
            session["import_user_type"] = user_type
            session["import_file_name"] = uploaded_file.filename

            return redirect(url_for("manager_import_users"))

        return render_template(
            "manager/import_users.html",
            preview_rows=preview_rows,
            preview_mode=preview_mode,
            selected_type=selected_type,
        )

    @app.route("/manager/import-users/confirm", methods=["POST"])
    def manager_import_users_confirm():
        preview_rows = session.get("import_preview_rows", [])
        user_type = session.get("import_user_type")
        file_name = session.get("import_file_name", "uploaded.csv")

        if not preview_rows or not user_type:
            flash("No pending import found. Please upload a file first.", "warning")
            return redirect(url_for("manager_import_users"))

        success_count = 0
        error_count = 0

        for row in preview_rows:
            if row["errors"]:
                error_count += 1
                continue

            if User.query.filter_by(email=row["email"]).first():
                error_count += 1
                continue

            user = User(
                name=row["name"],
                email=row["email"],
                role=row["role"],
                section=row.get("section"),
                program=row.get("program"),
                specialization=row.get("specialization"),
                post_nominals=row.get("post_nominals"),
                contact_number=row.get("contact_number"),
            )
            db.session.add(user)
            success_count += 1

        db.session.commit()

        log = ImportLog(
            user_type=user_type,
            file_name=file_name,
            success_count=success_count,
            error_count=error_count,
        )
        db.session.add(log)
        db.session.commit()

        session.pop("import_preview_rows", None)
        session.pop("import_user_type", None)
        session.pop("import_file_name", None)

        flash(f"Import completed. Added {success_count} users; skipped {error_count}.", "success")
        return redirect(url_for("manager_import_users"))

    @app.route("/manager/import-users/cancel", methods=["POST"])
    def manager_import_users_cancel():
        session.pop("import_preview_rows", None)
        session.pop("import_user_type", None)
        session.pop("import_file_name", None)
        flash("Pending import cleared.", "info")
        return redirect(url_for("manager_import_users"))

    @app.route("/manager/users")
    def manager_users():
        users = User.query.order_by(User.role.asc(), User.name.asc()).all()
        return render_template("manager/users.html", users=users)

    @app.route("/manager/import-logs")
    def manager_import_logs():
        logs = ImportLog.query.order_by(ImportLog.created_at.desc()).all()
        return render_template("manager/import_logs.html", logs=logs)
