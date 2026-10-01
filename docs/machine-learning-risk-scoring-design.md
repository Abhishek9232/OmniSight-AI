# Machine Learning Baseline & Behavioral Risk Scoring Design

## 1. Purpose & Scope

This document establishes the methodological, architectural, and operational design for **Phase 7 — Machine Learning Baseline & Behavioral Risk Scoring** within OmniSight-AI.

Phase 7 ingests the standardized 18-dimensional behavioral feature vector generated in Phase 6 for completed examination attempts and applies an **unsupervised baseline anomaly detection model** to produce an explainable, evidence-backed **Behavioral Risk Score** to aid human proctors and educators.

---

## 2. Core Architectural & Ethical Boundaries

### 2.1 The Guilt & Verdict Boundary
The system enforces a strict operational distinction:

$$\mathbf{ML\ Risk\ Assessment} \neq \mathbf{Automatic\ Misconduct\ Determination}$$

1. **Never Declare Guilt**: The system shall **never** produce a definitive verdict such as *"Student cheated"*, *"Cheating detected"*, *"Guilty"*, or *"Academic dishonesty confirmed"*.
2. **Core Invariant**:
   $$\mathbf{Event} \neq \mathbf{Misconduct} \quad \text{and} \quad \mathbf{Risk\ Score} \neq \mathbf{Misconduct\ Verdict}$$
3. **Human-in-the-Loop**: All outputs produced by the machine learning subsystem are advisory indicators. Final determinations of academic integrity remain exclusively the responsibility of human educators and authorized review committees.

### 2.2 Decoupling from Academic Performance
Behavioral risk assessment is strictly decoupled from examination performance. The ML pipeline has zero access to:
- Question correctness (`answers.is_correct`).
- Total or obtained examination marks (`results.total_marks`, `results.obtained_marks`).
- Academic percentage (`results.percentage`).
- Authoritative answer keys.

A student who scores 100% and a student who scores 20% are evaluated using identical behavioral feature definitions.

### 2.3 Runtime Pipeline Isolation
Phase 7 is strictly isolated from the live examination and submission pipeline:
- Active frame capture and proctoring state tracking (`ProctoringSession`) remain completely independent of ML execution.
- Student examination submission (`submit_attempt()`) and grading evaluation (`evaluate_attempt()`) shall **never** block on, invoke, or depend upon ML inference.
- ML scoring is executed as an asynchronous post-submission or on-demand administrative service.

### 2.4 Empirical Honesty & Anti-Fabrication Rule
In accordance with academic standards and Section 11 of `AGENTS.md`:
- We do **not** invent unavailable datasets, artificial labels, or fabricated performance metrics (e.g., claiming 99% accuracy on unverified data).
- Real-world proctoring misconduct datasets with ground-truth cheating labels are ethically and legally restricted (FERPA/GDPR) and are not publicly available.
- Therefore, the baseline methodology is fundamentally **unsupervised**, treating anomalous behavior as statistical divergence from typical session patterns rather than binary classification of guilt.

---

## 3. Current State, Approved Design, and Deferred Work

To maintain project discipline, capabilities are classified into three distinct categories:

| Status | Components / Capabilities |
|:---|:---|
| **Current Implemented Capabilities** | • Phase 1–4: Student/Teacher authentication, question management, timer, navigation, submission, evaluation, student scorecard, teacher analytics.<br>• Phase 5: Webcam face detection (`HaarCascadeDetector`), temporal state tracker (`FACE_ABSENT`, `MULTIPLE_FACES`), ~1 FPS sampling, 20s cooldowns, active exam proctoring integration.<br>• Phase 6: Deterministic 18-feature extraction pipeline (`src/features/extractor.py`), DB persistence service (`src/features/service.py`), idempotent batch transactions, terminal state guards (`SUBMITTED`/`EVALUATED`). |
| **Approved Design (Phase 7 Scope)** | • Complete 18-feature input contract & validation.<br>• Unsupervised **Isolation Forest** baseline model.<br>• Raw anomaly score semantics (statistical divergence, NOT cheating probability).<br>• Explainability framework separating concrete evidence from statistical inference.<br>• Advisory Behavioral Risk Score representation.<br>• No database schema change required at design stage; persistence mapping to `integrity_assessments` to be validated during implementation.<br>• Evaluation framework tailored for unlabelled behavioral data (distribution, spread, stability). |
| **Future / Deferred Work** | • Exact mathematical calibration method from raw anomaly score to calibrated risk score.<br>• Exact numerical risk-band thresholds (e.g., Low / Moderate / High cutoffs).<br>• Minimum required dataset size for stable baseline fitting.<br>• Contamination parameter tuning and empirical optimization.<br>• Final feature preprocessing and scaling strategy.<br>• Final Isolation Forest hyperparameter tuning.<br>• Permanent model artifact storage location and packaging format.<br>• Formal human-review labeling protocol for collecting ground truth.<br>• Supervised model comparison (Logistic Regression, Decision Trees, Random Forests) once verified human labels exist. |

---

## 4. End-to-End System Flow

The end-to-end processing pipeline from finalized examination attempt to human proctor review follows a unidirectional, verifiable sequence:

```
┌────────────────────────────────────────────────────────┐
│               Completed Exam Attempt                   │
│         (status: SUBMITTED or EVALUATED)               │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         Phase 6: 18 Behavioral Features Extractor       │
│     (attempt duration, event counts, ratios, thirds)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Feature Validation                   │
│   (18 dimensions, finite values, non-empty metadata)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             18-Dimensional Feature Vector              │
│                  x ∈ ℝ¹⁸ (Fixed Order)                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Isolation Forest Baseline                │
│    (Unsupervised anomaly tree path-length scoring)     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Raw Anomaly Signal                   │
│          s(x) ∈ [-1.0, 1.0] (statistical divergence)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Risk Score Calibration                 │
│         (Mapping to normalized [0.0, 1.0] scale)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                       Risk Band                        │
│            (Advisory Category: Low / Med / High)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                    Evidence Mapping                    │
│    (Correlate score with timestamped monitoring logs)  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Human Review                       │
│    (Teacher/Proctor inspects timeline & video context) │
└────────────────────────────────────────────────────────┘
```

---

## 5. Feature Input Contract

Phase 7 consumes the 18-feature behavioral catalog defined by [`src/features/extractor.py`](file:///C:/Users/user/OneDrive/Desktop/my%20final%20year%20project/Omni-sight-AI/src/features/extractor.py). The feature order is immutable across training, inference, and persistence.

### 5.1 Immutable Feature Catalog (`v1.0.0`)
1. `attempt_duration_sec`: Total elapsed attempt duration in seconds ($\ge 0$).
2. `absence_event_count`: Number of sustained face absence events ($\ge 0$).
3. `absence_total_duration_sec`: Total cumulative duration of face absence ($\ge 0$).
4. `absence_max_duration_sec`: Maximum single face absence duration ($\ge 0$).
5. `absence_avg_duration_sec`: Average duration of face absence events ($\ge 0$).
6. `absence_time_ratio`: Ratio of absence time to attempt duration ($\in [0.0, 1.0]$).
7. `multi_face_event_count`: Number of sustained multiple-face events ($\ge 0$).
8. `multi_face_total_duration_sec`: Total cumulative duration of multiple-face events ($\ge 0$).
9. `multi_face_max_duration_sec`: Maximum single multiple-face event duration ($\ge 0$).
10. `multi_face_time_ratio`: Ratio of multiple-face time to attempt duration ($\in [0.0, 1.0]$).
11. `total_monitoring_events`: Sum of all sustained monitoring events ($\ge 0$).
12. `event_rate_per_minute`: Monitoring events per minute of attempt time ($\ge 0$).
13. `early_exam_event_ratio`: Proportion of monitoring events in the first third ($\in [0.0, 1.0]$).
14. `mid_exam_event_ratio`: Proportion of monitoring events in the middle third ($\in [0.0, 1.0]$).
15. `late_exam_event_ratio`: Proportion of monitoring events in the final third ($\in [0.0, 1.0]$).
16. `avg_inter_event_interval_sec`: Mean elapsed time between consecutive event starts ($\ge 0$).
17. `questions_answered_ratio`: Answered questions divided by total exam questions ($\in [0.0, 1.0]$).
18. `attempt_duration_per_answered_question_sec`: Net attempt duration divided by answered questions count ($\ge 0$).

### 5.2 Input Validation Invariants
Prior to model evaluation, the input vector $\vec{x}$ must satisfy:
1. **Length Invariant**: $\text{len}(\vec{x}) = 18$ exactly.
2. **Type Invariant**: All elements must be convertible to 64-bit floating point numbers (`float64`).
3. **Finiteness Invariant**: $\forall x_i \in \vec{x},\ \neg\text{isnan}(x_i) \land \neg\text{isinf}(x_i)$.
4. **Boundary Invariant**: All ratio features ($i \in \{5, 9, 12, 13, 14, 16\}$) must satisfy $0.0 \le x_i \le 1.0$.

Any validation failure immediately raises `ValueError`, preventing corrupt or out-of-spec vectors from reaching the model.

---

## 6. Unsupervised Baseline: Isolation Forest

### 6.1 Rationale as an Academic Baseline
In the absence of ethically verified, large-scale ground-truth cheating datasets, unsupervised anomaly detection is the most scientifically sound starting point.

We select **Isolation Forest** as the initial baseline algorithm because:
- It isolates anomalies directly by randomly partitioning feature space rather than measuring distance or density profiles.
- It is computationally efficient ($O(n \log n)$ training, $O(n)$ inference).
- It handles mixed scales and multi-modal distributions effectively.
- It provides a standardized mathematical foundation without claiming unjustified algorithmic superiority.

*Academic Disclaimer*: Isolation Forest is specified strictly as a recognized unsupervised **baseline**. We do **not** claim that it is scientifically proven superior to all other anomaly detection or classification algorithms.

### 6.2 Raw Anomaly Score Semantics
The raw output from Isolation Forest represents the average path length required to isolate a sample across an ensemble of isolation trees.
- Samples with shorter path lengths are easier to isolate and are identified as statistical outliers.
- Samples with deeper path lengths represent typical, clustered behavior.

#### Critical Semantic Restriction:
The raw Isolation Forest output must **NOT** be interpreted as:
- A probability of cheating.
- A probability of misconduct.
- A degree of certainty that dishonesty occurred.

The score represents solely:
$$\mathbf{Degree\ of\ statistical\ divergence\ from\ typical\ examination\ behavior}$$

---

## 7. Risk Score Calibration & Advisory Bands

### 7.1 Calibration Strategy (Deferred Until Justified)
To make the raw anomaly signal interpretable to educators, the raw score will eventually be calibrated into a standardized scale (e.g., $0.0 \text{ to } 1.0$ or $0 \text{ to } 100$).

However, **the exact mathematical calibration method is intentionally deferred** until a representative baseline cohort of examination attempts has been collected and analyzed. Potential calibration approaches include:
- Min-Max scaling against empirical cohort boundaries.
- Sigmoid / logistic mapping.
- Empirical Cumulative Distribution Function (ECDF) percentile rank.

### 7.2 Advisory Risk Bands (Non-Frozen)
For preliminary UI communication, risk scores may be grouped into three advisory tiers:
- **Low Risk**: Behavior aligns with typical examination cohort profiles.
- **Moderate Risk**: Moderate behavioral variance or minor event clustering observed.
- **High Risk**: Substantial statistical divergence from typical session patterns.

#### Explicit Guardrail on Thresholds:
We do **NOT** permanently lock arbitrary cutoffs such as:
- $\text{Low} = [0.00, 0.39]$
- $\text{Moderate} = [0.40, 0.69]$
- $\text{High} = [0.70, 1.00]$

These figures represent illustrative guidelines only. Fixed numerical thresholds must not be frozen into the system architecture until justified by empirical distribution analysis and faculty input.

---

## 8. Evaluation Strategy

Because ground-truth labels are unavailable, conventional supervised evaluation metrics are invalid at this stage.

### 8.1 Current Evaluation Strategy (Unsupervised / Label-Free)
The initial ML baseline must be evaluated using descriptive statistical and behavioral criteria:

1. **Score Distribution Analysis**:
   - Assess normality, variance, skewness, and kurtosis of anomaly scores across test cohorts.
   - Verify that typical attempts cluster tightly around normal scores rather than scattering unpredictably.
2. **Variability & Separation Verification**:
   - Measure separation distance between synthetic "clean" sessions (zero events) and "extreme" sessions (continuous absences, multiple faces).
3. **Behavioral Evidence Inspection**:
   - Manually audit high-scoring sessions against their underlying `monitoring_events` timestamps to verify that high scores correlate with observable, verifiable telemetry.
4. **Controlled Scenario Testing**:
   - Evaluate model outputs against predefined, deterministic synthetic boundary cases (e.g., 0 events, 1 event, clustered events, uniform events).
5. **Stability & Determinism**:
   - Verify identical output scores across repeated runs using deterministic random-state configuration.

### 8.2 Explicit Metric Prohibition
In the absence of reliable ground-truth labels, the project shall **NOT** claim:
- Accuracy
- Precision
- Recall / Sensitivity
- F1-Score
- ROC-AUC / PR-AUC

Claiming these metrics without independent, verified ground-truth labels is academically invalid and prohibited.

### 8.3 Future Supervised Evaluation Strategy
If verified human-reviewed annotations become available in a future phase:
- A protocol for double-blind human proctor review will be established.
- Sessions will be annotated as `Typical` vs `Flagged for Investigation`.
- Supervised algorithms (Logistic Regression, Decision Trees, Random Forests) can then be benchmarked against the Isolation Forest baseline using standard cross-validation, Precision-Recall curves, and Confusion Matrices.

---

## 9. Explainability & Human-Facing Communication

### 9.1 The Two-Layer Explainability Boundary
To maintain absolute transparency and prevent unwarranted automation bias, the system strictly separates:

| Layer A: Concrete Behavioral Evidence | Layer B: Statistical Anomaly Output |
|:---|:---|
| • Objective, timestamped, verifiable facts.<br>• Example: *"3 absence events totaling 42 seconds."*<br>• Example: *"Event at 10:14:22 lasting 8 seconds."*<br>• Zero machine learning interpretation. | • Statistical inference produced by the algorithm.<br>• Example: *"Behavioral Risk Score: 0.72."*<br>• Example: *"Session placed in 90th percentile of cohort divergence."*<br>• Probabilistic anomaly representation. |

These two layers **must never be conflated**. The UI must never claim that the model "detected cheating"; it must present the model score alongside the concrete event timeline so the human reviewer can independently evaluate the context.

### 9.2 Teacher-Facing Communication Contract
The review interface will present:
1. **Behavioral Risk Score**: The normalized numerical score.
2. **Advisory Risk Tier**: Low, Moderate, or High (advisory only).
3. **Primary Contributing Signals**: Top features contributing to the divergence (e.g., elevated `absence_total_duration_sec`, high `event_rate_per_minute`).
4. **Chronological Event Timeline**: Timestamped log of sustained proctoring events.
5. **Mandatory Advisory Disclaimer**:
   > *"This Behavioral Risk Score is an advisory index generated by statistical anomaly modeling to assist faculty review. It does not constitute proof of cheating or academic dishonesty. All decisions must be based on human inspection of the session evidence."*

---

## 10. Database Persistence & Storage Strategy

### 10.1 Zero Schema Changes & Persistence Strategy
No database schema change is required at the current design stage. The persistence mapping to `integrity_assessments` will be validated during implementation. Runtime integration remains deferred.

The candidate table schema defined in [`database/schema.sql`](file:///C:/Users/user/OneDrive/Desktop/my%20final%20year%20project/Omni-sight-AI/database/schema.sql#L118-L129) is:

```sql
CREATE TABLE IF NOT EXISTS integrity_assessments (
    assessment_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    risk_score DECIMAL(6,3) NULL,
    risk_category VARCHAR(30) NULL,
    model_name VARCHAR(100) NULL,
    assessment_metadata JSON NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_integrity_assessments_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 10.2 Candidate Column Mapping (Subject to Validation)
Candidate column mapping to be validated during implementation:
- `attempt_id`: Foreign key referencing `exam_attempts(attempt_id)`.
- `risk_score`: Calibrated numerical score (e.g., `0.742` or `74.200`).
- `risk_category`: Advisory tier string (`'LOW'`, `'MODERATE'`, `'HIGH'`).
- `model_name`: Versioned model identifier (e.g., `'IsolationForest_v1.0'`).
- `assessment_metadata`: JSON payload storing feature contributions, raw anomaly score, schema version, and advisory disclaimers.
- `created_at`: Generation timestamp.

### 10.3 Transactional Idempotency
To ensure repeatability and prevent orphaned or duplicate records upon persistence:
- The scoring service executes within an atomic transaction.
- Any pre-existing assessment for the specified `attempt_id` is purged before inserting the new assessment:
  ```sql
  DELETE FROM integrity_assessments WHERE attempt_id = %s;
  INSERT INTO integrity_assessments (...) VALUES (...);
  ```

---

## 11. Reproducibility & Model Versioning

To ensure scientific repeatability across environments:
1. **Fixed Feature Schema**: Semantic versioning of feature definitions (`FEATURE_SCHEMA_VERSION = "1.0.0"`).
2. **Deterministic Random State**: Reproducibility requirements are defined, including deterministic random-state configuration to be finalized during implementation.
3. **Model Versioning**: Models are tracked via a structured manifest recording:
   - Training timestamp.
   - Algorithm type and hyperparameters.
   - Input feature names and exact ordering.
   - SHA-256 hash of the fitted model artifact.

---

## 12. Testing Strategy

Phase 7 implementation will be validated through dedicated unit and integration tests:

1. **Feature Input Validation Tests**:
   - Reject vectors with length $\neq 18$.
   - Reject vectors containing `NaN`, `Inf`, or string types.
   - Verify ratio feature bounds ($[0.0, 1.0]$).
2. **Isolation Forest Baseline Tests**:
   - Verify consistent anomaly score generation on synthetic benchmark vectors.
   - Verify that identical random seeds produce identical isolation tree splits.
   - Verify monotonic score behavior (extreme anomaly vector scores higher than clean baseline vector).
3. **Service & Database Integration Tests**:
   - Verify that attempts in `IN_PROGRESS` state are strictly rejected (zero writes).
   - Verify that `SUBMITTED` and `EVALUATED` attempts successfully persist assessments.
   - Verify transactional idempotency (re-running replaces existing row; zero duplicate rows).
   - Verify JSON metadata structure and schema compliance.
4. **Safety & Non-Contamination Tests**:
   - Verify zero dependency on student marks or answer keys.
   - Verify that missing models or inference exceptions are safely isolated without affecting core examination data.

---

## 13. Phase 7 Design Acceptance Criteria

- [x] **18-feature input contract defined**: Fixed ordering and dimensional validation specified.
- [x] **No performance leakage**: Academic scores, marks, and answer keys strictly excluded.
- [x] **No fabricated labels**: Unsupervised approach documented; zero invented ground-truth labels.
- [x] **Unsupervised baseline defined**: Anomaly detection formulated as statistical divergence.
- [x] **Isolation Forest baseline specified**: Baseline model selected without unjustified superiority claims.
- [x] **Raw anomaly score semantics defined**: Outlier score explicitly distinguished from cheating probability.
- [x] **Risk calibration deferred until justified**: Mathematical calibration method deferred to empirical phase.
- [x] **Risk bands not arbitrarily frozen**: Numerical cutoffs kept flexible and non-binding.
- [x] **Current evaluation strategy defined**: Distribution, separation, and evidence inspection specified.
- [x] **Future supervised evaluation defined**: Protocol for post-labeling supervised benchmarking outlined.
- [x] **Explainability boundary defined**: Strict separation between observed evidence and model output.
- [x] **Human-in-loop requirement defined**: System restricted to advisory recommendations; no automated guilt.
- [x] **Reproducibility requirements defined**: Reproducibility requirements are defined, including deterministic random-state configuration to be finalized during implementation.
- [x] **Testing strategy defined**: Input validation, model stability, DB integration, and safety tests outlined.
- [x] **Runtime integration intentionally deferred**: Core exam submission and active proctoring left untouched.
- [x] **No schema change required**: No database schema change is required at the current design stage. The persistence mapping to `integrity_assessments` will be validated during implementation.

---

## 14. Deferred Decisions

The following technical and operational decisions are explicitly deferred until empirical data collection and faculty review:

1. **Exact Risk-Score Calibration Method**: Selection between Min-Max scaling, logistic mapping, or percentile ranking.
2. **Exact Risk-Band Thresholds**: The final numerical cutoffs defining Low, Moderate, and High tiers.
3. **Minimum Dataset Size**: The number of completed examination attempts required to fit a stable baseline model.
4. **Contamination Parameter**: The exact `contamination` float value passed to `IsolationForest` (e.g., `0.05` vs `0.10` vs `'auto'`).
5. **Final Preprocessing/Scaling Strategy**: Selection between `RobustScaler`, `StandardScaler`, or non-parametric scaling.
6. **Final Isolation Forest Hyperparameters**: `n_estimators`, `max_samples`, and `bootstrap` tuning.
7. **Model Artifact Storage Location**: File system directory structure and serialization format (`.joblib` vs `.pkl`).
8. **Human-Review Labeling Protocol**: Standard operating procedures and rubrics for proctors to annotate flagged sessions.
9. **Future Supervised Model Selection**: Evaluation and selection of supervised classifiers (Logistic Regression, Decision Trees, Random Forests) once ground-truth annotations exist.
