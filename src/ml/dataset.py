"""
OmniSight-AI Machine Learning Dataset & Feature Matrix Assembly Layer (Phase 7).
Converts validated Phase 6 behavioral feature vectors into a deterministic feature matrix:

    X in R^(n x 18)

Core Architectural & Ethical Invariants:
- Row-to-Attempt Mapping: Preserves row_index -> attempt_id mapping strictly as metadata.
- attempt_id Excluded from X: attempt_id is NEVER included as an ML feature.
- Authoritative Ordering: Column order is immutable and matches ML_FEATURE_NAMES exactly.
- Validation Guarantee: Every row is validated through the Phase 7 contract layer.
- Zero Silent Repairs: Never silently impute, drop, scale, or normalize values.
- Flexible Cohort Size: Explicitly supports zero, one, or multiple attempts without
  enforcing an arbitrary minimum dataset size (deferred to empirical phase).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

from src.database.connection import get_connection
from src.ml.contract import (
    EXPECTED_FEATURE_COUNT,
    ML_FEATURE_NAMES,
    MLContractValidationError,
    ValidatedFeatureVector,
    validate_feature_dict,
)


@dataclass(frozen=True)
class MLDataset:
    """
    Immutable representation of an assembled ML feature dataset.

    Attributes:
        attempt_ids: Tuple of attempt IDs corresponding to each row in the matrix.
        feature_names: Authoritative tuple of 18 feature names.
        matrix: 2D tuple of shape (n, 18) containing validated float64 values.
    """
    attempt_ids: Tuple[int, ...]
    feature_names: Tuple[str, ...]
    matrix: Tuple[Tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_ids, tuple):
            object.__setattr__(self, "attempt_ids", tuple(self.attempt_ids))
        if not isinstance(self.feature_names, tuple):
            object.__setattr__(self, "feature_names", tuple(self.feature_names))
        if not isinstance(self.matrix, tuple):
            object.__setattr__(self, "matrix", tuple(tuple(row) for row in self.matrix))

        n_rows = len(self.attempt_ids)
        if len(self.matrix) != n_rows:
            raise MLContractValidationError(
                f"Row count mismatch: {n_rows} attempt_ids provided, but matrix has {len(self.matrix)} rows."
            )

        if len(self.feature_names) != EXPECTED_FEATURE_COUNT:
            raise MLContractValidationError(
                f"Feature count mismatch: expected {EXPECTED_FEATURE_COUNT} feature names, got {len(self.feature_names)}."
            )

        for i, row in enumerate(self.matrix):
            if len(row) != EXPECTED_FEATURE_COUNT:
                raise MLContractValidationError(
                    f"Row {i} (attempt_id={self.attempt_ids[i]}) has {len(row)} features; expected {EXPECTED_FEATURE_COUNT}."
                )

    @property
    def n_rows(self) -> int:
        """Number of valid attempts (samples) in the dataset."""
        return len(self.attempt_ids)

    @property
    def n_features(self) -> int:
        """Number of behavioral features (always 18)."""
        return EXPECTED_FEATURE_COUNT

    @property
    def shape(self) -> Tuple[int, int]:
        """Dimensions of the feature matrix (n_samples, 18)."""
        return (len(self.attempt_ids), EXPECTED_FEATURE_COUNT)

    @property
    def is_empty(self) -> bool:
        """True if the dataset contains 0 attempts."""
        return len(self.attempt_ids) == 0

    def to_numpy(self) -> "np.ndarray":
        """
        Export feature matrix X as a 2D float64 NumPy array of shape (n, 18).
        If n=0, returns an empty array of shape (0, 18).
        """
        if np is None:
            raise RuntimeError("NumPy is required to export dataset to numpy array.")
        if self.is_empty:
            return np.empty((0, EXPECTED_FEATURE_COUNT), dtype=np.float64)
        return np.array(self.matrix, dtype=np.float64)

    def to_dict(self) -> Dict[str, Any]:
        """
        Export dataset as a dictionary containing metadata and 2D data list.
        """
        return {
            "attempt_ids": list(self.attempt_ids),
            "feature_names": list(self.feature_names),
            "data": [list(row) for row in self.matrix],
            "shape": self.shape,
        }

    def to_records(self) -> List[Dict[str, Any]]:
        """
        Export as a list of dictionaries with attempt_id and feature key-value pairs.
        """
        records = []
        for att_id, row in zip(self.attempt_ids, self.matrix):
            rec = {"attempt_id": att_id}
            rec.update(dict(zip(self.feature_names, row)))
            records.append(rec)
        return records

    def get_row(self, index: int) -> ValidatedFeatureVector:
        """Retrieve the i-th row as a ValidatedFeatureVector."""
        if index < 0 or index >= len(self.matrix):
            raise IndexError(f"Dataset index {index} out of range (n_rows={self.n_rows}).")
        return ValidatedFeatureVector(values=self.matrix[index])

    def get_row_by_attempt_id(self, attempt_id: int) -> ValidatedFeatureVector:
        """Retrieve the feature vector for a specific attempt_id."""
        try:
            idx = self.attempt_ids.index(attempt_id)
            return self.get_row(idx)
        except ValueError:
            raise KeyError(f"attempt_id {attempt_id} not found in MLDataset.")

    def __len__(self) -> int:
        return len(self.attempt_ids)

    def __getitem__(self, index: int) -> Tuple[float, ...]:
        return self.matrix[index]

    def __repr__(self) -> str:
        return f"<MLDataset: shape={self.shape}, attempts={list(self.attempt_ids)}>"


def assemble_feature_matrix(
    attempts_data: Union[
        Mapping[int, Mapping[str, Any]],
        Sequence[Tuple[int, Mapping[str, Any]]],
        Sequence[Mapping[str, Any]],
    ],
) -> MLDataset:
    """
    Pure Python assembly function that converts a collection of attempt feature records
    into a deterministic MLDataset with shape (n, 18).

    Accepts:
    1. Mapping: {attempt_id: feature_dict, ...}
    2. Sequence of tuples: [(attempt_id, feature_dict), ...]
    3. Sequence of dicts: [{"attempt_id": 101, ...18 features...}, ...]

    Enforces:
    - Every attempt_id must be a positive integer.
    - Zero duplicate attempt_ids.
    - Every row is validated through validate_feature_dict.
    - attempt_id is strictly preserved as metadata and never enters the matrix.
    - Fails fast on any missing, unexpected, non-numeric, NaN, inf, ratio, or negative violation.
    - Zero silent drops or imputations.
    """
    if attempts_data is None:
        raise MLContractValidationError("attempts_data cannot be None.")

    # Normalize into an ordered sequence of (attempt_id, raw_feature_dict)
    normalized_items: List[Tuple[int, Mapping[str, Any]]] = []

    if isinstance(attempts_data, Mapping):
        for att_id, feat_dict in attempts_data.items():
            normalized_items.append((att_id, feat_dict))
    elif isinstance(attempts_data, Sequence) and not isinstance(attempts_data, (str, bytes)):
        for item in attempts_data:
            if isinstance(item, tuple) and len(item) == 2:
                normalized_items.append((item[0], item[1]))
            elif isinstance(item, Mapping):
                if "attempt_id" not in item:
                    raise MLContractValidationError(
                        "Attempt record mapping must include 'attempt_id' key."
                    )
                att_id = item["attempt_id"]
                feat_dict = {k: v for k, v in item.items() if k != "attempt_id"}
                normalized_items.append((att_id, feat_dict))
            else:
                raise MLContractValidationError(
                    f"Unsupported attempt item format: {type(item).__name__}. "
                    f"Expected tuple of (attempt_id, feature_dict) or dict with 'attempt_id'."
                )
    else:
        raise MLContractValidationError(
            f"Unsupported attempts_data type: {type(attempts_data).__name__}. "
            f"Expected Mapping or Sequence."
        )

    # Empty cohort handling (shape (0, 18))
    if not normalized_items:
        return MLDataset(
            attempt_ids=(),
            feature_names=ML_FEATURE_NAMES,
            matrix=(),
        )

    seen_ids: Set[int] = set()
    attempt_id_list: List[int] = []
    matrix_rows: List[Tuple[float, ...]] = []

    for att_id, feat_dict in normalized_items:
        # Validate attempt_id type and value
        if isinstance(att_id, bool) or not isinstance(att_id, int) or att_id <= 0:
            raise MLContractValidationError(
                f"Valid attempt_id must be a positive integer, got: {att_id!r} ({type(att_id).__name__})."
            )

        if att_id in seen_ids:
            raise MLContractValidationError(
                f"Duplicate attempt_id detected in dataset: {att_id}."
            )
        seen_ids.add(att_id)

        if not isinstance(feat_dict, Mapping):
            raise MLContractValidationError(
                f"Features for attempt {att_id} must be a dictionary/mapping, got {type(feat_dict).__name__}."
            )

        # Ensure attempt_id is excluded from feature keys before contract validation
        if "attempt_id" in feat_dict:
            rec_id = feat_dict["attempt_id"]
            if rec_id != att_id:
                raise MLContractValidationError(
                    f"attempt_id mismatch for attempt: key={att_id} vs dictionary 'attempt_id'={rec_id}."
                )
            clean_dict = {k: v for k, v in feat_dict.items() if k != "attempt_id"}
        else:
            clean_dict = feat_dict

        # Validate with Phase 7 feature contract (fails fast on any violation)
        validated_vector = validate_feature_dict(clean_dict)

        matrix_rows.append(validated_vector.to_tuple())
        attempt_id_list.append(att_id)

    return MLDataset(
        attempt_ids=tuple(attempt_id_list),
        feature_names=ML_FEATURE_NAMES,
        matrix=tuple(matrix_rows),
    )


def assemble_from_database(
    exam_id: Optional[int] = None,
    attempt_ids: Optional[Sequence[int]] = None,
    connection=None,
) -> MLDataset:
    """
    Retrieve persisted behavioral features from MySQL for completed attempts
    and assemble them into a validated MLDataset.

    Strict Invariants:
    - Only attempts with terminal status ('SUBMITTED' or 'EVALUATED') are eligible.
    - If any explicitly requested attempt is 'IN_PROGRESS', strictly raises ValueError.
    - If any explicitly requested attempt does not exist, strictly raises ValueError.
    - Pure assembly logic is reused via assemble_feature_matrix.
    """
    owns_conn = connection is None
    conn = connection or get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)

        # 1. If explicit attempt_ids are provided, check existence and terminal status
        if attempt_ids is not None:
            if not attempt_ids:
                return MLDataset(
                    attempt_ids=(),
                    feature_names=ML_FEATURE_NAMES,
                    matrix=(),
                )

            # Validate attempt_ids format
            for aid in attempt_ids:
                if isinstance(aid, bool) or not isinstance(aid, int) or aid <= 0:
                    raise ValueError(f"Valid attempt_id must be a positive integer, got: {aid!r}.")

            format_strings = ",".join(["%s"] * len(attempt_ids))
            cursor.execute(
                f"SELECT attempt_id, status FROM exam_attempts WHERE attempt_id IN ({format_strings});",
                tuple(attempt_ids),
            )
            found_attempts = {row["attempt_id"]: row["status"] for row in (cursor.fetchall() or [])}

            for aid in attempt_ids:
                if aid not in found_attempts:
                    raise ValueError(f"Exam attempt with ID {aid} does not exist.")
                st = found_attempts[aid]
                if st == "IN_PROGRESS":
                    raise ValueError(
                        f"Cannot assemble ML dataset for attempt {aid}: Attempt is currently IN_PROGRESS. "
                        f"Only finalized attempts ('SUBMITTED' or 'EVALUATED') are eligible."
                    )
                if st not in {"SUBMITTED", "EVALUATED"}:
                    raise ValueError(
                        f"Cannot assemble ML dataset for attempt {aid}: Attempt has non-terminal status '{st}'."
                    )

        # 2. Fetch features for eligible terminal attempts
        query = """
            SELECT a.attempt_id, bf.feature_name, bf.feature_value
            FROM exam_attempts a
            JOIN behavioral_features bf ON a.attempt_id = bf.attempt_id
            WHERE a.status IN ('SUBMITTED', 'EVALUATED')
        """
        params: List[Any] = []
        if exam_id is not None:
            query += " AND a.exam_id = %s"
            params.append(exam_id)
        if attempt_ids is not None:
            format_strings = ",".join(["%s"] * len(attempt_ids))
            query += f" AND a.attempt_id IN ({format_strings})"
            params.extend(attempt_ids)
        query += " ORDER BY a.attempt_id ASC, bf.feature_name ASC;"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []

        grouped: Dict[int, Dict[str, float]] = {}
        for row in rows:
            aid = row["attempt_id"]
            if aid not in grouped:
                grouped[aid] = {}
            grouped[aid][row["feature_name"]] = float(row["feature_value"])

        # If specific attempt_ids were requested, verify feature completeness
        if attempt_ids is not None:
            for aid in attempt_ids:
                if aid not in grouped:
                    raise ValueError(f"No behavioral features found in database for attempt {aid}.")

        # Maintain exact requested ordering if attempt_ids provided
        if attempt_ids is not None:
            ordered_grouped = {aid: grouped[aid] for aid in attempt_ids}
        else:
            ordered_grouped = grouped

        return assemble_feature_matrix(ordered_grouped)

    finally:
        if cursor:
            cursor.close()
        if owns_conn and conn and conn.is_connected():
            conn.close()
