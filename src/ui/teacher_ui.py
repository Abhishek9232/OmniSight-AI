"""
OmniSight-AI Teacher Exam Studio UI Module.
Provides the Streamlit interface for teachers and administrators to manage examinations.
"""
from typing import Optional, Dict, Any, List
import streamlit as st
from src.auth.session import get_current_user, require_role, logout
from src.exam.service import (
    get_teacher_exams,
    create_exam,
    update_exam,
    get_exam_questions,
    add_question,
    update_question,
    delete_question,
    publish_exam,
    close_exam,
)


def render_teacher_header(user: Dict[str, Any]) -> None:
    """
    Render top header showing title, teacher identity, and role badge.

    Args:
        user: Authenticated user dictionary from session.
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("Teacher Exam Studio")
        st.caption("Manage examinations, author questions, and administer assessment lifecycles.")

    with col2:
        st.markdown(f"**{user.get('name', 'User')}**")
        role_label = user.get("role", "teacher").upper()
        st.badge(f"Role: {role_label}") if hasattr(st, "badge") else st.caption(f"Role: **{role_label}**")
        if st.button("Log Out", key="teacher_logout_btn"):
            logout()
            st.rerun()

    st.divider()


def render_exam_list(teacher_id: int) -> None:
    """
    Render list of examinations owned by the authenticated teacher.

    Args:
        teacher_id: User ID of the teacher.
    """
    if "exam_created_success" in st.session_state:
        st.success(st.session_state.pop("exam_created_success"))
    if "exam_updated_success" in st.session_state:
        st.success(st.session_state.pop("exam_updated_success"))
    if "exam_lifecycle_success" in st.session_state:
        st.success(st.session_state.pop("exam_lifecycle_success"))

    st.subheader("Your Examinations")

    try:
        exams: List[Dict[str, Any]] = get_teacher_exams(teacher_id)
    except Exception as e:
        st.error(f"Failed to load examinations: {str(e)}")
        return

    if not exams:
        st.info("No examinations created yet. Use the 'Create Exam' section to author your first assessment.")
        return

    # Display count summary
    st.caption(f"Total examinations: **{len(exams)}**")

    # Render each exam in a clean card container
    for exam in exams:
        status = exam.get("status", "DRAFT")
        status_color = {
            "DRAFT": "orange",
            "PUBLISHED": "green",
            "CLOSED": "gray"
        }.get(status, "blue")

        with st.container(border=True):
            col_info, col_status = st.columns([3, 1])

            with col_info:
                st.markdown(f"### {exam.get('title', 'Untitled Exam')}")
                if exam.get("description"):
                    st.write(exam["description"])
                st.caption(
                    f"**Exam ID**: {exam.get('exam_id')} | "
                    f"**Duration**: {exam.get('duration_minutes', 0)} mins | "
                    f"**Created**: {exam.get('created_at', 'N/A')}"
                )

            with col_status:
                st.markdown(
                    f"<div style='text-align: right; font-weight: bold; color: {status_color};'>"
                    f"STATUS: {status}"
                    f"</div>",
                    unsafe_allow_html=True
                )


def render_create_exam_form(teacher_id: int) -> None:
    """
    Render form for creating a new examination and invoke create_exam service.

    Args:
        teacher_id: User ID of the authenticated teacher/admin.
    """
    st.markdown("### Create New Examination")
    st.caption("Draft a new examination by providing a title, optional instructions, and allowed duration.")

    with st.form("create_exam_form", clear_on_submit=True):
        title = st.text_input(
            "Exam Title",
            placeholder="e.g. CS101 - Introduction to Computer Science",
            max_chars=200,
            help="Required. Up to 200 characters.",
        )
        description = st.text_area(
            "Description / Instructions (Optional)",
            placeholder="e.g. Midterm assessment covering Modules 1 through 3. All questions are mandatory.",
            help="Optional guidelines or syllabus details for examinees.",
        )
        duration_minutes = st.number_input(
            "Duration (in minutes)",
            min_value=1,
            max_value=1440,
            value=60,
            step=5,
            help="Positive integer indicating total exam duration.",
        )
        submitted = st.form_submit_button("Create Examination", use_container_width=True)

    if submitted:
        clean_title = title.strip() if title else ""
        if not clean_title:
            st.error("Exam title is required and cannot be empty.")
            return

        if len(clean_title) > 200:
            st.error("Exam title cannot exceed 200 characters.")
            return

        try:
            dur_int = int(duration_minutes)
        except (ValueError, TypeError):
            st.error("Duration must be a valid integer.")
            return

        if dur_int <= 0:
            st.error("Duration must be a positive integer greater than zero.")
            return

        clean_desc = description.strip() if description and description.strip() else None

        try:
            created_exam = create_exam(
                title=clean_title,
                description=clean_desc,
                duration_minutes=dur_int,
                created_by=teacher_id,
            )
            st.session_state["exam_created_success"] = (
                f"Examination '{created_exam.get('title')}' (ID: {created_exam.get('exam_id')}) "
                f"successfully created in DRAFT status."
            )
            st.rerun()
        except ValueError as e:
            st.error(f"Validation Error: {str(e)}")
        except PermissionError as e:
            st.error(f"Permission Denied: {str(e)}")
        except Exception as e:
            st.error(f"Failed to create examination: {str(e)}")


def render_manage_exams_section(teacher_id: int) -> None:
    """
    Render form and controls for editing existing examinations.

    Args:
        teacher_id: User ID of the authenticated teacher/admin.
    """
    st.markdown("### Manage Examination Metadata")
    st.caption("Select an existing examination to update its title, description, or duration.")

    try:
        exams: List[Dict[str, Any]] = get_teacher_exams(teacher_id)
    except Exception as e:
        st.error(f"Failed to load examinations: {str(e)}")
        return

    if not exams:
        st.info("No examinations available to manage. Use the 'Create Exam' tab to create your first examination.")
        return

    exam_map = {exam["exam_id"]: exam for exam in exams}
    exam_ids = [exam["exam_id"] for exam in exams]

    selected_exam_id = st.selectbox(
        "Select Examination to Edit",
        options=exam_ids,
        format_func=lambda eid: f"ID {eid} — {exam_map[eid].get('title', 'Untitled')} [{exam_map[eid].get('status', 'DRAFT')}]",
        key="manage_exam_selector",
    )

    selected_exam = exam_map.get(selected_exam_id)
    if not selected_exam:
        st.warning("Selected examination could not be loaded.")
        return

    status = selected_exam.get("status", "DRAFT")
    st.markdown(f"**Current Status**: `{status}`")

    with st.form(f"edit_exam_form_{selected_exam_id}"):
        title = st.text_input(
            "Exam Title",
            value=selected_exam.get("title") or "",
            max_chars=200,
            help="Required. Up to 200 characters.",
            key=f"edit_title_{selected_exam_id}",
        )
        description = st.text_area(
            "Description / Instructions",
            value=selected_exam.get("description") or "",
            help="Optional guidelines or syllabus details for examinees.",
            key=f"edit_desc_{selected_exam_id}",
        )
        current_duration = selected_exam.get("duration_minutes") or 60
        duration_minutes = st.number_input(
            "Duration (in minutes)",
            min_value=1,
            max_value=1440,
            value=int(current_duration),
            step=5,
            help="Positive integer indicating total exam duration.",
            key=f"edit_duration_{selected_exam_id}",
        )
        submitted = st.form_submit_button("Save Changes", use_container_width=True)

    if submitted:
        clean_title = title.strip() if title else ""
        if not clean_title:
            st.error("Exam title is required and cannot be empty.")
            return

        if len(clean_title) > 200:
            st.error("Exam title cannot exceed 200 characters.")
            return

        try:
            dur_int = int(duration_minutes)
        except (ValueError, TypeError):
            st.error("Duration must be a valid integer.")
            return

        if dur_int <= 0:
            st.error("Duration must be a positive integer greater than zero.")
            return

        clean_desc = description.strip() if description and description.strip() else None

        try:
            updated_exam = update_exam(
                exam_id=selected_exam_id,
                teacher_id=teacher_id,
                title=clean_title,
                description=clean_desc,
                duration_minutes=dur_int,
            )
            success_msg = (
                f"Examination '{updated_exam.get('title')}' (ID: {updated_exam.get('exam_id')}) "
                f"updated successfully."
            )
            st.session_state["exam_updated_success"] = success_msg
            st.success(success_msg)
            st.rerun()
        except ValueError as e:
            st.error(f"Error: {str(e)}")
        except PermissionError as e:
            st.error(f"Permission Denied: {str(e)}")
        except Exception as e:
            st.error(f"Failed to update examination: {str(e)}")


def render_manage_questions_section(teacher_id: int) -> None:
    """
    Render question roster, authoring form, edit forms, and delete actions
    for examinations owned by the authenticated teacher/admin.

    Args:
        teacher_id: User ID of the authenticated teacher/admin.
    """
    st.markdown("### Manage Examination Questions")
    st.caption("View, author, modify, or remove multiple-choice questions for your examinations.")

    try:
        exams: List[Dict[str, Any]] = get_teacher_exams(teacher_id)
    except Exception as e:
        st.error(f"Failed to load examinations: {str(e)}")
        return

    if not exams:
        st.info("No examinations available. Please create an examination first before adding questions.")
        return

    exam_map = {exam["exam_id"]: exam for exam in exams}
    exam_ids = [exam["exam_id"] for exam in exams]

    selected_exam_id = st.selectbox(
        "Select Examination",
        options=exam_ids,
        format_func=lambda eid: f"ID {eid} — {exam_map[eid].get('title', 'Untitled')} [{exam_map[eid].get('status', 'DRAFT')}]",
        key="manage_questions_exam_selector",
    )

    selected_exam = exam_map.get(selected_exam_id)
    if not selected_exam:
        st.warning("Selected examination could not be loaded.")
        return

    status = selected_exam.get("status", "DRAFT")
    st.markdown(f"**Exam Status**: `{status}`")

    # Display feedback message if available
    if "question_action_success" in st.session_state:
        st.success(st.session_state.pop("question_action_success"))

    # Fetch existing questions for selected exam
    try:
        questions: List[Dict[str, Any]] = get_exam_questions(selected_exam_id, teacher_id)
    except ValueError as e:
        st.error(f"Error loading questions: {str(e)}")
        return
    except PermissionError as e:
        st.error(f"Permission Denied: {str(e)}")
        return
    except Exception as e:
        st.error(f"Failed to retrieve questions: {str(e)}")
        return

    total_marks = sum(q.get("marks", 0) for q in questions) if questions else 0
    st.markdown(f"**Questions in this exam**: {len(questions)} | **Total Marks**: {total_marks}")

    # Roster of existing questions
    if questions:
        st.markdown("#### Existing Questions")
        for idx, q in enumerate(questions, 1):
            q_id = q["question_id"]
            with st.container(border=True):
                col_header, col_meta = st.columns([3, 1])
                with col_header:
                    st.markdown(f"**Question {idx}**")
                with col_meta:
                    st.markdown(
                        f"<div style='text-align: right;'><strong>Marks: {q.get('marks', 1)}</strong></div>",
                        unsafe_allow_html=True,
                    )

                st.write(q.get("question_text", ""))

                col1, col2 = st.columns(2)
                with col1:
                    is_correct_a = " [Correct]" if q.get("correct_option") == "A" else ""
                    is_correct_c = " [Correct]" if q.get("correct_option") == "C" else ""
                    st.markdown(f"- **A**: {q.get('option_a')}{is_correct_a}")
                    st.markdown(f"- **C**: {q.get('option_c')}{is_correct_c}")
                with col2:
                    is_correct_b = " [Correct]" if q.get("correct_option") == "B" else ""
                    is_correct_d = " [Correct]" if q.get("correct_option") == "D" else ""
                    st.markdown(f"- **B**: {q.get('option_b')}{is_correct_b}")
                    st.markdown(f"- **D**: {q.get('option_d')}{is_correct_d}")

                # Edit expander
                with st.expander(f"Edit Question {idx}"):
                    with st.form(f"edit_question_form_{q_id}"):
                        edit_text = st.text_area(
                            "Question Text",
                            value=q.get("question_text", ""),
                            key=f"q_text_{q_id}",
                        )
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_a = st.text_input(
                                "Option A",
                                value=q.get("option_a", ""),
                                max_chars=500,
                                key=f"q_opt_a_{q_id}",
                            )
                            edit_c = st.text_input(
                                "Option C",
                                value=q.get("option_c", ""),
                                max_chars=500,
                                key=f"q_opt_c_{q_id}",
                            )
                        with col_e2:
                            edit_b = st.text_input(
                                "Option B",
                                value=q.get("option_b", ""),
                                max_chars=500,
                                key=f"q_opt_b_{q_id}",
                            )
                            edit_d = st.text_input(
                                "Option D",
                                value=q.get("option_d", ""),
                                max_chars=500,
                                key=f"q_opt_d_{q_id}",
                            )

                        col_ecorr, col_emarks = st.columns(2)
                        opt_list = ["A", "B", "C", "D"]
                        current_opt = q.get("correct_option", "A").upper()
                        opt_idx = opt_list.index(current_opt) if current_opt in opt_list else 0
                        with col_ecorr:
                            edit_correct = st.selectbox(
                                "Correct Option",
                                options=opt_list,
                                index=opt_idx,
                                key=f"q_corr_{q_id}",
                            )
                        with col_emarks:
                            edit_marks = st.number_input(
                                "Marks",
                                min_value=1,
                                max_value=100,
                                value=int(q.get("marks", 1)),
                                step=1,
                                key=f"q_marks_{q_id}",
                            )

                        submitted_edit = st.form_submit_button("Save Question Changes", use_container_width=True)

                    if submitted_edit:
                        clean_text = edit_text.strip() if edit_text else ""
                        clean_a = edit_a.strip() if edit_a else ""
                        clean_b = edit_b.strip() if edit_b else ""
                        clean_c = edit_c.strip() if edit_c else ""
                        clean_d = edit_d.strip() if edit_d else ""

                        if not clean_text:
                            st.error("Question text cannot be empty.")
                        elif not clean_a or not clean_b or not clean_c or not clean_d:
                            st.error("All four options (A, B, C, D) are required and cannot be empty.")
                        elif len(clean_a) > 500 or len(clean_b) > 500 or len(clean_c) > 500 or len(clean_d) > 500:
                            st.error("Options cannot exceed 500 characters.")
                        elif edit_correct not in {"A", "B", "C", "D"}:
                            st.error("Correct option must be one of 'A', 'B', 'C', or 'D'.")
                        elif int(edit_marks) <= 0:
                            st.error("Marks must be a positive integer.")
                        else:
                            try:
                                update_question(
                                    question_id=q_id,
                                    teacher_id=teacher_id,
                                    question_text=clean_text,
                                    option_a=clean_a,
                                    option_b=clean_b,
                                    option_c=clean_c,
                                    option_d=clean_d,
                                    correct_option=edit_correct,
                                    marks=int(edit_marks),
                                )
                                st.session_state["question_action_success"] = f"Question {idx} updated successfully."
                                st.rerun()
                            except ValueError as e:
                                st.error(f"Error: {str(e)}")
                            except PermissionError as e:
                                st.error(f"Permission Denied: {str(e)}")
                            except Exception as e:
                                st.error(f"Failed to update question: {str(e)}")

                # Delete action with confirmation
                with st.expander(f"Delete Question {idx}"):
                    st.warning(f"Are you sure you want to remove Question {idx}?")
                    confirm_del = st.checkbox(
                        "I confirm I want to permanently delete this question.",
                        key=f"confirm_del_{q_id}",
                    )
                    if st.button("Delete Question", key=f"del_btn_{q_id}", type="primary"):
                        if not confirm_del:
                            st.warning("Please check the confirmation box before deleting.")
                        else:
                            try:
                                delete_question(q_id, teacher_id)
                                st.session_state["question_action_success"] = f"Question {idx} deleted successfully."
                                st.rerun()
                            except ValueError as e:
                                st.error(f"Error: {str(e)}")
                            except PermissionError as e:
                                st.error(f"Permission Denied: {str(e)}")
                            except Exception as e:
                                st.error(f"Failed to delete question: {str(e)}")
    else:
        st.info("No questions have been added to this examination yet.")

    st.divider()

    # Add Question Form
    st.markdown("#### Add New Question")
    with st.form(f"add_question_form_{selected_exam_id}", clear_on_submit=True):
        new_text = st.text_area(
            "Question Text",
            placeholder="e.g. Which of the following data structures operates on a FIFO basis?",
            help="Required prompt text for the question.",
        )
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            new_opt_a = st.text_input("Option A", placeholder="First alternative", max_chars=500)
            new_opt_c = st.text_input("Option C", placeholder="Third alternative", max_chars=500)
        with col_a2:
            new_opt_b = st.text_input("Option B", placeholder="Second alternative", max_chars=500)
            new_opt_d = st.text_input("Option D", placeholder="Fourth alternative", max_chars=500)

        col_acorr, col_amarks = st.columns(2)
        with col_acorr:
            new_correct = st.selectbox(
                "Correct Option",
                options=["A", "B", "C", "D"],
                help="Select which option is correct.",
            )
        with col_amarks:
            new_marks = st.number_input(
                "Marks",
                min_value=1,
                max_value=100,
                value=1,
                step=1,
                help="Positive integer marks for this question.",
            )

        submitted_add = st.form_submit_button("Add Question to Examination", use_container_width=True)

    if submitted_add:
        clean_text = new_text.strip() if new_text else ""
        clean_a = new_opt_a.strip() if new_opt_a else ""
        clean_b = new_opt_b.strip() if new_opt_b else ""
        clean_c = new_opt_c.strip() if new_opt_c else ""
        clean_d = new_opt_d.strip() if new_opt_d else ""

        if not clean_text:
            st.error("Question text is required and cannot be empty.")
            return

        if not clean_a or not clean_b or not clean_c or not clean_d:
            st.error("All four options (Option A, Option B, Option C, Option D) are required and cannot be empty.")
            return

        if len(clean_a) > 500 or len(clean_b) > 500 or len(clean_c) > 500 or len(clean_d) > 500:
            st.error("Options cannot exceed 500 characters.")
            return

        if new_correct not in {"A", "B", "C", "D"}:
            st.error("Correct option must be one of 'A', 'B', 'C', or 'D'.")
            return

        try:
            dur_m = int(new_marks)
        except (ValueError, TypeError):
            st.error("Marks must be a valid integer.")
            return

        if dur_m <= 0:
            st.error("Marks must be a positive integer greater than zero.")
            return

        try:
            created_q = add_question(
                exam_id=selected_exam_id,
                teacher_id=teacher_id,
                question_text=clean_text,
                option_a=clean_a,
                option_b=clean_b,
                option_c=clean_c,
                option_d=clean_d,
                correct_option=new_correct,
                marks=dur_m,
            )
            st.session_state["question_action_success"] = (
                f"Question added successfully (ID: {created_q.get('question_id')})."
            )
            st.rerun()
        except ValueError as e:
            st.error(f"Error: {str(e)}")
        except PermissionError as e:
            st.error(f"Permission Denied: {str(e)}")
        except Exception as e:
            st.error(f"Failed to add question: {str(e)}")


def render_lifecycle_section(teacher_id: int) -> None:
    """
    Render exam lifecycle administration controls (Publish / Close)
    for examinations owned by the authenticated teacher/admin.

    Args:
        teacher_id: User ID of the authenticated teacher/admin.
    """
    st.markdown("### Examination Lifecycle Administration")
    st.caption("Manage assessment publication status and close completed examinations.")

    try:
        exams: List[Dict[str, Any]] = get_teacher_exams(teacher_id)
    except Exception as e:
        st.error(f"Failed to load examinations: {str(e)}")
        return

    if not exams:
        st.info("No examinations available. Please create an examination first.")
        return

    exam_map = {exam["exam_id"]: exam for exam in exams}
    exam_ids = [exam["exam_id"] for exam in exams]

    selected_exam_id = st.selectbox(
        "Select Examination",
        options=exam_ids,
        format_func=lambda eid: f"ID {eid} — {exam_map[eid].get('title', 'Untitled')} [{exam_map[eid].get('status', 'DRAFT')}]",
        key="lifecycle_exam_selector",
    )

    selected_exam = exam_map.get(selected_exam_id)
    if not selected_exam:
        st.warning("Selected examination could not be loaded.")
        return

    # Check for flash message within tab if available
    if "exam_lifecycle_tab_msg" in st.session_state:
        st.success(st.session_state.pop("exam_lifecycle_tab_msg"))

    # Fetch question count
    try:
        questions = get_exam_questions(selected_exam_id, teacher_id)
        q_count = len(questions)
    except Exception:
        q_count = None

    status = selected_exam.get("status", "DRAFT")
    status_color = {
        "DRAFT": "orange",
        "PUBLISHED": "green",
        "CLOSED": "gray"
    }.get(status, "blue")

    with st.container(border=True):
        st.markdown(f"#### {selected_exam.get('title', 'Untitled Exam')}")
        if selected_exam.get("description"):
            st.write(selected_exam["description"])

        col_dur, col_q, col_st = st.columns(3)
        with col_dur:
            st.markdown(f"**Duration**: {selected_exam.get('duration_minutes', 0)} mins")
        with col_q:
            q_display = f"{q_count} question(s)" if q_count is not None else "N/A"
            st.markdown(f"**Questions**: {q_display}")
        with col_st:
            st.markdown(
                f"**Status**: <span style='font-weight: bold; color: {status_color};'>{status}</span>",
                unsafe_allow_html=True,
            )

        st.divider()

        # Action based on lifecycle status
        if status == "DRAFT":
            st.info("This examination is currently in **DRAFT** status. Publishing it will make it visible to students.")
            if st.button("Publish Exam", key=f"publish_btn_{selected_exam_id}", type="primary"):
                try:
                    published = publish_exam(selected_exam_id, teacher_id)
                    msg = f"Examination '{published.get('title')}' (ID: {published.get('exam_id')}) successfully published."
                    st.session_state["exam_lifecycle_success"] = msg
                    st.session_state["exam_lifecycle_tab_msg"] = msg
                    st.rerun()
                except ValueError as e:
                    st.error(f"Cannot publish exam: {str(e)}")
                except PermissionError as e:
                    st.error(f"Permission Denied: {str(e)}")
                except Exception as e:
                    st.error(f"Failed to publish examination: {str(e)}")

        elif status == "PUBLISHED":
            st.warning("This examination is currently **PUBLISHED** and accessible to students. Closing it will terminate further attempts.")
            if st.button("Close Exam", key=f"close_btn_{selected_exam_id}", type="secondary"):
                try:
                    closed = close_exam(selected_exam_id, teacher_id)
                    msg = f"Examination '{closed.get('title')}' (ID: {closed.get('exam_id')}) has been closed."
                    st.session_state["exam_lifecycle_success"] = msg
                    st.session_state["exam_lifecycle_tab_msg"] = msg
                    st.rerun()
                except ValueError as e:
                    st.error(f"Cannot close exam: {str(e)}")
                except PermissionError as e:
                    st.error(f"Permission Denied: {str(e)}")
                except Exception as e:
                    st.error(f"Failed to close examination: {str(e)}")

        elif status == "CLOSED":
            st.info("This examination is **CLOSED**. No further lifecycle transitions or student attempts are permitted.")
        else:
            st.write(f"Unknown status: {status}")


def render_placeholders(teacher_id: int) -> None:
    """
    Render studio control tabs including Create Exam, Manage Exams,
    Manage Questions, and Publish / Close sections.

    Args:
        teacher_id: User ID of the authenticated teacher/admin.
    """
    st.subheader("Studio Controls")

    tab_create, tab_manage_exam, tab_manage_q, tab_lifecycle = st.tabs([
        "Create Exam",
        "Manage Exams",
        "Manage Questions",
        "Publish / Close"
    ])

    with tab_create:
        render_create_exam_form(teacher_id)

    with tab_manage_exam:
        render_manage_exams_section(teacher_id)

    with tab_manage_q:
        render_manage_questions_section(teacher_id)

    with tab_lifecycle:
        render_lifecycle_section(teacher_id)


def render_teacher_ui() -> None:
    """
    Main entrypoint for the Teacher Exam Studio presentation layer.
    Enforces teacher/admin role requirement before rendering dashboard.
    """
    if not require_role(["teacher", "admin"]):
        st.error("Access Denied: You must be signed in as a teacher or administrator to view this page.")
        return

    user = get_current_user()
    if not user or not user.get("id"):
        st.error("Session error: User identity not found. Please log in again.")
        return

    render_teacher_header(user)
    render_exam_list(user["id"])
    st.divider()
    render_placeholders(user["id"])
