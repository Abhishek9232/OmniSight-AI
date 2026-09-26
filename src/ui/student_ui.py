"""
OmniSight-AI Student Exam Portal UI Module.
Provides the Streamlit presentation layer for students to browse published examinations,
inspect exam instructions, and initiate assessment attempts.
"""

from typing import Optional, Dict, Any, List
import streamlit as st
from src.auth.session import get_current_user, require_role, logout
from src.exam.service import (
    get_published_exams,
    get_student_attempt_for_exam,
    get_exam,
    start_attempt,
)


def render_student_header(user: Dict[str, Any]) -> None:
    """
    Render the top navigation header displaying student identity, role, and logout control.

    Args:
        user: Authenticated user dictionary from session.
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("Student Exam Portal")
        st.caption("Discover available examinations, review syllabus instructions, and take assessments.")

    with col2:
        st.markdown(f"**{user.get('name', 'Student')}**")
        role_label = user.get("role", "student").upper()
        if hasattr(st, "badge"):
            st.badge(f"Role: {role_label}")
        else:
            st.caption(f"Role: **{role_label}**")
        if st.button("Log Out", key="student_logout_btn"):
            logout()
            st.rerun()

    st.divider()


def render_exam_catalog(student_id: int) -> None:
    """
    Render the catalog of all currently PUBLISHED examinations available to students.

    Args:
        student_id: User ID of the authenticated student.
    """
    st.subheader("Available Examinations")

    try:
        exams: List[Dict[str, Any]] = get_published_exams()
    except Exception as e:
        st.error(f"Failed to load examinations: {str(e)}")
        return

    if not exams:
        st.info("No published examinations available at this time. Please check back later.")
        return

    st.caption(f"Total available examinations: **{len(exams)}**")

    for exam in exams:
        exam_id = exam["exam_id"]

        # Check existing attempt for this student
        try:
            attempt = get_student_attempt_for_exam(exam_id, student_id)
        except Exception:
            attempt = None

        attempt_status = attempt.get("status") if attempt else None

        # Determine attempt status display badge and action
        if attempt_status is None:
            badge_label = "Available"
            badge_color = "#1E88E5"  # Blue
        elif attempt_status == "IN_PROGRESS":
            badge_label = "In Progress"
            badge_color = "#FB8C00"  # Orange
        elif attempt_status in {"SUBMITTED", "EVALUATED"}:
            badge_label = "Completed"
            badge_color = "#43A047"  # Green
        else:
            badge_label = attempt_status
            badge_color = "#757575"

        with st.container(border=True):
            col_info, col_action = st.columns([3, 1])

            with col_info:
                st.markdown(f"### {exam.get('title', 'Untitled Exam')}")
                if exam.get("description"):
                    st.write(exam["description"])

                q_count = exam.get("question_count", 0)
                st.caption(
                    f"**Exam ID**: {exam_id} | "
                    f"**Duration**: {exam.get('duration_minutes', 0)} mins | "
                    f"**Questions**: {q_count} | "
                    f"**Published**: {exam.get('created_at', 'N/A')}"
                )

            with col_action:
                st.markdown(
                    f"<div style='text-align: right; font-weight: bold; color: {badge_color}; margin-bottom: 12px;'>"
                    f"STATUS: {badge_label.upper()}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if attempt_status is None:
                    if st.button("View Instructions", key=f"start_prep_{exam_id}", use_container_width=True, type="primary"):
                        st.session_state["selected_exam_id"] = exam_id
                        st.session_state["student_view"] = "instructions"
                        st.rerun()
                elif attempt_status == "IN_PROGRESS":
                    if st.button("Resume Exam", key=f"resume_{exam_id}", use_container_width=True):
                        st.session_state["active_attempt_id"] = attempt["attempt_id"]
                        st.session_state["active_exam_id"] = exam_id
                        st.session_state["student_view"] = "active_exam"
                        st.rerun()
                elif attempt_status in {"SUBMITTED", "EVALUATED"}:
                    if st.button("View Result", key=f"result_{exam_id}", use_container_width=True):
                        st.session_state["view_result_attempt_id"] = attempt["attempt_id"]
                        st.session_state["student_view"] = "result"
                        st.rerun()


def render_exam_instructions(student_id: int, exam_id: Optional[int]) -> None:
    """
    Render the dedicated pre-flight instructions screen before initiating an attempt.

    Args:
        student_id: User ID of the authenticated student.
        exam_id: Unique exam identifier.
    """
    if not exam_id:
        st.warning("No examination selected.")
        if st.button("Back to Catalog"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    try:
        exam = get_exam(exam_id)
    except Exception as e:
        st.error(f"Failed to load examination: {str(e)}")
        if st.button("Back to Catalog"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    if not exam or exam.get("status") != "PUBLISHED":
        st.error("This examination is not available for participation.")
        if st.button("Back to Catalog"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    st.subheader(f"Examination Instructions: {exam.get('title')}")

    with st.container(border=True):
        st.markdown("### Examination Guidelines & Candidate Agreement")
        if exam.get("description"):
            st.markdown(f"**Instructions / Syllabus Coverage:**\n\n{exam['description']}")

        st.markdown(
            f"""
            ---
            **Key Examination Information:**
            - **Total Duration**: {exam.get('duration_minutes', 0)} minutes.
            - **Question Format**: Multiple-choice questions with 4 options and a single correct answer.
            - **Grading Policy**: Points awarded for correct answers; no negative markings for omitted questions.
            - **Single-Attempt Invariant**: You are permitted exactly ONE attempt. Once initiated, the exam cannot be restarted.
            - **Server-Side Timing**: The examination countdown timer commences immediately upon clicking "Start Examination" and runs continuously.
            - **Automatic Finalization**: If your time expires, your answers will be automatically finalized and submitted.
            ---
            """
        )

        st.warning(
            "Please ensure you have a stable network connection before starting. "
            "Do not close or reload the examination window while an attempt is in progress."
        )

        ready_confirmed = st.checkbox(
            "I have read, understood, and agree to the examination instructions and academic integrity standards.",
            key=f"ready_confirm_{exam_id}",
        )

        col_back, col_start = st.columns([1, 1])

        with col_back:
            if st.button("Back to Catalog", use_container_width=True):
                st.session_state["student_view"] = "catalog"
                st.session_state["selected_exam_id"] = None
                st.rerun()

        with col_start:
            if st.button("Start Examination", use_container_width=True, type="primary"):
                if not ready_confirmed:
                    st.warning("You must confirm that you have read and understood the instructions before beginning.")
                else:
                    try:
                        attempt = start_attempt(exam_id=exam_id, student_id=student_id)
                        st.session_state["active_attempt_id"] = attempt["attempt_id"]
                        st.session_state["active_exam_id"] = exam_id
                        st.session_state["student_view"] = "active_exam"
                        st.session_state["student_flash_msg"] = (
                            f"Examination '{exam.get('title')}' started successfully!"
                        )
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Cannot start examination: {str(e)}")
                    except PermissionError as e:
                        st.error(f"Permission Denied: {str(e)}")
                    except Exception as e:
                        st.error(f"Failed to initiate examination session: {str(e)}")


def render_student_ui() -> None:
    """
    Main entrypoint for the Student Exam Portal presentation layer.
    Enforces student role requirement and manages view routing across catalog,
    instructions, active exam, and result displays.
    """
    if not require_role(["student"]):
        st.error("Access Denied: You must be signed in as a student to access the examination portal.")
        return

    user = get_current_user()
    if not user or not user.get("id"):
        st.error("Session error: User identity not found. Please log in again.")
        return

    render_student_header(user)

    # Display flash notification if set
    if "student_flash_msg" in st.session_state:
        st.success(st.session_state.pop("student_flash_msg"))

    # Manage view routing
    view = st.session_state.get("student_view", "catalog")

    if view == "catalog":
        render_exam_catalog(user["id"])

    elif view == "instructions":
        selected_exam_id = st.session_state.get("selected_exam_id")
        render_exam_instructions(user["id"], selected_exam_id)

    elif view == "active_exam":
        active_attempt_id = st.session_state.get("active_attempt_id")
        active_exam_id = st.session_state.get("active_exam_id")
        st.subheader("Active Examination Session")
        st.info(
            f"Examination attempt (ID: {active_attempt_id}) is currently in progress.\n\n"
            "The active question-taking interface will be implemented in Step 3 Part 2B."
        )
        if st.button("Return to Catalog", key="return_from_active"):
            st.session_state["student_view"] = "catalog"
            st.rerun()

    elif view == "result":
        attempt_id = st.session_state.get("view_result_attempt_id")
        st.subheader("Examination Result")
        st.info(
            f"Viewing results for attempt ID: {attempt_id}.\n\n"
            "The comprehensive result scorecard interface will be implemented in Step 3 Part 2C."
        )
        if st.button("Return to Catalog", key="return_from_result"):
            st.session_state["student_view"] = "catalog"
            st.rerun()

    else:
        st.session_state["student_view"] = "catalog"
        render_exam_catalog(user["id"])
