import os

class Config:

    SECRET_KEY = "expense_categorizer_secret_key"

    SQLALCHEMY_DATABASE_URI = "sqlite:///expense.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = "expense_categorizer_project_super_secure_jwt_secret_2026"

    UPLOAD_FOLDER = "uploads"

    GEMINI_API_KEY = "AQ.Ab8RN6LpBu21cuLD5grrW9BgBhblB16nShQeBex1q8m3jdKAJA"