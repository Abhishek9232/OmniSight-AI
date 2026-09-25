"""
OmniSight-AI Database Connection Module
Provides a reusable connection function to connect to MySQL using
environment variables loaded from the project root .env file.
"""

import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

# Locate and load environment variables from the project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def get_connection():
    """
    Establish and return a MySQL connection using environment variables.
    """
    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD", "")

    return mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
