# UI Polish & Redesign — Design Spec

**Date:** 2026-04-08
**Branch:** feature/nehil/ui-framework-migration
**Approach:** Page-by-page redesign (Approach B) — same routing/data flow, upgraded presentation and interactions

## Context

The React + TypeScript frontend (built on React 19, Vite, shadcn/ui, Tailwind CSS v4) was migrated from Streamlit on 2026-04-07. The core wizard flow works (Upload -> Configure -> Review Plan -> Generate -> Results) but the UI feels like a developer prototype: cramped tables, emoji icons, minimal loading states, raw error messages, non-discoverable interactions.

## Goals

1. **Data interaction** (P1): Better tables, sorting, discoverable editing, proper CSV exploration
2. **Visual polish** (P2): Professional typography, spacing, loading skeletons, animations, consistent styling
3. **Status/feedback clarity** (P3): Better progress indication, error messages, run status, attempt tracking

## Constraints

- No new routes or pages
- No new API endpoints or backend changes
- No changes to existing data flow or state management architecture
- All improvements are purely frontend presentation and interaction
- Target audience: internal technical users + some non-technical stakeholders

## Design System

- **Font**: Fira Sans (body/headings) + Fira Code (monospace/data tables/code)
- **Color palette**: Blue-primary (#1E40AF) + amber-accent (#D97706), slate backgrounds
- **Icons**: Lucide React (replace all emoji throughout)
- **Components**: shadcn/ui (already in use, upgrade usage consistency)
- **Style**: Data-Dense Dashboard — professional, space-efficient, maximum data visibility

### Color Tokens

| Token | Light | Purpose |
|-------|-------|---------|
| primary | #1E40AF | Buttons, active states, links |
| secondary | #3B82F6 | Secondary actions, highlights |
| accent | #D97706 | CTAs, attention-drawing elements |
| background | #F8FAFC | Page background |
| foreground | #1E3A8A | Primary text |
| muted | #E9EEF6 | Muted backgrounds, disabled |
| border | #DBEAFE | Borders, dividers |
| destructive | #DC2626 | Errors, delete actions, failures |

---

## Section 1: Sidebar & Navigation

### Current State
- Emoji status icons (check, X, pause, clipboard)
- Truncated dataset names, no tooltips
- Small "New Run" button
- No refresh, no empty state

### Changes

1. **Status icons**: Replace emoji with Lucide icons with semantic colors
   - Completed: `CheckCircle2` (green)
   - Failed: `XCircle` (red)
   - Running: `Loader2` animated (blue)
   - Paused: `Pause` (amber)
   - Plan ready: `FileText` (blue)

2. **Run history items**: Card-style rows with:
   - Dataset name (truncated with title tooltip on hover)
   - Status badge: icon + label (e.g., "Completed", "Failed")
   - Relative timestamp ("2 min ago")
   - Model name (small muted text)

3. **"New Run" button**: Larger, primary color, `Plus` icon, top of sidebar. Clear main action.

4. **Sidebar header**: Clean app name, no gradient blob.

5. **Empty state**: "No runs yet — upload a CSV to get started" with upload icon.

---

## Section 2: Upload Page

### Current State
- Gradient hero blob
- Basic drag-drop
- Cramped data preview (text-xs)
- Metadata upload always visible
- No input validation feedback

### Changes

1. **Layout**: Clean card-based layout. No gradient blobs. Main upload card is the hero.

2. **File uploader states**:
   - Default: Dashed border, Upload icon, "Drag CSV here or click to browse"
   - Hovering: Border highlights, background tint, "Drop to upload"
   - Uploaded: File name, size, row/column count, "Remove" button
   - Error: Red border, inline error message

3. **Dataset name input**: Auto-filled from filename. Subtle validation: minimum length, allowed characters hint. Green checkmark when valid.

4. **Data preview table**:
   - `text-sm` font, comfortable padding
   - Column headers with type indicators (text/number/date icon)
   - Horizontal scroll with sticky first column
   - "Showing first 10 of N rows" label
   - Alternating row backgrounds

5. **Metadata upload**: Collapsible "Advanced: Add metadata CSV" section, default closed.

6. **Action button**: "Continue to Configure" at bottom, disabled until file uploaded + name valid.

---

## Section 3: Configure Page

### Current State
- Flat list of raw inputs
- No visual grouping
- Data preview takes most of page
- Raw `<select>` elements

### Changes

1. **Card-based grouping**:
   - **Model & Retries card**: shadcn Select for model, slider with value label for retries, brief description of what retries do
   - **Options card**: Toggle switches for MCP Discovery and Schema Examples, one-line descriptions
   - **Initial Feedback card** (collapsible, default closed): Textarea with placeholder guidance ("e.g., 'The date column uses YYYY-MM format'"), help text: "Optional — give the pipeline hints about your data"

2. **Data Explorer**: Move into own card with "Preview Your Data" heading. Same improvements as Upload page tables (sticky headers, alternating rows, `text-sm`, column types).

3. **Action buttons**: "Back to Upload" (ghost) + "Start Pipeline" (primary) button group. Loading state on click.

4. **Summary strip**: Info bar above actions: "dataset.csv — 1,234 rows x 15 columns — gemini-2.5-pro — 3 retries"

---

## Section 4: Review Plan Page

### Current State
- Two-phase page (waiting -> editing) with abrupt transition
- Plan is a raw textarea
- No indication of what the plan means
- Basic approve/back buttons

### Changes

1. **Phase 1 — Waiting**:
   - Improved ProgressTracker (see Section 6)
   - Heading: "Preparing your mapping plan..."
   - Skeleton placeholder where plan will appear (prevents layout jump)

2. **Phase 1 -> Phase 2 transition**:
   - Skeleton fades out, plan content fades in
   - Inline banner: "Plan ready for review"

3. **Phase 2 — Plan review**:
   - Render plan as **formatted markdown** by default (read mode)
   - "Edit" button toggles to textarea for modifications
   - Collapsible "How to read this plan" hint section at top

4. **Action buttons**:
   - "Approve & Generate" (primary, Play icon)
   - "Back to Configure" (ghost)

---

## Section 5: Progress Page (Generate)

### Current State
- Phase list with no real progress sense
- "Pipeline running..." is vague
- No logs visible
- Basic stop button
- No attempt counter

### Changes

1. **Progress tracker upgrade**:
   - Each phase: icon + label + status (pending/running/done/failed) + elapsed time
   - Running phase: animated spinner + pulsing highlight
   - Completed: green checkmark + time taken
   - Failed: red X + expandable error detail

2. **Attempt counter**: Prominent "Attempt 2 of 3" display with step dots.

3. **Live activity log** (collapsible panel):
   - Streams WebSocket events as log feed (auto-scroll, monospace Fira Code)
   - Timestamp + event type + message per entry
   - Color-coded: info (default), warning (amber), error (red), success (green)
   - Toggle: "Summary" (phase changes only) vs "Verbose" (all events)

4. **Status header**:
   - Dataset name
   - Status badge ("Running", "Validating", "Generating feedback")
   - Total elapsed time (ticking)
   - Stop button (red, with confirmation dialog)

5. **Auto-redirect**: On completion, success banner + 3-second countdown to Results. "View Results" button to skip.

---

## Section 6: Results Page

### Current State
- Plain tabs for output files
- Double-click CSV editing (non-obvious)
- Basic result banner
- Raw `<select>` in feedback form
- Markdown rendered with dangerouslySetInnerHTML unsanitized
- Errors go to console.error

### Changes

1. **Results summary banner** (top card):
   - Status badge (Passed/Failed/Stopped)
   - "2 of 3 attempts"
   - Exit reason in plain language
   - Quality score (colored number badge)
   - Dataset name, model, duration

2. **Output file tabs**:
   - File type icon + name per tab
   - Active tab clearly highlighted
   - Dot indicator for tabs with content, dimmed for missing files
   - Tab order: PVMAP, MCF, TMCF, StatVars, Metrics, Notes, Metadata

3. **PVMAP CSV viewer/editor**:
   - **View mode** (default): Proper data table — sticky headers, alternating rows, horizontal scroll, column sorting
   - **Edit mode**: Explicit "Edit PVMAP" button (not double-click). Cells become inputs on single click. Changed cells highlighted yellow. "Save & Revalidate" + "Discard changes" buttons. Validation spinner.

4. **Other file viewers**:
   - Code/text: Monospace Fira Code, line numbers, "Copy" button with "Copied!" confirmation
   - Markdown: Convert to HTML via existing approach, then sanitize with DOMPurify before setting innerHTML
   - Metrics/JSON: Formatted key-value card, not raw JSON

5. **Feedback form**:
   - shadcn Select (not raw `<select>`)
   - Textarea with placeholder guidance
   - Submit with loading state + success/error toast

6. **Download**: "Download ZIP" in summary banner area alongside "Re-run with feedback".

---

## Section 7: Cross-Cutting Improvements

### Icons (Global)
Replace all emoji with Lucide React icons throughout:
- Status: `CheckCircle2`, `XCircle`, `Clock`, `Loader2`, `AlertTriangle`
- Actions: `Upload`, `Settings`, `Play`, `Square`, `Download`, `Edit`, `Copy`
- Navigation: `ChevronRight`, `ChevronLeft`, `Plus`, `History`

### Loading States (Global)
Skeleton screens for all async content:
- Data tables: Animated gray bars in table layout
- File content: Lines of varying width
- Page transitions: Brief skeleton before content

### Toast Notifications (Global)
Using shadcn toast or Sonner:
- Success: "File uploaded", "PVMAP saved", "Revalidation complete"
- Error: "Upload failed: file too large", "Pipeline error: ..."
- Info: "Pipeline started", "Plan ready for review"
- Replace all `console.error` with user-visible toasts

### Error States (Global)
- API errors: Friendly message + "Try again" button (not raw backend JSON)
- Empty states: Message + primary action
- Failed loads: Retry button instead of infinite "Loading..."

### Table Standards (Global — all data tables)
- `text-sm`, comfortable padding (not `text-xs`)
- Sticky headers
- Alternating row backgrounds
- Row hover highlight
- Horizontal scroll with shadow indicators
- `font-variant-numeric: tabular-nums` for number columns

### Wizard Stepper
- Horizontal stepper with connector lines (div borders, not SVG)
- Step states: pending (muted outline), active (filled primary), completed (green checkmark), failed (red X)
- Connector lines: solid when completed, dashed when pending
- Completed steps are clickable to navigate back

---

## Files Changed

All changes are frontend-only:

| File | Change Type |
|------|-------------|
| `frontend/src/index.css` | Color tokens, font imports (Fira Sans + Fira Code) |
| `frontend/src/App.tsx` | Toast provider, minor layout |
| `frontend/src/components/Sidebar.tsx` | Lucide icons, card-style items, empty state |
| `frontend/src/components/WizardStepper.tsx` | Connector lines, click navigation, icon states |
| `frontend/src/components/FileUploader.tsx` | Enhanced drag-drop states |
| `frontend/src/components/DataPreview.tsx` | Table styling upgrade |
| `frontend/src/components/DataExplorer.tsx` | Table styling upgrade, card wrapper |
| `frontend/src/components/ProgressTracker.tsx` | Phase icons, elapsed time, expand errors |
| `frontend/src/components/OutputViewer.tsx` | Tab icons, sanitized markdown, JSON formatting |
| `frontend/src/components/CsvEditor.tsx` | Explicit edit mode, single-click cells, change highlight |
| `frontend/src/components/FeedbackForm.tsx` | shadcn Select, toast feedback |
| `frontend/src/components/CodeViewer.tsx` | Line numbers, copy confirmation |
| `frontend/src/components/DownloadButton.tsx` | Move to banner area |
| `frontend/src/pages/UploadPage.tsx` | Card layout, validation, collapsible metadata |
| `frontend/src/pages/ConfigurePage.tsx` | Card grouping, summary strip |
| `frontend/src/pages/ReviewPlanPage.tsx` | Markdown render, edit toggle, skeleton |
| `frontend/src/pages/ProgressPage.tsx` | Status header, attempt counter, activity log |
| `frontend/src/pages/ResultsPage.tsx` | Summary banner, explicit edit mode |
| `frontend/package.json` | Add: sonner (toast), dompurify (sanitizer) |

## New Dependencies

- `sonner` — Toast notifications (lightweight, shadcn-compatible)
- `dompurify` — HTML sanitization for markdown rendering
- `@fontsource-variable/fira-code` — Monospace font
- `@fontsource/fira-sans` — Body/heading font

## Not In Scope

- New pages or routes
- Backend/API changes
- New features (deferred to later work)
- Mobile-specific responsive design (desktop-first for internal tool)
- Dark mode (existing dark mode support preserved, not redesigned)
