"""
OmniSight-AI Main Application Entrypoint.
Minimal runner launching the authentication interface.
"""

import streamlit as st
from src.ui.auth_ui import render_auth_page

# Configure Streamlit page settings
st.set_page_config(
    page_title="OmniSight-AI",
    page_icon="👁️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    """Main application runner."""
    render_auth_page()


if __name__ == "__main__":
    main()
