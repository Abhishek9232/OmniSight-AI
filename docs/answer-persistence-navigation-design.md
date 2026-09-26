# OmniSight-AI — Active Examination Interface Design Specification
## Part 2B-2: Option Selection, Answer Persistence & Question Navigation

---

## 1. Purpose and Scope

Following the successful implementation and verification of **Part 2B-1** (Active Exam Foundation & Single-Question Presentation), this document establishes the technical design and architectural specification for **Part 2B-2: Option Selection, Answer Persistence & Question Navigation**.

In this sub-slice, examinees gain the interactive capabilities required to navigate an assessment, select and update answers with guaranteed database durability, inspect an overview Question Palette, and transition across questions without state collisions or data loss.

### 1.1 In-Scope for Part 2B-2
1. **Interactive Option Selection**: Examinee selects one of the 4 MCQ options (A, B, C, D) for the active question.
2. **Answer Persistence Integration**: Directly invoking the existing `save_answer(attempt_id, student_id, question_id, selected_option)` service function upon selection or save action.
3. **Database Durability & Upsert Atomicity**: Persisting or modifying answer records directly in the MySQL `answers` table.
4. **Answer Restoration**: Re-populating previously saved choices when returning to a question via Previous, Next, or the Question Palette.
5. **Clear Answer Capability**: Permitting examinees to deselect/clear an answer (`selected_option=None`), resetting the question to an unanswered state.
6. **Sequential Navigation Controls**: Implementing "Previous Question" and "Next Question" buttons with boundary checks.
7. **Question Palette Grid**: Providing an interactive matrix of all questions indicating their state (`Current`, `Answered`, `Unanswered`) with one-click direct jump navigation.
8. **Ownership & Timing Enforcement**: Delegating student identity, exam association, and deadline checks to `save_answer()`.
9. **Zero Answer Key Leakage Invariant**: Strict preservation of client-side masking; `correct_option` is never fetched or exposed.
10. **Strict UI/Service Separation**: Zero SQL queries inside `src/ui/student_ui.py`.

### 1.2 Explicit Non-Scope for Part 2B-2
- **No Client Countdown Timer UI**: Elapsed/remaining time display and ticking timer components are reserved for **Part 2B-3**.
- **No Submission Actions**: Calling `submit_attempt()` or finalizing attempts is reserved for **Part 2B-4**.
- **No Evaluation or Scoring**: Calling `evaluate_attempt()` or computing marks is reserved for **Part 2B-4**.
- **No Result Scorecard**: Score display is reserved for **Part 2C**.
- **No Proctoring / Telemetry / ML**: Zero webcam, facial detection, keystroke logging, or integrity risk calculation (Phases 5–8).
- **No Schema Mutations**: Zero alterations to existing MySQL tables, indexes, or columns.

---

## 2. Option Selection Workflow

The examinee interacts with a structured question card providing clear visual choices and persistence controls:

```text
+----------------------------------------------------------------------------------------------------+
| CS101 — Introduction to Computer Science                                          [Attempt #19]    |
+----------------------------------------------------------------------------------------------------+
| Question 2 of 5                                                                  Points: 2 Mark(s) |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
| Which of the following data structures operates on a First-In-First-Out (FIFO) principle?         |
|                                                                                                    |
| ( ) A. Stack                                                                                       |
| (*) B. Queue                                                                                       |
| ( ) C. Tree                                                                                        |
| ( ) D. Graph                                                                                       |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
| [ < Previous Question ]     [ Clear Selection ]     [ Save & Next > ]                              |
+----------------------------------------------------------------------------------------------------+
| QUESTION PALETTE:                                                                                  |
| [ 1: Answered ]  [ *2: Current ]  [ 3: Unanswered ]  [ 4: Unanswered ]  [ 5: Unanswered ]          |
+----------------------------------------------------------------------------------------------------+
```

### 2.1 Interaction Steps
1. The examinee views Question $i$. The UI retrieves any previously saved answer from session memory (or service).
2. The examinee selects a radio option (A, B, C, or D).
3. The UI persists the selection by calling `save_answer(attempt_id, student_id, question_id, selected_option)`:
   - When the student clicks **"Save & Next"**, or **"Save Answer"**, or upon widget interaction.
4. The service layer executes an atomic database UPSERT and returns the updated answer record.
5. The session-state answers cache is updated immediately: `answers_cache[question_id] = selected_option`.
6. The Question Palette badge for Question $i$ dynamically switches from `Unanswered` to `Answered`.

---

## 3. Mapping to Existing `save_answer()` Service Function

All answer persistence operations map strictly to the existing function in `src/exam/service.py`:

```python
def save_answer(
    attempt_id: int,
    student_id: int,
    question_id: int,
    selected_option: Optional[str]
) -> Dict[str, Any]:
```

### 3.1 Input Mapping
| UI Component / Value | Service Parameter | Type | Validation / Constraints |
| :--- | :--- | :--- | :--- |
| `st.session_state["active_attempt_id"]` | `attempt_id` | `int` | Must be positive int, matching active session. |
| `get_current_user()["id"]` | `student_id` | `int` | Must match authenticated student. |
| `current_question["question_id"]` | `question_id` | `int` | Must be an active question in the attempt's exam. |
| Selected radio choice or `None` | `selected_option` | `Optional[str]` | Must normalize to `'A'`, `'B'`, `'C'`, `'D'`, or `None`. |

### 3.2 Service Return Payload
`save_answer()` returns a sanitized dictionary:
```python
{
    "answer_id": int,
    "attempt_id": int,
    "question_id": int,
    "selected_option": Optional[str],
    "answered_at": datetime
}
```
Note that `is_correct` remains `NULL` in the database until evaluation in Part 2B-4. The return payload contains zero evaluation data and zero answer keys.

---

## 4. Answer Persistence Behavior and Atomicity

Persistence in OmniSight-AI is governed by strict database atomicity and server-side rules:

### 4.1 Database Atomicity (UPSERT)
Inside `save_answer()`, database operations are wrapped within a transaction:
1. Query `answers` for existing record:
   ```sql
   SELECT answer_id FROM answers WHERE attempt_id = %s AND question_id = %s LIMIT 1;
   ```
2. **If record exists**:
   ```sql
   UPDATE answers 
   SET selected_option = %s, answered_at = NOW() 
   WHERE answer_id = %s;
   ```
3. **If record does not exist**:
   ```sql
   INSERT INTO answers (attempt_id, question_id, selected_option, is_correct, answered_at) 
   VALUES (%s, %s, %s, NULL, NOW());
   ```
4. `conn.commit()` ensures immediate durability. If any query fails, `conn.rollback()` executes, preventing partial or corrupt records.

### 4.2 Handling Changes to Already-Saved Answers
- If a student changes their answer from `'A'` to `'B'`, the existing row is updated in place.
- No duplicate records are created in `answers` for the same `(attempt_id, question_id)` pair.
- The `answered_at` timestamp is updated to the current time.

### 4.3 Handling Answer Deletion / Clearing
- If a student clicks **"Clear Selection"**, `save_answer()` is called with `selected_option=None`.
- The database row updates `selected_option = NULL`.
- The question transitions to `Unanswered` in the session cache and Question Palette.

---

## 5. Answer Restoration and Cold-Start Recovery

A critical requirement of an online examination system is that a student must never lose their answered state when navigating between questions or refreshing the browser.

### 5.1 Intra-Session Caching
During an active session, `st.session_state` maintains an in-memory answers cache:
```python
cache_key = f"attempt_answers_{attempt_id}"
# Structure: { question_id (int): selected_option (str or None) }
if cache_key not in st.session_state:
    st.session_state[cache_key] = {}
```

### 5.2 Cold-Start / Browser Reload Recovery
If a student refreshes their browser or resumes an in-progress exam from the catalog, `st.session_state` is initially empty for that connection. 

To prevent data desynchronization without writing SQL in the presentation layer, the service layer can provide a read-only helper:
```python
def get_attempt_answers(attempt_id: int, student_id: int) -> Dict[int, Optional[str]]:
    """
    Retrieve all previously saved answer selections for an attempt.
    Returns: Dict mapping question_id -> selected_option.
    """
```
**Cold-Start Flow:**
1. Upon loading `render_active_exam()`, the UI checks if `f"attempt_answers_{attempt_id}"` exists in `session_state`.
2. If missing, it invokes `get_attempt_answers(attempt_id, student_id)`.
3. The returned mapping `{question_id: selected_option}` is populated into `st.session_state[cache_key]`.
4. All subsequent renders and palette indicators draw from this verified state.

### 5.3 Widget Value Restoration
When Question $i$ is rendered:
```python
saved_option = st.session_state[cache_key].get(current_question["question_id"])
# Determine default radio index:
option_list = ["A", "B", "C", "D"]
default_idx = option_list.index(saved_option) if saved_option in option_list else None
```
The radio widget is initialized with `index=default_idx`. If `saved_option` is `None` or absent, `index=None` ensures no option appears selected.

---

## 6. Student, Attempt, and Question Ownership Validation

Security boundaries are strictly enforced before every state mutation:

```mermaid
flowchart TD
    UserAction[Student Selects Option / Clicks Save] --> CallUI[UI invokes save_answer()]
    CallUI --> RoleCheck{Caller role == 'student'?}
    RoleCheck -- No --> DenyRole[PermissionError: Role Denied]
    RoleCheck -- Yes --> AttemptCheck{Attempt exists & belongs to student?}
    AttemptCheck -- No --> DenyAttempt[PermissionError: Unauthorized Attempt]
    AttemptCheck -- Yes --> StatusCheck{Attempt status == 'IN_PROGRESS'?}
    StatusCheck -- No --> DenyStatus[ValueError: Attempt not active]
    StatusCheck -- Yes --> TimeCheck{NOW() <= started_at + duration + grace?}
    TimeCheck -- No --> DenyTime[ValueError: Exam duration expired]
    TimeCheck -- Yes --> QCheck{Question belongs to attempt's exam?}
    QCheck -- No --> DenyQ[ValueError: Invalid Question ID]
    QCheck -- Yes --> CommitDB[Execute Atomic UPSERT & Commit]
```

### Invariants:
1. **Student Isolation**: Attempt ID ownership is checked against `student_id`. A student attempting to persist answers to another student's attempt raises `PermissionError`.
2. **Exam Consistency**: Question ID is validated against the attempt's `exam_id`. Persisting answers for questions belonging to a different exam raises `ValueError`.
3. **Status Guard**: Answers cannot be persisted if attempt status is `SUBMITTED` or `EVALUATED`.
4. **Server-Side Deadline**: If `NOW() > started_at + duration + 60s`, `save_answer()` rejects the operation with `ValueError("Exam duration has expired. Answers can no longer be saved.")`.

---

## 7. Navigation Controls Specification

The bottom section of the question card provides intuitive, robust navigation controls:

### 7.1 "Previous Question" Button
- **Label**: `← Previous`
- **Behavior**:
  - Decrements question index: `st.session_state[f"q_index_{attempt_id}"] -= 1`.
  - Clamped to minimum `0`.
  - Disabled (`disabled=True`) when `current_idx == 0`.
  - Triggers `st.rerun()`.

### 7.2 "Next Question" Button
- **Label**: `Next →`
- **Behavior**:
  - Increments question index: `st.session_state[f"q_index_{attempt_id}"] += 1`.
  - Clamped to maximum `len(questions) - 1`.
  - Disabled (`disabled=True`) when `current_idx == len(questions) - 1`.
  - Triggers `st.rerun()`.

### 7.3 "Clear Selection" Button
- **Label**: `Clear Selection`
- **Behavior**:
  - If the question has a saved answer:
    - Calls `save_answer(attempt_id, student_id, question_id, None)`.
    - Sets `answers_cache[question_id] = None`.
    - Resets the widget session state key.
    - Triggers `st.rerun()`.
  - If the question is already unanswered:
    - No-op or disabled.

### 7.4 "Save & Next" / "Save Answer" Button
- **Label**: `Save & Next →` (or `Save Answer` on the final question)
- **Behavior**:
  - Reads the current radio selection.
  - Calls `save_answer(attempt_id, student_id, question_id, selected_option)`.
  - Updates `answers_cache[question_id] = selected_option`.
  - On questions $0 \dots N-2$: advances index to $i+1$ and reruns.
  - On question $N-1$: updates answer, displays a success confirmation, and remains on question $N-1$.

---

## 8. Question Palette Specification

The **Question Palette** gives examinees a holistic view of assessment progress and allows random-access jumping across questions.

### 8.1 Visual Grid Layout
The Question Palette is rendered inside a bordered container below the active question:
- Renders as a multi-column responsive grid (e.g. 5 to 10 questions per row).
- Each question is represented by a styled button: `[ 1 ]`, `[ 2 ]`, `[ 3 ]`, $\dots$, `[ N ]`.

### 8.2 Question Status Indicators
Each palette button indicates the question's operational status:
| Status | Condition | Palette Styling / Badge |
| :--- | :--- | :--- |
| **Current** | `idx == current_idx` | Primary color, bold border, prefix `●` |
| **Answered** | `question_id in answers_cache and answers_cache[question_id] is not None` | Green badge / filled indicator (e.g. `✓`) |
| **Unanswered** | `answers_cache.get(question_id) is None` | Outline / muted secondary indicator |

### 8.3 Palette Interaction (Direct Jump)
- Clicking button `Qk`:
  1. Sets `st.session_state[f"q_index_{attempt_id}"] = k - 1`.
  2. Calls `st.rerun()`.
  3. UI immediately renders Question $k$.

### 8.4 Summary Statistics Banner
Above or below the palette buttons, the UI displays an aggregate tally:
- Total Questions: $N$
- Answered: $A$
- Unanswered: $N - A$

---

## 9. Streamlit Widget State and Rerun Considerations

Streamlit's execution model re-runs the entire script upon each user interaction. Proper widget key isolation is essential to prevent ghost selections or cross-question bleed:

### 9.1 Widget Key Isolation
The radio button for each question must use a unique, deterministic key:
```python
widget_key = f"option_choice_{attempt_id}_{current_question['question_id']}"
```
Because the key includes both `attempt_id` and `question_id`:
- Navigating from Question 1 to Question 2 completely unbinds the Question 1 widget.
- Navigating back to Question 1 re-binds to `option_choice_{attempt_id}_1`, reading its pre-populated value without contaminating Question 2.

### 9.2 Avoiding `StreamlitAPIException`
In Streamlit, modifying `st.session_state[widget_key]` directly while the widget is active can raise an exception. 
To ensure safety:
1. Always maintain the authoritative answer state in `st.session_state[f"attempt_answers_{attempt_id}"]`.
2. Supply `index=default_idx` derived from `answers_cache` when declaring `st.radio()`.
3. In action buttons (e.g. "Save & Next", "Clear Selection"), update `answers_cache` and let the subsequent `st.rerun()` synchronize the radio widget cleanly.

---

## 10. Handling Unanswered and Invalid States

| Scenario | UI / System Handling |
| :--- | :--- |
| **Student skips question without answering** | UI allows skipping freely via "Next", "Previous", or Palette. Question remains `Unanswered` in DB and Palette. |
| **Student clicks Next on last question** | "Next" button is disabled. Final question offers "Save Answer". Final submission button is non-scope for 2B-2. |
| **Student clears answer on unanswered question** | Handled gracefully without error; cache remains `None`. |
| **Exam deadline expires during attempt** | `save_answer()` raises `ValueError("Exam duration has expired...")`. UI catches exception, renders `st.error`, and locks option inputs. |
| **Database connection drops on save** | `save_answer()` rolls back transaction and raises error. UI displays `st.error("Failed to save answer. Please retry.")`; previous cached state is not corrupted. |
| **Orphaned attempt ID** | UI detects missing attempt, shows warning, and routes back to catalog. |

---

## 11. Zero Answer Key Leakage Invariant

OmniSight-AI strictly guarantees that students cannot access correct answers through browser inspection, network inspection, or session tampering:

1. **Service Layer**:
   - `get_attempt_questions()` executes `SELECT question_id, question_text, option_a, option_b, option_c, option_d, marks ...`. `correct_option` is excluded at SQL compilation.
   - `save_answer()` returns `{answer_id, attempt_id, question_id, selected_option, answered_at}`. `correct_option` is never queried or returned.
   - `get_attempt_answers()` returns `{question_id: selected_option}`.
2. **Presentation Layer**:
   - `src/ui/student_ui.py` never references, stores, or handles `correct_option`.
   - Inspection of Streamlit session state or DOM reveals only options A, B, C, D and the student's own selected choices.

---

## 12. UI and Service Layer Separation

```text
+----------------------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER (student_ui.py)                              |
|                                                                                                    |
|  - render_active_exam(student_id, attempt_id)                                                      |
|  - Manages session state keys:                                                                     |
|      * active_attempt_id                                                                           |
|      * q_index_{attempt_id}                                                                        |
|      * attempt_answers_{attempt_id}                                                                |
|  - Renders question container, radio choices, navigation buttons, and question palette.            |
|  - Dispatches calls to service layer:                                                              |
|      * get_attempt(attempt_id, student_id)                                                         |
|      * get_attempt_questions(attempt_id, student_id)                                               |
|      * get_attempt_answers(attempt_id, student_id)                                                 |
|      * save_answer(attempt_id, student_id, question_id, selected_option)                           |
|  - ZERO SQL QUERIES.                                                                               |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v  (Service Layer Function Calls Only)
+----------------------------------------------------------------------------------------------------+
|                                      SERVICE LAYER (service.py)                                    |
|                                                                                                    |
|  - Validates role ('student') and attempt ownership.                                               |
|  - Enforces server-side deadline and attempt status ('IN_PROGRESS').                               |
|  - Executes atomic MySQL UPSERT transactions on `answers` table.                                   |
|  - Masks correct_option in all student-facing projections.                                         |
+----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v  (MySQL Connection Pool)
+----------------------------------------------------------------------------------------------------+
|                                          DATABASE LAYER (MySQL)                                    |
|                                                                                                    |
|  - Tables: users, exams, questions, exam_attempts, answers                                         |
|  - Atomic commits, foreign key constraints, rollback on failure.                                   |
+----------------------------------------------------------------------------------------------------+
```

---

## 13. State Machine & Navigation Workflow

```text
+----------------------------------------------------------------------------------------------------+
|                                   EXAMINATION NAVIGATION FLOW                                      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|                                     [ render_active_exam ]                                         |
|                                                |                                                   |
|                        Load questions via get_attempt_questions()                                  |
|                        Load existing answers via get_attempt_answers()                             |
|                                                |                                                   |
|                                                v                                                   |
|                                   Display Question [current_idx]                                   |
|                                                |                                                   |
|             +----------------------------------+----------------------------------+                |
|             |                                  |                                  |                |
|             v                                  v                                  v                |
|   [ Option Selected ]                [ Navigation Action ]             [ Palette Jump ]            |
|             |                                  |                                  |                |
|             v                                  v                                  v                |
|    Click "Save & Next"               Click "Previous" / "Next"         Click Question Button       |
|             |                                  |                                  |                |
|             v                                  v                                  v                |
|    save_answer(opt)                   Update current_idx                 Update current_idx        |
|    answers_cache[qid] = opt           Clamped [0, N-1]                   Set to selected index     |
|    current_idx += 1                            |                                  |                |
|             |                                  |                                  |                |
|             +----------------------------------+----------------------------------+                |
|                                                |                                                   |
|                                                v                                                   |
|                                           st.rerun()                                               |
|                                                |                                                   |
|                                                v                                                   |
|                                   Re-render updated Question                                       |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 14. Acceptance Criteria for Part 2B-2

Part 2B-2 will be accepted when all of the following requirements are fulfilled and verified:

1. **Option Selection & Persistence**:
   - [ ] Examinee can select any of the 4 options (A, B, C, D) for the active question.
   - [ ] Selecting an option and clicking save successfully invokes `save_answer()`.
   - [ ] A record is inserted into the `answers` table with `attempt_id`, `question_id`, `selected_option`, and timestamp.
   - [ ] Changing an answer updates the existing row in `answers` (no duplicate rows created).
2. **Answer Restoration**:
   - [ ] Navigating away from a question and returning restores the saved selection on the radio button.
   - [ ] Refreshing the session or reloading the exam restores all previously saved answers from the database.
3. **Clear Selection**:
   - [ ] Examinee can click "Clear Selection" to clear their choice.
   - [ ] Invokes `save_answer(..., selected_option=None)`, setting `selected_option` to `NULL` in the database and resetting palette status to `Unanswered`.
4. **Navigation Controls**:
   - [ ] "Previous" button navigates to question $i - 1$; disabled on question 0.
   - [ ] "Next" button navigates to question $i + 1$; disabled on the final question.
5. **Question Palette**:
   - [ ] Renders all question numbers in an interactive matrix.
   - [ ] Accurately displays visual indicators for `Current`, `Answered`, and `Unanswered`.
   - [ ] Clicking any question button in the palette immediately jumps to that question.
   - [ ] Displays aggregate counts of total, answered, and unanswered questions.
6. **Security & Data Sanitization**:
   - [ ] `correct_option` is never fetched, queried, or displayed in the UI.
   - [ ] Unauthorized students receive `PermissionError` if attempting to call `save_answer()` on another student's attempt.
   - [ ] Attempt expiration rejects further answer persistence with an appropriate error.
7. **Architectural Purity**:
   - [ ] `student_ui.py` contains **zero SQL queries**.
   - [ ] No schema migrations or table modifications.
   - [ ] Teacher UI and Catalog flows remain 100% operational.
