# Domain Terminology Dictionary (Domain Context)

[中文](CONTEXT.md) | **English**

This project covers the complete lifecycle of **question bank authoring, paper assembly, exam organization, timed student attempts, automated & manual grading, result publication, and mistake review**.

To prevent ambiguity between terms like "Paper" and "Exam", or "Attempt Score" and "Final Result", the UI, codebase, and documentation strictly follow these 14 domain definitions:

---

## Terminology Reference

### 1. Authoring & Paper Assembly

- **Question (`Question`)**
  - **Plain-English Definition**: A reusable source question in the shared question bank, complete with question type (Single Choice, Multiple Choice, True/False, Short Answer), stem, options, reference answer, explanation, subject, difficulty, and knowledge tags.
  - *Do not confuse with*: A frozen question inside an **Exam Snapshot**.

- **Paper (`Paper`)**
  - **Plain-English Definition**: A reusable **static template of questions** picked from the question bank with a defined order and per-question points. One paper can be used to create multiple exams.
  - *Do not confuse with*: An **Exam** or a student's **Exam Attempt**. A paper has no schedule or participant list.

- **Exam (`Exam`)**
  - **Plain-English Definition**: A scheduled **assessment event** for students. In addition to copying content from a paper, it defines who can participate, start/end windows, time limit, allowed attempt count, scoring rules, and review permissions.
  - *Do not confuse with*: The source **Paper** template.

- **Exam Snapshot (`Exam Snapshot`)**
  - **Plain-English Definition**: When a teacher creates an exam from a paper, the system immediately **deep-copies** all questions, options, points, and answer keys into a standalone snapshot owned exclusively by that exam. Future edits to the question bank or source paper never affect existing exams.
  - *Do not confuse with*: A live reference to the source paper or question bank.

---

### 2. Organization & Participation

- **Teaching Class (`Teaching Class`)**
  - **Plain-English Definition**: A group of students and responsible teachers used for daily teaching organization. A class can have multiple teachers, and a student can belong to multiple classes.
  - *Do not confuse with*: A mutually exclusive administrative class.

- **Exam Participant / Eligibility (`Exam Participant`)**
  - **Plain-English Definition**: A student's admission ticket to a specific exam. Each student has at most one participant record per exam; importing multiple teaching classes into a restricted exam automatically deduplicates overlapping students.
  - *Do not confuse with*: Teaching class membership (changing class members later does not automatically alter existing exam participant lists) or a single attempt.

- **Exam Attempt (`Exam Attempt`)**
  - **Plain-English Definition**: A complete **answering record** created when a student clicks "Start Exam" and consumes one attempt opportunity (including personal deadline, saved answers, submission status, and attempt score). If an exam allows 2 attempts, a student can have Attempt #1 and Attempt #2.
  - *Do not confuse with*: A **Paper** or the student's **Final Result**.

- **Student Answer (`Student Answer`)**
  - **Plain-English Definition**: A student's response to a single exam snapshot question within one attempt, along with its graded score and teacher comment.
  - *Do not confuse with*: The reference answer key in the question bank.

- **Void Attempt (`Void Attempt`)**
  - **Plain-English Definition**: An attempt invalidated because the student's exam eligibility was revoked or the entire exam was cancelled. It is retained in the database for security auditing but excluded from normal score tables, analytics, and mistake notebooks.
  - *Do not confuse with*: Hard-deleting data or submitting a blank attempt.

---

### 3. Grading, Results & Learning Feedback

- **Grading Task (`Grading Task`)**
  - **Plain-English Definition**: A manual grading work item assigned to a designated teacher after an exam ends, scoped to **one entire attempt** that contains non-empty short-answer responses.
  - *Do not confuse with*: Single-question task sharding. Tasks are assigned per attempt.

- **Attempt Score (`Attempt Score`)**
  - **Plain-English Definition**: The total score of **one specific attempt** after all objective and subjective questions in that attempt have been graded.
  - *Do not confuse with*: The student's **Final Result** for the exam when multiple attempts exist.

- **Final Result (`Final Result`)**
  - **Plain-English Definition**: A student's official score for an exam. The rule is strict: **it always equals the score of the student's last valid submission** (never the highest score). If the last valid submission is still awaiting manual grading, the final result remains "Pending Grading" rather than falling back to an earlier graded attempt.
  - *Do not confuse with*: Highest score or most recently graded score.

- **Publish Results (`Publish Results`)**
  - **Plain-English Definition**: The explicit teacher action—performed after the exam ends and all valid attempts are fully graded—that opens scores, reviews, and analytics to students.
  - *Do not confuse with*: **Releasing an Exam** (which makes the exam available for students to take) or submitting an attempt.

- **Mistake Record (`Mistake`)**
  - **Plain-English Definition**: Any question from a published, review-enabled valid attempt where the student did not earn full points (including both objective questions and partially scored short-answer questions). Answering correctly on a second attempt does not erase the mistake record from the first attempt.
  - *Do not confuse with*: Objective-only errors or mistakes from only the final attempt.
