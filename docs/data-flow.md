# Data Flow Design

## 1. Purpose

This document describes how data moves through the major components of OmniSight-AI.

The data flow is derived from the defined system architecture, modules, database design, and requirements.

---

## 2. Level 0 — Overall System Flow

At the highest level, the system follows:

```text
Teacher / Student
       │
       ▼
Streamlit User Interface
       │
       ▼
Application / Business Logic
       │
       ├──────────────► MySQL Database
       │
       ▼
Processing Modules
       │
       ├── Examination Processing
       ├── Computer Vision Monitoring
       ├── Event Logging
       ├── Feature Engineering
       └── ML / Integrity Analysis
       │
       ▼
Teacher Dashboard / Student Results
```

---

## 3. Student Examination Data Flow

The student examination workflow is:

```text
Student
   │
   ▼
Login
   │
   ▼
Authentication
   │
   ▼
Available Examinations
   │
   ▼
Start Examination
   │
   ├──────────────► Examination Data
   │
   ▼
Answer Questions
   │
   ├──────────────► Answer Records
   │
   ▼
Submit / Time Expiry
   │
   ▼
Evaluation
   │
   ▼
Result
   │
   ▼
Student Result View
```

### Data involved

* Student identity.
* Examination identity.
* Questions.
* Selected answers.
* Submission timestamp.
* Examination status.
* Evaluation result.

---

## 4. Teacher Examination Management Flow

The teacher workflow is:

```text
Teacher
   │
   ▼
Login
   │
   ▼
Teacher Dashboard
   │
   ▼
Create Examination
   │
   ├── Exam Details
   ├── Duration
   └── Questions
   │
   ▼
Validation
   │
   ▼
MySQL Database
   │
   ▼
Examination Available to Students
```

The teacher can subsequently retrieve examination results and integrity-related information from the database through the application layer.

---

## 5. Examination Monitoring Data Flow

During an active examination:

```text
Student Examination
        │
        ▼
Webcam / Monitoring Input
        │
        ▼
Computer Vision Module
        │
        ├── Face Presence
        ├── No-Face Event
        └── Multiple-Face Event
        │
        ▼
Event Logging Module
        │
        ▼
MySQL Database
```

The monitoring module produces structured observations/events. These observations are stored for later analysis.

---

## 6. Behavioral Event Analysis Flow

Stored events are processed as follows:

```text
Monitoring Events
       │
       ▼
Event Retrieval
       │
       ▼
Feature Engineering
       │
       ├── Event Frequency
       ├── Event Occurrence
       ├── Event Timing
       └── Activity Patterns
       │
       ▼
Structured Feature Dataset
```

The final feature set will be determined during the feature-engineering and experimentation phase.

---

## 7. Machine Learning / Integrity Analysis Flow

The analytical workflow is:

```text
Structured Features
       │
       ▼
Data Preparation
       │
       ▼
Baseline ML Model
       │
       ▼
Model Evaluation
       │
       ▼
Integrity-Risk Assessment
       │
       ├── Risk Score
       ├── Risk Category
       └── Supporting Evidence
       │
       ▼
Stored Assessment
```

The machine-learning output is an analytical assessment and should not automatically be treated as a definitive determination of misconduct.

---

## 8. Teacher Review Data Flow

The teacher dashboard retrieves relevant information through the application layer:

```text
MySQL Database
      │
      ├── Examination Results
      ├── Monitoring Events
      ├── Behavioral Features
      └── Integrity Assessments
      │
      ▼
Application / Processing Layer
      │
      ▼
Teacher Dashboard
      │
      ├── Student Score
      ├── Integrity-Risk Information
      ├── Event Timeline
      └── Supporting Evidence
      │
      ▼
Human Review
```

---

## 9. Database Data Flow

The database acts as the persistent storage layer.

```text
Application Modules
       │
       ▼
Database Access Layer
       │
       ▼
MySQL
       │
       ├── users
       ├── exams
       ├── questions
       ├── exam_attempts
       ├── answers
       ├── results
       ├── monitoring_events
       ├── behavioral_features
       └── integrity_assessments
```

The database access layer should isolate database operations from the Streamlit presentation layer where practical.

---

## 10. End-to-End Integrity Analysis Flow

The complete integrity-analysis path is:

```text
Student Starts Examination
          │
          ▼
Examination Activity
          │
          ├──────────────┐
          ▼              ▼
   Answer Activity   Monitoring
                          │
                          ▼
                 Monitoring Events
                          │
                          ▼
                    Event Storage
                          │
                          ▼
                  Feature Engineering
                          │
                          ▼
                   ML / Data Analysis
                          │
                          ▼
                Integrity-Risk Assessment
                          │
                          ▼
                  Teacher Dashboard
                          │
                          ▼
                     Human Review
```

---

## 11. Data Ownership and Responsibility

| Data                 | Generated By                   | Stored In               | Used By                          |
| -------------------- | ------------------------------ | ----------------------- | -------------------------------- |
| User information     | Authentication/User Management | `users`                 | Authentication, dashboards       |
| Examination data     | Examination Management         | `exams`                 | Student Examination              |
| Questions            | Examination Management         | `questions`             | Student Examination              |
| Answers              | Student Examination            | `answers`               | Evaluation                       |
| Examination attempt  | Student Examination            | `exam_attempts`         | Evaluation, monitoring, analysis |
| Results              | Evaluation Module              | `results`               | Student/Teacher Dashboard        |
| Monitoring events    | Computer Vision Module         | `monitoring_events`     | Feature Engineering              |
| Behavioral features  | Feature Engineering            | `behavioral_features`   | ML Analysis                      |
| Integrity assessment | ML Module                      | `integrity_assessments` | Teacher Dashboard                |

---

## 12. Data Flow Boundaries

The following boundaries should be maintained:

1. User interface should communicate with application logic rather than directly performing database operations wherever practical.
2. Monitoring should generate structured events rather than final decisions.
3. Feature engineering should consume stored/structured data.
4. Machine-learning components should consume prepared features.
5. Teacher dashboard should retrieve processed information through the application layer.
6. Persistent application data should be stored in MySQL.

---

## 13. End-to-End System Flow

The complete system can be represented as:

```text
                    ┌──────────────┐
                    │    Teacher   │
                    └──────┬───────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Streamlit UI    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Application     │
                  │ Logic           │
                  └───────┬─────────┘
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
    Exam Management   Monitoring      Data Analysis
          │               │                │
          │               ▼                ▼
          │        Event Logging    Feature Engineering
          │                                │
          │                                ▼
          │                           ML Analysis
          │                                │
          └───────────────┬────────────────┘
                          ▼
                  ┌─────────────────┐
                  │     MySQL       │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Teacher         │
                  │ Dashboard       │
                  └─────────────────┘
```

The student follows the examination workflow through the same application layer, while monitoring and activity information are collected during the examination and later used for analysis.

---

## 14. Design Principle

Data should move through clearly defined stages:

**Input → Validation → Processing → Storage → Analysis → Presentation**

The system should preserve sufficient context so that analytical results can be traced back to the underlying examination and monitoring events.
