# OmniSight-AI — Examination Presentation Layer Design Specification (Phase 4, Step 3)

## 1. Purpose and Scope

The **Examination Presentation Layer** delivers the Streamlit user interface for the Core Examination System. It bridges authenticated users with the existing examination service functions in `src/exam/service.py`.

The presentation layer is responsible for:
- Providing an intuitive, modular **Teacher Exam Studio** for exam authoring, question management, and lifecycle controls (`DRAFT`, `PUBLISHED`, `CLOSED`).
- Providing an accessible, responsive **Student Exam Portal** for browsing available exams, attempting timed multiple-choice assessments, saving answers, submitting responses, and reviewing scorecards.
- Managing role-based navigation and authentication routing through `src/auth/session.py`.
- Preserving strict separation of concerns: UI components execute zero database queries, zero scoring calculations, and zero cryptographic algorithms.

---

## 2. Role-Based Navigation & Application Routing

The top-level application router (`app.py`) controls view rendering based on authentication and role state:

```text
+-----------------------------------------------------------------------+
|                               app.py                                  |
|                      (Top-Level Router / Controller)                  |
+-----------------------------------+-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            | Is user authenticated?                        |
            | (is_authenticated() from src/auth/session.py) |
            +-----------------------+-----------------------+
                                    |
                +-------------------+-------------------+
                |                                       |
             [ False ]                               [ True ]
                |                                       |
    +-----------v-----------+               +-----------v-----------+
    |    render_auth_page() |               |   Check user role     |
    |   (src/ui/auth_ui.py) |               |  (get_current_user()) |
    +-----------------------+               +-----------+-----------+
                                                        |
                        +-------------------------------+-------------------------------+
                        |                               |                               |
                 role == "teacher"               role == "student"               role == "admin"
                        |                               |                               |
             +----------v----------+         +----------v----------+         +----------v----------+
             | render_teacher_ui() |         | render_student_ui() |         | render_teacher_ui() |
             | (Teacher Studio)    |         | (Student Portal)    |         | (Admin Switcher)    |
             +---------------------+         +---------------------+         +---------------------+
```

### Navigation Rules:
1. **Unauthenticated Session**:
   - The user is confined to Login and Registration tabs (`src/ui/auth_ui.py`).
2. **Teacher Session (`role == "teacher"`)**:
   - Routed to the **Teacher Exam Studio** (`src/ui/teacher_ui.py`).
   - Sidebar displays user credentials, active role badge, and "Logout" button.
3. **Student Session (`role == "student"`)**:
   - Routed to the **Student Exam Portal** (`src/ui/student_ui.py`).
   - Sidebar displays student profile badge, exam status, and "Logout" button.
4. **Admin Session (`role == "admin"`)**:
   - Grants full access to teacher management views and oversight controls.

---

## 3. Teacher Exam Studio (`src/ui/teacher_ui.py`)

The Teacher Exam Studio provides a tabbed or multi-view workflow for comprehensive assessment administration:

```text
+---------------------------------------------------------------------------------+
|                              TEACHER EXAM STUDIO                                |
+---------------------------------------------------------------------------------+
|  [Tab 1: My Examinations]  |  [Tab 2: Create New Exam]  |  [Tab 3: Exam Editor] |
+---------------------------------------------------------------------------------+
```

### 3.1 Component 1: Teacher Dashboard (My Examinations)
- Displays all examinations owned by the authenticated teacher via `get_teacher_exams(teacher_id)`.
- Rendered as structured cards or an interactive table showing:
  - Exam Title and Description
  - Duration (minutes)
  - Lifecycle Status badge (`DRAFT` [Yellow], `PUBLISHED` [Green], `CLOSED` [Gray])
  - Question count
  - Creation timestamp
- Action Controls per card:
  - **Edit / Manage Questions**: Loads the examination into the Exam Editor tab.
  - **Publish Button**: Enabled only for `DRAFT` exams with $\ge 1$ question. Calls `publish_exam()`.
  - **Close Button**: Enabled only for `PUBLISHED` exams. Calls `close_exam()`.

### 3.2 Component 2: Exam Creation View
- Form fields:
  - `Title`: Text input (required, max 200 characters).
  - `Description`: Text area (optional instructions/syllabus).
  - `Duration (minutes)`: Number input (required, integer > 0).
- Actions:
  - "Create Examination" button calling `create_exam(title, description, duration, teacher_id)`.
  - Validates inputs, handles errors via `st.error`, and switches view to question management upon success.

### 3.3 Component 3: Question Management UI (Exam Editor)
- Visible only when an exam is selected in `DRAFT` status:
  - **Metadata Editor**: Allows updating title, description, and duration via `update_exam()`.
  - **Question Roster**: Displays existing questions retrieved via `get_exam_questions(exam_id, teacher_id)`.
  - **Question Cards**:
    - Displays question prompt, options (A, B, C, D), correct option badge, and marks.
    - "Edit Question" expander calling `update_question()`.
    - "Delete Question" button calling `delete_question()`.
  - **Add Question Form**:
    - Question Text (text area).
    - Option A, Option B, Option C, Option D (text inputs, max 500 characters).
    - Correct Option selector (dropdown: `A`, `B`, `C`, `D`).
    - Marks (number input, integer $\ge 1$).
    - "Add Question" button calling `add_question()`.

---

## 4. Student Exam Portal (`src/ui/student_ui.py`)

The Student Exam Portal guides examinees through assessment discovery, session taking, and score review:

```text
+---------------------------------------------------------------------------------+
|                              STUDENT EXAM PORTAL                                |
+---------------------------------------------------------------------------------+
| Phase A: Exam Catalog -> Phase B: Active Examination -> Phase C: Result Summary |
+---------------------------------------------------------------------------------+
```

### 4.1 Component 1: Published Exam Catalog
- Fetches active published examinations.
- Displays exam metadata cards: Title, Description, Duration, Total Questions.
- Checks whether an attempt already exists via `get_attempt()`:
  - If no attempt exists: Displays "Start Exam" button.
  - If attempt exists and status is `IN_PROGRESS`: Displays "Resume Exam" button.
  - If attempt exists and status is `SUBMITTED` or `EVALUATED`: Displays "View Result" button.

### 4.2 Component 2: Examination Taking Interface
- Active session state (`attempt_id` stored in `st.session_state`).
- **Header Section**:
  - Examination title and instructions.
  - Progress indicator (e.g., "Question 2 of 5").
  - Server-calculated countdown timer widget.
- **Question Presentation**:
  - Fetches sanitized questions via `get_attempt_questions(attempt_id, student_id)`.
  - Strictly presents question prompt, options A–D, and point value.
  - **Zero answer key exposure**: UI never receives or renders `correct_option`.
- **Response Selection & Persistence**:
  - Radio button or option buttons for choices: `A`, `B`, `C`, `D`, or "Clear Selection".
  - On change: Triggers `save_answer(attempt_id, student_id, question_id, selected_option)`.
  - Displays instant auto-save confirmation ("Saved").
- **Navigation Controls**:
  - "Previous Question" and "Next Question" buttons.
  - Question overview grid allowing direct jumping between questions.

### 4.3 Component 3: Submission & Final Evaluation
- "Submit Examination" button with modal / confirmation checkbox.
- Submission action:
  1. Calls `submit_attempt(attempt_id, student_id)`.
  2. Immediately chains to `evaluate_attempt(attempt_id, student_id)`.
  3. Transitions UI state to Result Scorecard.

### 4.4 Component 4: Result Scorecard Display
- Fetches evaluation data via `get_attempt_result(attempt_id, student_id)`.
- Displays clean, read-only summary:
  - Total Marks
  - Obtained Marks
  - Percentage Score (formatted to 2 decimal places)
  - Completion Timestamp
  - Performance status badge
- "Back to Catalog" button to return to available exams.

---

## 5. UI Action to Service Layer Function Mapping

Every interactive widget and user action maps directly to an established function in `src/exam/service.py`:

| UI Workflow Area | User Action in Streamlit UI | Target Function in `src/exam/service.py` | State / Data Impact |
| :--- | :--- | :--- | :--- |
| **Teacher Dashboard** | Load examination list | `get_teacher_exams(teacher_id)` | Populates exam card list. |
| **Teacher Studio** | Submit Exam Creation form | `create_exam(title, desc, duration, teacher_id)` | Creates new `exams` row with `status='DRAFT'`. |
| **Teacher Studio** | Submit Exam Details edit form | `update_exam(exam_id, teacher_id, title, ...)` | Updates draft exam title, desc, duration. |
| **Teacher Studio** | Load questions for draft exam | `get_exam_questions(exam_id, teacher_id)` | Renders question list with answer keys. |
| **Teacher Studio** | Submit Add Question form | `add_question(exam_id, teacher_id, text, opt_a..d, correct, marks)` | Inserts new question into `questions`. |
| **Teacher Studio** | Submit Edit Question form | `update_question(question_id, teacher_id, ...)` | Updates existing question record. |
| **Teacher Studio** | Click Delete Question button | `delete_question(question_id, teacher_id)` | Removes row from `questions`. |
| **Teacher Studio** | Click "Publish Exam" | `publish_exam(exam_id, teacher_id)` | Transitions status `DRAFT` $\rightarrow$ `PUBLISHED`. |
| **Teacher Studio** | Click "Close Exam" | `close_exam(exam_id, teacher_id)` | Transitions status `PUBLISHED` $\rightarrow$ `CLOSED`. |
| **Student Catalog** | Browse active assessments | Query published exams via service helper | Lists available published exams. |
| **Student Catalog** | Click "Start Exam" | `start_attempt(exam_id, student_id)` | Creates `exam_attempts` row with `status='IN_PROGRESS'`. |
| **Student Portal** | Load attempt session | `get_attempt(attempt_id, student_id)` | Retrieves attempt timestamps & status. |
| **Student Portal** | Render question list | `get_attempt_questions(attempt_id, student_id)` | Returns questions with answer keys masked. |
| **Student Portal** | Select / update option choice | `save_answer(attempt_id, student_id, question_id, option)` | Upserts student choice into `answers`. |
| **Student Portal** | Click "Submit Exam" / Timer 0 | `submit_attempt(attempt_id, student_id)` | Transitions status `IN_PROGRESS` $\rightarrow$ `SUBMITTED`. |
| **Student Portal** | Finalize assessment | `evaluate_attempt(attempt_id, student_id)` | Grades answers, inserts row in `results`, marks `EVALUATED`. |
| **Student Portal** | View scorecard | `get_attempt_result(attempt_id, student_id)` | Renders final marks, total, and percentage. |

---

## 6. Streamlit Session State & Navigation Flow

To maintain robust state across Streamlit rerun cycles without session corruption, the presentation layer utilizes structured session keys:

### 6.1 Session State Schema

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `st.session_state.current_page` | `str` | `"dashboard"` | Controls active view (`"catalog"`, `"exam_taking"`, `"exam_result"`, `"teacher_editor"`). |
| `st.session_state.selected_exam_id` | `Optional[int]` | `None` | Tracks active exam being configured or previewed. |
| `st.session_state.current_attempt_id` | `Optional[int]` | `None` | Tracks active attempt being taken by student. |
| `st.session_state.current_question_idx` | `int` | `0` | Tracks active question index in student taking view. |
| `st.session_state.exam_answers` | `Dict[int, str]` | `{}` | Local cache of selected choices mapped by `question_id`. |

### 6.2 State Transition Logic
- **Logout Action**: Calling `logout()` wipes all authentication and exam session state, triggering `st.rerun()`.
- **Exam Completion**: When `submit_attempt()` and `evaluate_attempt()` succeed, `current_question_idx` is cleared, and `current_page` transitions to `"exam_result"`.

---

## 7. Error Handling and Validation Strategy

The presentation layer catches service-layer exceptions and translates them into actionable user feedback:

```text
Service Exception Caught:
├── ValueError        -> st.error("Validation Error: <Friendly Message>")
├── PermissionError   -> st.warning("Access Denied: <Explanation>")
└── RuntimeError      -> st.error("System Error: Please contact administrator.")
```

### Specific Scenarios Handled in UI:
1. **Empty / Invalid Inputs**: Handled client-side before calling service functions (e.g., checking non-empty title, positive duration).
2. **Expired Exam Attempt**: Caught when `save_answer()` or `submit_attempt()` raises expired message $\rightarrow$ automatically transitions student to submission/evaluation screen.
3. **Draft Modification Locked**: Editing controls are disabled if exam status is `PUBLISHED` or `CLOSED`.

---

## 8. Separation of Concerns & Security Boundaries

```text
=================================================================================
                            STRICT ARCHITECTURAL ISOLATION
=================================================================================
 [ Presentation Layer (src/ui/) ]
    - Streamlit components: st.button, st.form, st.radio, st.metric
    - Calls functions from src/exam/service.py and src/auth/session.py
    - ZERO SQL queries (No SELECT, INSERT, UPDATE, DELETE)
    - ZERO Password hashing or verification logic
    - ZERO Exam grading or scoring logic
    - ZERO Exposure of correct_option or answer keys
 --------------------------------------------------------------------------------
                                      |  (Function Calls with Parameterized Inputs)
                                      v
 [ Examination Service Layer (src/exam/service.py) ]
    - Enforces RBAC permissions, lifecycle status locks, timing deadlines
    - Computes objective MCQ evaluation and percentages
    - Parameterized SQL execution via src/database/connection.py
=================================================================================
```

---

## 9. Explicit Non-Scope for Phase 4 Step 3

In compliance with the project roadmap, the following technologies and features are **strictly excluded**:
- **No Webcam Feed or Video Capture**: No browser camera requests.
- **No Computer Vision**: No OpenCV, MediaPipe, or facial landmark tracking.
- **No Behavioral Monitoring**: No tab-switching traps, focus loss events, or keystroke dynamics.
- **No Machine Learning**: No integrity risk scoring, clustering, or model inference.
- **No Proctoring Dashboard**: Phase 4 focuses purely on the functional examination platform.

---

## 10. Proposed File Structure

```text
src/
├── ui/
│   ├── __init__.py           (Existing)
│   ├── auth_ui.py            (Existing Authentication View)
│   ├── teacher_ui.py         (NEW: Teacher Exam Studio View)
│   └── student_ui.py         (NEW: Student Exam Portal View)
app.py                        (UPDATED: Integrated Navigation Router)
```

---

## 11. End-to-End Workflow Diagrams

### 11.1 Teacher End-to-End Workflow (ASCII)

```text
[Teacher Login]
      |
      v
[Teacher Studio Dashboard]
      |
      +---> [Create Exam Form]
      |           | (Title, Description, Duration)
      |           v
      |     create_exam() -> status='DRAFT'
      |           |
      +<----------+
      |
      +---> [Select Draft Exam]
      |           |
      |           v
      |     [Question Management]
      |           |---> add_question(Text, Options A-D, Correct, Marks)
      |           |---> update_question(...)
      |           |---> delete_question(...)
      |           v
      |     [Validate Readiness] (Questions >= 1)
      |           |
      |           v
      |     publish_exam() -> status='PUBLISHED'
      |           |
      +<----------+
      |
      +---> [Live Published Exam]
                  |
                  v
            close_exam() -> status='CLOSED'
```

### 11.2 Student End-to-End Workflow (ASCII)

```text
[Student Login]
      |
      v
[Published Exam Catalog]
      |
      v
[Select Exam & Read Instructions]
      |
      v
Click "Start Exam" ---> start_attempt() -> status='IN_PROGRESS'
      |
      v
[Exam Taking Portal]
      |---> get_attempt_questions() [MASKED: No answer keys]
      |---> Loop: Select Option -> save_answer(question_id, option)
      |---> Countdown Timer Tracking
      |
      v
Click "Submit Exam" (OR Timer Expiry)
      |
      v
submit_attempt() -> status='SUBMITTED'
      |
      v
evaluate_attempt() -> status='EVALUATED'
      | (Grades objective choices, computes total, obtained, percentage)
      v
[Result Scorecard]
      |---> get_attempt_result() [Displays Marks, Percentage, Timestamp]
      |
      v
[Return to Catalog]
```
