# OmniSight-AI — Active Examination Interface Design Specification
## Part 2B-1: Active Exam Foundation & Question Rendering

---

## 1. Purpose and Scope

The **Active Examination Interface** represents the operational core of the Student Exam Portal (`src/ui/student_ui.py`), where an examinee interacts with assessment content under an active session.

Following the completion of **Part 2A** (Published Exam Catalog and Exam Instructions), this document specifies the detailed architecture for **Part 2B-1: Active Exam Foundation & Question Rendering**.

### 1.1 Scope of Part 2B-1
This initial sub-slice establishes:
1. **View Transition**: Transitioning smoothly from the Part 2A pre-flight instructions screen into active examination mode.
2. **Session State Maintenance**: Maintaining and recovering the `active_attempt_id` across Streamlit rerun cycles.
3. **Attempt Validation**: Verifying that the attempt is valid, belongs to the authenticated student, and remains in `IN_PROGRESS` status before rendering questions.
4. **Safe Question Retrieval**: Invoking the existing `get_attempt_questions(attempt_id, student_id)` service function.
5. **Student-Safe Data Invariant**: Confirming that correct answer keys (`correct_option`) are excluded at the service layer and never reach the client UI.
6. **Question Presentation Card**: Structuring the layout for presenting the active question (header, mark weight, question prompt, and 4 choices A–D).
7. **Current-Question Pointer**: Managing the active question index within session state (`current_question_index`).
8. **Initial Selection & State Isolation**: Ensuring predictable question loading and preventing widget state contamination.
9. **Error & Fallback Handling**: Gracefully redirecting to the catalog if an attempt is missing, invalid, expired, or completed.

### 1.2 Explicit Non-Scope for Slice 2B-1
To ensure verifiable and incremental development:
- **No Answer Persistence**: Saving or upserting selected answers via `save_answer()` is reserved for **Part 2B-2**.
- **No Navigation Controls**: "Previous", "Next", and question jumping grids are reserved for **Part 2B-2**.
- **No Timer Widget / Countdown**: Client-side timer rendering and auto-expiration detection are reserved for **Part 2B-3**.
- **No Submission Actions**: Calling `submit_attempt()` or `evaluate_attempt()` is reserved for **Part 2B-4**.
- **No Proctoring / MediaPipe / OpenCV**: Zero webcam access, facial landmarking, or gaze tracking (Phase 5).
- **No Behavioral Telemetry**: Zero keystroke, mouse, or event logging (Phase 6).
- **No ML / Integrity Scoring**: Zero baseline models, suspicion metrics, or risk flags (Phase 7–8).

---

## 2. Transition from Part 2A to Active Examination

The student enters the active examination view through one of two legitimate pathways:

```text
Path 1: Fresh Attempt Initiation (Part 2A Instructions)
[Exam Catalog] 
     --> Click "View Instructions" (sets student_view = "instructions")
     --> Review instructions & check readiness box
     --> Click "Start Examination"
     --> start_attempt(exam_id, student_id) returns new attempt_id
     --> Sets st.session_state["active_attempt_id"] = attempt_id
     --> Sets st.session_state["student_view"] = "active_exam"
     --> st.rerun()

Path 2: In-Progress Attempt Resumption (Part 2A Catalog)
[Exam Catalog]
     --> Detects existing attempt with status == "IN_PROGRESS"
     --> Click "Resume Exam"
     --> Sets st.session_state["active_attempt_id"] = attempt_id
     --> Sets st.session_state["student_view"] = "active_exam"
     --> st.rerun()
```

When `render_student_ui()` executes with `st.session_state["student_view"] == "active_exam"`, it delegates presentation to `render_active_exam(student_id: int, attempt_id: Optional[int])`.

---

## 3. Session State Maintenance for `active_attempt_id`

Streamlit re-executes the entire script upon any user interaction. To prevent attempt loss or desynchronization:

1. **Authoritative Session Keys**:
   - `st.session_state["active_attempt_id"]`: Stores the active integer `attempt_id`.
   - `st.session_state["active_exam_id"]`: Stores the associated integer `exam_id`.
   - `st.session_state["q_index_<attempt_id>"]`: Tracks the active 0-based question pointer.
2. **Persistence Guarantee**:
   - `active_attempt_id` remains stored in `st.session_state` until explicit assessment submission (Part 2B-4) or manual catalog exit.
3. **Missing State Recovery**:
   - If `active_attempt_id` is missing or `None` when `student_view == "active_exam"`, the UI treats this as an orphaned state:
     - Sets `st.session_state["student_view"] = "catalog"`
     - Displays `st.warning("No active examination session found. Returning to catalog.")`
     - Calls `st.rerun()`.

---

## 4. Active Attempt Pre-Render Validation

Before any questions or exam content are rendered, the UI performs rigorous validation against `src/exam/service.py`:

```mermaid
flowchart TD
    Start[Active Exam Request] --> CheckAttemptId{active_attempt_id present?}
    CheckAttemptId -- No --> RedirectCatalog[Clear State & Redirect to Catalog]
    CheckAttemptId -- Yes --> CallGetAttempt[Call get_attempt(active_attempt_id, student_id)]
    
    CallGetAttempt -- ValueError / PermissionError --> ShowError[st.error & Redirect to Catalog]
    CallGetAttempt -- Success --> CheckStatus{attempt.status == 'IN_PROGRESS'?}
    
    CheckStatus -- SUBMITTED / EVALUATED --> RedirectResult[Set student_view = 'result' & Redirect]
    CheckStatus -- Other / Invalid --> AbortAttempt[Show Error & Return to Catalog]
    CheckStatus -- IN_PROGRESS --> LoadQuestions[Call get_attempt_questions(attempt_id, student_id)]
```

### Pre-Render Invariants:
1. **Student Ownership**: `get_attempt(attempt_id, student_id)` strictly verifies that `attempt["student_id"] == student_id`. Cross-student attempt hijacking raises `PermissionError` and is halted.
2. **Lifecycle State**:
   - If `attempt["status"] == "IN_PROGRESS"`: Proceed to render questions.
   - If `attempt["status"] in {"SUBMITTED", "EVALUATED"}`: The exam was already concluded (e.g. from another tab or deadline expiration). The UI sets `st.session_state["view_result_attempt_id"] = attempt_id`, sets `student_view = "result"`, and reruns.
3. **Exam Existence**: Verifies associated exam details via `get_exam(attempt["exam_id"])`.

---

## 5. Safe Question Retrieval via Existing Service Layer

Questions are retrieved using ONLY the existing service function:
```python
questions: List[Dict[str, Any]] = get_attempt_questions(attempt_id, student_id)
```

### 5.1 Service-Level Guarantees
In `src/exam/service.py`, `get_attempt_questions()` executes:
```sql
SELECT question_id, question_text, option_a, option_b, option_c, option_d, marks
FROM questions
WHERE exam_id = %s
ORDER BY question_id ASC;
```
- **Zero Answer Key Leakage**: Notice that `correct_option` is **never selected** in the SQL query.
- The returned dictionaries contain only:
  - `question_id`: integer
  - `question_text`: string prompt
  - `option_a`: string
  - `option_b`: string
  - `option_c`: string
  - `option_d`: string
  - `marks`: integer point weight
- **Strict Prohibition**: Under no circumstances does `student_ui.py` request, compute, or expose `correct_option`.

---

## 6. Question Presentation Structure

For slice 2B-1, the question interface renders a clean, focused single-question presentation card:

```text
+----------------------------------------------------------------------------------------------------+
| CS101 — Introduction to Computer Science                                           [Attempt #12]   |
+----------------------------------------------------------------------------------------------------+
| Question 1 of 10                                                                  Points: 2 Mark(s)|
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
| Which of the following data structures operates on a First-In-First-Out (FIFO) principle?         |
|                                                                                                    |
| ( ) A. Stack                                                                                       |
| ( ) B. Queue                                                                                       |
| ( ) C. Tree                                                                                        |
| ( ) D. Graph                                                                                       |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
| [Notice: Option selection and navigation controls will be enabled in slice 2B-2]                  |
| [Exit to Catalog]                                                                                  |
+----------------------------------------------------------------------------------------------------+
```

### 6.1 Visual Component Hierarchy:
1. **Exam Header Banner**:
   - Examination title (`exam["title"]`).
   - Current attempt identifier badge (`Attempt ID: #...`).
2. **Question Context Bar**:
   - Question counter: `Question {index + 1} of {total_questions}`.
   - Points badge: `Marks: {current_question["marks"]}`.
3. **Question Card Container (`st.container(border=True)`)**:
   - Prompt statement rendered prominently via `st.markdown()` or `st.write()`.
   - Option choices presented clearly:
     - Formatted as distinct labels: Option A, Option B, Option C, Option D.
4. **Temporary Safe Exit Control**:
   - An "Exit to Catalog" button allowing safe return to the dashboard during 2B-1 testing without terminating the attempt.

---

## 7. Current-Question State Management

To track which question is currently rendered:

1. **State Key**: `st.session_state[f"q_index_{attempt_id}"]` (0-based integer).
2. **Initialization**:
   ```python
   index_key = f"q_index_{attempt_id}"
   if index_key not in st.session_state:
       st.session_state[index_key] = 0
   ```
3. **Boundary Enforcing**:
   ```python
   current_idx = st.session_state[index_key]
   if current_idx < 0:
       current_idx = 0
       st.session_state[index_key] = 0
   elif current_idx >= len(questions):
       current_idx = len(questions) - 1
       st.session_state[index_key] = current_idx
   ```
4. **Active Question Extraction**:
   ```python
   current_question = questions[current_idx]
   ```

---

## 8. Initial Question Selection & State Isolation

When a question is rendered:
1. **Widget Key Isolation**:
   Streamlit maintains widget identity across reruns via keys. For the option selector:
   `key=f"option_choice_{attempt_id}_{current_question['question_id']}"`
   This ensures that choices for Question 1 never bleed into Question 2 upon re-rendering.
2. **Read-Only / Display Mode for 2B-1**:
   In slice 2B-1, the option selection widget renders the choices without triggering `save_answer()`. The persistence callback and validation will be hooked up in slice 2B-2.

---

## 9. Handling Missing, Invalid, or Terminated Attempts

| Failure Scenario | Detection Point | Action / System Response |
| :--- | :--- | :--- |
| **`active_attempt_id` is None** | UI entrypoint | Set `student_view = "catalog"`, show warning, trigger `st.rerun()`. |
| **Attempt not found in DB** | `get_attempt()` raises `ValueError` | Catch error, clear session keys, display `st.error`, return to catalog. |
| **Student does not own attempt** | `get_attempt()` raises `PermissionError`| Catch error, log unauthorized attempt, display access denied alert. |
| **Attempt already SUBMITTED** | `attempt["status"] == "SUBMITTED"` | Set `view_result_attempt_id = attempt_id`, route to `"result"`. |
| **Attempt already EVALUATED** | `attempt["status"] == "EVALUATED"` | Set `view_result_attempt_id = attempt_id`, route to `"result"`. |
| **Exam has zero questions** | `len(questions) == 0` | Display warning that exam has no questions, provide catalog exit button. |

---

## 10. UI and Service Layer Separation

```text
+------------------------------------------------------------------------------------+
|                          Presentation Layer: student_ui.py                         |
|                                                                                    |
|  - render_active_exam(student_id, attempt_id)                                      |
|  - Validates active_attempt_id presence in session state.                          |
|  - Renders question container, options, and progress badges.                       |
|  - Tracks active question index in session state.                                  |
|  - ZERO SQL QUERIES.                                                               |
|  - ZERO CORRECT ANSWER KEYS EXPOSED.                                               |
|  - ZERO TIMING CALCULATION TAMPERING.                                              |
+-----------------------------------------+------------------------------------------+
                                          | (Service API Calls Only)
                                          v
+------------------------------------------------------------------------------------+
|                         Business Service Layer: service.py                         |
|                                                                                    |
|  - get_attempt(attempt_id, student_id)                                             |
|  - get_attempt_questions(attempt_id, student_id)                                   |
|  - get_exam(exam_id)                                                               |
|                                                                                    |
|  * Enforces role authorization and student ownership.                             |
|  * Filters questions by exam_id (excludes correct_option from SELECT).             |
|  * Returns immutable safe dictionaries.                                            |
+------------------------------------------------------------------------------------+
```

---

## 11. Streamlit Rerun and State Flow Diagram

```text
+----------------------------------------------------------------------------------------------------+
|                                      ACTIVE EXAM STATE MACHINE                                     |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|                             st.session_state["student_view"]                                       |
|                                            |                                                       |
|                     +----------------------+----------------------+                                |
|                     |                                             |                                |
|             == "catalog"                                  == "active_exam"                         |
|                     |                                             |                                |
|                     v                                             v                                |
|           render_exam_catalog()                    render_active_exam()                            |
|                     |                                             |                                |
|             [Start/Resume Exam]                                   |                                |
|                     |                                             v                                |
|                     +-------------------------------> Check active_attempt_id                      |
|                                                                   |                                |
|                                                +------------------+------------------+             |
|                                                |                                     |             |
|                                             Missing?                              Valid?           |
|                                                |                                     |             |
|                                                v                                     v             |
|                                        Redirect to Catalog               get_attempt(attempt_id)   |
|                                                                                      |             |
|                                                                       +--------------+-----------+ |
|                                                                       |                          | |
|                                                                  IN_PROGRESS?               Other? |
|                                                                       |                          | |
|                                                                       v                          v |
|                                                          get_attempt_questions()      Route Result |
|                                                                       |                            |
|                                                                       v                            |
|                                                          Render Question #1 of N                   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 12. Acceptance Criteria for Part 2B-1

The implementation of Part 2B-1 will be accepted when all of the following conditions are met:

1. **Session State Routing**:
   - [ ] When `student_view == "active_exam"`, the portal invokes `render_active_exam()` instead of rendering the placeholder.
   - [ ] Missing or orphaned `active_attempt_id` gracefully returns to the catalog without application crash.
2. **Attempt Validation**:
   - [ ] Queries `get_attempt(attempt_id, student_id)` before displaying exam content.
   - [ ] Rejects cross-student access with an unauthorized error banner.
   - [ ] Already submitted or evaluated attempts are intercepted and routed away from the active interface.
3. **Question Retrieval & Data Sanitization**:
   - [ ] Calls `get_attempt_questions(attempt_id, student_id)` to load questions.
   - [ ] Explicitly verified that no `correct_option` field is present or accessible in the UI data structures.
4. **Question Presentation**:
   - [ ] Displays examination title and current attempt identifier.
   - [ ] Displays question index indicator (e.g. "Question 1 of N") and points badge.
   - [ ] Clearly renders the question prompt text and all 4 options (A, B, C, D).
5. **Question Pointer Initialization**:
   - [ ] Correctly initializes `q_index_<attempt_id>` to `0` and clamps index within bounds `[0, total_questions - 1]`.
6. **Architectural Purity**:
   - [ ] `student_ui.py` contains **zero SQL queries**.
   - [ ] No modifications to database schema or existing service functions.
   - [ ] Teacher Exam Studio and Catalog flows remain intact.
