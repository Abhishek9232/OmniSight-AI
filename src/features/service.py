"""
OmniSight-AI Behavioral Feature Service.
Handles database access, attempt lifecycle validation, feature persistence,
and tabular matrix generation for Phase 6.

Core Architectural Invariants:
- Standalone: Operates independently of UI or active exam controllers.
- Terminal Validation: Feature extraction is permitted exclusively on
  terminal attempts ('SUBMITTED' or 'EVALUATED'). 'IN_PROGRESS' attempts are strictly rejected.
- Atomic & Idempotent: Re-running feature extraction replaces previous feature rows
  atomically within a transaction without creating duplicates.
- Decoupled from Results: Features are extracted without reading exam scores,
  percentages, or answer correctness.
"""

from datetime import datetime
import json
import math
from typing import Dict, Any, List, Optional, Tuple

from src.database.connection import get_connection
from src.features.extractor import (
    extract_behavioral_features,
    FEATURE_NAMES,
)


def extract_and_persist_behavioral_features(attempt_id: int) -> Dict[str, Any]:
    """
    Ingest attempt metadata, answers, and monitoring events from MySQL,
    compute the 18 standardized behavioral features via the pure extractor,
    and atomically persist them into the existing behavioral_features table.

    Args:
        attempt_id: Examination attempt ID.

    Returns:
        Dict containing success status, attempt_id, feature dictionary, and feature_count.

    Raises:
        ValueError: If attempt_id is invalid, attempt is not found, or attempt is IN_PROGRESS.
        RuntimeError: If a database transaction error occurs.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt_id must be a positive integer.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch attempt record
        cursor.execute(
            """
            SELECT attempt_id, exam_id, student_id, started_at, submitted_at, status
            FROM exam_attempts
            WHERE attempt_id = %s;
            """,
            (attempt_id,),
        )
        attempt = cursor.fetchone()
        if not attempt:
            raise ValueError(f"Exam attempt with ID {attempt_id} does not exist.")

        # 2. Strict terminal state validation
        status = attempt.get("status")
        if status == "IN_PROGRESS":
            raise ValueError(
                f"Cannot extract behavioral features for attempt {attempt_id}: "
                f"Attempt is currently IN_PROGRESS. Feature extraction is strictly restricted "
                f"to finalized attempts ('SUBMITTED' or 'EVALUATED')."
            )
        if status not in {"SUBMITTED", "EVALUATED"}:
            raise ValueError(
                f"Cannot extract behavioral features for attempt {attempt_id}: "
                f"Attempt has non-terminal status '{status}'."
            )

        exam_id = attempt["exam_id"]

        # 3. Fetch exam metadata
        cursor.execute(
            """
            SELECT exam_id, title, duration_minutes
            FROM exams
            WHERE exam_id = %s;
            """,
            (exam_id,),
        )
        exam = cursor.fetchone()

        # 4. Fetch question count
        cursor.execute(
            "SELECT COUNT(*) AS total_q FROM questions WHERE exam_id = %s;",
            (exam_id,),
        )
        q_row = cursor.fetchone()
        total_questions = q_row["total_q"] if q_row else 0

        # 5. Fetch answers (strictly omitting is_correct, marks_obtained)
        cursor.execute(
            """
            SELECT answer_id, attempt_id, question_id, selected_option, answered_at
            FROM answers
            WHERE attempt_id = %s;
            """,
            (attempt_id,),
        )
        answers = cursor.fetchall() or []

        # 6. Fetch monitoring events ordered chronologically
        cursor.execute(
            """
            SELECT event_id, attempt_id, event_type, event_timestamp, event_metadata
            FROM monitoring_events
            WHERE attempt_id = %s
            ORDER BY event_timestamp ASC;
            """,
            (attempt_id,),
        )
        monitoring_events = cursor.fetchall() or []

        # 7. Stateless feature calculation
        features = extract_behavioral_features(
            attempt=attempt,
            exam=exam,
            total_questions=total_questions,
            answers=answers,
            monitoring_events=monitoring_events,
        )

        # 8. Sanity check: Ensure all 18 features are present and finite
        if len(features) != len(FEATURE_NAMES):
            raise RuntimeError(
                f"Extraction invariant violation: expected {len(FEATURE_NAMES)} features, "
                f"got {len(features)}."
            )

        for name, val in features.items():
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise RuntimeError(
                    f"Invalid non-finite feature value for '{name}': {val}"
                )

        # 9. Atomic idempotent persistence: Purge old features, insert new batch
        cursor.execute(
            "DELETE FROM behavioral_features WHERE attempt_id = %s;",
            (attempt_id,),
        )

        insert_query = """
            INSERT INTO behavioral_features (attempt_id, feature_name, feature_value, generated_at)
            VALUES (%s, %s, %s, NOW());
        """
        insert_rows = [
            (attempt_id, name, float(val))
            for name, val in features.items()
        ]
        cursor.executemany(insert_query, insert_rows)

        conn.commit()

        return {
            "success": True,
            "attempt_id": attempt_id,
            "features": features,
            "feature_count": len(features),
            "attempt_status": status,
        }

    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_behavioral_feature_vector(attempt_id: int) -> Dict[str, float]:
    """
    Retrieve the persisted behavioral feature vector for an attempt as a dictionary.

    Args:
        attempt_id: Unique attempt ID.

    Returns:
        Dictionary mapping feature_name -> float value. Empty dict if not found.
    """
    if not isinstance(attempt_id, int) or attempt_id <= 0:
        raise ValueError("Valid attempt_id must be a positive integer.")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT feature_name, feature_value
            FROM behavioral_features
            WHERE attempt_id = %s
            ORDER BY feature_name ASC;
            """,
            (attempt_id,),
        )
        rows = cursor.fetchall() or []
        return {row["feature_name"]: float(row["feature_value"]) for row in rows}

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_feature_matrix(
    exam_id: Optional[int] = None,
    as_dataframe: bool = True,
) -> Any:
    """
    Retrieve pivoted behavioral feature vectors for multiple attempts across an exam
    (or all exams) formatted as a 2D matrix / tabular representation suitable for ML pipelines.

    Args:
        exam_id: Optional exam filter. If None, retrieves features across all attempts.
        as_dataframe: If True, attempts to return a pandas.DataFrame; falls back to dict
                      if pandas is unavailable.

    Returns:
        pandas.DataFrame or dict with 'index' (attempt_ids), 'columns' (feature_names),
        'data' (2D float matrix), and 'records' (List of dicts).
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT a.attempt_id, bf.feature_name, bf.feature_value
            FROM exam_attempts a
            JOIN behavioral_features bf ON a.attempt_id = bf.attempt_id
            WHERE (%s IS NULL OR a.exam_id = %s)
            ORDER BY a.attempt_id ASC, bf.feature_name ASC;
        """
        cursor.execute(query, (exam_id, exam_id))
        rows = cursor.fetchall() or []

        # Pivot rows by attempt_id
        grouped: Dict[int, Dict[str, float]] = {}
        for row in rows:
            att_id = row["attempt_id"]
            if att_id not in grouped:
                grouped[att_id] = {}
            grouped[att_id][row["feature_name"]] = float(row["feature_value"])

        index: List[int] = sorted(grouped.keys())
        columns: List[str] = list(FEATURE_NAMES)
        data: List[List[float]] = []
        records: List[Dict[str, Any]] = []

        for att_id in index:
            att_features = grouped[att_id]
            row_vals = [att_features.get(col, 0.0) for col in columns]
            data.append(row_vals)
            rec = {"attempt_id": att_id}
            rec.update({col: att_features.get(col, 0.0) for col in columns})
            records.append(rec)

        if as_dataframe:
            try:
                import pandas as pd
                return pd.DataFrame(data=data, index=index, columns=columns)
            except Exception:
                # Fallback gracefully if pandas cannot be imported
                pass

        return {
            "index": index,
            "columns": columns,
            "data": data,
            "records": records,
            "shape": (len(index), len(columns)),
        }

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
