"""
OmniSight-AI Authentication UI Module.
Provides Streamlit user interfaces for login and user registration.
"""

import streamlit as st
from src.auth.service import authenticate_user, register_user
from src.auth.session import init_session, login_session, logout, get_current_user


def render_login_form() -> None:
    """
    Render the user login form and handle authentication submission.
    """
    st.subheader("Login to Your Account")

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email Address", placeholder="e.g. user@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Log In", use_container_width=True)

    if submitted:
        clean_email = email.strip()
        if not clean_email or not password:
            st.error("Please enter both email address and password.")
            return

        user = authenticate_user(clean_email, password)
        if user:
            login_session(user)
            st.success(f"Welcome back, {user['name']}!")
            st.rerun()
        else:
            st.error("Invalid email or password.")


def render_register_form() -> None:
    """
    Render the user registration form and handle account creation.
    """
    st.subheader("Create a New Account")

    with st.form("register_form", clear_on_submit=True):
        name = st.text_input("Full Name", placeholder="e.g. John Doe")
        email = st.text_input("Email Address", placeholder="e.g. user@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter a secure password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
        role = st.selectbox(
            "Account Role",
            options=["student", "teacher"],
            format_func=lambda r: r.capitalize(),
            help="Select whether you are registering as a student or a teacher."
        )
        submitted = st.form_submit_button("Register", use_container_width=True)

    if submitted:
        clean_name = name.strip()
        clean_email = email.strip()

        if not clean_name:
            st.error("Please enter your full name.")
            return

        if not clean_email:
            st.error("Please enter a valid email address.")
            return

        if not password:
            st.error("Please enter a password.")
            return

        if password != confirm_password:
            st.error("Passwords do not match.")
            return

        created_user = register_user(clean_name, clean_email, password, role)
        if created_user:
            st.success("Registration successful! You may now log in using the Login tab.")
        else:
            st.error(
                "Registration failed. Please ensure the email is not already registered and that all fields are valid."
            )


def render_auth_page() -> None:
    """
    Render the primary authentication view, managing login and registration tabs,
    or displaying session status if already authenticated.
    """
    init_session()
    current_user = get_current_user()

    if current_user:
        st.info(f"Currently signed in as: **{current_user['name']}** ({current_user['role'].capitalize()})")
        if st.button("Log Out"):
            logout()
            st.rerun()
        return

    st.title("OmniSight-AI")
    st.caption("AI-Assisted Online Examination & Integrity Monitoring Platform")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        render_login_form()

    with tab_register:
        render_register_form()
