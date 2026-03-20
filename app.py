
from flask import Flask
from models import db
from routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
