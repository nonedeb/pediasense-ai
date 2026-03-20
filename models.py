from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)

    role = db.Column(db.String(20), nullable=False)  # student / faculty

    section = db.Column(db.String(50))
    program = db.Column(db.String(100))

    specialization = db.Column(db.String(150))
    post_nominals = db.Column(db.String(100))

    contact_number = db.Column(db.String(30))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ImportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20))
    file_name = db.Column(db.String(255))
    success_count = db.Column(db.Integer)
    error_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
