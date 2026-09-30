"""
OmniSight-AI Proctoring Event Persistence & Query Service.
Handles transaction-safe recording and retrieval of monitoring events in MySQL.
Strictly enforces attempt lifecycle rules:
- Events can ONLY be persisted when attempt status is IN_PROGRESS.
- SUBMITTED and EVALUATED attempts produce ZERO database writes.
- Failure-isolated: database errors never crash calling processes.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import mysql.connector
from src.database.connection import get_connection


def _get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Internal helper to retrieve user role and id."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, role, email, name FROM users WHERE id = %s LIMIT 1;", (user_id,))
        return cursor.fetchone()
    except mysql.connector.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def record_monitoring_event(
    attempt_id: int,
    event_type: str,
    event_metadata: Optional[Dict[str, Any]] = None,
    event_timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Atomically validate attempt status and persist a monitoring event to MySQL.

    Enforces critical invariants:
    - Attempt must exist and have status 'IN_PROGRESS'.
    - If attempt is 'SUBMITTED', 'EVALUATED', or any other terminal status, the write
      is refused and 0 records are inserted.
    - Uses row-level locking (SELECT ... FOR UPDATE) inside an explicit transaction
      to ensure race-condition-free evaluation against concurrent submissions.
    - Traps all exceptions to guarantee failure isolation from the exam engine.

    Args:
        attempt_id: Target exam attempt ID.
        event_type: Domain event identifier (e.g. 'FACE_ABSENT', 'MULTIPLE_FACES').
        event_metadata: Optional dictionary of observation telemetry and parameters.
        event_timestamp: Wall-clock timestamp of event. Defaults to datetime.now().

    Returns:
        Dict conforming to result contract:
        {
            "success": bool,
            "recorded": bool,
            "event_id": Optional[int],
            "reason": Optional[str],
            "error": Optional[str]
        }
    """
    # 1. Parameter validation
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        return {
            "success": False,
            "recorded": False,
            "event_id": None,
            "reason": "Invalid attempt_id provided.",
            "error": "Valid attempt_id must be a positive integer.",
        }

    if not event_type or not isinstance(event_type, str) or not event_type.strip():
        return {
            "success": False,
            "recorded": False,
            "event_id": None,
            "reason": "Invalid event_type provided.",
            "error": "Valid non-empty event_type string is required.",
        }

    clean_event_type = event_type.strip()
    ts = event_timestamp if isinstance(event_timestamp, datetime) else datetime.now()
    meta_json = json.dumps(event_metadata) if event_metadata is not None else None

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 2. Atomic attempt status check with row locking
        cursor.execute(
            "SELECT attempt_id, status FROM exam_attempts WHERE attempt_id = %s FOR UPDATE;",
            (attempt_id,)
        )
        attempt = cursor.fetchone()

        if not attempt:
            conn.rollback()
            return {
                "success": False,
                "recorded": False,
                "event_id": None,
                "reason": f"Exam attempt {attempt_id} not found.",
                "error": f"Exam attempt with ID {attempt_id} does not exist.",
            }

        current_status = attempt["status"]

        # 3. Invariant: Only IN_PROGRESS attempts may receive monitoring events
        if current_status != "IN_PROGRESS":
            conn.rollback()
            return {
                "success": True,
                "recorded": False,
                "event_id": None,
                "reason": f"Attempt is in non-active status '{current_status}'. Monitoring events can only be recorded when IN_PROGRESS.",
                "error": None,
            }

        # 4. Insert into monitoring_events table
        insert_query = """
            INSERT INTO monitoring_events (attempt_id, event_type, event_timestamp, event_metadata)
            VALUES (%s, %s, %s, %s);
        """
        cursor.execute(insert_query, (attempt_id, clean_event_type, ts, meta_json))
        conn.commit()
        event_id = cursor.lastrowid

        return {
            "success": True,
            "recorded": True,
            "event_id": event_id,
            "reason": None,
            "error": None,
        }

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {
            "success": False,
            "recorded": False,
            "event_id": None,
            "reason": "Database transaction failure.",
            "error": f"Failed to persist monitoring event: {str(e)}",
        }

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn and conn.is_connected():
            try:
                conn.close()
            except Exception:
                pass


def get_attempt_monitoring_events(
    attempt_id: int,
    requesting_user_id: int,
) -> List[Dict[str, Any]]:
    """
    Retrieve all monitoring events associated with an examination attempt.
    Enforces strict role-based access control (RBAC):
    - Students can ONLY access monitoring events for their own attempts.
    - Teachers can ONLY access monitoring events for attempts on exams they authored.
    - Administrators can access monitoring events for any attempt.

    Args:
        attempt_id: Examination attempt ID.
        requesting_user_id: ID of the user requesting telemetry.

    Returns:
        List of monitoring event dictionaries ordered chronologically.

    Raises:
        ValueError: If attempt_id or requesting_user_id is invalid or attempt not found.
        PermissionError: If user is unauthorized to view the events.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt ID is required.")

    if not isinstance(requesting_user_id, int) or requesting_user_id <= 0:
        raise ValueError("Valid requesting user ID is required.")

    user = _get_user_info(requesting_user_id)
    if not user:
        raise ValueError("Requesting user does not exist.")

    user_role = user["role"].lower()

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Retrieve attempt and associated exam creator
        attempt_query = """
            SELECT a.attempt_id, a.student_id, a.exam_id, a.status, e.created_by AS exam_teacher_id
            FROM exam_attempts a
            JOIN exams e ON a.exam_id = e.exam_id
            WHERE a.attempt_id = %s
            LIMIT 1;
        """
        cursor.execute(attempt_query, (attempt_id,))
        attempt = cursor.fetchone()

        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} not found.")

        # RBAC Authorization
        if user_role == "student":
            if attempt["student_id"] != requesting_user_id:
                raise PermissionError("Unauthorized: You do not have permission to view monitoring events for this attempt.")
        elif user_role == "teacher":
            if attempt["exam_teacher_id"] != requesting_user_id:
                raise PermissionError("Unauthorized: You do not own the examination associated with this attempt.")
        elif user_role == "admin":
            pass
        else:
            raise PermissionError(f"Unauthorized: Role '{user_role}' cannot access proctoring telemetry.")

        # Retrieve events
        events_query = """
            SELECT event_id, attempt_id, event_type, event_timestamp, event_metadata
            FROM monitoring_events
            WHERE attempt_id = %s
            ORDER BY event_id ASC;
        """
        cursor.execute(events_query, (attempt_id,))
        rows = cursor.fetchall()

        events: List[Dict[str, Any]] = []
        for row in rows:
            meta = row["event_metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            events.append({
                "event_id": row["event_id"],
                "attempt_id": row["attempt_id"],
                "event_type": row["event_type"],
                "event_timestamp": row["event_timestamp"],
                "event_metadata": meta if meta is not None else {},
            })

        return events

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_monitoring_event_summary(
    attempt_id: int,
    requesting_user_id: int,
) -> Dict[str, Any]:
    """
    Retrieve aggregated summary statistics of monitoring events for an attempt.

    Args:
        attempt_id: Examination attempt ID.
        requesting_user_id: ID of the user requesting telemetry summary.

    Returns:
        Dict containing counts of total, absence, and multi-face events.
    """
    events = get_attempt_monitoring_events(attempt_id, requesting_user_id)

    total_count = len(events)
    absence_count = sum(1 for e in events if e["event_type"] == "FACE_ABSENT")
    multiple_faces_count = sum(1 for e in events if e["event_type"] == "MULTIPLE_FACES")
    other_count = total_count - (absence_count + multiple_faces_count)

    return {
        "attempt_id": attempt_id,
        "total_events": total_count,
        "absence_events": absence_count,
        "multiple_faces_events": multiple_faces_count,
        "other_events": other_count,
    }
