# Requirements Traceability Matrix

## 1. Purpose

The Requirements Traceability Matrix (RTM) establishes a clear relationship between the requirements of OmniSight-AI and the corresponding system features, development phases, and planned validation activities.

The purpose of the RTM is to ensure that each identified requirement is considered during system development and testing.

Since the project is currently in the requirements and planning stage, implementation and testing statuses will be updated as development progresses.

---

## 2. Traceability Matrix

| Requirement ID | Requirement                          | Related Feature                        | Planned Development Phase                       | Planned Validation                            |
| -------------- | ------------------------------------ | -------------------------------------- | ----------------------------------------------- | --------------------------------------------- |
| FR-01          | User Registration and Authentication | User authentication and roles          | Phase 5 — Authentication + User Management      | Authentication and authorization testing      |
| FR-02          | Teacher Examination Management       | Exam and question management           | Phase 6 — Core Examination System               | Exam creation and question-management testing |
| FR-03          | Student Examination Access           | Student exam interface                 | Phase 6 — Core Examination System               | Student examination workflow testing          |
| FR-04          | Examination Timer                    | Exam timer and expiry handling         | Phase 6 — Core Examination System               | Timer and automatic-expiry testing            |
| FR-05          | Answer Submission and Evaluation     | Answer storage and result calculation  | Phase 6 — Core Examination System               | Submission and evaluation testing             |
| FR-06          | Examination Monitoring               | Face and multiple-face monitoring      | Phase 7 — Proctoring / Computer Vision          | Controlled computer-vision testing            |
| FR-07          | Examination Activity Event Logging   | Monitoring and activity event logging  | Phase 7 — Proctoring / Computer Vision          | Event generation and storage testing          |
| FR-08          | Behavioral Feature Generation        | Feature engineering pipeline           | Phase 8 — Behavioral Data & Feature Engineering | Feature-generation validation                 |
| FR-09          | Integrity-Risk Analysis              | Machine-learning-based risk assessment | Phase 9 — Machine Learning                      | Model evaluation and analysis                 |
| FR-10          | Teacher Review Dashboard             | Results and integrity dashboard        | Phase 10 — Explainable Integrity Dashboard      | Dashboard and integration testing             |
| FR-11          | Evidence Timeline                    | Chronological event visualization      | Phase 10 — Explainable Integrity Dashboard      | Event ordering and display testing            |
| FR-12          | Data Persistence                     | MySQL database storage                 | Phase 4 — Database Implementation               | Database and data-integrity testing           |
| FR-13          | Role-Based Access                    | Teacher/student authorization          | Phase 5 — Authentication + User Management      | Access-control testing                        |
| FR-14          | Examination Completion               | Manual and automatic submission        | Phase 6 — Core Examination System               | Submission and timeout testing                |
| FR-15          | Human Review Support                 | Evidence-based integrity presentation  | Phase 10 — Explainable Integrity Dashboard      | Human-review workflow testing                 |

---

## 3. Non-Functional Requirement Traceability

| NFR Area        | Related System Concern                                     | Planned Development / Validation         |
| --------------- | ---------------------------------------------------------- | ---------------------------------------- |
| Usability       | Simple student and teacher interfaces                      | Phase 6 and Phase 10                     |
| Performance     | Responsive examination and dashboard interaction           | Integration and performance checks       |
| Reliability     | Consistent exam state and data storage                     | Phase 4, Phase 6 and integration testing |
| Security        | Authentication, authorization and configuration protection | Phase 5 and security checks              |
| Maintainability | Modular and understandable implementation                  | All development phases                   |
| Scalability     | Structured application and database design                 | Phase 2 and Phase 4                      |
| Explainability  | Evidence-supported integrity assessment                    | Phase 9 and Phase 10                     |
| Data Integrity  | Consistent examination and monitoring records              | Phase 4 and Phase 8                      |
| Compatibility   | Browser and development-environment support                | Integration testing                      |
| Testability     | Independent and integrated component testing               | Phase 11 — Integration + Testing         |

---

## 4. Traceability Status

At the current Phase 0 stage:

* Requirements: **Defined**
* System features: **Planned**
* Development phases: **Mapped**
* Implementation: **Not started**
* Validation: **Planned**
* Final verification: **Pending implementation**

The RTM will be updated during development whenever requirements, implementation decisions, or validation procedures change.

---

## 5. Traceability Principle

Every major implementation feature should be traceable to at least one documented requirement.

Conversely, every approved functional requirement should eventually have:

**Requirement → Feature → Implementation → Test → Verification**

This ensures that project development remains aligned with the approved project scope.
