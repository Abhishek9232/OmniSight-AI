# Project Scope

## 1. Project Objective

OmniSight-AI is an academic prototype for conducting online examinations and supporting examination-integrity analysis through examination activity, basic computer-vision-based monitoring, behavioral event logging, and an explainable integrity-risk assessment.

The project focuses on creating a complete and demonstrable workflow rather than building an enterprise-scale examination platform.

---

## 2. In Scope

### 2.1 User Management

* Student and teacher user roles.
* Basic authentication.
* Role-based access to relevant system features.

### 2.2 Examination Management

* Teacher can create and manage examinations.
* Teacher can add and manage objective-type questions.
* Student can access assigned examinations.
* Examination timer.
* Answer submission.
* Automatic handling of examination completion and submission.

### 2.3 Result Management

* Automatic evaluation of objective-type questions.
* Student result generation.
* Score and basic performance information.
* Teacher access to examination results.

### 2.4 AI-Assisted Monitoring

The initial prototype will implement selected computer-vision-based monitoring capabilities, including:

* Face presence detection.
* Detection of multiple faces.
* Recording relevant monitoring events.
* Timestamping of detected events.

### 2.5 Behavioral Event Logging

The system will record selected examination activity events that can contribute to integrity analysis, such as:

* Examination activity events.
* Monitoring events.
* Relevant interaction or focus-related events where technically feasible.

The exact event set may be refined during implementation based on technical feasibility and testing.

### 2.6 Feature Engineering and Analysis

* Convert recorded events into structured features.
* Perform exploratory analysis of relevant examination and behavioral data.
* Prepare features for machine-learning-based analysis.
* Evaluate selected baseline machine-learning models.

### 2.7 Integrity-Risk Assessment

* Generate an integrity-risk assessment from available features.
* Provide interpretable contributing evidence where possible.
* Avoid treating an individual event as conclusive proof of misconduct.
* Support human review of the available evidence.

### 2.8 Teacher Dashboard

The teacher-facing interface will provide:

* Examination results.
* Integrity-risk information.
* Relevant monitoring events.
* Evidence/event timeline.
* Basic performance and integrity-related visualizations.

---

## 3. Out of Scope for the Initial MVP

The following features are intentionally excluded from the initial implementation:

* Secure execution sandbox for programming/code-based examinations.
* Advanced automated coding evaluation.
* Large-scale distributed examination infrastructure.
* Microservices architecture.
* Kubernetes or container orchestration.
* Multi-tenant SaaS architecture.
* Advanced deep-learning-based behavioral analysis.
* Complex gaze estimation or emotion recognition.
* Fully automated determination of cheating or misconduct.
* Automatic disciplinary decisions based solely on AI output.
* Large language model-based automatic question generation.
* Enterprise-level identity verification systems.
* Large-scale cloud deployment and production infrastructure.

These features may be considered as future extensions if the core academic prototype is completed successfully.

---

## 4. MVP Boundary

The minimum viable version of OmniSight-AI should demonstrate the following complete workflow:

**Teacher → Create Exam → Student Attempts Exam → Examination Monitoring → Event Logging → Feature Generation → Integrity-Risk Analysis → Teacher Dashboard → Human Review**

The MVP will be considered complete when this workflow can be demonstrated reliably using a controlled academic test environment.

---

## 5. Project Constraints

The project is designed as a final-year academic prototype. Therefore:

* Implementation complexity should remain appropriate for the available development timeline.
* Technologies should remain understandable and maintainable by the project team.
* Features should be added only when they support an identified requirement.
* AI predictions should be treated as analytical assistance rather than definitive judgments.
* Testing should focus on demonstrating functional correctness and the behavior of the proposed system under controlled scenarios.

---

## 6. Future Extensions

Possible future extensions include:

* Programming examination and secure code execution.
* More advanced computer-vision models.
* Additional behavioral signals.
* Improved machine-learning models using larger datasets.
* AI-assisted question generation.
* Cloud deployment and scalability improvements.
* More comprehensive examination analytics.
