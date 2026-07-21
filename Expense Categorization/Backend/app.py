from flask import Flask

from flask_cors import CORS

from flask_jwt_extended import JWTManager

from database import db

from config import Config

from auth import auth_bp

from expense_routes import expense_bp

app = Flask(__name__)

app.config.from_object(Config)

CORS(app)

JWTManager(app)

db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(
    auth_bp,
    url_prefix="/api/auth"
)

app.register_blueprint(
    expense_bp,
    url_prefix="/api/expense"
)


@app.route("/")
def home():

    return {
        "message":
        "AI Expense Categorizer API Running"
    }


if __name__ == "__main__":

    app.run(
        debug=True
    )