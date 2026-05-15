"""
VeraBil — Configuration
Load from environment variables with safe defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY       = os.getenv("SECRET_KEY", "verabill-dev-secret-change-in-production")
    DEBUG            = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # Upload
    UPLOAD_FOLDER    = os.path.join(os.path.dirname(__file__), "uploads")
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # OpenAI
    OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o")

    # MSSQL — uses pyodbc DSN or connection string
    DB_SERVER        = os.getenv("DB_SERVER",   "localhost")
    DB_NAME          = os.getenv("DB_DATABASE",  "VeraBilDB")
    DB_USER          = os.getenv("DB_USER",      "sa")
    DB_PASSWORD      = os.getenv("DB_PASSWORD",  "")
    DB_DRIVER        = os.getenv("DB_DRIVER",    "ODBC Driver 17 for SQL Server")

    @classmethod
    def get_connection_string(cls) -> str:
        return (
            f"DRIVER={{{cls.DB_DRIVER}}};"
            f"SERVER={cls.DB_SERVER};"
            f"DATABASE={cls.DB_NAME};"
            f"UID={cls.DB_USER};"
            f"PWD={cls.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
