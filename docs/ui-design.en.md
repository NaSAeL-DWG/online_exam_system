# UI Visual Design Specification & C3 Theme Standard

[中文](ui-design.md) | **English**

This document defines the active **C3 Visual Design System** for the **Online Exam System**, including its five-tier visual hierarchy, 50-shade color palette, layout standards across all 30 application pages, and frontend visual acceptance criteria.

---

## 1. Core Design Philosophy

An examination system is a focused productivity workspace, not a decorative marketing landing page. Our visual design is built around four principles: **sharp, serious, orderly, and task-first**.
- **Subtle Gray Canvas + Pure White Panels**: Decorative gradients, diffuse glows, and heavy drop shadows are eliminated. The workspace canvas uses a subtle cool gray (`#F6F7F9`) to frame pure white content cards (`#FFFFFF`), keeping question stems, answer inputs, and grading forms at the center of attention.
- **Crisp Geometric Boundaries**: Sidebar navigation items and their `3 px` left active bar use **strict square corners (`0 px` radius)**; content cards and form controls use a tight `0–4 px` border radius; input focus highlights the control's own inner border without outer halo rings; dropdown popovers use restrained elevation shadows, and loading skeletons feature a 3.2-second white shimmer sweep.

---

## 2. Five-Tier Visual Hierarchy

During a timed exam, coloring every badge and button with bright accents creates visual noise. Interface elements are strictly ordered into 5 priority tiers:

| Priority Tier | Typical Elements | Design Rule |
| :--- | :--- | :--- |
| **1. Critical Alerts & Warnings**<br>(Highest only when active) | Autosave failure, imminent time expiration, multi-tab takeover conflict | Display clear reasons and recovery actions right next to the control using Red or Amber; **never occupy top visual weight during normal operation** |
| **2. Core Task Area** | Student question stem & answer area; teacher student-answer reader & scoring form | Allocate maximum screen real estate, comfortable typography, and high contrast |
| **3. Exam Controls & Progress** | Start/Continue Exam, countdown timer, saved status, question palette, Submit, Release/Publish | Keep in predictable, easy-to-find locations; use one primary blue button (`#2164CE`) per task region; **separate "Submit Exam" from "Previous/Next Question" to prevent accidental clicks** |
| **4. Decision Metadata** | Exam window, duration, remaining attempts, unanswered count, grading progress, result status | Place adjacent to related actions using structured labels and tabular numerals |
| **5. Supporting Navigation** | Global sidebar, list filters, account profile, general statistics, admin utilities | Keep legible and accessible using low-saturation neutral tones |

### Key Role Workspace Layouts
- **Student Home (`StudentHomeView`)**: Prioritizes the **"Active Exam Card (with read-only live countdown panel)"** followed by a **"Upcoming Exams / Recent Learning Records"** two-column layout and exam notices.
- **Student Exam Detail (`StudentExamDetailView`)**: Displays a top row of three overview cards (**Exam Status, Duration, Paper Structure**) with clean `1 px` borders (no colored top stripes; all three turn neutral gray once the exam ends), followed by vertical metadata rows and numbered rules.
- **Student Distraction-Free Attempt (`StudentAttemptView`)**: Hides the global sidebar, condensing name, student number, deadline, timer, and "Exit Workspace / Submit" into a compact top header over a **main question column + `268 px` right-hand question palette** (collapsible on mobile).
- **Teacher Distraction-Free Grading (`StaffAttemptView`)**: Hides the global sidebar in a centered `1248 px` workspace (**left main column** for question stem, gray-background student answer, rubric, and grading history; **right `300 px` column** for the score/comment form and progress).
- **Administrator Role Separation**: Removes front-line grading workspaces and scoring buttons from admin views; administrators focus on accounts, classes, student approvals, system logs, and **"Grading Progress & Task Reassignment"** inside Exam Details.

---

## 3. C3 Color System & 50-Shade HEX Palette

The C3 theme defines **4 ten-shade primary color families (Bright Blue, Pine Green, Amber, Dark Red) + 1 ten-shade Neutral Gray family**, implemented in `frontend/src/styles/tokens.css` and `frontend/src/design/theme.ts`:

### 1. Full 50-Shade HEX Reference Table

| Shade | Bright Blue<br>Primary Action / Focus / Selected | Pine Green<br>Saved / Completed / Passed | Amber<br>Time Warning / Unanswered Alert | Dark Red<br>Save Failed / Destructive Action | Neutral Gray<br>Canvas / Borders / Text |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **50** | `#F2F7FF` | `#EDF7F2` | `#FCF6E9` | `#FBF0F0` | **`#F6F7F9` (Workspace Canvas)** |
| **100** | `#E0EDFF` | `#D6ECE0` | `#F5E8C5` | `#F5DEDE` | `#F4F4F4` |
| **200** | `#BED8FF` | `#ADD8C0` | `#ECD39B` | `#E8BABA` | `#E5E5E5` |
| **300** | `#91BAFA` | `#7ABB9A` | `#DFB665` | `#D88F90` | `#D0D0D0` |
| **400** | `#639BF2` | `#4B9874` | `#C99536` | `#C36468` | `#A6A6A6` |
| **500** | `#397DE7` | `#2F7B59` | `#A97920` | `#A9464E` | `#8C8C8C` (Default Input Border) |
| **600** | **`#2164CE` (Primary / Focus)** | `#236344` | `#885E16` | `#8F333E` | `#626262` (Secondary Text) |
| **700** | `#1A50AA` (Primary Hover) | **`#1C5038` (Success Text)** | `#6E4A15` | **`#752936` (Error / Danger)** | `#454545` |
| **800** | `#194386` (Primary Active) | `#173F2E` | **`#573B14` (Warning Text)** | `#5F2430` | `#303030` |
| **900** | `#173762` | `#123325` | `#452F12` | `#4C1F29` | **`#202020` (Primary Body Text)** |

### 2. Component Semantic Mapping

| UI Element | Foreground / Text | Background / Border | Usage Rule |
| :--- | :--- | :--- | :--- |
| **Workspace & Panels** | Neutral 900 (`#202020`) | Canvas Neutral 50 (`#F6F7F9`); panels & sidebar `#FFFFFF`; dividers `#E5E5E5` | Subtle gray canvas contrasts cleanly with white cards |
| **Primary Buttons** | White `#FFFFFF` | Default Blue 600 (`#2164CE`); hover `700`; active `800` | Start exam, save, submit (`5.56:1` contrast ratio) |
| **Active Sidebar Item** | Blue 700 (`#1A50AA`) | Blue 50 (`#F2F7FF`) fill + `3 px` left Blue 600 bar | Strict `0 px` square corners (`7.04:1` contrast ratio) |
| **Inputs & Selects** | Neutral 900 (`#202020`) | Default border Neutral 500 (`#8C8C8C`); focus border Blue 600 (`#2164CE`) | Inner border focus emphasis; dropdown popovers carry subtle shadow |
| **Question Palette Buttons** | Current: White; Answered: Blue 800 | Current: Blue 600 solid; Answered: Blue 100 fill + Blue 500 border | Distinctly separates current, answered, and unanswered questions |
| **"Marked for Review" Button** | White `#FFFFFF` + solid white flag | Dedicated dark gray **`#3A3A3A`** (unmarked uses light gray + outline flag) | Distinct from both primary blue and amber warnings (`11.37:1` contrast) |
| **Saving / Saved Indicator** | Saved: Green 700 (`#1C5038`) | Green 50 (`#EDF7F2`) fill + Green 500 border | "Saving" shows a spinning loader icon; checkmark appears only when saved |
| **Time Warning / Save Error** | Warning: Amber 800; Error: Red 700 | Warning: Amber 50 + 600 border; Error: Red 50 + 600 border | Always paired with explicit text and retry actions |

---

## 4. 30-Page Layout & Real-Data Adaptation Rules

All 30 page scenarios across the application (11 Student pages, 6 Teacher/Admin Exam & Grading pages, 8 Content & System Admin pages, and 5 Public/Account pages) adhere to these rules:

1. **Shared Component Reuse**: Pages consistently use `PageHeader.vue` (English eyebrow label + `30 px` title + primary action slot), `SurfacePanel.vue`, `AppSelect.vue`, and `LoadingSkeleton.vue`.
2. **Honest Real-API Boundaries (Zero Fabricated Data)**:
   - Pre-exam detail endpoints do not expose question breakdowns early, so the "Paper Structure" card displays the real total points and states that question counts and types are shown after starting the attempt.
   - Result views follow the "last valid submission" rule; unpublished or pending-grading states render `—` with neutral explanations rather than `0`.
   - On Registration and Change Password pages, the standalone "Password Requirements" box sits between the password inputs and the submit button.
3. **Contrast & Viewport Standards**:
   - Body text maintains at least **4.5:1** contrast (secondary text `#626262` on `#F6F7F9` measures `5.69:1`), and control borders/focus states maintain at least **3:1**.
   - Every view supports both **1440px / 1280px desktop** and **390px mobile** widths without full-page horizontal overflow (wide data tables scroll horizontally inside their container).

---

## 5. Automated UI & Layout Verification Commands

After modifying frontend styles, layouts, or shared UI components, run the C3 Playwright verification suites inside `frontend/` (uses deterministic route snapshots; no backend required):

```bash
cd frontend

# 1. Verify C3 base primitives, theme tokens, and key interactive states
npx playwright test \
  tests/e2e/c3-foundation.spec.ts \
  tests/e2e/c3-content.spec.ts \
  tests/e2e/c3-student.spec.ts \
  tests/e2e/c3-implementation.spec.ts \
  tests/e2e/c3-review-details.spec.ts \
  --workers=1

# 2. Verify all 30 page layouts and 1440px / 390px responsiveness
npx playwright test \
  tests/e2e/student-home-design.spec.ts \
  tests/e2e/student-pages-design.spec.ts \
  tests/e2e/staff-exam-pages-design.spec.ts \
  tests/e2e/content-admin-pages-design.spec.ts \
  tests/e2e/public-pages-design.spec.ts \
  --workers=1

# 3. Verify TypeScript build and Prettier formatting
npm run build
npm run format:check
```
