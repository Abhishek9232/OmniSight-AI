"""
OmniSight-AI Machine Learning Input Contract & Validation Foundation (Phase 7).
Strictly decoupled, pure-Python mathematical validation layer.

Enforces the standardized 18-feature behavioral input contract defined in Phase 6
before any model inference, training, or preprocessing occurs.

Ethical & Architectural Boundaries:
- Event != Misconduct: Input vectors represent statistical behavioral telemetry,
  NOT accusations or guilt verdicts.
- Decoupled from Academic Performance: Zero dependency on grades, answer keys, or marks.
- Deterministic Ordering: Feature order is immutable and matches Phase 6 authoritative catalog.
- Zero Silent Repairs: Invalid or corrupt inputs fail fast with explicit exceptions.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Set, Tuple, Union

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore

from src.features.extractor import (
    FEATURE_NAMES,
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

# Semantic schema version for ML feature input contract
FEATURE_SCHEMA_VERSION: str = "1.0.0"

# Authoritative feature count and immutable ordering (reusing Phase 6 definition)
EXPECTED_FEATURE_COUNT: int = 18
ML_FEATURE_NAMES: Tuple[str, ...] = FEATURE_NAMES
ML_FEATURE_NAMES_SET: Set[str] = set(ML_FEATURE_NAMES)

# Features strictly bounded within [0.0, 1.0]
RATIO_FEATURE_NAMES: Tuple[str, ...] = (
    FEATURE_ABSENCE_TIME_RATIO,
    FEATURE_MULTI_FACE_TIME_RATIO,
    FEATURE_EARLY_EXAM_EVENT_RATIO,
    FEATURE_MID_EXAM_EVENT_RATIO,
    FEATURE_LATE_EXAM_EVENT_RATIO,
    FEATURE_QUESTIONS_ANSWERED_RATIO,
)
RATIO_FEATURE_INDICES: Tuple[int, ...] = tuple(
    i for i, name in enumerate(ML_FEATURE_NAMES) if name in RATIO_FEATURE_NAMES
)

# All 18 features are non-negative by definition (counts, durations, rates, intervals, ratios)
NON_NEGATIVE_FEATURE_NAMES: Tuple[str, ...] = ML_FEATURE_NAMES


class MLContractValidationError(ValueError):
    """Raised when an input feature vector or dictionary violates the Phase 7 ML contract."""
    pass


@dataclass(frozen=True)
class ValidatedFeatureVector:
    """
    Immutable container representing a validated 18-dimensional behavioral feature vector.
    Guarantees deterministic feature ordering and valid numerical ranges.
    """
    values: Tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple):
            object.__setattr__(self, "values", tuple(self.values))
        if len(self.values) != EXPECTED_FEATURE_COUNT:
            raise MLContractValidationError(
                f"ValidatedFeatureVector requires exactly {EXPECTED_FEATURE_COUNT} values, got {len(self.values)}."
            )

    @property
    def feature_names(self) -> Tuple[str, ...]:
        """Return the immutable sequence of feature names corresponding to indices."""
        return ML_FEATURE_NAMES

    def to_tuple(self) -> Tuple[float, ...]:
        """Export as immutable tuple of floats."""
        return self.values

    def to_list(self) -> List[float]:
        """Export as standard Python list of floats."""
        return list(self.values)

    def to_dict(self) -> Dict[str, float]:
        """Export as dictionary mapping authoritative feature names to float values."""
        return dict(zip(ML_FEATURE_NAMES, self.values))

    def to_numpy(self) -> "np.ndarray":
        """Export as 1-dimensional float64 NumPy array of shape (18,)."""
        if np is None:
            raise RuntimeError("NumPy is required to convert feature vector to numpy array.")
        return np.array(self.values, dtype=np.float64)

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> float:
        return self.values[index]


def _validate_numeric_value(val: Any, feature_name: str) -> float:
    """
    Validates that a single value is a finite, numeric float/int (excluding bool)
    and complies with non-negativity and ratio constraints.
    """
    if isinstance(val, bool):
        raise MLContractValidationError(
            f"Feature '{feature_name}' must be numeric (int or float), got boolean: {val}."
        )

    if not isinstance(val, (int, float)):
        # Support numpy numeric scalar types if numpy is available
        if np is not None and isinstance(val, (np.floating, np.integer)):
            val = float(val)
        else:
            raise MLContractValidationError(
                f"Feature '{feature_name}' must be numeric (int or float), got {type(val).__name__} ({val!r})."
            )

    float_val = float(val)

    if math.isnan(float_val):
        raise MLContractValidationError(f"Feature '{feature_name}' contains NaN (not a number).")

    if math.isinf(float_val):
        raise MLContractValidationError(f"Feature '{feature_name}' contains infinite value: {float_val}.")

    if float_val < 0.0:
        raise MLContractValidationError(
            f"Feature '{feature_name}' cannot be negative, got {float_val}."
        )

    if feature_name in RATIO_FEATURE_NAMES and float_val > 1.0:
        raise MLContractValidationError(
            f"Ratio feature '{feature_name}' must be within [0.0, 1.0], got {float_val}."
        )

    return float_val


def validate_feature_dict(features: Mapping[str, Any]) -> ValidatedFeatureVector:
    """
    Validates a dictionary mapping feature names to numerical values.

    Invariants enforced:
    - Input must be a mapping (dict).
    - Exactly 18 features must be present.
    - Zero missing features from ML_FEATURE_NAMES.
    - Zero unexpected/extra features.
    - All values must be numeric, finite, non-negative.
    - Ratio features must be within [0.0, 1.0].

    Returns:
        ValidatedFeatureVector with deterministically ordered values.
    """
    if not isinstance(features, Mapping):
        raise MLContractValidationError(
            f"Expected a mapping (dict) of features, got {type(features).__name__}."
        )

    provided_keys = set(features.keys())

    missing = [name for name in ML_FEATURE_NAMES if name not in provided_keys]
    if missing:
        raise MLContractValidationError(
            f"Missing {len(missing)} required feature(s): {missing}."
        )

    unexpected = sorted(provided_keys - ML_FEATURE_NAMES_SET)
    if unexpected:
        raise MLContractValidationError(
            f"Unexpected feature(s) provided: {unexpected}."
        )

    if len(features) != EXPECTED_FEATURE_COUNT:
        raise MLContractValidationError(
            f"Expected exactly {EXPECTED_FEATURE_COUNT} features, got {len(features)}."
        )

    validated_values = []
    for name in ML_FEATURE_NAMES:
        validated_values.append(_validate_numeric_value(features[name], name))

    return ValidatedFeatureVector(values=tuple(validated_values))


def validate_feature_vector(vector: Sequence[Any]) -> ValidatedFeatureVector:
    """
    Validates an ordered sequence or 1D array of 18 feature values.

    Invariants enforced:
    - Exactly 18 elements.
    - All values must be numeric, finite, non-negative.
    - Ratio indices must be within [0.0, 1.0].

    Returns:
        ValidatedFeatureVector with verified values.
    """
    if isinstance(vector, (Mapping, str, bytes)):
        raise MLContractValidationError(
            f"Expected a sequence of 18 feature values, got {type(vector).__name__}."
        )

    if np is not None and isinstance(vector, np.ndarray):
        if vector.ndim != 1:
            raise MLContractValidationError(
                f"Feature array must be 1-dimensional, got shape {vector.shape}."
            )
        vector_seq = list(vector)
    elif isinstance(vector, Sequence):
        vector_seq = list(vector)
    else:
        raise MLContractValidationError(
            f"Expected a sequence of 18 feature values, got {type(vector).__name__}."
        )

    if len(vector_seq) != EXPECTED_FEATURE_COUNT:
        raise MLContractValidationError(
            f"Expected exactly {EXPECTED_FEATURE_COUNT} feature values, got {len(vector_seq)}."
        )

    validated_values = []
    for idx, (val, name) in enumerate(zip(vector_seq, ML_FEATURE_NAMES)):
        validated_values.append(_validate_numeric_value(val, name))

    return ValidatedFeatureVector(values=tuple(validated_values))


def validate_features(data: Union[Mapping[str, Any], Sequence[Any]]) -> ValidatedFeatureVector:
    """
    Universal entrypoint for validating Phase 7 behavioral features.
    Accepts either a named feature dictionary or an ordered 18-element sequence.
    """
    if isinstance(data, Mapping):
        return validate_feature_dict(data)
    elif isinstance(data, (list, tuple)) or (np is not None and isinstance(data, np.ndarray)):
        return validate_feature_vector(data)
    else:
        raise MLContractValidationError(
            f"Input must be a feature dict or an 18-element sequence, got {type(data).__name__}."
        )
