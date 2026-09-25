# Functional Requirements

## FR-01: User Registration and Authentication

The system shall provide basic authentication for users.

The system shall support at least two user roles:

* Teacher
* Student

The system shall restrict access to role-specific functionality.

---

## FR-02: Teacher Examination Management

The system shall allow a teacher to:

* Create an examination.
* Define examination details.
* Add objective-type questions.
* Define the correct answer for each question.
* Set the examination duration.
* View and manage created examinations.

---

## FR-03: Student Examination Access

The system shall allow an authenticated student to:

* View available examinations.
* Start an assigned examination.
* View examination questions.
* Select answers.
* Navigate through the examination interface.
* Submit the examination.

---

## FR-04: Examination Timer

The system shall:

* Start the examination timer when the student begins the examination.
* Display the remaining examination time.
* Prevent the examination from continuing beyond the configured duration.
* Handle examination completion when the timer expires.

---

## FR-05: Answer Submission and Evaluation

The system shall:

* Record the answers submitted by the student.
* Store the examination submission.
* Automatically evaluate objective-type questions.
* Calculate the student's score.
* Make the result available to the appropriate user.

---

## FR-06: Examination Monitoring

During an examination, the system shall support basic computer-vision-based monitoring.

The system shall be capable of recording selected monitoring events, including:

* No-face detection.
* Multiple-face detection.
* Face-presence information where applicable.

Each recorded monitoring event should include relevant contextual information such as a timestamp.

---

## FR-07: Examination Activity Event Logging

The system shall record selected examination activity events that are relevant to integrity analysis.

Examples may include:

* Monitoring events.
* Examination interaction events.
* Focus-related events where technically feasible.

The exact event set may be refined during implementation and testing.

---

## FR-08: Behavioral Feature Generation

The system shall transform relevant recorded events into structured features.

The feature-generation process shall support analysis of information such as:

* Event frequency.
* Event occurrence.
* Event timing.
* Examination activity patterns.

The final feature set shall be determined during the feature-engineering phase based on available data and technical feasibility.

---

## FR-09: Integrity-Risk Analysis

The system shall provide an integrity-risk assessment based on available examination and behavioral features.

The system shall:

* Process relevant features.
* Apply selected baseline machine-learning models where appropriate.
* Generate an integrity-risk result.
* Preserve relevant evidence contributing to the assessment.

The system shall not treat a single monitoring event as definitive proof of misconduct.

---

## FR-10: Teacher Review Dashboard

The system shall provide a teacher-oriented dashboard through which the teacher can view:

* Examination results.
* Student scores.
* Integrity-risk information.
* Relevant monitoring events.
* Event timestamps.
* Available supporting evidence.
* Basic examination and integrity-related visualizations.

---

## FR-11: Evidence Timeline

The system shall provide a chronological representation of relevant examination events.

The timeline should allow the teacher to understand:

* What event occurred.
* When the event occurred.
* Which examination/student the event belongs to.
* How the event contributes to the available integrity evidence.

---

## FR-12: Data Persistence

The system shall store required application data in the project database.

Stored data may include:

* User information.
* Examination information.
* Questions.
* Student answers.
* Examination results.
* Monitoring events.
* Behavioral features.
* Integrity-risk assessment results.

---

## FR-13: Role-Based Access

The system shall ensure that:

* Teachers can access teacher-specific functionality.
* Students can access student-specific functionality.
* Students cannot access teacher administration or review functionality.
* Users can access only the information permitted by their role.

---

## FR-14: Examination Completion

The system shall support normal examination completion through:

* Manual submission by the student.
* Automatic completion when the examination timer expires.

The final examination state and submitted answers shall be stored.

---

## FR-15: Human Review Support

The system shall present automated monitoring and integrity-analysis results as supporting information for human review.

The system shall not automatically make a final disciplinary determination based solely on its AI-generated assessment.
