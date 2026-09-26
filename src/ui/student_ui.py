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
    get_attempt,
    get_attempt_questions,
    get_attempt_answers,
    save_answer,
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


def _on_radio_select(attempt_id: int, student_id: int, qid: int, widget_key: str, cache_key: str) -> None:
    """Callback triggered whenever student selects or changes a radio option."""
    selected = st.session_state.get(widget_key)
    if selected in {"A", "B", "C", "D"}:
        try:
            save_answer(attempt_id, student_id, qid, selected)
            if cache_key in st.session_state:
                st.session_state[cache_key][qid] = selected
        except Exception as e:
            st.session_state["active_exam_error"] = f"Failed to save answer: {str(e)}"


def _on_clear_selection(attempt_id: int, student_id: int, qid: int, widget_key: str, cache_key: str) -> None:
    """Callback triggered to clear answer selection for the active question."""
    try:
        save_answer(attempt_id, student_id, qid, None)
        if cache_key in st.session_state:
            st.session_state[cache_key][qid] = None
        if widget_key in st.session_state:
            st.session_state[widget_key] = None
    except Exception as e:
        st.session_state["active_exam_error"] = f"Failed to clear selection: {str(e)}"


def _on_nav_prev(index_key: str) -> None:
    """Callback triggered to navigate to the previous question."""
    if index_key in st.session_state and st.session_state[index_key] > 0:
        st.session_state[index_key] -= 1


def _on_save_and_next(
    attempt_id: int,
    student_id: int,
    qid: int,
    widget_key: str,
    cache_key: str,
    index_key: str,
    max_idx: int,
) -> None:
    """Callback triggered to ensure current answer is saved and advance to next question."""
    selected = st.session_state.get(widget_key)
    if selected in {"A", "B", "C", "D"}:
        try:
            save_answer(attempt_id, student_id, qid, selected)
            if cache_key in st.session_state:
                st.session_state[cache_key][qid] = selected
        except Exception as e:
            st.session_state["active_exam_error"] = f"Failed to save answer: {str(e)}"
    if index_key in st.session_state and st.session_state[index_key] < max_idx:
        st.session_state[index_key] += 1


def _on_palette_jump(index_key: str, target_idx: int) -> None:
    """Callback triggered to jump directly to a target question from the palette."""
    st.session_state[index_key] = target_idx


def render_active_exam(student_id: int, attempt_id: Optional[int]) -> None:
    """
    Render the active examination interface displaying the current question, options,
    navigation controls, and interactive question palette with answer persistence.

    Args:
        student_id: User ID of the authenticated student.
        attempt_id: Active attempt ID from session state.
    """
    if not attempt_id:
        st.warning("No active examination session found. Returning to catalog.")
        if st.button("Return to Catalog", key="no_active_attempt_btn"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    try:
        attempt = get_attempt(attempt_id, student_id)
    except ValueError as e:
        st.error(f"Examination attempt error: {str(e)}")
        if st.button("Return to Catalog", key="val_err_attempt_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return
    except PermissionError as e:
        st.error(f"Unauthorized Access: {str(e)}")
        if st.button("Return to Catalog", key="perm_err_attempt_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return
    except Exception as e:
        st.error(f"Failed to load examination attempt: {str(e)}")
        if st.button("Return to Catalog", key="gen_err_attempt_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    attempt_status = attempt.get("status")
    if attempt_status in {"SUBMITTED", "EVALUATED"}:
        st.session_state["view_result_attempt_id"] = attempt_id
        st.session_state["student_view"] = "result"
        st.rerun()
        return

    if attempt_status != "IN_PROGRESS":
        st.error(f"Examination attempt has invalid status '{attempt_status}'.")
        if st.button("Return to Catalog", key="invalid_status_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    exam_id = attempt["exam_id"]
    try:
        exam = get_exam(exam_id)
    except Exception as e:
        st.error(f"Failed to load examination details: {str(e)}")
        if st.button("Return to Catalog", key="exam_load_err_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    if not exam:
        st.error(f"Associated examination with ID {exam_id} could not be found.")
        if st.button("Return to Catalog", key="missing_exam_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    try:
        questions = get_attempt_questions(attempt_id, student_id)
    except Exception as e:
        st.error(f"Failed to retrieve questions for attempt: {str(e)}")
        if st.button("Return to Catalog", key="q_err_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    if not questions:
        st.warning("This examination currently contains no questions. Please contact your instructor.")
        if st.button("Return to Catalog", key="empty_questions_btn"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    # Initialize or restore answers cache from service layer
    cache_key = f"attempt_answers_{attempt_id}"
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = get_attempt_answers(attempt_id, student_id)
        except Exception:
            st.session_state[cache_key] = {}
    answers_cache = st.session_state[cache_key]

    # Display active exam flash errors if any
    if "active_exam_error" in st.session_state:
        st.error(st.session_state.pop("active_exam_error"))

    index_key = f"q_index_{attempt_id}"
    if index_key not in st.session_state:
        st.session_state[index_key] = 0

    current_idx = st.session_state[index_key]
    if current_idx < 0:
        current_idx = 0
        st.session_state[index_key] = 0
    elif current_idx >= len(questions):
        current_idx = len(questions) - 1
        st.session_state[index_key] = current_idx

    current_q = questions[current_idx]
    qid = current_q["question_id"]

    col_title, col_badge = st.columns([3, 1])
    with col_title:
        st.subheader(exam.get("title", "Examination"))
        if exam.get("description"):
            st.caption(exam["description"])
    with col_badge:
        st.markdown(
            f"<div style='text-align: right; margin-top: 8px; font-weight: bold; color: #FB8C00;'>"
            f"ATTEMPT #{attempt_id} (IN PROGRESS)"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    col_qnum, col_marks = st.columns([3, 1])
    with col_qnum:
        st.markdown(f"#### Question {current_idx + 1} of {len(questions)}")
    with col_marks:
        marks = current_q.get("marks", 1)
        mark_label = "Mark" if marks == 1 else "Marks"
        st.markdown(
            f"<div style='text-align: right; font-weight: bold; padding-top: 4px;'>"
            f"Points: {marks} {mark_label}"
            f"</div>",
            unsafe_allow_html=True,
        )

    saved_option = answers_cache.get(qid)
    option_keys = ["A", "B", "C", "D"]
    default_idx = option_keys.index(saved_option) if saved_option in option_keys else None
    widget_key = f"option_choice_{attempt_id}_{qid}"

    with st.container(border=True):
        st.markdown(f"**{current_q.get('question_text', '')}**")
        st.write("")

        option_labels = {
            "A": f"A. {current_q.get('option_a', '')}",
            "B": f"B. {current_q.get('option_b', '')}",
            "C": f"C. {current_q.get('option_c', '')}",
            "D": f"D. {current_q.get('option_d', '')}",
        }

        st.radio(
            label="Select your answer:",
            options=option_keys,
            format_func=lambda opt: option_labels.get(opt, opt),
            index=default_idx,
            key=widget_key,
            on_change=_on_radio_select,
            args=(attempt_id, student_id, qid, widget_key, cache_key),
        )

    # Navigation Controls Row
    col_prev, col_clear, col_save_next = st.columns([1, 1, 1])

    with col_prev:
        st.button(
            "← Previous",
            key=f"prev_btn_{attempt_id}_{qid}",
            disabled=(current_idx == 0),
            on_click=_on_nav_prev,
            args=(index_key,),
            use_container_width=True,
        )

    with col_clear:
        st.button(
            "Clear Selection",
            key=f"clear_btn_{attempt_id}_{qid}",
            disabled=(saved_option is None),
            on_click=_on_clear_selection,
            args=(attempt_id, student_id, qid, widget_key, cache_key),
            use_container_width=True,
        )

    with col_save_next:
        if current_idx < len(questions) - 1:
            st.button(
                "Save & Next →",
                key=f"save_next_btn_{attempt_id}_{qid}",
                type="primary",
                on_click=_on_save_and_next,
                args=(attempt_id, student_id, qid, widget_key, cache_key, index_key, len(questions) - 1),
                use_container_width=True,
            )
        else:
            st.button(
                "Save Answer",
                key=f"save_btn_{attempt_id}_{qid}",
                type="primary",
                on_click=_on_radio_select,
                args=(attempt_id, student_id, qid, widget_key, cache_key),
                use_container_width=True,
            )

    # Question Palette Section
    st.divider()
    st.markdown("### Question Palette")

    total_q = len(questions)
    answered_q = sum(1 for q in questions if answers_cache.get(q["question_id"]) is not None)
    unanswered_q = total_q - answered_q

    col_tot, col_ans, col_unans = st.columns(3)
    col_tot.metric("Total Questions", total_q)
    col_ans.metric("Answered", answered_q)
    col_unans.metric("Unanswered", unanswered_q)

    st.write("")
    palette_cols_count = min(total_q, 6)
    if palette_cols_count > 0:
        for row_start in range(0, total_q, palette_cols_count):
            row_slice = questions[row_start:row_start + palette_cols_count]
            cols = st.columns(palette_cols_count)
            for offset, q in enumerate(row_slice):
                q_num = row_start + offset
                q_id = q["question_id"]
                is_curr = (q_num == current_idx)
                is_ans = (answers_cache.get(q_id) is not None)

                if is_curr:
                    btn_label = f"● {q_num + 1}"
                    btn_type = "primary"
                elif is_ans:
                    btn_label = f"✓ {q_num + 1}"
                    btn_type = "secondary"
                else:
                    btn_label = f"{q_num + 1}"
                    btn_type = "secondary"

                cols[offset].button(
                    label=btn_label,
                    key=f"palette_btn_{attempt_id}_{q_id}",
                    on_click=_on_palette_jump,
                    args=(index_key, q_num),
                    use_container_width=True,
                    type=btn_type,
                    help=f"Question {q_num + 1}: {'Current' if is_curr else ('Answered' if is_ans else 'Unanswered')}"
                )

    st.write("")
    if st.button("Exit to Catalog", key=f"exit_active_{attempt_id}"):
        st.session_state["student_view"] = "catalog"
        st.rerun()


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
        render_active_exam(user["id"], active_attempt_id)

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
