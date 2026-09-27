"""
OmniSight-AI Main Application Entrypoint.
Top-level application router dispatching unauthenticated sessions to the
authentication portal, and authenticated sessions to role-specific user interfaces.
"""

import streamlit as st
from src.auth.session import init_session, get_current_user, logout
from src.ui.auth_ui import render_auth_page
from src.ui.student_ui import render_student_ui
from src.ui.teacher_ui import render_teacher_ui

# Configure Streamlit page settings
st.set_page_config(
    page_title="OmniSight-AI",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    """
    Main application runner and top-level role router.
    Routes unauthenticated sessions to the authentication interface,
    and authenticated sessions to their respective role dashboards.
    """
    init_session()
    current_user = get_current_user()

    if not current_user:
        render_auth_page()
        return

    role = current_user.get("role")
    if role == "student":
        render_student_ui()
    elif role in ("teacher", "admin"):
        render_teacher_ui()
    else:
        st.error(f"Access Denied: Unrecognized or unauthorized user role '{role}'.")
        if st.button("Log Out", key="invalid_role_logout_btn"):
            logout()
            st.rerun()


if __name__ == "__main__":
    main()
