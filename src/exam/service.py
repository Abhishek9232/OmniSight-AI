"""
OmniSight-AI Core Examination Service Module.
Handles teacher exam CRUD, lifecycle management, and validation.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import mysql.connector
from src.database.connection import get_connection


def _get_user_role(user_id: int) -> Optional[str]:
    """Internal helper to retrieve user role by user ID."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM users WHERE id = %s LIMIT 1", (user_id,))
        row = cursor.fetchone()
        return row["role"] if row else None
    except mysql.connector.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def create_exam(
    title: str,
    description: Optional[str],
    duration_minutes: int,
    created_by: int
) -> Dict[str, Any]:
    """
    Create a new examination in DRAFT status.

    Args:
        title: Title of the examination.
        description: Instructions or description for the exam.
        duration_minutes: Total duration allowed in minutes (must be > 0).
        created_by: User ID of the teacher/admin creating the exam.

    Returns:
        Dict with created exam details.

    Raises:
        ValueError: If validation fails (empty title, non-positive duration, etc.).
        PermissionError: If user is not authorized to create exams.
    """
    if not title or not isinstance(title, str) or not title.strip():
        raise ValueError("Exam title is required and cannot be empty.")

    clean_title = title.strip()
    if len(clean_title) > 200:
        raise ValueError("Exam title cannot exceed 200 characters.")

    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise ValueError("Exam duration must be a positive integer.")

    if not isinstance(created_by, int) or created_by <= 0:
        raise ValueError("Valid creator user ID is required.")

    user_role = _get_user_role(created_by)
    if not user_role:
        raise ValueError("Creator user does not exist.")
    if user_role.lower() not in {"teacher", "admin"}:
        raise PermissionError(f"User with role '{user_role}' is not authorized to create exams.")

    clean_desc = description.strip() if description and isinstance(description, str) else None

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO exams (title, description, duration_minutes, created_by, status)
            VALUES (%s, %s, %s, %s, 'DRAFT');
        """
        cursor.execute(query, (clean_title, clean_desc, duration_minutes, created_by))
        conn.commit()
        exam_id = cursor.lastrowid
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    created_exam = get_exam(exam_id)
    if not created_exam:
        raise RuntimeError("Failed to retrieve created exam.")
    return created_exam


def get_exam(exam_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve an exam by its exam_id.

    Args:
        exam_id: Unique exam identifier.

    Returns:
        Dict of exam record if found, None otherwise.
    """
    if not isinstance(exam_id, int) or exam_id <= 0:
        return None

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT exam_id, title, description, duration_minutes, created_by, status, created_at
            FROM exams
            WHERE exam_id = %s
            LIMIT 1;
        """
        cursor.execute(query, (exam_id,))
        return cursor.fetchone()
    except mysql.connector.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_teacher_exams(teacher_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all exams created by a specific teacher.

    Args:
        teacher_id: User ID of the teacher.

    Returns:
        List of dicts representing the teacher's exams.
    """
    if not isinstance(teacher_id, int) or teacher_id <= 0:
        return []

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT exam_id, title, description, duration_minutes, created_by, status, created_at
            FROM exams
            WHERE created_by = %s
            ORDER BY created_at DESC;
        """
        cursor.execute(query, (teacher_id,))
        return cursor.fetchall()
    except mysql.connector.Error:
        return []
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def update_exam(
    exam_id: int,
    teacher_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    duration_minutes: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update exam details (title, description, duration) while in DRAFT status.

    Args:
        exam_id: Unique exam identifier.
        teacher_id: User ID of the teacher requesting update.
        title: Optional new title.
        description: Optional new description.
        duration_minutes: Optional new duration in minutes (> 0).

    Returns:
        Updated exam dictionary.

    Raises:
        ValueError: If exam not found, status is not DRAFT, or invalid data.
        PermissionError: If user does not own the exam.
    """
    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own this examination.")

    if exam["status"] != "DRAFT":
        raise ValueError(f"Cannot update exam with status '{exam['status']}'. Only DRAFT exams can be modified.")

    updates = []
    params = []

    if title is not None:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Exam title cannot be empty.")
        clean_title = title.strip()
        if len(clean_title) > 200:
            raise ValueError("Exam title cannot exceed 200 characters.")
        updates.append("title = %s")
        params.append(clean_title)

    if description is not None:
        clean_desc = description.strip() if isinstance(description, str) and description.strip() else None
        updates.append("description = %s")
        params.append(clean_desc)

    if duration_minutes is not None:
        if not isinstance(duration_minutes, int) or duration_minutes <= 0:
            raise ValueError("Exam duration must be a positive integer.")
        updates.append("duration_minutes = %s")
        params.append(duration_minutes)

    if not updates:
        return exam

    params.append(exam_id)
    sql = f"UPDATE exams SET {', '.join(updates)} WHERE exam_id = %s"

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    updated_exam = get_exam(exam_id)
    if not updated_exam:
        raise RuntimeError("Failed to retrieve updated exam.")
    return updated_exam


def publish_exam(exam_id: int, teacher_id: int) -> Dict[str, Any]:
    """
    Transition an examination from DRAFT to PUBLISHED.

    Validates:
    - User is authorized owner or admin.
    - Exam is currently in DRAFT status.
    - At least one question exists.
    - All questions have valid options and valid correct answer keys (A, B, C, or D).

    Args:
        exam_id: Unique exam identifier.
        teacher_id: User ID of the teacher.

    Returns:
        Updated exam dictionary with status='PUBLISHED'.

    Raises:
        ValueError: If exam not found, status is not DRAFT, or questions invalid/empty.
        PermissionError: If user is unauthorized.
    """
    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own this examination.")

    if exam["status"] != "DRAFT":
        raise ValueError(f"Cannot publish exam with status '{exam['status']}'. Only DRAFT exams can be published.")

    # Validate questions exist and have valid keys
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT question_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks
            FROM questions
            WHERE exam_id = %s;
        """, (exam_id,))
        questions = cursor.fetchall()

        if not questions:
            raise ValueError("Cannot publish exam: The exam has no questions. At least one question is required.")

        for idx, q in enumerate(questions, 1):
            if not q["question_text"] or not q["question_text"].strip():
                raise ValueError(f"Question #{idx} is missing question text.")
            for opt in ["option_a", "option_b", "option_c", "option_d"]:
                if not q[opt] or not q[opt].strip():
                    raise ValueError(f"Question #{idx} is missing content for {opt}.")
            valid_keys = {"A", "B", "C", "D"}
            if not q["correct_option"] or q["correct_option"].strip().upper() not in valid_keys:
                raise ValueError(f"Question #{idx} has invalid correct_option '{q['correct_option']}'. Must be A, B, C, or D.")

        cursor.execute("UPDATE exams SET status = 'PUBLISHED' WHERE exam_id = %s", (exam_id,))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    updated_exam = get_exam(exam_id)
    if not updated_exam:
        raise RuntimeError("Failed to retrieve published exam.")
    return updated_exam


def close_exam(exam_id: int, teacher_id: int) -> Dict[str, Any]:
    """
    Transition an examination from PUBLISHED to CLOSED.

    Args:
        exam_id: Unique exam identifier.
        teacher_id: User ID of the teacher.

    Returns:
        Updated exam dictionary with status='CLOSED'.

    Raises:
        ValueError: If exam not found or status is not PUBLISHED.
        PermissionError: If user is unauthorized.
    """
    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own this examination.")

    if exam["status"] != "PUBLISHED":
        raise ValueError(f"Cannot close exam with status '{exam['status']}'. Only PUBLISHED exams can be closed.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE exams SET status = 'CLOSED' WHERE exam_id = %s", (exam_id,))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    updated_exam = get_exam(exam_id)
    if not updated_exam:
        raise RuntimeError("Failed to retrieve closed exam.")
    return updated_exam


def get_question(question_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single question by question_id.

    Args:
        question_id: Unique question identifier.

    Returns:
        Dict representing question record if found, None otherwise.
    """
    if not isinstance(question_id, int) or question_id <= 0:
        return None

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT question_id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks
            FROM questions
            WHERE question_id = %s
            LIMIT 1;
        """
        cursor.execute(query, (question_id,))
        return cursor.fetchone()
    except mysql.connector.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def add_question(
    exam_id: int,
    teacher_id: int,
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: str,
    marks: int = 1
) -> Dict[str, Any]:
    """
    Add a new question to an examination in DRAFT status.

    Args:
        exam_id: Exam to which the question belongs.
        teacher_id: User ID of the requesting teacher/admin.
        question_text: The question prompt text.
        option_a: Option A text.
        option_b: Option B text.
        option_c: Option C text.
        option_d: Option D text.
        correct_option: Single character ('A', 'B', 'C', or 'D').
        marks: Positive integer point value for the question (default: 1).

    Returns:
        Dict with created question details.

    Raises:
        ValueError: If exam not found, status is not DRAFT, or field validation fails.
        PermissionError: If user is unauthorized or not exam owner.
    """
    if not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("Valid exam ID is required.")

    if not isinstance(teacher_id, int) or teacher_id <= 0:
        raise ValueError("Valid teacher ID is required.")

    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() == "student":
        raise PermissionError("Unauthorized: Students cannot manage questions.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own this examination.")

    if exam["status"] != "DRAFT":
        raise ValueError(f"Cannot add question to exam with status '{exam['status']}'. Questions can only be added to DRAFT exams.")

    # Validate question_text
    if not question_text or not isinstance(question_text, str) or not question_text.strip():
        raise ValueError("Question text is required and cannot be empty.")
    clean_text = question_text.strip()

    # Validate options
    options = {"option_a": option_a, "option_b": option_b, "option_c": option_c, "option_d": option_d}
    clean_options = {}
    for opt_key, opt_val in options.items():
        if not opt_val or not isinstance(opt_val, str) or not opt_val.strip():
            raise ValueError(f"{opt_key.replace('_', ' ').capitalize()} is required and cannot be empty.")
        clean_val = opt_val.strip()
        if len(clean_val) > 500:
            raise ValueError(f"{opt_key.replace('_', ' ').capitalize()} cannot exceed 500 characters.")
        clean_options[opt_key] = clean_val

    # Validate correct_option
    if not correct_option or not isinstance(correct_option, str):
        raise ValueError("Correct option must be one of 'A', 'B', 'C', or 'D'.")
    clean_correct = correct_option.strip().upper()
    if clean_correct not in {"A", "B", "C", "D"}:
        raise ValueError(f"Invalid correct option '{correct_option}'. Must be one of 'A', 'B', 'C', or 'D'.")

    # Validate marks
    if type(marks) is not int or marks <= 0:
        raise ValueError("Marks must be a positive integer.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(query, (
            exam_id,
            clean_text,
            clean_options["option_a"],
            clean_options["option_b"],
            clean_options["option_c"],
            clean_options["option_d"],
            clean_correct,
            marks
        ))
        conn.commit()
        question_id = cursor.lastrowid
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    created_question = get_question(question_id)
    if not created_question:
        raise RuntimeError("Failed to retrieve created question.")
    return created_question


def get_exam_questions(exam_id: int, teacher_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all questions for a specific examination.

    Args:
        exam_id: Unique exam identifier.
        teacher_id: User ID of the requesting teacher/admin.

    Returns:
        List of question dictionaries ordered by question_id ASC.

    Raises:
        ValueError: If exam not found or user does not exist.
        PermissionError: If user is not authorized to view the questions.
    """
    if not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("Valid exam ID is required.")

    if not isinstance(teacher_id, int) or teacher_id <= 0:
        raise ValueError("Valid teacher ID is required.")

    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() == "student":
        raise PermissionError("Unauthorized: Students cannot access exam management questions.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own this examination.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT question_id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks
            FROM questions
            WHERE exam_id = %s
            ORDER BY question_id ASC;
        """
        cursor.execute(query, (exam_id,))
        return cursor.fetchall()
    except mysql.connector.Error:
        return []
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def update_question(
    question_id: int,
    teacher_id: int,
    question_text: Optional[str] = None,
    option_a: Optional[str] = None,
    option_b: Optional[str] = None,
    option_c: Optional[str] = None,
    option_d: Optional[str] = None,
    correct_option: Optional[str] = None,
    marks: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update an existing question in a DRAFT examination.

    Args:
        question_id: Unique question identifier.
        teacher_id: User ID of the teacher/admin requesting update.
        question_text: Optional updated question text.
        option_a: Optional updated option A.
        option_b: Optional updated option B.
        option_c: Optional updated option C.
        option_d: Optional updated option D.
        correct_option: Optional updated correct option ('A', 'B', 'C', or 'D').
        marks: Optional updated marks (> 0).

    Returns:
        Updated question dictionary.

    Raises:
        ValueError: If question not found, exam not in DRAFT, or invalid data.
        PermissionError: If user is unauthorized or not owner.
    """
    if not isinstance(question_id, int) or question_id <= 0:
        raise ValueError("Valid question ID is required.")

    if not isinstance(teacher_id, int) or teacher_id <= 0:
        raise ValueError("Valid teacher ID is required.")

    question = get_question(question_id)
    if not question:
        raise ValueError(f"Question with ID {question_id} not found.")

    exam = get_exam(question["exam_id"])
    if not exam:
        raise ValueError(f"Exam for question ID {question_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() == "student":
        raise PermissionError("Unauthorized: Students cannot modify questions.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own the examination for this question.")

    if exam["status"] != "DRAFT":
        raise ValueError(f"Cannot update question in exam with status '{exam['status']}'. Questions can only be modified in DRAFT exams.")

    updates = []
    params = []

    if question_text is not None:
        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError("Question text cannot be empty.")
        updates.append("question_text = %s")
        params.append(question_text.strip())

    options_to_check = [("option_a", option_a), ("option_b", option_b), ("option_c", option_c), ("option_d", option_d)]
    for opt_name, opt_val in options_to_check:
        if opt_val is not None:
            if not isinstance(opt_val, str) or not opt_val.strip():
                raise ValueError(f"{opt_name.replace('_', ' ').capitalize()} cannot be empty.")
            clean_val = opt_val.strip()
            if len(clean_val) > 500:
                raise ValueError(f"{opt_name.replace('_', ' ').capitalize()} cannot exceed 500 characters.")
            updates.append(f"{opt_name} = %s")
            params.append(clean_val)

    if correct_option is not None:
        if not isinstance(correct_option, str):
            raise ValueError("Correct option must be one of 'A', 'B', 'C', or 'D'.")
        clean_correct = correct_option.strip().upper()
        if clean_correct not in {"A", "B", "C", "D"}:
            raise ValueError(f"Invalid correct option '{correct_option}'. Must be one of 'A', 'B', 'C', or 'D'.")
        updates.append("correct_option = %s")
        params.append(clean_correct)

    if marks is not None:
        if type(marks) is not int or marks <= 0:
            raise ValueError("Marks must be a positive integer.")
        updates.append("marks = %s")
        params.append(marks)

    if not updates:
        return question

    params.append(question_id)
    sql = f"UPDATE questions SET {', '.join(updates)} WHERE question_id = %s"

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    updated_question = get_question(question_id)
    if not updated_question:
        raise RuntimeError("Failed to retrieve updated question.")
    return updated_question


def delete_question(question_id: int, teacher_id: int) -> bool:
    """
    Delete a question from an examination in DRAFT status.

    Args:
        question_id: Unique question identifier.
        teacher_id: User ID of the teacher/admin requesting deletion.

    Returns:
        True if deleted successfully.

    Raises:
        ValueError: If question not found or exam not in DRAFT status.
        PermissionError: If user is unauthorized or not owner.
    """
    if not isinstance(question_id, int) or question_id <= 0:
        raise ValueError("Valid question ID is required.")

    if not isinstance(teacher_id, int) or teacher_id <= 0:
        raise ValueError("Valid teacher ID is required.")

    question = get_question(question_id)
    if not question:
        raise ValueError(f"Question with ID {question_id} not found.")

    exam = get_exam(question["exam_id"])
    if not exam:
        raise ValueError(f"Exam for question ID {question_id} not found.")

    user_role = _get_user_role(teacher_id)
    if not user_role:
        raise ValueError("Requesting user does not exist.")

    if user_role.lower() == "student":
        raise PermissionError("Unauthorized: Students cannot delete questions.")

    if user_role.lower() != "admin" and exam["created_by"] != teacher_id:
        raise PermissionError("Unauthorized: You do not own the examination for this question.")

    if exam["status"] != "DRAFT":
        raise ValueError(f"Cannot delete question from exam with status '{exam['status']}'. Questions can only be deleted from DRAFT exams.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE question_id = %s", (question_id,))
        conn.commit()
        return True
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def start_attempt(exam_id: int, student_id: int) -> Dict[str, Any]:
    """
    Initiate a new examination attempt for an authenticated student.

    Args:
        exam_id: Unique exam identifier.
        student_id: User ID of the student.

    Returns:
        Dict containing attempt details (attempt_id, exam_id, student_id, started_at, submitted_at, status).

    Raises:
        ValueError: If exam or student does not exist, exam is not PUBLISHED, or attempt already exists.
        PermissionError: If user does not have the student role.
    """
    if not isinstance(exam_id, int) or exam_id <= 0:
        raise ValueError("Valid exam ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Validate that the student/user exists & 2. Role is strictly student
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot start examination attempts.")

    # 3. Validate that the exam exists
    exam = get_exam(exam_id)
    if not exam:
        raise ValueError(f"Exam with ID {exam_id} not found.")

    # 4. Validate that the exam status is PUBLISHED
    if exam["status"] != "PUBLISHED":
        raise ValueError(f"Cannot start attempt: Exam status is '{exam['status']}'. Only PUBLISHED exams can be attempted.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 5. Enforce MVP single-attempt policy
        check_query = """
            SELECT attempt_id, status FROM exam_attempts
            WHERE exam_id = %s AND student_id = %s
            LIMIT 1;
        """
        cursor.execute(check_query, (exam_id, student_id))
        existing_attempt = cursor.fetchone()
        if existing_attempt:
            raise ValueError("You have already initiated or completed an attempt for this examination.")

        # 6. Create row in exam_attempts
        insert_query = """
            INSERT INTO exam_attempts (exam_id, student_id, started_at, submitted_at, status)
            VALUES (%s, %s, NOW(), NULL, 'IN_PROGRESS');
        """
        cursor.execute(insert_query, (exam_id, student_id))
        attempt_id = cursor.lastrowid

        # 7. Retrieve the newly created attempt record
        select_query = """
            SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status
            FROM exam_attempts
            WHERE attempt_id = %s
            LIMIT 1;
        """
        cursor.execute(select_query, (attempt_id,))
        created_attempt = cursor.fetchone()

        conn.commit()

        if not created_attempt:
            raise RuntimeError("Failed to retrieve created examination attempt.")

        return created_attempt
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_attempt(attempt_id: int, student_id: int) -> Dict[str, Any]:
    """
    Retrieve an examination attempt belonging to an authenticated student.

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the requesting student.

    Returns:
        Dict containing attempt details (attempt_id, exam_id, student_id, started_at, submitted_at, status).

    Raises:
        ValueError: If parameters are invalid, student not found, or attempt not found.
        PermissionError: If user does not have student role, or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Verify that the student exists & 2. Verify user has the STUDENT role
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot access student attempt details.")

    # 3. Fetch the attempt by attempt_id
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status
            FROM exam_attempts
            WHERE attempt_id = %s
            LIMIT 1;
        """
        cursor.execute(query, (attempt_id,))
        attempt = cursor.fetchone()

        # 5. If the attempt does not exist, raise an appropriate ValueError
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 4 & 6. Verify that the attempt belongs to the supplied student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to access this examination attempt.")

        # 7. Return only safe attempt-level fields
        return attempt
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_attempt_questions(attempt_id: int, student_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all questions for an examination attempt, strictly masking answer keys.

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the student.

    Returns:
        List of dicts containing student-safe question fields:
        (question_id, question_text, option_a, option_b, option_c, option_d, marks).

    Raises:
        ValueError: If IDs are invalid, student not found, attempt not found, or exam not found.
        PermissionError: If user is not a student or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Verify that the student exists & 2. Verify caller has STUDENT role
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot access student attempt questions.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Fetch attempt by attempt_id
        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 4 & 5. Verify that the attempt belongs to student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to access questions for this examination attempt.")

        # 6. Verify associated exam exists
        exam = get_exam(attempt["exam_id"])
        if not exam:
            raise ValueError(f"Associated exam with ID {attempt['exam_id']} not found.")

        # 7, 8, 9, 10, 11: Fetch questions for that exam ordered by question_id ASC, strictly excluding correct_option
        query = """
            SELECT question_id, question_text, option_a, option_b, option_c, option_d, marks
            FROM questions
            WHERE exam_id = %s
            ORDER BY question_id ASC;
        """
        cursor.execute(query, (attempt["exam_id"],))
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def save_answer(
    attempt_id: int,
    student_id: int,
    question_id: int,
    selected_option: Optional[str]
) -> Dict[str, Any]:
    """
    Persist or update a student's answer selection for a question.

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the student.
        question_id: Unique question identifier.
        selected_option: Option choice ('A', 'B', 'C', 'D') or None to clear answer.

    Returns:
        Dict containing answer details (answer_id, attempt_id, question_id, selected_option, answered_at).

    Raises:
        ValueError: If validation fails (invalid option, question not in exam, expired attempt, non-existent entity).
        PermissionError: If user is not student or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    if not isinstance(question_id, int) or question_id <= 0:
        raise ValueError("Valid question ID is required.")

    # 1. Verify student exists & 2. Verify caller has STUDENT role
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot save examination answers.")

    # 9. Validate selected_option
    clean_option = None
    if selected_option is not None:
        if not isinstance(selected_option, str):
            raise ValueError("Selected option must be a string or None.")
        normalized = selected_option.strip().upper()
        if normalized not in {"A", "B", "C", "D"}:
            raise ValueError(f"Invalid selected option '{selected_option}'. Must be one of 'A', 'B', 'C', 'D', or None.")
        clean_option = normalized

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Fetch attempt
        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 4. Verify attempt belongs to student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to modify this examination attempt.")

        # 5. Only allow saving answers when attempt status is IN_PROGRESS
        if attempt["status"] != "IN_PROGRESS":
            raise ValueError(f"Cannot save answer: Attempt status is '{attempt['status']}'. Answers can only be saved while attempt is IN_PROGRESS.")

        # Fetch associated exam for timing and relationship verification
        exam = get_exam(attempt["exam_id"])
        if not exam:
            raise ValueError(f"Associated exam with ID {attempt['exam_id']} not found.")

        # 6. Enforce server-side timing: started_at + exam duration + 60s grace period
        duration_minutes = exam.get("duration_minutes", 0)
        started_at = attempt["started_at"]
        grace_period_seconds = 60
        deadline = started_at + timedelta(minutes=duration_minutes, seconds=grace_period_seconds)
        now = datetime.now()

        if now > deadline:
            raise ValueError("Exam duration has expired. Answers can no longer be saved.")

        # 7 & 8. Verify question exists and belongs to the exam associated with the attempt
        cursor.execute(
            "SELECT question_id, exam_id FROM questions WHERE question_id = %s LIMIT 1;",
            (question_id,)
        )
        question = cursor.fetchone()
        if not question:
            raise ValueError(f"Question with ID {question_id} not found.")

        if question["exam_id"] != attempt["exam_id"]:
            raise ValueError("Question does not belong to the examination for this attempt.")

        # 11 & 12. Check if answer already exists (UPSERT pattern)
        cursor.execute(
            "SELECT answer_id FROM answers WHERE attempt_id = %s AND question_id = %s LIMIT 1;",
            (attempt_id, question_id)
        )
        existing_answer = cursor.fetchone()

        if existing_answer:
            answer_id = existing_answer["answer_id"]
            cursor.execute(
                "UPDATE answers SET selected_option = %s, answered_at = NOW() WHERE answer_id = %s;",
                (clean_option, answer_id)
            )
        else:
            cursor.execute(
                "INSERT INTO answers (attempt_id, question_id, selected_option, is_correct, answered_at) VALUES (%s, %s, %s, NULL, NOW());",
                (attempt_id, question_id, clean_option)
            )
            answer_id = cursor.lastrowid

        # 10. Fetch updated answer record (strictly omitting correct_option)
        cursor.execute(
            "SELECT answer_id, attempt_id, question_id, selected_option, answered_at FROM answers WHERE answer_id = %s LIMIT 1;",
            (answer_id,)
        )
        saved_record = cursor.fetchone()

        conn.commit()

        if not saved_record:
            raise RuntimeError("Failed to retrieve saved answer record.")

        return saved_record
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def submit_attempt(attempt_id: int, student_id: int) -> Dict[str, Any]:
    """
    Finalize and submit an active examination attempt.

    Transitions attempt status from IN_PROGRESS to SUBMITTED and stamps submitted_at.
    Does NOT calculate marks or populate results (reserved for evaluate_attempt).

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the student.

    Returns:
        Dict containing safe attempt fields (attempt_id, exam_id, student_id, started_at, submitted_at, status).

    Raises:
        ValueError: If attempt or student not found, or attempt is not in IN_PROGRESS status.
        PermissionError: If user is not student or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Verify student exists & 2. Verify caller has STUDENT role
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot submit examination attempts.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Fetch attempt by attempt_id
        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 4. Verify attempt belongs to student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to submit this examination attempt.")

        # 5. Only an IN_PROGRESS attempt can be submitted
        if attempt["status"] != "IN_PROGRESS":
            raise ValueError(f"Cannot submit attempt: Attempt status is '{attempt['status']}'. Only IN_PROGRESS attempts can be submitted.")

        # 6 & 7. Server-side timing validation: calculate deadline with 60-second grace period
        exam = get_exam(attempt["exam_id"])
        if not exam:
            raise ValueError(f"Associated exam with ID {attempt['exam_id']} not found.")

        duration_minutes = exam.get("duration_minutes", 0)
        started_at = attempt["started_at"]
        # In all cases (within limit or past deadline), finalize status to SUBMITTED
        # so the attempt is permanently locked against further modifications.
        cursor.execute(
            "UPDATE exam_attempts SET status = 'SUBMITTED', submitted_at = NOW() WHERE attempt_id = %s;",
            (attempt_id,)
        )

        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        submitted_record = cursor.fetchone()

        conn.commit()

        if not submitted_record:
            raise RuntimeError("Failed to retrieve submitted examination attempt.")

        return submitted_record
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def evaluate_attempt(attempt_id: int, student_id: int) -> Dict[str, Any]:
    """
    Evaluate an examination attempt, compute marks, persist results, and transition status to EVALUATED.

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the student.

    Returns:
        Dict containing safe result details:
        (result_id, attempt_id, total_marks, obtained_marks, percentage, evaluated_at, status).

    Raises:
        ValueError: If attempt or student not found, attempt is not in SUBMITTED status, or duplicate evaluation.
        PermissionError: If user is not student or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Verify student exists & 2. Verify caller has STUDENT role
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot evaluate examination attempts.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Fetch attempt by attempt_id
        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 4. Verify attempt belongs to student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to evaluate this examination attempt.")

        # 5 & 6. Only a SUBMITTED attempt can be evaluated; reject duplicate evaluation
        if attempt["status"] == "EVALUATED":
            raise ValueError("Cannot evaluate attempt: Attempt has already been EVALUATED.")
        if attempt["status"] != "SUBMITTED":
            raise ValueError(f"Cannot evaluate attempt: Attempt status is '{attempt['status']}'. Only SUBMITTED attempts can be evaluated.")

        cursor.execute(
            "SELECT result_id FROM results WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        existing_result = cursor.fetchone()
        if existing_result:
            raise ValueError("A result record already exists for this examination attempt.")

        # 7. Fetch all questions belonging to the exam
        cursor.execute(
            "SELECT question_id, correct_option, marks FROM questions WHERE exam_id = %s ORDER BY question_id ASC;",
            (attempt["exam_id"],)
        )
        questions = cursor.fetchall()
        if not questions:
            raise ValueError(f"No questions found for exam ID {attempt['exam_id']}.")

        # 8. Fetch the student's answers for this attempt
        cursor.execute(
            "SELECT answer_id, question_id, selected_option FROM answers WHERE attempt_id = %s;",
            (attempt_id,)
        )
        student_answers = cursor.fetchall()
        answers_by_qid = {a["question_id"]: a for a in student_answers}

        # 9, 10, 11. Calculate total_marks, obtained_marks, percentage
        total_marks = 0.0
        obtained_marks = 0.0

        for q in questions:
            q_id = q["question_id"]
            q_marks = float(q["marks"])
            total_marks += q_marks

            ans = answers_by_qid.get(q_id)
            if ans and ans["selected_option"]:
                is_correct = (ans["selected_option"].strip().upper() == q["correct_option"].strip().upper())
                cursor.execute(
                    "UPDATE answers SET is_correct = %s WHERE answer_id = %s;",
                    (is_correct, ans["answer_id"])
                )
                if is_correct:
                    obtained_marks += q_marks
            elif ans:
                cursor.execute(
                    "UPDATE answers SET is_correct = FALSE WHERE answer_id = %s;",
                    (ans["answer_id"],)
                )

        percentage = round((obtained_marks / total_marks) * 100, 2) if total_marks > 0 else 0.0

        # 13, 14, 15. Create exactly ONE result record
        cursor.execute(
            """
            INSERT INTO results (attempt_id, total_marks, obtained_marks, percentage, evaluated_at)
            VALUES (%s, %s, %s, %s, NOW());
            """,
            (attempt_id, total_marks, obtained_marks, percentage)
        )
        result_id = cursor.lastrowid

        # 16. Update exam_attempts.status from SUBMITTED -> EVALUATED
        cursor.execute(
            "UPDATE exam_attempts SET status = 'EVALUATED' WHERE attempt_id = %s;",
            (attempt_id,)
        )

        cursor.execute(
            "SELECT result_id, attempt_id, total_marks, obtained_marks, percentage, evaluated_at FROM results WHERE result_id = %s LIMIT 1;",
            (result_id,)
        )
        saved_result = cursor.fetchone()

        # 17. Atomic commit of result creation and status update
        conn.commit()

        if not saved_result:
            raise RuntimeError("Failed to retrieve created examination result.")

        return {
            "result_id": saved_result["result_id"],
            "attempt_id": saved_result["attempt_id"],
            "total_marks": float(saved_result["total_marks"]),
            "obtained_marks": float(saved_result["obtained_marks"]),
            "percentage": float(saved_result["percentage"]) if saved_result["percentage"] is not None else 0.0,
            "evaluated_at": saved_result["evaluated_at"],
            "status": "EVALUATED"
        }
    except Exception:
        # 18. Rollback complete transaction on failure
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_attempt_result(attempt_id: int, student_id: int) -> Dict[str, Any]:
    """
    Retrieve finalized examination result details for an authenticated student.

    Args:
        attempt_id: Unique attempt identifier.
        student_id: User ID of the student.

    Returns:
        Dict containing safe result fields:
        (result_id, attempt_id, total_marks, obtained_marks, percentage, evaluated_at, status).

    Raises:
        ValueError: If attempt or student not found, or attempt has not been evaluated yet.
        PermissionError: If user is not student or attempt belongs to another student.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("Valid student ID is required.")

    # 1. Verify student exists & has role 'student'
    user_role = _get_user_role(student_id)
    if not user_role:
        raise ValueError("Student user does not exist.")

    if user_role.lower() != "student":
        raise PermissionError(f"Unauthorized: Users with role '{user_role}' cannot access student examination results.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 2. Fetch attempt by attempt_id
        cursor.execute(
            "SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status FROM exam_attempts WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # 3. Verify attempt belongs to the given student_id
        if attempt["student_id"] != student_id:
            raise PermissionError("Unauthorized: You do not have permission to access results for this examination attempt.")

        # 4 & 5. Fetch result row using attempt_id
        cursor.execute(
            "SELECT result_id, attempt_id, total_marks, obtained_marks, percentage, evaluated_at FROM results WHERE attempt_id = %s LIMIT 1;",
            (attempt_id,)
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"No result found for attempt ID {attempt_id}. The examination attempt has not been evaluated yet.")

        # 6 & 7. Return only safe result fields (no correct_option, no answer keys)
        return {
            "result_id": result["result_id"],
            "attempt_id": result["attempt_id"],
            "total_marks": float(result["total_marks"]),
            "obtained_marks": float(result["obtained_marks"]),
            "percentage": float(result["percentage"]) if result["percentage"] is not None else 0.0,
            "evaluated_at": result["evaluated_at"],
            "status": attempt["status"]
        }
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
