"""
OmniSight-AI Streamlit Session Management Module.
Centralizes Streamlit session-state management for authenticated users.
"""

from typing import Optional, Dict, Any, List, Union
import streamlit as st


def init_session() -> None:
    """
    Initialize authentication-related session keys if they do not exist.
    """
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None


def login_session(user: Dict[str, Any]) -> None:
    """
    Store authenticated user information into Streamlit session state.

    Args:
        user: Authenticated user dictionary from authenticate_user().
    """
    init_session()
    if not user or not isinstance(user, dict):
        return

    st.session_state.is_authenticated = True
    st.session_state.user_id = user.get("id")
    st.session_state.user_name = user.get("name")
    st.session_state.user_email = user.get("email")
    st.session_state.user_role = user.get("role")


def logout() -> None:
    """
    Clear user-specific authentication session values.
    """
    st.session_state.is_authenticated = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_email = None
    st.session_state.user_role = None


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Return the currently authenticated user's basic information.

    Returns:
        dict with user information if authenticated, None otherwise.
    """
    init_session()
    if not getattr(st.session_state, "is_authenticated", False):
        return None

    return {
        "id": st.session_state.user_id,
        "name": st.session_state.user_name,
        "email": st.session_state.user_email,
        "role": st.session_state.user_role,
    }


def require_role(allowed_roles: Union[List[str], str]) -> bool:
    """
    Check whether the current authenticated user's role belongs to the supplied roles.

    Args:
        allowed_roles: Single role string or list/collection of allowed role strings.

    Returns:
        bool: True if authenticated and user's role is in allowed_roles, False otherwise.
    """
    current_user = get_current_user()
    if not current_user:
        return False

    user_role = current_user.get("role")
    if not user_role:
        return False

    if isinstance(allowed_roles, str):
        roles_set = {allowed_roles.strip().lower()}
    else:
        roles_set = {r.strip().lower() for r in allowed_roles if isinstance(r, str)}

    return user_role.lower() in roles_set
