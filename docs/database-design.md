# Database Design

## 1. Purpose

This document defines the logical database design for OmniSight-AI.

The database is designed to support:

* User management.
* Examination management.
* Questions and answers.
* Examination attempts.
* Results.
* Monitoring events.
* Behavioral features.
* Integrity-risk assessments.

The initial implementation will use **MySQL**.

---

## 2. Design Principles

The database design follows these principles:

1. Each major business entity should have a dedicated table.
2. Primary keys uniquely identify records.
3. Foreign keys maintain relationships between related entities.
4. Examination and student data should remain traceable.
5. Monitoring events should be associated with the relevant examination attempt.
6. Integrity assessments should be traceable to the corresponding analysis context.
7. The schema should remain simple enough for the academic MVP.

---

# 3. Entities

## 3.1 Users

Stores teacher and student account information.

### Table: `users`

| Column          | Type           | Constraint         | Description            |
| --------------- | -------------- | ------------------ | ---------------------- |
| `user_id`       | INT            | PK, AUTO_INCREMENT | Unique user identifier |
| `name`          | VARCHAR(100)   | NOT NULL           | User's name            |
| `email`         | VARCHAR(150)   | UNIQUE, NOT NULL   | User email             |
| `password_hash` | VARCHAR(255)   | NOT NULL           | Hashed password        |
| `role`          | ENUM / VARCHAR | NOT NULL           | Teacher or Student     |
| `created_at`    | DATETIME       | NOT NULL           | Account creation time  |

---

## 3.2 Examinations

Stores examination-level information.

### Table: `exams`

| Column             | Type         | Constraint         | Description                   |
| ------------------ | ------------ | ------------------ | ----------------------------- |
| `exam_id`          | INT          | PK, AUTO_INCREMENT | Unique examination identifier |
| `title`            | VARCHAR(200) | NOT NULL           | Examination title             |
| `description`      | TEXT         | NULL               | Examination description       |
| `duration_minutes` | INT          | NOT NULL           | Examination duration          |
| `created_by`       | INT          | FK → users.user_id | Teacher who created the exam  |
| `status`           | VARCHAR(30)  | NOT NULL           | Exam status                   |
| `created_at`       | DATETIME     | NOT NULL           | Creation timestamp            |

### Relationship

One teacher can create multiple examinations.

```text
users (Teacher) 1 ─────── N exams
```

---

## 3.3 Questions

Stores questions belonging to examinations.

### Table: `questions`

| Column           | Type         | Constraint         | Description                |
| ---------------- | ------------ | ------------------ | -------------------------- |
| `question_id`    | INT          | PK, AUTO_INCREMENT | Unique question identifier |
| `exam_id`        | INT          | FK → exams.exam_id | Associated examination     |
| `question_text`  | TEXT         | NOT NULL           | Question content           |
| `option_a`       | TEXT         | NOT NULL           | Option A                   |
| `option_b`       | TEXT         | NOT NULL           | Option B                   |
| `option_c`       | TEXT         | NOT NULL           | Option C                   |
| `option_d`       | TEXT         | NOT NULL           | Option D                   |
| `correct_option` | VARCHAR(1)   | NOT NULL           | Correct option             |
| `marks`          | DECIMAL(5,2) | NOT NULL           | Marks for question         |

### Relationship

One examination can contain multiple questions.

```text
exams 1 ─────── N questions
```

---

## 3.4 Examination Attempts

Represents a student's attempt at an examination.

### Table: `exam_attempts`

| Column         | Type        | Constraint         | Description                 |
| -------------- | ----------- | ------------------ | --------------------------- |
| `attempt_id`   | INT         | PK, AUTO_INCREMENT | Unique attempt identifier   |
| `exam_id`      | INT         | FK → exams.exam_id | Examination being attempted |
| `student_id`   | INT         | FK → users.user_id | Student attempting exam     |
| `started_at`   | DATETIME    | NOT NULL           | Attempt start time          |
| `submitted_at` | DATETIME    | NULL               | Submission time             |
| `status`       | VARCHAR(30) | NOT NULL           | Attempt status              |

### Relationships

One examination can have multiple student attempts.

One student can have multiple examination attempts.

```text
exams 1 ─────── N exam_attempts
users 1 ─────── N exam_attempts
```

---

## 3.5 Answers

Stores the answers submitted during an examination attempt.

### Table: `answers`

| Column            | Type       | Constraint                    | Description               |
| ----------------- | ---------- | ----------------------------- | ------------------------- |
| `answer_id`       | INT        | PK, AUTO_INCREMENT            | Unique answer identifier  |
| `attempt_id`      | INT        | FK → exam_attempts.attempt_id | Related attempt           |
| `question_id`     | INT        | FK → questions.question_id    | Related question          |
| `selected_option` | VARCHAR(1) | NULL                          | Student's selected option |
| `is_correct`      | BOOLEAN    | NULL                          | Evaluation result         |
| `answered_at`     | DATETIME   | NULL                          | Answer timestamp          |

### Relationships

One attempt can contain multiple answers.

One question can appear in multiple attempts.

```text
exam_attempts 1 ─────── N answers
questions     1 ─────── N answers
```

---

## 3.6 Results

Stores the final result of an examination attempt.

### Table: `results`

| Column           | Type         | Constraint                    | Description              |
| ---------------- | ------------ | ----------------------------- | ------------------------ |
| `result_id`      | INT          | PK, AUTO_INCREMENT            | Unique result identifier |
| `attempt_id`     | INT          | FK → exam_attempts.attempt_id | Related attempt          |
| `total_marks`    | DECIMAL(7,2) | NOT NULL                      | Maximum marks            |
| `obtained_marks` | DECIMAL(7,2) | NOT NULL                      | Marks obtained           |
| `percentage`     | DECIMAL(5,2) | NULL                          | Percentage score         |
| `evaluated_at`   | DATETIME     | NOT NULL                      | Evaluation time          |

### Relationship

An examination attempt produces a result.

```text
exam_attempts 1 ─────── 1 results
```

---

# 4. Monitoring and Integrity Entities

## 4.1 Monitoring Events

Stores events detected during examination monitoring.

### Table: `monitoring_events`

| Column            | Type        | Constraint                    | Description                  |
| ----------------- | ----------- | ----------------------------- | ---------------------------- |
| `event_id`        | INT         | PK, AUTO_INCREMENT            | Unique event identifier      |
| `attempt_id`      | INT         | FK → exam_attempts.attempt_id | Related examination attempt  |
| `event_type`      | VARCHAR(50) | NOT NULL                      | Type of monitoring event     |
| `event_timestamp` | DATETIME    | NOT NULL                      | Time of event                |
| `event_metadata`  | JSON / TEXT | NULL                          | Additional event information |

### Example event types

* `NO_FACE`
* `MULTIPLE_FACES`
* Other approved monitoring events added during implementation.

### Relationship

One examination attempt can generate multiple monitoring events.

```text
exam_attempts 1 ─────── N monitoring_events
```

---

## 4.2 Behavioral Features

Stores structured features generated from examination and monitoring events.

### Table: `behavioral_features`

| Column          | Type          | Constraint                    | Description             |
| --------------- | ------------- | ----------------------------- | ----------------------- |
| `feature_id`    | INT           | PK, AUTO_INCREMENT            | Unique feature record   |
| `attempt_id`    | INT           | FK → exam_attempts.attempt_id | Related attempt         |
| `feature_name`  | VARCHAR(100)  | NOT NULL                      | Feature name            |
| `feature_value` | DECIMAL(12,4) | NOT NULL                      | Feature value           |
| `generated_at`  | DATETIME      | NOT NULL                      | Feature generation time |

### Example features

* Number of no-face events.
* Number of multiple-face events.
* Event frequency.
* Event duration where measurable.

The final feature set will be determined during the feature-engineering phase.

### Relationship

One examination attempt can have multiple behavioral features.

```text
exam_attempts 1 ─────── N behavioral_features
```

---

## 4.3 Integrity Assessments

Stores the output of the integrity-risk analysis.

### Table: `integrity_assessments`

| Column                | Type         | Constraint                    | Description                       |
| --------------------- | ------------ | ----------------------------- | --------------------------------- |
| `assessment_id`       | INT          | PK, AUTO_INCREMENT            | Unique assessment identifier      |
| `attempt_id`          | INT          | FK → exam_attempts.attempt_id | Related attempt                   |
| `risk_score`          | DECIMAL(6,3) | NULL                          | Generated risk score              |
| `risk_category`       | VARCHAR(30)  | NULL                          | Risk category                     |
| `model_name`          | VARCHAR(100) | NULL                          | Model used for assessment         |
| `assessment_metadata` | JSON / TEXT  | NULL                          | Additional assessment information |
| `created_at`          | DATETIME     | NOT NULL                      | Assessment timestamp              |

### Relationship

An examination attempt may have one or more assessments depending on the analysis workflow.

For the initial MVP, the application may maintain the latest valid assessment for an attempt.

```text
exam_attempts 1 ─────── N integrity_assessments
```

---

# 5. Overall Entity Relationship

The major relationships are:

```text
                         ┌──────────────┐
                         │    users     │
                         └──────┬───────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
             creates                       attempts
                 │                             │
                 ▼                             ▼
          ┌──────────────┐             ┌────────────────┐
          │     exams    │             │  exam_attempts │
          └──────┬───────┘             └───────┬────────┘
                 │                             │
                 ▼                             │
          ┌──────────────┐                     │
          │  questions   │                     │
          └──────┬───────┘                     │
                 │                             │
                 └──────────────┐              │
                                ▼              ▼
                           ┌────────────────────────┐
                           │        answers         │
                           └────────────────────────┘

                                  exam_attempts
                                        │
             ┌──────────────────────────┼─────────────────────────┐
             │                          │                         │
             ▼                          ▼                         ▼
   ┌──────────────────┐       ┌──────────────────┐      ┌─────────────────────┐
   │     results      │       │ monitoring_events│      │ behavioral_features  │
   └──────────────────┘       └──────────────────┘      └─────────────────────┘
                                        │
                                        │
                                        ▼
                              ┌─────────────────────┐
                              │ integrity_assessments│
                              └─────────────────────┘
```

---

# 6. Relationship Summary

| Relationship                                | Cardinality |
| ------------------------------------------- | ----------- |
| User → Exams created                        | 1 : N       |
| Exam → Questions                            | 1 : N       |
| Exam → Examination Attempts                 | 1 : N       |
| Student/User → Examination Attempts         | 1 : N       |
| Examination Attempt → Answers               | 1 : N       |
| Question → Answers                          | 1 : N       |
| Examination Attempt → Result                | 1 : 1       |
| Examination Attempt → Monitoring Events     | 1 : N       |
| Examination Attempt → Behavioral Features   | 1 : N       |
| Examination Attempt → Integrity Assessments | 1 : N       |

---

# 7. Database Design Constraints

The implementation should enforce appropriate constraints such as:

* Unique email addresses for users.
* Valid foreign-key relationships.
* Required fields for essential examination data.
* Appropriate timestamps for attempts and monitoring events.
* Valid references between answers, questions, and attempts.
* Consistent association between monitoring events and examination attempts.

The exact MySQL data types and constraints may be refined during implementation based on the selected database-access approach.

---

# 8. Design Boundary

This is the **logical database design** for the academic MVP.

The actual MySQL schema, indexes, migrations, and SQL implementation will be created during **Phase 4 — Database Implementation**, after the design is reviewed and verified.

No database table should be created solely from an implementation assumption that contradicts this design without first updating the design documentation.
