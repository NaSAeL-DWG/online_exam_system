# Three-Role User Guide

[中文](user-guide.md) | **English**

The system supports three roles: **Students, Teachers, and Administrators**. All roles sign in through the same login page using their **student number, staff ID, or administrator login name**.

### General UI & Form Tips

- **First Login & Forgotten Passwords**: New teacher accounts and administrator-reset accounts use a **temporary password** that must be changed upon first login. Self-service SMS/email OTP recovery is not included in v1; contact an administrator for identity verification and password reset.
- **Inline Validation & Unsaved Changes Protection**: Form errors appear in plain language directly beneath the offending field, and submitting focuses the first invalid input. The password strength bar (Strong/Medium/Weak) is advisory, while the confirmation field checks matching in real time. Closing an editor or navigating away with unsaved edits triggers a confirmation prompt so you never lose work accidentally.

---

## 1. Student Guide: Taking Exams & Reviewing Feedback

### 1. Registration & Approval
1. Click **Student Registration** on the login page and fill in your student number, real name, email, phone number, and password.
2. Newly registered accounts enter a **Pending Review** state, where logging in only displays your application status.
3. Once a teacher or administrator approves your application, the full student workspace unlocks. If rejected, you can view the rejection reason, update your information, and resubmit.

### 2. Pre-Exam Check & Starting an Attempt
1. Open an exam from **My Exams** to inspect its start/end window, personal time limit, and allowed attempt count.
2. **Viewing the exam detail page does not consume an attempt**. An attempt is created and timed only when you click **"Start Exam"**. If you already have an active unsubmitted attempt, the button reads **"Continue Attempt"** and resumes your existing session.

### 3. Timed Answering, Autosave & Multi-Tab Takeover
1. **Autosave Behavior**: Objective choices save immediately upon selection; short-answer responses autosave shortly after you stop typing, or whenever you click manual save. **Always rely on the on-screen "Saved" indicator**—unsynced local drafts in your browser do not count as server-received answers.
2. **Authoritative Countdown**: Your personal deadline is the earlier of your **personal duration** or the **exam closing time**. Because the timer is controlled by the server, **disconnecting from the network, closing the browser, or changing your computer clock will never pause or extend the countdown**. When time expires, late local drafts are rejected and the worker auto-submits using the answers already saved on the server.
3. **Refreshing & Device/Tab Takeover**: Refreshing the page (`F5`) seamlessly restores your active attempt. However, to prevent conflicting overwrites, **only one browser tab can hold write permission for an attempt at a time**. Opening the exam on another device or tab enters read-only mode and prompts you to click **"Take Over"**—once taken over, the previous tab immediately becomes read-only. Always check the server-saved answers before editing after a takeover.

### 4. Manual Submission & Multiple Attempts
1. Clicking **Submit** flushes any in-flight saves and lists unanswered questions for final confirmation.
2. **Submitted attempts are locked and cannot be edited**. If the exam window is still open and you have remaining attempts, you may start a new attempt.

### 5. Checking Scores, Reviewing Papers & Mistake Notebook
1. **Why isn't my score visible right after submitting?** Immediately after submission, you see a submission receipt. Scores remain hidden while the exam is still ongoing, while short-answer questions are being graded, before a teacher clicks "Publish Results", or while results are temporarily withdrawn for correction.
2. **How is the Final Result calculated?** Once results are published, open **Exam History** to view each attempt's score and your **Final Result**. Note the core rule: **your Final Result is strictly the score of your last valid submission—never your highest score**. If you took the exam twice and your second attempt is still awaiting manual grading, your Final Result displays "Pending Grading" rather than falling back to your first attempt's score.
3. **Paper Review & Mistake Notebook**:
   - When the teacher enables **Allow Review**, you can inspect your answers, reference keys, explanations, and teacher comments question by question. Any question where you did not earn full marks is automatically added to **My Mistakes** (mistakes from all valid attempts are retained—getting a question right on Attempt #2 does not delete the mistake from Attempt #1). You can write personal study notes, mark items as "Mastered", and view **Learning Analytics**.
   - When **Allow Review** is disabled, you can view your published total score, but question details, answer keys, mistakes, and knowledge breakdowns remain hidden.
   - If your exam eligibility is revoked or the exam is cancelled, related attempts become void.

---

## 2. Teacher Guide: From Authoring to Result Publication

> **Shared Collaboration Note**: Question banks, papers, exams, and staff attempt views are **shared across all active teachers**. If two teachers edit the same item concurrently, the second save receives a version conflict warning—reload and review your colleague's changes before saving. Items use "Close / Archive" instead of hard deletion so historical exam snapshots never break.

### 1. Student Approvals & Teaching Classes
- Teachers can approve or reject student registration applications.
- Administrators create teaching classes and assign teachers (a class can have multiple teachers, and a student can join multiple classes). Assigned teachers can add or remove students in their classes.
- **Note**: Modifying teaching class membership **does not** retroactively alter participant lists of already-created exams.

### 2. Authoring Questions, Assembling Papers & Releasing Exams
1. **Shared Question Bank**: Create Single Choice, Multiple Choice, True/False, or Short Answer questions tagged by subject, difficulty, and knowledge points. Stems and explanations support Markdown, LaTeX math, and uploaded images; student short-answer inputs are plain text. Closing an outdated question prevents new papers from selecting it without affecting existing papers or exam snapshots.
2. **Shared Papers**: Pick questions from the bank, adjust their order, and assign decimal points. **A "Paper" is a reusable template of questions**—it has no schedule or student roster.
3. **Creating an Exam & Independent Snapshot**: Creating an **Exam** from a paper immediately deep-copies all questions into an isolated **Exam Snapshot**. Subsequent edits to the source question bank or paper never affect existing exams, nor do draft edits inside the exam write back to the source bank.
4. **Configuring Rules & Participants**:
   - Configure start/end times, duration, allowed attempts, multiple-choice scoring rules, question/option shuffling, post-exam review permissions, and passing score.
   - **Exams containing short-answer questions must designate at least one active grading teacher**.
   - **Participant Scope**: "Public Exams" are open to all active students; "Restricted Exams" import students by teaching class or individual student number (automatically deduplicated; re-importing a class will not silently restore a previously revoked student—eligibility must be restored explicitly).
5. **Releasing an Exam**: Save and click **Release Exam** to lock core settings. You can withdraw a release only if **no student has started an attempt yet**. Clicking "Cancel Exam" permanently voids the exam and all its attempts.

### 3. Grading Short Answers, Publishing & Correcting Results
1. **When are manual grading tasks assigned?** Objective questions and blank short answers are auto-graded upon submission. Once **the entire exam window closes and all valid attempts finish submission and objective grading**, the background worker evenly distributes attempts containing non-empty short answers as whole-attempt tasks among the designated grading teachers.
2. **Manual Grading & Audited Re-Scoring**:
   - Open assigned tasks from the **Grading Workspace** to enter scores (within valid bounds) and feedback comments per question.
   - **First-Grading Exclusivity**: Until a whole attempt is graded for the first time, only its assigned teacher can score it. Once initial grading is complete, other active teachers can adjust scores by providing a mandatory **reason for score change**, with every modification recorded in the immutable grading history.
3. **Analytics Rules**: Score tables and distribution charts use each student's **last valid submission**. Public exams have no fixed roster denominator for absence rates, and ungraded attempts are never counted as zero.
4. **Publish Results**: After the exam ends and all historical valid attempts are fully graded, click **"Publish Results"** to make scores visible to students. Remember: **"Release Exam" lets students take the exam; "Publish Results" lets students see their grades**.
5. **Withdrawing & Re-Grading Published Results**: If you need to fix an answer key or adjust a score after publication:
   - Provide a reason and click **"Withdraw Results"** (this immediately hides the exam's scores, mistakes, and analytics from students).
   - Adjust manual scores or **correct the snapshot answer key / rubric** (which automatically re-grades affected questions while preserving unrelated question scores).
   - Once all re-grading is complete, click **"Publish Results"** again.

---

## 3. Administrator Guide: Organization & Exception Handling

Administrators manage identities, organizational structure, and operational exceptions:

- **Teachers & Teaching Classes**: Create teacher accounts with temporary passwords; create teaching classes, assign teachers, and maintain class rosters.
- **Student Accounts & Identity Verification**: Review student registrations, activate/deactivate accounts, and—after manual identity verification—correct student numbers/names or issue temporary password resets (resetting a password or deactivating an account immediately revokes active sessions, and **reactivating an account never resets or extends an ongoing exam countdown**).
- **Content & Exam Oversight**: Manage shared questions, papers, and exams. To maintain role separation, **administrators do not have a grading workspace or direct scoring buttons**; instead, they monitor progress under the "Grading Progress & Results" tab in Exam Details.
- **Reassigning Stalled Grading Tasks**: If a designated grading teacher is deactivated or unavailable, administrators can select **"Reassign Task"** in the exam progress list, record a reason, and transfer the task to an active teacher (preserving all previously graded question scores and history).
- **Revoking Exam Eligibility**: Revoking a student's eligibility voids all of their attempts for that exam. Restoring eligibility later does not revive voided attempts or grant extra attempt counts; create a separate make-up exam if needed.
- **System Logs & Security Audits**: Open **System Logs** (`/admin/logs`) to inspect runtime diagnostics and security audits, enable 15-minute temporary DEBUG collection by module, or toggle server log file persistence. See **[System Logs & Security Audit](logging.en.md)**.
- **Admin Password Recovery**: If an administrator forgets their own password, reset it via the local CLI command documented in **[Operations Guide](operations.en.md#5-administrator--session-recovery)**.
