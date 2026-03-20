from flask import render_template, request, redirect, url_for, flash
from models import db, User, ImportLog
import csv, io

def normalize_email(email):
    return email.strip().lower()

def register_routes(app):

    @app.route("/", methods=["GET", "POST"])
    def import_users():
        preview = []
        errors = []
        user_type = request.form.get("user_type")

        if request.method == "POST":
            file = request.files.get("file")

            if not file:
                flash("Please upload a file", "danger")
                return redirect(url_for("import_users"))

            content = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))

            for i, row in enumerate(reader, start=1):
                name = row.get("name", "").strip()
                email = normalize_email(row.get("email", ""))
                contact = row.get("contact_number", "")

                row_error = []

                if not name:
                    row_error.append("Missing name")

                if not email:
                    row_error.append("Missing email")

                # duplicate check
                existing = User.query.filter_by(email=email).first()
                if existing:
                    row_error.append("Duplicate email")

                if user_type == "student":
                    section = row.get("section", "").strip()
                    program = row.get("program", "").strip()

                    if not section:
                        row_error.append("Missing section")
                    if not program:
                        row_error.append("Missing program")

                else:
                    specialization = row.get("specialization", "").strip()

                preview.append({
                    "row": row,
                    "errors": row_error
                })

            return render_template(
                "manager/import_users.html",
                preview=preview,
                user_type=user_type
            )

        return render_template("manager/import_users.html", preview=[], user_type=None)


    @app.route("/import-confirm", methods=["POST"])
    def import_confirm():

        content = request.form.get("raw_data")
        user_type = request.form.get("user_type")

        reader = csv.DictReader(io.StringIO(content))

        success = 0
        errors = 0

        for row in reader:
            name = row.get("name", "").strip()
            email = normalize_email(row.get("email", ""))

            if not name or not email:
                errors += 1
                continue

            if User.query.filter_by(email=email).first():
                errors += 1
                continue

            if user_type == "student":
                user = User(
                    name=name,
                    email=email,
                    role="student",
                    section=row.get("section"),
                    program=row.get("program"),
                    contact_number=row.get("contact_number")
                )

            else:
                user = User(
                    name=name,
                    email=email,
                    role="faculty",
                    specialization=row.get("specialization"),
                    post_nominals=row.get("post_nominals"),
                    contact_number=row.get("contact_number")
                )

            db.session.add(user)
            success += 1

        db.session.commit()

        log = ImportLog(
            user_type=user_type,
            file_name="uploaded",
            success_count=success,
            error_count=errors
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Imported {success} users. Skipped {errors}.", "success")
        return redirect(url_for("import_users"))
