from flask import Blueprint
from flask import request
from flask import jsonify

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from flask_jwt_extended import create_access_token

from database import db
from models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():

    data = request.json

    username = data["username"]
    email = data["email"]
    password = data["password"]

    existing_user = User.query.filter_by(
        email=email
    ).first()

    if existing_user:
        return jsonify({
            "message": "Email already exists"
        }), 400

    hashed_password = generate_password_hash(
        password
    )

    user = User(
        username=username,
        email=email,
        password=hashed_password
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Registration successful"
    })


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data["email"]
    password = data["password"]

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:
        return jsonify({
            "message": "User not found"
        }), 404

    if not check_password_hash(
            user.password,
            password):
        return jsonify({
            "message": "Invalid credentials"
        }), 401

    token = create_access_token(
        identity=str(user.id)
    )

    return jsonify({
        "token": token,
        "username": user.username
    })