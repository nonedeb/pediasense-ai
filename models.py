from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # student / faculty / manager
    section = db.Column(db.String(50), nullable=True)
    program = db.Column(db.String(100), nullable=True)
    specialization = db.Column(db.String(150), nullable=True)
    post_nominals = db.Column(db.String(100), nullable=True)
    contact_number = db.Column(db.String(30), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ImportLog(db.Model):
    __tablename__ = "import_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
