"""
OmniSight-AI Authentication Service Module.
Handles user registration, user retrieval, and credential authentication.
"""

from typing import Optional, Dict, Any
import mysql.connector
from src.database.connection import get_connection
from src.auth.security import hash_password, verify_password

ALLOWED_REGISTRATION_ROLES = {"student", "teacher"}


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user record by email address.

    Args:
        email: Email address to search for.

    Returns:
        dict with user record if found, None otherwise.
    """
    if not email or not isinstance(email, str):
        return None

    normalized_email = email.strip().lower()
    if not normalized_email:
        return None

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, name, email, password_hash, role, created_at
            FROM users
            WHERE email = %s
            LIMIT 1;
        """
        cursor.execute(query, (normalized_email,))
        user = cursor.fetchone()
        return user
    except mysql.connector.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def register_user(
    name: str,
    email: str,
    password: str,
    role: str
) -> Optional[Dict[str, Any]]:
    """
    Register a new student or teacher user in the database.

    Args:
        name: Full name of the user.
        email: Email address of the user.
        password: Plaintext password (will be hashed).
        role: User role ('student' or 'teacher').

    Returns:
        Dict with registered user information (without password) on success,
        or None on validation/database error (e.g. duplicate email).
    """
    if not name or not isinstance(name, str) or not name.strip():
        return None
    if not email or not isinstance(email, str) or not email.strip():
        return None
    if not password or not isinstance(password, str):
        return None
    if not role or not isinstance(role, str):
        return None

    normalized_name = name.strip()
    normalized_email = email.strip().lower()
    normalized_role = role.strip().lower()

    if normalized_role not in ALLOWED_REGISTRATION_ROLES:
        return None

    # Check for existing email before attempting insertion
    if get_user_by_email(normalized_email) is not None:
        return None

    hashed_pw = hash_password(password)

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s);
        """
        cursor.execute(query, (normalized_name, normalized_email, hashed_pw, normalized_role))
        conn.commit()
        user_id = cursor.lastrowid
        return {
            "id": user_id,
            "name": normalized_name,
            "email": normalized_email,
            "role": normalized_role
        }
    except mysql.connector.Error:
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user credentials against the database.

    Args:
        email: User email.
        password: User plaintext password.

    Returns:
        Dict with authenticated user details (id, name, email, role) on success,
        or None on authentication failure (invalid email or incorrect password).
    """
    if not email or not isinstance(email, str) or not password or not isinstance(password, str):
        return None

    user = get_user_by_email(email)
    if not user:
        return None

    stored_hash = user.get("password_hash")
    if not stored_hash or not verify_password(password, stored_hash):
        return None

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    }
