"""
OmniSight-AI Student Exam Portal UI Module.
Provides the Streamlit presentation layer for students to browse published examinations,
inspect exam instructions, and initiate assessment attempts.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import streamlit as st
import streamlit.components.v1 as components
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
    submit_attempt,
    evaluate_attempt,
    get_attempt_result,
    get_attempt_scorecard_details,
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


def _on_go_to_review(
    attempt_id: int,
    student_id: int,
    qid: int,
    widget_key: str,
    cache_key: str,
) -> None:
    """Callback triggered to ensure current answer is saved and navigate to review screen."""
    selected = st.session_state.get(widget_key)
    if selected in {"A", "B", "C", "D"}:
        try:
            save_answer(attempt_id, student_id, qid, selected)
            if cache_key in st.session_state:
                st.session_state[cache_key][qid] = selected
        except Exception as e:
            st.session_state["active_exam_error"] = f"Failed to save answer: {str(e)}"
    st.session_state["student_view"] = "review_exam"


def _render_countdown_timer(
    official_deadline: datetime,
    grace_deadline: datetime,
    remaining_seconds: int,
    grace_remaining_seconds: int,
) -> None:
    """
    Render an isolated client-side countdown timer component using HTML/JavaScript.
    Operates smoothly without blocking Python execution or triggering Streamlit reruns.
    Transitions seamlessly from official exam duration to the 60-second grace window.

    Args:
        official_deadline: Authoritative server-side expiration timestamp.
        grace_deadline: Authoritative server-side hard cutoff timestamp (deadline + 60s).
        remaining_seconds: Current calculated remaining seconds until official deadline.
        grace_remaining_seconds: Current calculated remaining seconds until hard cutoff.
    """
    target_timestamp_ms = int(official_deadline.timestamp() * 1000)
    grace_timestamp_ms = int(grace_deadline.timestamp() * 1000)

    in_grace = remaining_seconds <= 0

    if in_grace:
        initial_color = "#D32F2F"
        initial_bg = "rgba(211, 47, 47, 0.12)"
        initial_border = "#D32F2F"
        initial_label = f"⏰ Grace Window: {max(0, grace_remaining_seconds)}s remaining"
    else:
        rem_diff = max(0, remaining_seconds)
        hours = rem_diff // 3600
        mins = (rem_diff % 3600) // 60
        secs = rem_diff % 60
        if hours > 0:
            formatted_initial = f"{hours:02d}:{mins:02d}:{secs:02d}"
        else:
            formatted_initial = f"{mins:02d}:{secs:02d}"

        if rem_diff > 300:
            initial_color = "#1E88E5"
            initial_bg = "rgba(30, 136, 229, 0.12)"
            initial_border = "#1E88E5"
            initial_label = f"⏳ Time Remaining: {formatted_initial}"
        elif rem_diff > 60:
            initial_color = "#FB8C00"
            initial_bg = "rgba(251, 140, 0, 0.12)"
            initial_border = "#FB8C00"
            initial_label = f"⚠️ Time Remaining: {formatted_initial}"
        else:
            initial_color = "#E53935"
            initial_bg = "rgba(229, 57, 53, 0.12)"
            initial_border = "#E53935"
            initial_label = f"🚨 Final Minute: {formatted_initial}"

    timer_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            overflow: hidden;
        }}
        #countdown-display {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: {initial_color};
            background: {initial_bg};
            border: 1px solid {initial_border};
        }}
    </style>
    </head>
    <body>
    <div id="countdown-display">{initial_label}</div>
    <script>
        const officialTarget = {target_timestamp_ms};
        const graceTarget = {grace_timestamp_ms};
        function tick() {{
            const now = Date.now();
            const el = document.getElementById("countdown-display");
            if (!el) return;

            if (now < officialTarget) {{
                const diff = Math.max(0, Math.floor((officialTarget - now) / 1000));
                const hours = Math.floor(diff / 3600);
                const mins = Math.floor((diff % 3600) / 60);
                const secs = diff % 60;
                let formatted = "";
                if (hours > 0) {{
                    formatted = String(hours).padStart(2, '0') + ":" + String(mins).padStart(2, '0') + ":" + String(secs).padStart(2, '0');
                }} else {{
                    formatted = String(mins).padStart(2, '0') + ":" + String(secs).padStart(2, '0');
                }}

                if (diff > 300) {{
                    el.innerText = "⏳ Time Remaining: " + formatted;
                    el.style.color = "#1E88E5";
                    el.style.background = "rgba(30, 136, 229, 0.12)";
                    el.style.borderColor = "#1E88E5";
                }} else if (diff > 60) {{
                    el.innerText = "⚠️ Time Remaining: " + formatted;
                    el.style.color = "#FB8C00";
                    el.style.background = "rgba(251, 140, 0, 0.12)";
                    el.style.borderColor = "#FB8C00";
                }} else {{
                    el.innerText = "🚨 Final Minute: " + formatted;
                    el.style.color = "#E53935";
                    el.style.background = "rgba(229, 57, 53, 0.12)";
                    el.style.borderColor = "#E53935";
                }}
            }} else if (now <= graceTarget) {{
                const graceDiff = Math.max(0, Math.floor((graceTarget - now) / 1000));
                el.innerText = "⏰ Grace Window: " + graceDiff + "s remaining";
                el.style.color = "#D32F2F";
                el.style.background = "rgba(211, 47, 47, 0.12)";
                el.style.borderColor = "#D32F2F";
            }} else {{
                el.innerText = "⛔ Time Expired! Submitting...";
                el.style.color = "#D32F2F";
                el.style.background = "rgba(211, 47, 47, 0.12)";
                el.style.borderColor = "#D32F2F";
                clearInterval(timerInterval);
                setTimeout(function() {{
                    try {{
                        window.parent.location.reload();
                    }} catch(e) {{}}
                }}, 1000);
            }}
        }}
        tick();
        const timerInterval = setInterval(tick, 1000);
    </script>
    </body>
    </html>
    """
    components.html(timer_html, height=45)


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

    # Authoritative backend server-side timing validation
    started_at = attempt["started_at"]
    duration_minutes = exam.get("duration_minutes", 0)
    official_deadline = started_at + timedelta(minutes=duration_minutes)
    grace_deadline = official_deadline + timedelta(seconds=60)
    now = datetime.now()

    # Hard cutoff: only past the 60-second grace window
    if now > grace_deadline:
        auto_submit_key = f"auto_submit_handled_{attempt_id}"
        if not st.session_state.get(auto_submit_key, False):
            st.session_state[auto_submit_key] = True
            try:
                submit_attempt(attempt_id, student_id)
                evaluate_attempt(attempt_id, student_id)
            except Exception:
                pass
        st.session_state["student_flash_msg"] = (
            "Your examination time has expired. Your attempt has been automatically submitted and evaluated."
        )
        st.session_state["active_attempt_id"] = None
        st.session_state["view_result_attempt_id"] = attempt_id
        st.session_state["student_view"] = "result"
        st.rerun()
        return

    remaining_seconds = int((official_deadline - now).total_seconds())
    grace_remaining_seconds = max(0, int((grace_deadline - now).total_seconds()))
    in_grace_window = (now > official_deadline) and (now <= grace_deadline)

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

    # Visual urgency and grace window alerts
    if in_grace_window:
        st.error(
            f"⏰ Official examination time has concluded. You are in the 60-second grace window "
            f"({grace_remaining_seconds}s remaining) for in-flight answer saving. "
            "Your attempt will be automatically submitted when grace concludes."
        )
    elif 0 < remaining_seconds <= 60:
        st.error("🚨 Final Minute! Less than 60 seconds remaining. Your attempt will be automatically submitted when time expires.")
    elif 0 < remaining_seconds <= 300:
        st.warning("⚠️ Attention: Less than 5 minutes remaining. Please review your answers.")

    col_qnum, col_marks, col_timer = st.columns([2, 1, 2])
    with col_qnum:
        st.markdown(f"#### Question {current_idx + 1} of {len(questions)}")
    with col_marks:
        marks = current_q.get("marks", 1)
        mark_label = "Mark" if marks == 1 else "Marks"
        st.markdown(
            f"<div style='text-align: center; font-weight: bold; padding-top: 8px;'>"
            f"Points: {marks} {mark_label}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_timer:
        _render_countdown_timer(
            official_deadline,
            grace_deadline,
            remaining_seconds,
            grace_remaining_seconds,
        )

    if in_grace_window:
        if st.button("Finalize & Submit Exam Now", key=f"grace_submit_{attempt_id}", type="primary", use_container_width=True):
            try:
                submit_attempt(attempt_id, student_id)
                evaluate_attempt(attempt_id, student_id)
            except Exception:
                pass
            st.session_state["student_flash_msg"] = (
                "Examination finalized, submitted, and evaluated successfully."
            )
            st.session_state["active_attempt_id"] = None
            st.session_state["view_result_attempt_id"] = attempt_id
            st.session_state["student_view"] = "result"
            st.rerun()

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
                "Review & Submit Exam →",
                key=f"review_final_btn_{attempt_id}_{qid}",
                type="primary",
                on_click=_on_go_to_review,
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
    col_rev_main, col_exit = st.columns([2, 1])
    with col_rev_main:
        st.button(
            "🏁 Review & Submit Examination",
            key=f"palette_review_btn_{attempt_id}",
            type="primary",
            on_click=_on_go_to_review,
            args=(attempt_id, student_id, qid, widget_key, cache_key),
            use_container_width=True,
            help="Review all answered and unanswered questions before confirming submission.",
        )
    with col_exit:
        if st.button("Exit to Catalog", key=f"exit_active_{attempt_id}", use_container_width=True):
            st.session_state["student_view"] = "catalog"
            st.rerun()


def render_exam_review(student_id: int, attempt_id: Optional[int]) -> None:
    """
    Render the pre-submission review and confirmation interface.
    Displays summary statistics (total, answered, unanswered), question-by-question
    answer states with navigation jump links, irreversible submission warning,
    and enforces authoritative backend server-side timing and grace periods.

    Args:
        student_id: User ID of the authenticated student.
        attempt_id: Active attempt ID from session state.
    """
    if not attempt_id:
        st.warning("No active examination session found. Returning to catalog.")
        if st.button("Return to Catalog", key="no_active_attempt_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    try:
        attempt = get_attempt(attempt_id, student_id)
    except ValueError as e:
        st.error(f"Examination attempt error: {str(e)}")
        if st.button("Return to Catalog", key="val_err_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return
    except PermissionError as e:
        st.error(f"Unauthorized Access: {str(e)}")
        if st.button("Return to Catalog", key="perm_err_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return
    except Exception as e:
        st.error(f"Failed to load examination attempt: {str(e)}")
        if st.button("Return to Catalog", key="gen_err_review_btn"):
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
        if st.button("Return to Catalog", key="invalid_status_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    exam_id = attempt["exam_id"]
    try:
        exam = get_exam(exam_id)
    except Exception as e:
        st.error(f"Failed to load examination details: {str(e)}")
        if st.button("Return to Catalog", key="exam_load_err_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    if not exam:
        st.error(f"Associated examination with ID {exam_id} could not be found.")
        if st.button("Return to Catalog", key="missing_exam_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    # Authoritative backend server-side timing validation
    started_at = attempt["started_at"]
    duration_minutes = exam.get("duration_minutes", 0)
    official_deadline = started_at + timedelta(minutes=duration_minutes)
    grace_deadline = official_deadline + timedelta(seconds=60)
    now = datetime.now()

    # Hard cutoff: only past the 60-second grace window
    if now > grace_deadline:
        auto_submit_key = f"auto_submit_handled_{attempt_id}"
        if not st.session_state.get(auto_submit_key, False):
            st.session_state[auto_submit_key] = True
            try:
                submit_attempt(attempt_id, student_id)
                evaluate_attempt(attempt_id, student_id)
            except Exception:
                pass
        st.session_state["student_flash_msg"] = (
            "Your examination time expired while reviewing. Your attempt has been automatically submitted and evaluated."
        )
        st.session_state["active_attempt_id"] = None
        st.session_state["view_result_attempt_id"] = attempt_id
        st.session_state["student_view"] = "result"
        st.rerun()
        return

    remaining_seconds = int((official_deadline - now).total_seconds())
    grace_remaining_seconds = max(0, int((grace_deadline - now).total_seconds()))
    in_grace_window = (now > official_deadline) and (now <= grace_deadline)

    try:
        questions = get_attempt_questions(attempt_id, student_id)
    except Exception as e:
        st.error(f"Failed to retrieve questions for attempt: {str(e)}")
        if st.button("Return to Catalog", key="q_err_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["active_attempt_id"] = None
            st.rerun()
        return

    if not questions:
        st.warning("This examination currently contains no questions. Please contact your instructor.")
        if st.button("Return to Catalog", key="empty_questions_review_btn"):
            st.session_state["student_view"] = "catalog"
            st.rerun()
        return

    try:
        answers = get_attempt_answers(attempt_id, student_id)
    except Exception:
        answers = {}

    cache_key = f"attempt_answers_{attempt_id}"
    st.session_state[cache_key] = answers

    total_q = len(questions)
    answered_q = sum(1 for q in questions if answers.get(q["question_id"]) is not None)
    unanswered_q = total_q - answered_q

    # Review Screen Context Header
    col_title, col_badge = st.columns([3, 1])
    with col_title:
        st.subheader("🏁 Examination Submission Review")
        st.markdown(f"**{exam.get('title', 'Examination')}**")
        if exam.get("description"):
            st.caption(exam["description"])
    with col_badge:
        st.markdown(
            f"<div style='text-align: right; margin-top: 8px; font-weight: bold; color: #FB8C00;'>"
            f"ATTEMPT #{attempt_id} (REVIEW)"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Visual urgency and grace window alerts
    if in_grace_window:
        st.error(
            f"⏰ Official examination time has concluded. You are in the 60-second grace window "
            f"({grace_remaining_seconds}s remaining). Submit your examination immediately before the hard cutoff."
        )
    elif 0 < remaining_seconds <= 60:
        st.error("🚨 Final Minute! Less than 60 seconds remaining. Your attempt will be automatically submitted when time expires.")
    elif 0 < remaining_seconds <= 300:
        st.warning("⚠️ Attention: Less than 5 minutes remaining. Please finalize your submission.")

    col_info, col_timer = st.columns([3, 2])
    with col_info:
        st.caption("Review your answered and unanswered questions before confirming your final submission.")
    with col_timer:
        _render_countdown_timer(
            official_deadline,
            grace_deadline,
            remaining_seconds,
            grace_remaining_seconds,
        )

    # Irreversible Warning Notice
    st.warning(
        "⚠️ **Final Submission Warning**: Submitting your examination is permanent and irreversible. "
        "Once submitted, you cannot change any answers or resume this attempt. "
        "Please review your answers carefully before confirming."
    )

    # Metrics Summary Cards
    col_tot, col_ans, col_unans = st.columns(3)
    col_tot.metric("Total Questions", total_q)
    col_ans.metric("Answered Questions", f"{answered_q} / {total_q}")
    col_unans.metric("Unanswered Questions", unanswered_q)

    # Completion State Callouts
    if unanswered_q == 0:
        st.success(f"✅ All {total_q} questions have been answered. You are ready to finalize and submit your examination.")
    elif answered_q > 0:
        st.warning(f"⚠️ You have {unanswered_q} unanswered question(s) out of {total_q}. Any unanswered questions will receive 0 marks.")
    else:
        st.error(f"🚨 Critical Alert: You have NOT answered any questions (0 / {total_q}). Submitting now will finalize your attempt with an obtained score of 0.0 marks.")

    st.divider()
    st.markdown("### Question Breakdown")

    # Question Breakdown List
    for idx, q in enumerate(questions):
        q_id = q["question_id"]
        saved_option = answers.get(q_id)
        is_ans = (saved_option is not None)

        with st.container(border=True):
            col_qnum, col_qtxt, col_status, col_btn = st.columns([1, 4, 2, 2])
            with col_qnum:
                st.markdown(f"**Question {idx + 1}**")
                marks = q.get("marks", 1)
                st.caption(f"{marks} Mark{'s' if marks != 1 else ''}")
            with col_qtxt:
                q_text = q.get("question_text", "")
                if len(q_text) > 75:
                    q_text = q_text[:72] + "..."
                st.markdown(q_text)
            with col_status:
                if is_ans:
                    st.markdown(
                        f"<div style='color: #2E7D32; font-weight: bold; padding-top: 6px;'>"
                        f"✓ Option {saved_option}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='color: #D32F2F; font-weight: bold; padding-top: 6px;'>"
                        "⚠️ Unanswered"
                        "</div>",
                        unsafe_allow_html=True,
                    )
            with col_btn:
                btn_txt = f"Edit Q{idx + 1}" if is_ans else f"Answer Q{idx + 1}"
                if st.button(btn_txt, key=f"rev_jump_{attempt_id}_{q_id}", use_container_width=True):
                    st.session_state[f"q_index_{attempt_id}"] = idx
                    st.session_state["student_view"] = "active_exam"
                    st.rerun()

    st.divider()

    # Zero-answered confirmation guard
    submit_disabled = False
    if answered_q == 0:
        ack_key = f"ack_empty_submit_{attempt_id}"
        ack = st.checkbox(
            "I acknowledge that I am submitting an empty examination with 0 answers and will receive 0 marks.",
            key=ack_key,
        )
        if not ack:
            submit_disabled = True

    # Action Buttons Row
    col_ret, col_sub = st.columns([1, 2])
    with col_ret:
        if st.button("← Return to Exam", key=f"rev_return_btn_{attempt_id}", use_container_width=True):
            st.session_state["student_view"] = "active_exam"
            st.rerun()

    with col_sub:
        submit_btn_label = "Finalize & Submit Exam Now" if in_grace_window else "Confirm & Submit Examination"
        if st.button(
            submit_btn_label,
            key=f"rev_submit_btn_{attempt_id}",
            type="primary",
            disabled=submit_disabled,
            use_container_width=True,
        ):
            try:
                submit_attempt(attempt_id, student_id)
            except ValueError as e:
                st.error(f"Submission failed: {str(e)}")
                try:
                    att_check = get_attempt(attempt_id, student_id)
                    if att_check.get("status") in {"SUBMITTED", "EVALUATED"}:
                        st.session_state["active_attempt_id"] = None
                        st.session_state["view_result_attempt_id"] = attempt_id
                        st.session_state["student_view"] = "result"
                        st.rerun()
                        return
                except Exception:
                    pass
                return
            except Exception as e:
                st.error(f"An unexpected error occurred during submission: {str(e)}")
                return

            eval_success = True
            try:
                evaluate_attempt(attempt_id, student_id)
            except Exception:
                eval_success = False

            # Cleanup session state
            st.session_state.pop(f"attempt_answers_{attempt_id}", None)
            st.session_state.pop(f"q_index_{attempt_id}", None)
            st.session_state.pop(f"auto_submit_handled_{attempt_id}", None)
            st.session_state.pop(f"ack_empty_submit_{attempt_id}", None)
            st.session_state["active_attempt_id"] = None
            st.session_state["view_result_attempt_id"] = attempt_id
            st.session_state["student_view"] = "result"
            if eval_success:
                st.session_state["student_flash_msg"] = (
                    "🎉 Examination submitted and evaluated successfully!"
                )
            else:
                st.session_state["student_flash_msg"] = (
                    "Examination submitted successfully. Results evaluation is pending."
                )
            st.rerun()


def render_result_view(student_id: int, attempt_id: Optional[int]) -> None:
    """
    Render the comprehensive examination result scorecard interface for an evaluated attempt.
    Displays exam metadata, overall marks, percentage, aggregate answer counts,
    and question-by-question breakdown while strictly keeping the authoritative
    answer key concealed.

    Args:
        student_id: User ID of the authenticated student.
        attempt_id: Unique attempt identifier from session state.
    """
    if not attempt_id:
        st.warning("No examination attempt selected for result display.")
        if st.button("Return to Catalog", key="no_result_attempt_btn", type="primary"):
            st.session_state["student_view"] = "catalog"
            st.session_state["view_result_attempt_id"] = None
            st.rerun()
        return

    # Retrieve scorecard details directly (read-only query)
    scorecard = None
    try:
        scorecard = get_attempt_scorecard_details(attempt_id, student_id)
    except ValueError as e:
        st.error(f"Examination scorecard is currently unavailable: {str(e)}")
        if st.button("Return to Catalog", key="scorecard_val_err_btn", type="primary"):
            st.session_state["student_view"] = "catalog"
            st.session_state["view_result_attempt_id"] = None
            st.rerun()
        return
    except PermissionError as e:
        st.error(f"Access Denied: {str(e)}")
        if st.button("Return to Catalog", key="scorecard_perm_err_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["view_result_attempt_id"] = None
            st.rerun()
        return
    except Exception as e:
        st.error(f"Unexpected error loading examination scorecard: {str(e)}")
        if st.button("Return to Catalog", key="scorecard_gen_err_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["view_result_attempt_id"] = None
            st.rerun()
        return

    if not scorecard:
        st.error("Examination scorecard could not be retrieved.")
        if st.button("Return to Catalog", key="scorecard_empty_btn"):
            st.session_state["student_view"] = "catalog"
            st.session_state["view_result_attempt_id"] = None
            st.rerun()
        return

    # 1. Header & Title Block
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.subheader("Examination Scorecard")
        st.markdown(f"### {scorecard['exam_title']}")
    with col_status:
        st.markdown(
            f"<div style='text-align: right; padding-top: 10px; font-weight: bold; color: #2E7D32;'>"
            f"STATUS: {scorecard['status']}"
            f"</div>",
            unsafe_allow_html=True
        )

    st.success(
        f"Attempt #{scorecard['attempt_id']} has been evaluated!\n\n"
        f"**Score:** {scorecard['obtained_marks']} / {scorecard['total_marks']} ({scorecard['percentage']}%)"
    )

    # 2. Metadata Information Container
    time_taken_sec = scorecard.get("time_taken_seconds", 0)
    minutes = time_taken_sec // 60
    seconds = time_taken_sec % 60
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    started_str = scorecard["started_at"].strftime("%Y-%m-%d %H:%M:%S") if scorecard.get("started_at") else "N/A"
    submitted_str = scorecard["submitted_at"].strftime("%Y-%m-%d %H:%M:%S") if scorecard.get("submitted_at") else "N/A"
    evaluated_str = scorecard["evaluated_at"].strftime("%Y-%m-%d %H:%M:%S") if scorecard.get("evaluated_at") else "N/A"

    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.caption(f"**Attempt ID**: #{scorecard['attempt_id']}")
        m1.caption(f"**Exam Duration**: {scorecard['duration_minutes']} mins")
        m2.caption(f"**Started**: {started_str}")
        m2.caption(f"**Submitted**: {submitted_str}")
        m3.caption(f"**Time Taken**: {time_str}")
        m3.caption(f"**Evaluated**: {evaluated_str}")
        m4.caption(f"**Total Questions**: {scorecard['total_questions']}")
        m4.caption(f"**Evaluation**: Automated")

    # 3. Overall Result Metric Cards
    total_m = scorecard["total_marks"]
    obtained_m = scorecard["obtained_marks"]
    percentage = scorecard["percentage"]
    answered_count = scorecard["correct_count"] + scorecard["incorrect_count"]
    total_q = scorecard["total_questions"]

    st.markdown("#### Performance Overview")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Obtained Score", f"{obtained_m:.1f} / {total_m:.1f}")
    kpi2.metric("Percentage", f"{percentage:.2f}%")
    kpi3.metric("Completion Rate", f"{answered_count} / {total_q}")

    # 4. Performance Summary Badges / Answer Counters
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div style='background-color: #E8F5E9; border-left: 5px solid #2E7D32; padding: 12px; border-radius: 4px;'>"
            f"<div style='font-size: 13px; color: #1B5E20; font-weight: bold;'>✓ Correct Answers</div>"
            f"<div style='font-size: 22px; font-weight: bold; color: #2E7D32;'>{scorecard['correct_count']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"<div style='background-color: #FFEBEE; border-left: 5px solid #D32F2F; padding: 12px; border-radius: 4px;'>"
            f"<div style='font-size: 13px; color: #B71C1C; font-weight: bold;'>✗ Incorrect Answers</div>"
            f"<div style='font-size: 22px; font-weight: bold; color: #D32F2F;'>{scorecard['incorrect_count']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"<div style='background-color: #FFF3E0; border-left: 5px solid #ED6C02; padding: 12px; border-radius: 4px;'>"
            f"<div style='font-size: 13px; color: #E65100; font-weight: bold;'>⚠️ Unanswered Questions</div>"
            f"<div style='font-size: 22px; font-weight: bold; color: #ED6C02;'>{scorecard['unanswered_count']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.divider()

    # 5. Question-Wise Breakdown
    st.markdown("#### Question-Wise Breakdown")
    st.caption("Review your responses and awarded marks. Authoritative answer keys are concealed to protect examination integrity.")

    questions = scorecard.get("questions_breakdown", [])
    for idx, q in enumerate(questions):
        status = q.get("status", "UNANSWERED")
        q_marks = q.get("marks", 1.0)
        awarded = q.get("marks_awarded", 0.0)
        selected = q.get("selected_option")

        if status == "CORRECT":
            status_color = "#2E7D32"
            status_bg = "#E8F5E9"
            badge_icon = "✓"
            badge_label = "Correct"
        elif status == "INCORRECT":
            status_color = "#D32F2F"
            status_bg = "#FFEBEE"
            badge_icon = "✗"
            badge_label = "Incorrect"
        else:
            status_color = "#ED6C02"
            status_bg = "#FFF3E0"
            badge_icon = "⚠️"
            badge_label = "Unanswered"

        with st.container(border=True):
            col_qhead, col_qscore = st.columns([3, 1])
            with col_qhead:
                st.markdown(
                    f"**Question {idx + 1}** &nbsp; "
                    f"<span style='background-color: {status_bg}; color: {status_color}; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-size: 12px;'>"
                    f"{badge_icon} {badge_label}"
                    f"</span>",
                    unsafe_allow_html=True
                )
            with col_qscore:
                st.markdown(
                    f"<div style='text-align: right; font-weight: bold; color: {status_color};'>"
                    f"{awarded:.1f} / {q_marks:.1f} Marks"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.markdown(f"**{q.get('question_text', '')}**")

            # Selected option display
            if selected:
                opt_key = f"option_{selected.lower()}"
                opt_content = q.get(opt_key, "")
                st.markdown(
                    f"**Your Answer:** &nbsp; "
                    f"<span style='color: {status_color}; font-weight: bold;'>"
                    f"Option {selected}: {opt_content}"
                    f"</span>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "**Your Answer:** &nbsp; "
                    "<span style='color: #ED6C02; font-style: italic;'>"
                    "None (Question Skipped)"
                    "</span>",
                    unsafe_allow_html=True
                )

    st.divider()

    # 6. Navigation Control: Return to Catalog
    if st.button("← Return to Examination Catalog", key="return_to_catalog_from_scorecard", type="primary", use_container_width=True):
        st.session_state["student_view"] = "catalog"
        st.session_state["view_result_attempt_id"] = None
        st.rerun()


def render_student_ui() -> None:
    """
    Main entrypoint for the Student Exam Portal presentation layer.
    Enforces student role requirement and manages view routing across catalog,
    instructions, active exam, review exam, and result displays.
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

    elif view == "review_exam":
        active_attempt_id = st.session_state.get("active_attempt_id")
        render_exam_review(user["id"], active_attempt_id)

    elif view == "result":
        attempt_id = st.session_state.get("view_result_attempt_id")
        render_result_view(user["id"], attempt_id)

    else:
        st.session_state["student_view"] = "catalog"
        render_exam_catalog(user["id"])
