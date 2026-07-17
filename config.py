import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///student_result.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
