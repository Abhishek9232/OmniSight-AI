"""
OmniSight-AI Behavioral Feature Extractor.
Pure, stateless mathematical feature calculation engine.
Strictly decoupled from SQL, Streamlit, and UI layers.

Transforms raw exam attempt lifecycle metadata, answering records, and
persisted computer-vision monitoring events into a deterministic, reproducible
vector of 18 standardized behavioral features.

Core Ethical & Architectural Invariants:
- Event != Misconduct: Extracted metrics represent objective camera/interaction telemetry,
  NOT cheating accusations or guilt verdicts.
- Decoupled from Academic Performance: Zero usage of `answers.is_correct`,
  `results.obtained_marks`, or `results.percentage`.
- Zero NaN / Inf: All emitted features are finite, sanitized floats rounded to 4 decimal places.
"""

from datetime import datetime
import json
import math
from typing import Dict, Any, List, Optional, Tuple


# -----------------------------------------------------------------------------
# 18 Standard Feature Name Constants
# -----------------------------------------------------------------------------
FEATURE_ATTEMPT_DURATION_SEC = "attempt_duration_sec"
FEATURE_ABSENCE_EVENT_COUNT = "absence_event_count"
FEATURE_ABSENCE_TOTAL_DURATION_SEC = "absence_total_duration_sec"
FEATURE_ABSENCE_MAX_DURATION_SEC = "absence_max_duration_sec"
FEATURE_ABSENCE_AVG_DURATION_SEC = "absence_avg_duration_sec"
FEATURE_ABSENCE_TIME_RATIO = "absence_time_ratio"
FEATURE_MULTI_FACE_EVENT_COUNT = "multi_face_event_count"
FEATURE_MULTI_FACE_TOTAL_DURATION_SEC = "multi_face_total_duration_sec"
FEATURE_MULTI_FACE_MAX_DURATION_SEC = "multi_face_max_duration_sec"
FEATURE_MULTI_FACE_TIME_RATIO = "multi_face_time_ratio"
FEATURE_TOTAL_MONITORING_EVENTS = "total_monitoring_events"
FEATURE_EVENT_RATE_PER_MINUTE = "event_rate_per_minute"
FEATURE_EARLY_EXAM_EVENT_RATIO = "early_exam_event_ratio"
FEATURE_MID_EXAM_EVENT_RATIO = "mid_exam_event_ratio"
FEATURE_LATE_EXAM_EVENT_RATIO = "late_exam_event_ratio"
FEATURE_AVG_INTER_EVENT_INTERVAL_SEC = "avg_inter_event_interval_sec"
FEATURE_QUESTIONS_ANSWERED_RATIO = "questions_answered_ratio"
FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC = "attempt_duration_per_answered_question_sec"

FEATURE_NAMES: Tuple[str, ...] = (
    FEATURE_ATTEMPT_DURATION_SEC,
    FEATURE_ABSENCE_EVENT_COUNT,
    FEATURE_ABSENCE_TOTAL_DURATION_SEC,
    FEATURE_ABSENCE_MAX_DURATION_SEC,
    FEATURE_ABSENCE_AVG_DURATION_SEC,
    FEATURE_ABSENCE_TIME_RATIO,
    FEATURE_MULTI_FACE_EVENT_COUNT,
    FEATURE_MULTI_FACE_TOTAL_DURATION_SEC,
    FEATURE_MULTI_FACE_MAX_DURATION_SEC,
    FEATURE_MULTI_FACE_TIME_RATIO,
    FEATURE_TOTAL_MONITORING_EVENTS,
    FEATURE_EVENT_RATE_PER_MINUTE,
    FEATURE_EARLY_EXAM_EVENT_RATIO,
    FEATURE_MID_EXAM_EVENT_RATIO,
    FEATURE_LATE_EXAM_EVENT_RATIO,
    FEATURE_AVG_INTER_EVENT_INTERVAL_SEC,
    FEATURE_QUESTIONS_ANSWERED_RATIO,
    FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC,
)


def _parse_datetime(dt_val: Any) -> Optional[datetime]:
    """Parse datetime from datetime instance or ISO string."""
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        clean_str = dt_val.strip()
        try:
            return datetime.fromisoformat(clean_str)
        except ValueError:
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
            ):
                try:
                    return datetime.strptime(clean_str, fmt)
                except ValueError:
                    pass
    return None


def _parse_metadata(metadata: Any) -> Dict[str, Any]:
    """Safely extract dictionary metadata from JSON string or dict."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def extract_behavioral_features(
    attempt: Dict[str, Any],
    exam: Optional[Dict[str, Any]] = None,
    total_questions: Optional[int] = None,
    answers: Optional[List[Dict[str, Any]]] = None,
    monitoring_events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    """
    Stateless calculation engine that computes 18 standardized behavioral features.

    Args:
        attempt: Attempt dictionary containing started_at, submitted_at, status.
        exam: Optional exam metadata dictionary.
        total_questions: Optional total count of questions in the examination.
        answers: Optional list of saved answer dictionaries for the attempt.
        monitoring_events: Optional list of raw monitoring event dictionaries.

    Returns:
        Deterministic dictionary containing all 18 feature keys mapped to finite float values,
        rounded to 4 decimal places.
    """
    if not isinstance(attempt, dict):
        raise ValueError("Valid attempt dictionary is required.")

    started_at = _parse_datetime(attempt.get("started_at"))
    if started_at is None:
        raise ValueError("Attempt started_at timestamp is required and must be valid.")

    submitted_at = _parse_datetime(attempt.get("submitted_at"))
    if submitted_at is not None and submitted_at < started_at:
        submitted_at = started_at

    end_time = submitted_at if submitted_at is not None else started_at
    attempt_duration_sec = max(0.0, (end_time - started_at).total_seconds())

    # -------------------------------------------------------------------------
    # Parse & Normalize Monitoring Events
    # -------------------------------------------------------------------------
    raw_events = monitoring_events if monitoring_events is not None else []
    absence_durations: List[float] = []
    multi_face_durations: List[float] = []
    normalized_event_records: List[Tuple[datetime, float, str]] = []

    for ev in raw_events:
        if not isinstance(ev, dict):
            continue

        raw_ev_type = ev.get("event_type")
        if not raw_ev_type:
            continue
        ev_type = str(raw_ev_type).strip().upper()

        ev_ts = _parse_datetime(ev.get("event_timestamp"))
        if ev_ts is None:
            ev_ts = started_at

        # Clamp event timestamp within finalized attempt window
        if ev_ts < started_at:
            ev_ts = started_at
        elif ev_ts > end_time:
            ev_ts = end_time

        offset_sec = max(0.0, (ev_ts - started_at).total_seconds())
        meta = _parse_metadata(ev.get("event_metadata"))

        dur = meta.get("sustained_duration_sec")
        if dur is None or not isinstance(dur, (int, float)):
            dur = meta.get("threshold_sec", 0.0)
        try:
            dur_float = max(0.0, float(dur))
        except (ValueError, TypeError):
            dur_float = 0.0

        if ev_type == "FACE_ABSENT":
            absence_durations.append(dur_float)
            normalized_event_records.append((ev_ts, offset_sec, ev_type))
        elif ev_type == "MULTIPLE_FACES":
            multi_face_durations.append(dur_float)
            normalized_event_records.append((ev_ts, offset_sec, ev_type))

    # Sort normalized events chronologically by timestamp
    normalized_event_records.sort(key=lambda item: item[0])

    # -------------------------------------------------------------------------
    # Group 1: Visual Absence Dynamics
    # -------------------------------------------------------------------------
    absence_event_count = float(len(absence_durations))
    absence_total_duration_sec = float(sum(absence_durations))
    absence_max_duration_sec = float(max(absence_durations)) if absence_durations else 0.0
    absence_avg_duration_sec = (
        (absence_total_duration_sec / absence_event_count)
        if absence_event_count > 0.0
        else 0.0
    )
    absence_time_ratio = min(
        1.0,
        max(0.0, absence_total_duration_sec / max(attempt_duration_sec, 1.0)),
    )

    # -------------------------------------------------------------------------
    # Group 2: Visual Multi-Presence Dynamics
    # -------------------------------------------------------------------------
    multi_face_event_count = float(len(multi_face_durations))
    multi_face_total_duration_sec = float(sum(multi_face_durations))
    multi_face_max_duration_sec = float(max(multi_face_durations)) if multi_face_durations else 0.0
    multi_face_time_ratio = min(
        1.0,
        max(0.0, multi_face_total_duration_sec / max(attempt_duration_sec, 1.0)),
    )

    # -------------------------------------------------------------------------
    # Group 3: Event Frequency, Density & Temporal Distribution
    # -------------------------------------------------------------------------
    total_monitoring_events = float(len(normalized_event_records))
    # Clamped to at least 60.0s (1.0 minute) to avoid inflated rate on short attempts
    rate_denominator_minutes = max(attempt_duration_sec, 60.0) / 60.0
    event_rate_per_minute = total_monitoring_events / rate_denominator_minutes

    if total_monitoring_events == 0.0 or attempt_duration_sec <= 0.0:
        early_exam_event_ratio = 0.0
        mid_exam_event_ratio = 0.0
        late_exam_event_ratio = 0.0
    else:
        b1 = attempt_duration_sec / 3.0
        b2 = (2.0 * attempt_duration_sec) / 3.0
        early_count = sum(1 for _, off, _ in normalized_event_records if off < b1)
        mid_count = sum(1 for _, off, _ in normalized_event_records if b1 <= off < b2)
        late_count = sum(1 for _, off, _ in normalized_event_records if off >= b2)

        early_exam_event_ratio = min(1.0, max(0.0, early_count / total_monitoring_events))
        mid_exam_event_ratio = min(1.0, max(0.0, mid_count / total_monitoring_events))
        late_exam_event_ratio = min(1.0, max(0.0, late_count / total_monitoring_events))

    # Inter-event interval calculation
    if len(normalized_event_records) < 2:
        avg_inter_event_interval_sec = 0.0
    else:
        ts_list = [item[0] for item in normalized_event_records]
        intervals = [
            max(0.0, (t_next - t_curr).total_seconds())
            for t_curr, t_next in zip(ts_list[:-1], ts_list[1:])
        ]
        avg_inter_event_interval_sec = sum(intervals) / float(len(intervals))

    # -------------------------------------------------------------------------
    # Group 4: Assessment Engagement & Answering Activity
    # -------------------------------------------------------------------------
    ans_list = answers if answers is not None else []
    answered_count = sum(
        1
        for a in ans_list
        if a.get("selected_option") is not None
        and str(a.get("selected_option")).strip() != ""
    )

    q_count = total_questions
    if q_count is None and exam and exam.get("question_count"):
        q_count = exam.get("question_count")
    if q_count is None or q_count <= 0:
        q_count = max(len(ans_list), 1)

    questions_answered_ratio = min(
        1.0,
        max(0.0, float(answered_count) / float(max(q_count, 1))),
    )

    if answered_count == 0:
        attempt_duration_per_answered_question_sec = 0.0
    else:
        attempt_duration_per_answered_question_sec = attempt_duration_sec / float(answered_count)

    # -------------------------------------------------------------------------
    # Assemble & Sanitize All 18 Features
    # -------------------------------------------------------------------------
    raw_vector: Dict[str, float] = {
        FEATURE_ATTEMPT_DURATION_SEC: attempt_duration_sec,
        FEATURE_ABSENCE_EVENT_COUNT: absence_event_count,
        FEATURE_ABSENCE_TOTAL_DURATION_SEC: absence_total_duration_sec,
        FEATURE_ABSENCE_MAX_DURATION_SEC: absence_max_duration_sec,
        FEATURE_ABSENCE_AVG_DURATION_SEC: absence_avg_duration_sec,
        FEATURE_ABSENCE_TIME_RATIO: absence_time_ratio,
        FEATURE_MULTI_FACE_EVENT_COUNT: multi_face_event_count,
        FEATURE_MULTI_FACE_TOTAL_DURATION_SEC: multi_face_total_duration_sec,
        FEATURE_MULTI_FACE_MAX_DURATION_SEC: multi_face_max_duration_sec,
        FEATURE_MULTI_FACE_TIME_RATIO: multi_face_time_ratio,
        FEATURE_TOTAL_MONITORING_EVENTS: total_monitoring_events,
        FEATURE_EVENT_RATE_PER_MINUTE: event_rate_per_minute,
        FEATURE_EARLY_EXAM_EVENT_RATIO: early_exam_event_ratio,
        FEATURE_MID_EXAM_EVENT_RATIO: mid_exam_event_ratio,
        FEATURE_LATE_EXAM_EVENT_RATIO: late_exam_event_ratio,
        FEATURE_AVG_INTER_EVENT_INTERVAL_SEC: avg_inter_event_interval_sec,
        FEATURE_QUESTIONS_ANSWERED_RATIO: questions_answered_ratio,
        FEATURE_ATTEMPT_DURATION_PER_ANSWERED_QUESTION_SEC: attempt_duration_per_answered_question_sec,
    }

    sanitized_vector: Dict[str, float] = {}
    for name in FEATURE_NAMES:
        val = raw_vector[name]
        if not math.isfinite(val):
            val = 0.0
        sanitized_vector[name] = round(float(val), 4)

    return sanitized_vector
