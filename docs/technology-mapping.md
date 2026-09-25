# Technology Mapping

## 1. Purpose

This document defines the technologies selected for the OmniSight-AI system and maps each technology to its intended role within the system.

The technology selection is designed for an academic MVP that is understandable, maintainable, testable, and practical to implement.

---

## 2. Technology Stack Overview

| Layer / Module             | Technology                | Purpose                                                                       |
| -------------------------- | ------------------------- | ----------------------------------------------------------------------------- |
| User Interface             | Streamlit                 | Student examination interface and teacher dashboard                           |
| Programming Language       | Python                    | Core application development                                                  |
| Database                   | MySQL                     | Persistent storage of users, exams, answers, results, events, and assessments |
| Database Access            | SQLAlchemy                | Application-to-database interaction                                           |
| Data Processing            | Pandas                    | Behavioral data processing and feature preparation                            |
| Numerical Computing        | NumPy                     | Numerical calculations and feature operations                                 |
| Machine Learning           | scikit-learn              | Baseline integrity-risk prediction models                                     |
| Computer Vision            | OpenCV                    | Webcam processing and basic face monitoring                                   |
| Face / Landmark Processing | MediaPipe                 | Additional face-related analysis where justified                              |
| Visualization              | Plotly / Streamlit Charts | Results, behavioral patterns, and integrity-risk visualization                |
| Version Control            | Git                       | Source-code version management                                                |
| Remote Repository          | GitHub                    | Code hosting and project history                                              |
| Environment Management     | Python `.venv`            | Isolated Python development environment                                       |
| Configuration              | `.env`                    | Environment-specific configuration and sensitive settings                     |

---

## 3. Technology-to-Module Mapping

### 3.1 Streamlit

**Modules:**

* Student Examination
* Teacher Dashboard
* Authentication Interface
* Result and Integrity Assessment Presentation

**Role:**

Streamlit provides the primary user interface for the academic MVP. It will be used to create the examination workflow for students and the monitoring, result, and integrity-analysis views for teachers.

---

### 3.2 Python

**Modules:**

* Application Logic
* Examination Management
* Monitoring
* Data Processing
* Machine Learning
* Database Integration

**Role:**

Python is the primary programming language for the system. It provides a common development environment for application logic, computer vision, data processing, and machine learning.

---

### 3.3 MySQL

**Modules:**

* User Management
* Examination Management
* Answer Storage
* Result Storage
* Monitoring Event Storage
* Behavioral Feature Storage
* Integrity Assessment Storage

**Role:**

MySQL provides persistent relational storage for the structured data generated and used by the system.

---

### 3.4 SQLAlchemy

**Modules:**

* Database Access
* User Management
* Examination Management
* Result Management
* Monitoring Event Management

**Role:**

SQLAlchemy provides the application-level database access layer between Python and MySQL. It helps maintain a structured separation between application logic and database operations.

---

### 3.5 Pandas

**Modules:**

* Behavioral Data Processing
* Feature Engineering
* ML Dataset Preparation
* Result Analysis

**Role:**

Pandas will be used to transform logged behavioral and examination data into structured datasets suitable for analysis and machine-learning workflows.

---

### 3.6 NumPy

**Modules:**

* Feature Engineering
* Numerical Processing
* Machine Learning Data Preparation

**Role:**

NumPy will support numerical operations required during feature calculation and machine-learning data preparation.

---

### 3.7 scikit-learn

**Modules:**

* Machine Learning
* Integrity-Risk Analysis
* Model Evaluation

**Role:**

scikit-learn will be used for baseline machine-learning models that estimate an integrity-risk level from engineered behavioral and examination features.

The initial implementation will prioritize interpretable and academically suitable baseline models rather than unnecessarily complex deep-learning architectures.

---

### 3.8 OpenCV

**Modules:**

* Webcam Monitoring
* Face Detection
* Frame Processing
* Monitoring Event Generation

**Role:**

OpenCV will handle webcam access and image/frame processing required for basic examination monitoring.

Potential monitoring signals include:

* Face detected
* Face absent
* Multiple faces detected

These signals will be recorded as monitoring events rather than automatically treated as proof of misconduct.

---

### 3.9 MediaPipe

**Modules:**

* Optional Face / Landmark Analysis
* Additional Computer-Vision Features

**Role:**

MediaPipe may be used when additional face or landmark information is required beyond the capabilities of the basic OpenCV implementation.

MediaPipe is not considered mandatory for every monitoring feature. It will be introduced only where it provides a justified improvement to the MVP.

---

### 3.10 Plotly / Streamlit Charts

**Modules:**

* Teacher Dashboard
* Result Visualization
* Behavioral Analysis
* Integrity Assessment

**Role:**

Visualization libraries will present examination results, behavioral patterns, monitoring-event summaries, and integrity-risk information in a form that is easier for teachers to interpret.

---

### 3.11 Git

**Modules:**

* Entire Development Lifecycle

**Role:**

Git will be used for local version control, feature development, commit history, and recovery of previous project states.

---

### 3.12 GitHub

**Modules:**

* Source Code Management
* Project Documentation
* Development History

**Role:**

GitHub will serve as the remote repository for the project source code and documentation.

Meaningful development progress will be committed and pushed to the repository.

---

### 3.13 Python Virtual Environment

**Technology:**
`.venv`

**Role:**

The virtual environment isolates project dependencies from the system-wide Python installation and provides a reproducible development environment.

---

### 3.14 Environment Configuration

**Technology:**
`.env`

**Role:**

Environment variables will be used for configuration values such as database connection settings and other environment-specific values.

Sensitive credentials should not be committed to GitHub.

---

## 4. Technology Selection Principles

The technology stack follows these principles:

1. **Simplicity** — technologies should be practical for the academic MVP.
2. **Maintainability** — modules should remain understandable and independently manageable.
3. **Integration** — selected technologies should work effectively within the Python ecosystem.
4. **Explainability** — ML and monitoring components should support understandable outputs.
5. **Testability** — individual modules should be testable during development.
6. **Scope Control** — unnecessary enterprise-level technologies should be avoided.
7. **Academic Reproducibility** — the system should be implementable and demonstrable in an academic environment.

---

## 5. Deliberate Technology Boundaries

The initial MVP will **not** require:

* Microservices
* Kubernetes
* Distributed streaming systems
* Enterprise-scale cloud infrastructure
* Complex deep-learning architectures
* Large-scale LLM integration
* Advanced gaze estimation
* Emotion recognition
* Automated cheating verdict systems

These technologies may be considered in future research or extension work if justified.

---

## 6. Final Technology Architecture

The primary technology flow is:

**Streamlit → Python Application Logic → SQLAlchemy → MySQL**

with supporting analytical and monitoring components:

**OpenCV → Monitoring Events → Pandas / NumPy → Feature Engineering → scikit-learn → Integrity-Risk Assessment → Streamlit Dashboard**

Git and GitHub support the development lifecycle across all components.

---

## 7. Technology Mapping Principle

The system follows:

**Technology → Module → Purpose → Validation**

Every selected technology should have a clear responsibility within the system and should be introduced only when its functionality is required by the project scope.
