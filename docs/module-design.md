# Module / Component Design

## 1. Purpose

This document defines the major software modules of OmniSight-AI, their responsibilities, inputs, outputs, and dependencies.

The module boundaries are derived from the system architecture and functional requirements. Each module should have a focused responsibility so that individual components can be developed, tested, and maintained independently where practical.

---

## 2. Authentication and User Management Module

### Responsibility

Handles user identity, authentication, and role-based access.

### Main Functions

* User registration where required.
* User login.
* User authentication.
* Role identification.
* Access control for teacher and student functionality.

### Inputs

* User credentials.
* User role information.

### Outputs

* Authenticated user session.
* Authorized user context.
* Authentication errors when applicable.

### Dependencies

* MySQL database.
* Streamlit session/state management.

---

## 3. Examination Management Module

### Responsibility

Handles examination creation and administration by teachers.

### Main Functions

* Create examination.
* Update examination details.
* Add questions.
* Update questions.
* Define correct answers.
* Configure examination duration.
* Manage available examinations.

### Inputs

* Examination details.
* Question data.
* Duration.
* Teacher information.

### Outputs

* Stored examination.
* Stored questions.
* Examination availability information.

### Dependencies

* Authentication module.
* Database module.

---

## 4. Student Examination Module

### Responsibility

Handles the student's examination experience.

### Main Functions

* Display available examinations.
* Start examination.
* Display questions.
* Record selected answers.
* Track examination state.
* Submit examination.
* Handle examination timeout.

### Inputs

* Student identity.
* Examination ID.
* Question data.
* Examination duration.
* Student answers.

### Outputs

* Examination attempt.
* Submitted answers.
* Completion status.

### Dependencies

* Authentication module.
* Examination management module.
* Database module.
* Monitoring module.

---

## 5. Examination Evaluation Module

### Responsibility

Evaluates submitted objective-type examinations and generates results.

### Main Functions

* Compare submitted answers with correct answers.
* Calculate score.
* Calculate basic performance information.
* Store examination results.

### Inputs

* Student answers.
* Correct answers.
* Examination information.

### Outputs

* Score.
* Result record.
* Basic performance metrics.

### Dependencies

* Student examination module.
* Examination management module.
* Database module.

---

## 6. Computer Vision / Monitoring Module

### Responsibility

Captures and processes selected visual monitoring signals during an examination.

### Initial Monitoring Capabilities

* Face presence detection.
* No-face event detection.
* Multiple-face detection.

### Inputs

* Webcam/video frames.

### Outputs

* Monitoring events.
* Event type.
* Event timestamp.
* Relevant event metadata.

### Dependencies

* OpenCV.
* Optional MediaPipe components where technically justified.
* Event logging module.

### Boundary

This module detects and records observations. It does **not** independently determine whether a student has cheated.

---

## 7. Event Logging Module

### Responsibility

Converts examination and monitoring observations into structured event records.

### Main Functions

* Create event records.
* Associate events with student and examination.
* Record event timestamps.
* Store event metadata.
* Retrieve events for analysis.

### Inputs

* Monitoring events.
* Examination activity events.
* Student/examination context.

### Outputs

* Structured event records.

### Dependencies

* Database module.
* Monitoring module.
* Student examination module.

---

## 8. Feature Engineering Module

### Responsibility

Transforms raw examination and event records into structured features for analysis.

### Main Functions

* Load relevant event data.
* Aggregate events.
* Calculate event-related features.
* Prepare feature datasets.
* Validate feature data before model processing.

### Potential Feature Categories

* Event frequency.
* Event occurrence.
* Event timing.
* Examination activity patterns.

### Inputs

* Stored examination events.
* Monitoring events.
* Examination metadata.

### Outputs

* Structured feature dataset.

### Dependencies

* Event logging module.
* Pandas.
* NumPy.

---

## 9. Machine Learning / Integrity Analysis Module

### Responsibility

Uses engineered features to generate an integrity-risk assessment.

### Main Functions

* Prepare model input.
* Train baseline models where applicable.
* Evaluate models.
* Generate predictions.
* Produce integrity-risk information.
* Preserve relevant model/evidence information.

### Inputs

* Engineered features.
* Training data where available.
* Selected model configuration.

### Outputs

* Model evaluation metrics.
* Integrity-risk assessment.
* Relevant contributing evidence.

### Dependencies

* Feature engineering module.
* scikit-learn.
* Stored data.

### Boundary

The ML module provides analytical assistance. Its output must not be treated as an automatic disciplinary decision.

---

## 10. Teacher Dashboard Module

### Responsibility

Presents examination results and integrity-related evidence to teachers.

### Main Functions

* Display examination results.
* Display student scores.
* Display integrity-risk information.
* Display monitoring events.
* Display event timeline.
* Display basic visualizations.

### Inputs

* Examination results.
* Monitoring events.
* Engineered features.
* Integrity-risk assessments.

### Outputs

* Teacher-facing dashboard.
* Evidence-oriented visualizations.

### Dependencies

* Authentication module.
* Evaluation module.
* Event logging module.
* ML module.
* Database module.
* Streamlit visualization components.

---

## 11. Database Access Module

### Responsibility

Provides a controlled interface between application modules and the MySQL database.

### Main Functions

* Database connection management.
* Data insertion.
* Data retrieval.
* Data update.
* Data deletion where required.
* Transaction handling.
* Error handling for database operations.

### Main Data Domains

* Users.
* Examinations.
* Questions.
* Examination attempts.
* Answers.
* Results.
* Monitoring events.
* Features.
* Integrity assessments.

### Dependencies

* MySQL.
* Python database access layer.

---

## 12. Module Dependency Overview

The high-level dependency relationship is:

```text
Authentication
      ↓
Examination Management
      ↓
Student Examination
      ↓
Evaluation
      ↓
Results
```

Monitoring and analysis flow:

```text
Student Examination
      ↓
Computer Vision / Monitoring
      ↓
Event Logging
      ↓
Feature Engineering
      ↓
Machine Learning / Integrity Analysis
      ↓
Teacher Dashboard
```

Persistent storage is shared through:

```text
Application Modules
      ↓
Database Access Module
      ↓
MySQL
```

---

## 13. Module Design Principles

The following principles will guide implementation:

1. Each module should have a clearly defined responsibility.
2. Modules should communicate through well-defined data or service interfaces.
3. UI logic should not contain complex machine-learning or database logic.
4. Computer-vision components should produce structured events.
5. ML components should consume structured features rather than raw UI state.
6. Database access should be centralized where practical.
7. Modules should remain independently testable where feasible.
8. A change in one module should not unnecessarily require changes throughout the application.

---

## 14. MVP Module Boundary

The initial MVP will focus on:

* Authentication and user management.
* Examination management.
* Student examination workflow.
* Objective-question evaluation.
* Basic computer-vision monitoring.
* Event logging.
* Feature engineering.
* Baseline ML analysis.
* Teacher dashboard.
* MySQL persistence.

Advanced coding evaluation, large-scale infrastructure, and complex AI monitoring remain outside the initial module boundary.
