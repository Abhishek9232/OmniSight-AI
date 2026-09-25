"""
OmniSight-AI Password Security Module.
Provides standalone cryptographic functions for salted password hashing
and constant-time verification using bcrypt.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt with an automatically generated salt.

    Args:
        password: Plaintext password to hash.

    Returns:
        str: UTF-8 decoded bcrypt hash string.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash string.

    Args:
        password: Plaintext password to verify.
        hashed_password: Stored bcrypt hash string.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    if not isinstance(password, str) or not isinstance(hashed_password, str):
        return False

    password_bytes = password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")

    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False
