# OmniSight-AI — Student Exam Portal Design Specification
## Part 2A: Published Exam Catalog & Exam Instructions

---

## 1. Purpose and Scope

The **Student Exam Portal** provides the student-facing presentation layer for discovering, initiating, completing, and reviewing online assessments within OmniSight-AI.

Following the successful implementation and verification of the **Teacher Exam Studio** (Part 1A & Part 1B), this document defines the detailed architectural and interaction design for **Part 2A: Published Exam Catalog & Exam Instructions**, to be implemented in `src/ui/student_ui.py`.

### 1.1 Scope of Part 2A
Part 2A encompasses:
1. **Student Role Guarding**: Verifying authenticated student identity via `src/auth/session.py`.
2. **Published Exam Catalog**: Discovering and listing active assessments in `PUBLISHED` status.
3. **Exam Card Presentation**: Rendering clean exam cards displaying title, description summary, duration, and attempt status.
4. **Attempt State Discrimination**: Identifying whether the student has not attempted, is currently taking, or has already completed an exam.
5. **Exam Instructions View**: Providing a dedicated pre-flight instructions screen with syllabus details, duration, single-attempt policy, and rules before timer initiation.
6. **Attempt Initialization**: Safely invoking the existing `start_attempt(exam_id, student_id)` service function and transitioning the presentation state into the active exam view.
7. **Strict UI/Service Separation**: Guaranteeing zero SQL, zero answer key exposure, and zero duplicate lifecycle logic in the UI layer.

### 1.2 Explicit Non-Scope for Part 2A and Phase 4
As mandated by master project guidelines and architectural roadmap:
- **No Webcam / Video Feeds**: No camera capture, frame processing, or permissions requests.
- **No OpenCV / MediaPipe**: No computer vision, facial landmarks, or gaze estimation.
- **No Monitoring Events**: No tab-switch logging, face absence detection, or background event capture.
- **No Behavioral Telemetry**: No response-time modeling or keystroke analysis.
- **No Machine Learning**: No baseline models, risk prediction, or anomaly detection.
- **No Integrity Scoring**: No suspicion classification or cheating accusations.
- **No Question Answering UI**: Active question interaction is reserved for Part 2B.
- **No Result Scorecard UI**: Final score review is reserved for Part 2C.

---

## 2. Student-Facing Workflow

The student interaction model for Part 2A follows a clear, sequential path:

```text
+----------------------------------------------------------------------------------------------------+
|                                    STUDENT EXAM PORTAL — PART 2A                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   1. Login & Auth Check                                                                            |
|      Student signs in -> Session verifies user role == 'student'.                                 |
|                                                                                                    |
|   2. Exam Catalog View                                                                             |
|      Display list of available examinations where exams.status == 'PUBLISHED'.                     |
|                                                                                                    |
|   3. Status Discrimination per Exam Card:                                                          |
|      +---------------------+-----------------------+------------------------------------------+    |
|      | Attempt State       | Card Status Badge     | Available User Action                    |    |
|      +---------------------+-----------------------+------------------------------------------+    |
|      | NOT_STARTED         | [Available] (Blue)    | Button: "View Instructions & Start"      |    |
|      | IN_PROGRESS         | [In Progress] (Orange)| Button: "Resume Exam" (routes to Part 2B)|    |
|      | SUBMITTED/EVALUATED | [Completed] (Green)   | Button: "View Result" (routes to Part 2C)|    |
|      +---------------------+-----------------------+------------------------------------------+    |
|                                                                                                    |
|   4. Exam Instructions Screen (for NOT_STARTED):                                                  |
|      - Displays full exam metadata (title, syllabus/description, time allowance).                  |
|      - Displays assessment rules (single attempt, no pauses, auto-submission on expiration).       |
|      - Displays readiness confirmation checkbox: [x] "I am ready to begin this exam."              |
|      - Actions: [Back to Catalog] | [Start Examination]                                            |
|                                                                                                    |
|   5. Start Exam Trigger:                                                                           |
|      - Student clicks "Start Examination".                                                         |
|      - UI invokes start_attempt(exam_id, student_id).                                              |
|      - On success: Stores active_attempt_id in session_state, switches view to active exam.         |
|      - On error: Displays service error (ValueError / PermissionError) via st.error.               |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Published Exam Visibility Rules

1. **Publication Invariant**: A student can only view and attempt an examination if `exams.status = 'PUBLISHED'`.
2. **Draft Invisibility**: Examinations in `DRAFT` status are strictly hidden from students. Students cannot browse, inspect instructions for, or attempt draft exams.
3. **Closed Exam Invariant**: Examinations in `CLOSED` status cannot be initiated. If a student previously completed an attempt for a now-closed exam, they may view their historical result, but new attempts are strictly disallowed.
4. **Non-Existent Exams**: Any attempt to navigate directly to an invalid `exam_id` returns an immediate "Examination Not Found" notification and redirects to the catalog.

---

## 4. Exam Card Information Requirements

Each examination presented in the catalog is rendered within a clean, structured container (`st.container(border=True)`) containing:

- **Exam Title**: Clear prominent heading (e.g., `CS101 — Data Structures & Algorithms`).
- **Description / Syllabus Summary**: Instructions or coverage summary authored by the instructor.
- **Duration**: Displayed in minutes (e.g., `Duration: 60 minutes`).
- **Question Count & Total Points**: Number of questions and maximum achievable marks (if returned by service data).
- **Attempt Status Badge**:
  - `Available` (`#1E88E5` / Blue): No attempt initiated yet.
  - `In Progress` (`#FB8C00` / Orange): Active timed attempt exists.
  - `Completed` (`#43A047` / Green): Attempt finalized and evaluated.
- **Contextual Action Button**:
  - For `Available`: **"View Instructions"** $\rightarrow$ opens the pre-flight instructions screen.
  - For `In Progress`: **"Resume Examination"** $\rightarrow$ stores `attempt_id` and enters active testing view.
  - For `Completed`: **"View Results"** $\rightarrow$ stores `attempt_id` and navigates to scorecard.

---

## 5. Already-Attempted Exam Behavior

OmniSight-AI strictly adheres to a **single-attempt policy** per student per examination, as established in `docs/exam-attempt-design.md`:

1. **Attempt Detection**:
   - The UI evaluates existing attempts for the authenticated student using the service layer.
   - If an attempt already exists:
     - An attempt in `IN_PROGRESS` status represents an active, ongoing test session. The UI presents a **"Resume Examination"** action rather than creating a duplicate attempt.
     - An attempt in `SUBMITTED` or `EVALUATED` status represents a finalized assessment. The UI presents a **"View Result"** action.
2. **Duplicate Creation Prevention**:
   - The UI does not provide a "Start Exam" button for already-attempted exams.
   - Even if bypassed or invoked concurrently, `start_attempt(exam_id, student_id)` at the service layer queries `exam_attempts` and raises:
     `ValueError("You have already initiated or completed an attempt for this examination.")`
   - The UI catches this exception gracefully and displays `st.warning("You have already completed or initiated an attempt for this examination.")`.

---

## 6. Exam Instructions Screen (Pre-Flight View)

Before the examination timer starts running on the server, the student is presented with an **Instructions Screen**. This prevents accidental time consumption and guarantees student informed consent.

### 6.1 Display Elements
- **Assessment Header**: Full title, creator name (if available), duration limit.
- **Instructions & Syllabus**: Complete description and guidelines provided by the teacher.
- **Operational Rules**:
  - **Single Attempt**: Students may only start and submit this examination once.
  - **Server-Side Timing**: The countdown timer starts immediately upon clicking "Start Examination" and runs continuously.
  - **Auto-Submission**: If the time limit expires, the examination will be automatically finalized and submitted.
  - **Objective Scoring**: All questions are multiple-choice with a single correct option. Questions left unanswered receive zero marks without negative penalty.
- **Integrity Notice**: Reminder to maintain academic honesty and adhere to institutional policies.
- **Readiness Checkbox**:
  `st.checkbox("I have read and understood all examination instructions and am ready to begin.")`

### 6.2 Controls
- **"Back to Catalog" Button**: Returns to the exam catalog without modifying database state or consuming an attempt.
- **"Start Examination" Button**: Primary action button. Disabled or validated against the readiness checkbox. Triggers `start_attempt()`.

---

## 7. Start Exam Action & Service Layer Mapping

When the student confirms readiness and clicks **"Start Examination"**:

```text
Student Clicks [Start Examination]
             |
             v
Validate Readiness Checkbox (UI)
             |
             v
Call: start_attempt(exam_id, student_id) in src/exam/service.py
             |
             +---> Database creates row in exam_attempts:
             |     - status = 'IN_PROGRESS'
             |     - started_at = NOW()
             |     - submitted_at = NULL
             |
             +---> Returns attempt dictionary:
             |     {
             |         "attempt_id": 42,
             |         "exam_id": 5,
             |         "student_id": 12,
             |         "started_at": datetime(...),
             |         "submitted_at": None,
             |         "status": "IN_PROGRESS"
             |     }
             |
             v
Update Streamlit Session State:
  - st.session_state["student_view"] = "active_exam"
  - st.session_state["active_attempt_id"] = attempt["attempt_id"]
  - st.session_state["active_exam_id"] = exam_id
             |
             v
st.rerun() -> Hands execution over to Part 2B (Exam Taking UI)
```

### Exception Handling Mapping:
- `ValueError` (Exam not published, already attempted, invalid ID):
  $\rightarrow$ Rendered via `st.error(f"Cannot start examination: {str(e)}")`.
- `PermissionError` (Non-student role attempted invocation):
  $\rightarrow$ Rendered via `st.error("Permission Denied: Only students are permitted to attempt examinations.")`.
- `Exception` (Database connection disruption or unexpected failure):
  $\rightarrow$ Rendered via `st.error(f"Failed to initiate examination session: {str(e)}")`.

---

## 8. Student Ownership & Security Considerations

1. **Identity Source**:
   - The student user ID is **never** accepted from untrusted client sources (URL query parameters, hidden form fields, or client cookies).
   - Identity is obtained exclusively from `get_current_user()` in `src/auth/session.py`.
2. **Role Verification**:
   - Every student view entrypoint enforces `require_role(["student"])`. If an unauthenticated user or an instructor accesses the page, access is denied immediately.
3. **Data Sanitization**:
   - In Part 2A, question answer keys (`correct_option`) are **never requested or rendered**. Questions are not even loaded during the catalog or instructions phase.
4. **Immutability of Server State**:
   - Client-side browser clocks are ignored; attempt initiation records the authoritative MySQL `NOW()` timestamp.

---

## 9. Streamlit Session-State Architecture

To guarantee predictable navigation across Streamlit rerun cycles without state desynchronization, `src/ui/student_ui.py` uses structured session-state keys:

| Session Key | Data Type | Permitted Values | Purpose |
| :--- | :--- | :--- | :--- |
| `student_view` | `str` | `"catalog"`, `"instructions"`, `"active_exam"`, `"result"` | Primary view router within the Student Exam Portal. |
| `selected_exam_id` | `Optional[int]` | `None` or positive integer | Identifies the exam currently being inspected in the Instructions view. |
| `active_attempt_id`| `Optional[int]` | `None` or positive integer | Identifies the active `IN_PROGRESS` attempt being taken in Part 2B. |
| `view_result_attempt_id` | `Optional[int]` | `None` or positive integer | Identifies the evaluated attempt being inspected in Part 2C. |
| `student_flash_msg`| `Optional[str]` | `None` or descriptive string | Flash notification message displayed across view reruns. |

### Navigation State Machine for Part 2A:
- **Default State**: `student_view = "catalog"`, `selected_exam_id = None`.
- **View Instructions**: `selected_exam_id = exam_id`, `student_view = "instructions"`, `st.rerun()`.
- **Back to Catalog**: `selected_exam_id = None`, `student_view = "catalog"`, `st.rerun()`.
- **Start / Resume Exam**: `active_attempt_id = attempt_id`, `student_view = "active_exam"`, `st.rerun()`.
- **View Result**: `view_result_attempt_id = attempt_id`, `student_view = "result"`, `st.rerun()`.

---

## 10. UI and Service Layer Separation of Concerns

```text
+-----------------------------------------------------------------------------------+
|                         Presentation Layer: student_ui.py                         |
|                                                                                   |
|  - Renders Streamlit layouts, cards, and instruction views.                       |
|  - Maintains view routing via st.session_state["student_view"].                   |
|  - Performs client-side readiness checks (e.g. confirmation checkbox).            |
|  - Catches ValueError and PermissionError, rendering clean st.error alerts.       |
|  - ZERO SQL QUERIES.                                                              |
|  - ZERO DIRECT DATABASE CONNECTIONS.                                              |
|  - ZERO ATTEMPT SCORING OR TIMING CALCULATIONS.                                   |
+------------------------------------------+----------------------------------------+
                                           | (Pure Python Function Calls)
                                           v
+-----------------------------------------------------------------------------------+
|                        Business Service Layer: service.py                         |
|                                                                                   |
|  - start_attempt(exam_id, student_id)                                             |
|  - get_exam(exam_id)                                                              |
|  - get_attempt(attempt_id, student_id)                                            |
|  - get_attempt_result(attempt_id, student_id)                                     |
|  - (Catalog helper service function for published exams + student attempt status) |
|                                                                                   |
|  * Enforces role authorization and exam ownership.                                |
|  * Enforces single-attempt invariants and PUBLISHED status checks.                |
|  * Executes parameterized database queries with transactional rollback on failure.|
+-----------------------------------------------------------------------------------+
```

---

## 11. Existing Service Functions & Catalog Service Requirements

### 11.1 Existing Service Functions Reused:
- `start_attempt(exam_id: int, student_id: int) -> Dict[str, Any]` (Phase 4 Step 2C)
- `get_exam(exam_id: int) -> Optional[Dict[str, Any]]` (Phase 4 Step 2A)
- `get_attempt(attempt_id: int, student_id: int) -> Dict[str, Any]` (Phase 4 Step 2C)
- `get_attempt_result(attempt_id: int, student_id: int) -> Dict[str, Any]` (Phase 4 Step 2C)

### 11.2 Catalog Service Support:
In keeping with the rule that **UI must contain no SQL**, `src/ui/student_ui.py` cannot execute `SELECT * FROM exams WHERE status='PUBLISHED'`.
The service layer (`src/exam/service.py`) will need a clean, parameterized helper function:
- `get_published_exams() -> List[Dict[str, Any]]`: Retrieves all exams currently in `PUBLISHED` status.
- `get_student_attempt_for_exam(exam_id: int, student_id: int) -> Optional[Dict[str, Any]]`: Returns the student's existing attempt record for the given exam, or `None` if not attempted.

*(Note: In accordance with prompt constraints, these helpers will be formally introduced during the implementation step without modifying `src/exam/service.py` during this design-only step).*

---

## 12. ASCII Architecture & Flow Diagram

```text
+-----------------------------------------------------------------------------------------------------+
|                                          OMNISIGHT-AI                                               |
|                                 Student Exam Portal Architecture                                    |
+-----------------------------------------------------------------------------------------------------+
|                                                                                                     |
|    [Student Browser]                                                                                |
|           |                                                                                         |
|           v                                                                                         |
|    +-------------------------------------------------------------------------------------------+    |
|    | src/ui/student_ui.py                                                                      |    |
|    |                                                                                           |    |
|    |   +-----------------------+         +-----------------------+                             |    |
|    |   | render_student_header |         | render_exam_catalog   |                             |    |
|    |   +-----------------------+         +-----------------------+                             |    |
|    |                                                 |                                         |    |
|    |                         [View Instructions]     | [Resume / View Result]                  |    |
|    |                                 v               v                                         |    |
|    |                     +-------------------------------+                                     |    |
|    |                     | render_exam_instructions      |                                     |    |
|    |                     +-------------------------------+                                     |    |
|    |                                 |                                                         |    |
|    |                         [Start Examination]                                               |    |
|    |                                 v                                                         |    |
|    |                     +-------------------------------+                                     |    |
|    |                     | start_attempt(exam, student)  |                                     |    |
|    |                     +-------------------------------+                                     |    |
|    +---------------------------------+---------------------------------------------------------+    |
|                                      |                                                              |
|                                      | Service API Calls (No SQL in UI)                             |
|                                      v                                                              |
|    +-------------------------------------------------------------------------------------------+    |
|    | src/exam/service.py                                                                       |    |
|    |                                                                                           |    |
|    |   - get_published_exams()                                                                 |    |
|    |   - get_student_attempt_for_exam(exam_id, student_id)                                     |    |
|    |   - get_exam(exam_id)                                                                     |    |
|    |   - start_attempt(exam_id, student_id)                                                    |    |
|    +---------------------------------+---------------------------------------------------------+    |
|                                      |                                                              |
|                                      | Parameterized SQL Queries                                    |
|                                      v                                                              |
|    +-------------------------------------------------------------------------------------------+    |
|    | MySQL Database (OmniSight-AI Schema)                                                      |    |
|    |   - exams (status = 'PUBLISHED')                                                          |    |
|    |   - exam_attempts (status: 'IN_PROGRESS', 'SUBMITTED', 'EVALUATED')                       |    |
|    |   - users (role = 'student')                                                              |    |
|    +-------------------------------------------------------------------------------------------+    |
|                                                                                                     |
+-----------------------------------------------------------------------------------------------------+
```

---

## 13. Acceptance Criteria for Part 2A

The implementation of Part 2A will be evaluated against the following criteria:

1. **Authentication & Role Guard**:
   - [ ] Access is restricted strictly to authenticated users with role `student`. Teachers/admins or unauthenticated users receive access denial.
2. **Catalog Retrieval & Visibility**:
   - [ ] Only examinations with `status = 'PUBLISHED'` are displayed in the student catalog.
   - [ ] `DRAFT` examinations are completely hidden.
3. **Card Information Presentation**:
   - [ ] Each published exam card clearly shows title, description summary, duration in minutes, and attempt status badge.
4. **Attempt Discrimination**:
   - [ ] An unattempted exam displays `Available` and a "View Instructions & Start" action.
   - [ ] An active attempt displays `In Progress` and a "Resume Examination" action.
   - [ ] A completed attempt displays `Completed` and a "View Results" action.
5. **Exam Instructions Screen**:
   - [ ] Displays full instructions, syllabus, time limit, objective format, and grading policy.
   - [ ] Provides a working "Back to Catalog" button that safely returns without state loss.
   - [ ] Requires readiness confirmation before enabling "Start Examination".
6. **Attempt Initialization**:
   - [ ] Clicking "Start Examination" calls `start_attempt(exam_id, student_id)` through the service layer.
   - [ ] The returned `attempt_id` is persisted in `st.session_state`.
   - [ ] Re-attempting an already initiated exam is blocked by the service and handled with an error banner.
7. **Architectural Purity**:
   - [ ] `student_ui.py` contains **zero SQL queries**.
   - [ ] `student_ui.py` contains **zero answer keys** or evaluation logic.
   - [ ] No changes to database schema or non-UI existing modules.
