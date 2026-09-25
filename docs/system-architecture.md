# System Architecture

## 1. Architecture Overview

OmniSight-AI will use a modular application architecture designed for an academic online examination and integrity-analysis prototype.

The architecture separates the user interface, application logic, examination management, monitoring, data analysis, machine-learning components, and persistent storage into clearly defined responsibilities.

The high-level flow is:

**User → Streamlit Interface → Application Services → Processing Modules → MySQL Database**

The monitoring and analysis workflow is:

**Examination → Monitoring & Activity Events → Event Storage → Feature Engineering → ML Analysis → Integrity-Risk Assessment → Teacher Dashboard**

---

## 2. High-Level Components

### 2.1 User Layer

The system will support two primary user roles:

* **Teacher**
* **Student**

The user interacts with the system through the Streamlit-based web interface.

---

### 2.2 Presentation Layer

The presentation layer will be implemented using **Streamlit**.

It will provide interfaces for:

* Authentication
* Teacher dashboard
* Student dashboard
* Examination creation and management
* Examination attempt interface
* Examination results
* Monitoring information
* Integrity-risk analysis
* Evidence/event visualization

The presentation layer should primarily handle user interaction and presentation rather than containing complex business logic.

---

### 2.3 Application / Business Logic Layer

This layer will coordinate the main application workflows.

Responsibilities include:

* Authentication and authorization.
* Examination management.
* Question management.
* Examination attempt handling.
* Timer and submission logic.
* Result calculation.
* Monitoring-event coordination.
* Feature-generation workflow.
* Integrity-analysis workflow.

Business rules should remain separated from the Streamlit UI wherever practical.

---

### 2.4 Examination Management Module

This module will manage the core examination workflow.

Responsibilities:

* Create examinations.
* Manage questions.
* Assign examinations.
* Start examination attempts.
* Record answers.
* Handle submission.
* Calculate objective-question results.
* Store examination outcomes.

---

### 2.5 Computer Vision / Monitoring Module

This module will provide the initial AI-assisted monitoring capabilities.

The initial monitoring scope includes:

* Face presence detection.
* Multiple-face detection.
* Relevant monitoring-event generation.
* Event timestamping.

The module will produce monitoring events rather than directly declaring misconduct.

---

### 2.6 Event Logging Module

The event logging module will convert relevant examination and monitoring observations into structured records.

A monitoring/activity event should contain information such as:

* Event type.
* Student/examination context.
* Timestamp.
* Relevant event metadata.

These records will provide the source data for later behavioral analysis.

---

### 2.7 Feature Engineering Module

This module will transform raw examination and event information into structured features suitable for analysis.

Potential feature categories include:

* Event frequency.
* Event occurrence.
* Event timing.
* Examination activity patterns.

The final feature set will be determined during implementation and experimentation.

---

### 2.8 Machine Learning / Integrity Analysis Module

This module will process the engineered features and generate an integrity-risk assessment.

The initial implementation will focus on evaluating baseline machine-learning approaches appropriate for the available dataset.

The module should support:

* Feature preparation.
* Model training where applicable.
* Model evaluation.
* Prediction/inference.
* Integrity-risk assessment.
* Preservation of relevant evidence.

The output should be treated as analytical support for human review rather than a definitive judgment.

---

### 2.9 Teacher Review / Dashboard Module

The teacher dashboard will present:

* Student examination results.
* Integrity-risk information.
* Monitoring events.
* Event timestamps.
* Evidence timeline.
* Basic performance and integrity visualizations.

The dashboard should make the available evidence understandable to the teacher.

---

### 2.10 Database Layer

The project will use **MySQL** for persistent data storage.

The database will store information related to:

* Users.
* Roles.
* Examinations.
* Questions.
* Examination attempts.
* Student answers.
* Results.
* Monitoring events.
* Behavioral features.
* Integrity-risk assessments.

Database design will be developed separately during the database-design stage.

---

## 3. High-Level Data Flow

The primary examination workflow is:

```text
Teacher
   ↓
Create Examination
   ↓
Store Examination Data
   ↓
Student
   ↓
Start Examination
   ↓
Answer Questions
   ↓
Monitoring + Activity Events
   ↓
Event Logging
   ↓
Submit / Time Expiry
   ↓
Result Calculation
   ↓
Feature Engineering
   ↓
Integrity-Risk Analysis
   ↓
Teacher Dashboard
   ↓
Human Review
```

---

## 4. Architectural Boundaries

The following boundaries will be maintained:

* UI code should not directly implement complex machine-learning logic.
* Database operations should be separated from presentation logic where practical.
* Computer-vision monitoring should produce structured events rather than final misconduct decisions.
* Feature engineering should operate on structured data.
* ML models should be replaceable without redesigning the entire application.
* Teacher review should remain separate from automated risk generation.

---

## 5. Technology Mapping

| Architectural Component   | Technology                               |
| ------------------------- | ---------------------------------------- |
| User Interface            | Streamlit                                |
| Application Logic         | Python                                   |
| Data Processing           | Pandas, NumPy                            |
| Machine Learning          | scikit-learn                             |
| Computer Vision           | OpenCV                                   |
| Optional Vision Utilities | MediaPipe where justified                |
| Database                  | MySQL                                    |
| Visualization             | Streamlit charts / Plotly where required |
| Version Control           | Git + GitHub                             |

---

## 6. Initial Architecture Principle

The architecture should remain appropriate for a final-year academic prototype.

The project will prioritize:

* Clear separation of responsibilities.
* Understandable implementation.
* Requirement traceability.
* Testability.
* Explainability.
* Controlled project complexity.

Enterprise-scale distributed architecture is outside the initial MVP.
