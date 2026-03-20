
from flask import render_template, request
import csv, io

def register_routes(app):

    @app.route("/", methods=["GET", "POST"])
    def import_users():
        preview = []
        if request.method == "POST":
            file = request.files["file"]
            content = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                preview.append(row)
        return render_template("manager/import_users.html", preview=preview)
