# UI Polish & Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all 5 wizard pages + sidebar from developer prototype to professional data tool, improving data interaction, visual polish, and status clarity.

**Architecture:** Page-by-page redesign keeping existing routing, state management, and API layer untouched. New dependencies: `sonner` (toasts), `dompurify` (sanitization), `@fontsource/fira-sans` + `@fontsource-variable/fira-code` (fonts). All changes are frontend-only.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Lucide React, Vite

**Spec:** `docs/superpowers/specs/2026-04-08-ui-polish-redesign-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/package.json` | Modify | Add new dependencies |
| `frontend/src/index.css` | Modify | New font imports, color tokens |
| `frontend/src/App.tsx` | Modify | Add Toaster provider |
| `frontend/src/components/Sidebar.tsx` | Rewrite | Lucide icons, card items, empty state |
| `frontend/src/components/WizardStepper.tsx` | Rewrite | Connector lines, icon states, clickable |
| `frontend/src/components/FileUploader.tsx` | Modify | Lucide icons, improved states |
| `frontend/src/components/DataPreview.tsx` | Modify | Better table styling |
| `frontend/src/components/DataExplorer.tsx` | Modify | Better table styling, skeleton loading |
| `frontend/src/components/ProgressTracker.tsx` | Rewrite | Lucide icons, elapsed per phase, expandable errors |
| `frontend/src/components/OutputViewer.tsx` | Rewrite | Tab icons, explicit edit mode, sanitized markdown |
| `frontend/src/components/CsvEditor.tsx` | Rewrite | Explicit edit button, single-click edit, change highlighting |
| `frontend/src/components/FeedbackForm.tsx` | Modify | shadcn Select, toast feedback |
| `frontend/src/components/CodeViewer.tsx` | Modify | Line numbers, copy confirmation icon |
| `frontend/src/components/DownloadButton.tsx` | Modify | Add icon |
| `frontend/src/pages/UploadPage.tsx` | Rewrite | Card layout, no gradient hero, collapsible metadata |
| `frontend/src/pages/ConfigurePage.tsx` | Rewrite | Card grouping, summary strip, collapsible feedback |
| `frontend/src/pages/ReviewPlanPage.tsx` | Rewrite | Markdown render mode, edit toggle, skeleton |
| `frontend/src/pages/ProgressPage.tsx` | Rewrite | Status header, attempt counter, activity log |
| `frontend/src/pages/ResultsPage.tsx` | Modify | Summary banner improvements |

---

### Task 1: Install Dependencies & Update Design Tokens

**Files:**
- Modify: `frontend/package.json:12-24`
- Modify: `frontend/src/index.css:1-130`

- [ ] **Step 1: Install new npm dependencies**

```bash
cd frontend && npm install sonner dompurify @fontsource/fira-sans @fontsource-variable/fira-code && npm install -D @types/dompurify
```

- [ ] **Step 2: Update index.css — replace font imports and color tokens**

Replace the entire `frontend/src/index.css` with:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import "@fontsource/fira-sans/400.css";
@import "@fontsource/fira-sans/500.css";
@import "@fontsource/fira-sans/600.css";
@import "@fontsource/fira-sans/700.css";
@import "@fontsource-variable/fira-code";

@custom-variant dark (&:is(.dark *));

@theme inline {
    --font-heading: 'Fira Sans', sans-serif;
    --font-sans: 'Fira Sans', sans-serif;
    --font-mono: 'Fira Code Variable', monospace;
    --color-sidebar-ring: var(--sidebar-ring);
    --color-sidebar-border: var(--sidebar-border);
    --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
    --color-sidebar-accent: var(--sidebar-accent);
    --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
    --color-sidebar-primary: var(--sidebar-primary);
    --color-sidebar-foreground: var(--sidebar-foreground);
    --color-sidebar: var(--sidebar);
    --color-chart-5: var(--chart-5);
    --color-chart-4: var(--chart-4);
    --color-chart-3: var(--chart-3);
    --color-chart-2: var(--chart-2);
    --color-chart-1: var(--chart-1);
    --color-ring: var(--ring);
    --color-input: var(--input);
    --color-border: var(--border);
    --color-destructive: var(--destructive);
    --color-accent-foreground: var(--accent-foreground);
    --color-accent: var(--accent);
    --color-muted-foreground: var(--muted-foreground);
    --color-muted: var(--muted);
    --color-secondary-foreground: var(--secondary-foreground);
    --color-secondary: var(--secondary);
    --color-primary-foreground: var(--primary-foreground);
    --color-primary: var(--primary);
    --color-popover-foreground: var(--popover-foreground);
    --color-popover: var(--popover);
    --color-card-foreground: var(--card-foreground);
    --color-card: var(--card);
    --color-foreground: var(--foreground);
    --color-background: var(--background);
    --radius-sm: calc(var(--radius) * 0.6);
    --radius-md: calc(var(--radius) * 0.8);
    --radius-lg: var(--radius);
    --radius-xl: calc(var(--radius) * 1.4);
    --radius-2xl: calc(var(--radius) * 1.8);
    --radius-3xl: calc(var(--radius) * 2.2);
    --radius-4xl: calc(var(--radius) * 2.6);
}

:root {
    --background: #F8FAFC;
    --foreground: #1E3A8A;
    --card: #FFFFFF;
    --card-foreground: #1E3A8A;
    --popover: #FFFFFF;
    --popover-foreground: #1E3A8A;
    --primary: #1E40AF;
    --primary-foreground: #FFFFFF;
    --secondary: #EFF6FF;
    --secondary-foreground: #1E40AF;
    --muted: #E9EEF6;
    --muted-foreground: #64748B;
    --accent: #D97706;
    --accent-foreground: #FFFFFF;
    --destructive: #DC2626;
    --border: #DBEAFE;
    --input: #DBEAFE;
    --ring: #1E40AF;
    --chart-1: #1E40AF;
    --chart-2: #3B82F6;
    --chart-3: #D97706;
    --chart-4: #059669;
    --chart-5: #7C3AED;
    --radius: 0.625rem;
    --sidebar: #FFFFFF;
    --sidebar-foreground: #1E3A8A;
    --sidebar-primary: #1E40AF;
    --sidebar-primary-foreground: #FFFFFF;
    --sidebar-accent: #EFF6FF;
    --sidebar-accent-foreground: #1E40AF;
    --sidebar-border: #DBEAFE;
    --sidebar-ring: #1E40AF;
}

.dark {
    --background: #0F172A;
    --foreground: #E2E8F0;
    --card: #1E293B;
    --card-foreground: #E2E8F0;
    --popover: #1E293B;
    --popover-foreground: #E2E8F0;
    --primary: #3B82F6;
    --primary-foreground: #FFFFFF;
    --secondary: #1E293B;
    --secondary-foreground: #E2E8F0;
    --muted: #334155;
    --muted-foreground: #94A3B8;
    --accent: #D97706;
    --accent-foreground: #FFFFFF;
    --destructive: #EF4444;
    --border: #334155;
    --input: #334155;
    --ring: #3B82F6;
    --chart-1: #3B82F6;
    --chart-2: #60A5FA;
    --chart-3: #F59E0B;
    --chart-4: #34D399;
    --chart-5: #A78BFA;
    --sidebar: #1E293B;
    --sidebar-foreground: #E2E8F0;
    --sidebar-primary: #3B82F6;
    --sidebar-primary-foreground: #FFFFFF;
    --sidebar-accent: #334155;
    --sidebar-accent-foreground: #E2E8F0;
    --sidebar-border: #334155;
    --sidebar-ring: #3B82F6;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
    }
  body {
    @apply bg-background text-foreground;
    }
  html {
    @apply font-sans;
    }
}
```

- [ ] **Step 3: Verify the frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add -f frontend/package.json frontend/package-lock.json frontend/src/index.css
git commit -m "feat(ui): install dependencies and update design tokens

Add sonner, dompurify, Fira Sans/Code fonts. Replace oklch color system
with blue-primary + amber-accent hex palette for data tool aesthetic."
```

---

### Task 2: Add Toast Provider to App Root

**Files:**
- Modify: `frontend/src/App.tsx:1-155`

- [ ] **Step 1: Add Toaster import and render in App.tsx**

In `frontend/src/App.tsx`, add the import at the top (after other imports, around line 21):

```typescript
import { Toaster } from "sonner";
```

Then wrap the BrowserRouter content — replace the `App` function (lines 148-154):

```typescript
export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
      <Toaster position="bottom-right" richColors closeButton />
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(ui): add sonner toast provider to app root"
```

---

### Task 3: Redesign Sidebar

**Files:**
- Rewrite: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Rewrite Sidebar.tsx**

Replace the entire content of `frontend/src/components/Sidebar.tsx` with:

```tsx
/**
 * Persistent sidebar with navigation, history, and status.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { listRuns } from "@/lib/api";
import type { Run } from "@/types";
import {
  Plus,
  CheckCircle2,
  XCircle,
  Loader2,
  Pause,
  FileText,
  Database,
} from "lucide-react";

interface SidebarProps {
  currentRunId: string | null;
  status: string;
  onNewRun: () => void;
}

function formatTimestamp(ts: string): string {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function StatusIcon({ run }: { run: Run }) {
  const passed = run.validation_passed;
  const stopped = run.status === "stopped";
  const planReady = run.status === "plan_ready";
  const running = run.status === "running";

  if (running) return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
  if (planReady) return <FileText className="w-4 h-4 text-blue-500" />;
  if (stopped) return <Pause className="w-4 h-4 text-amber-500" />;
  if (passed) return <CheckCircle2 className="w-4 h-4 text-green-500" />;
  return <XCircle className="w-4 h-4 text-red-400" />;
}

function statusLabel(run: Run): string {
  if (run.status === "running") return "Running";
  if (run.status === "plan_ready") return "Plan Ready";
  if (run.status === "stopped") return "Stopped";
  if (run.validation_passed) return "Passed";
  return "Failed";
}

export function Sidebar({ currentRunId, status, onNewRun }: SidebarProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<Run[]>([]);

  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [status]);

  return (
    <aside className="w-64 border-r flex flex-col h-screen bg-card">
      {/* Header */}
      <div className="px-4 py-4 border-b">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Database className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-sm font-semibold leading-tight">Agent B</h2>
            <p className="text-xs text-muted-foreground leading-tight">Auto Schematization</p>
          </div>
        </div>
      </div>

      {/* New Run button */}
      <div className="px-3 py-3">
        <Button onClick={onNewRun} className="w-full gap-2" size="sm">
          <Plus className="w-4 h-4" />
          New Run
        </Button>
      </div>

      <Separator />

      {/* History */}
      <div className="flex-1 min-h-0 flex flex-col px-3 py-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">
          History
        </h3>
        <ScrollArea className="flex-1">
          {history.length === 0 ? (
            <div className="text-center py-8 px-2">
              <Database className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
              <p className="text-xs text-muted-foreground">No runs yet</p>
              <p className="text-xs text-muted-foreground mt-0.5">Upload a CSV to get started</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {history.slice(0, 20).map((run) => {
                const isSelected = run.run_id === currentRunId;
                const ts = formatTimestamp(run.timestamp ?? "");
                return (
                  <button
                    key={run.run_id}
                    onClick={() => {
                      if (run.status === "plan_ready") {
                        navigate(`/runs/${run.run_id}/plan`);
                      } else {
                        navigate(`/runs/${run.run_id}/results`);
                      }
                    }}
                    title={run.dataset_name}
                    className={`
                      w-full text-left px-2.5 py-2 rounded-md transition-colors cursor-pointer
                      ${isSelected
                        ? "bg-secondary text-secondary-foreground"
                        : "hover:bg-muted/50 text-foreground"
                      }
                    `}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 flex-shrink-0">
                        <StatusIcon run={run} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate leading-tight">
                          {run.dataset_name}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground">{statusLabel(run)}</span>
                          {ts && (
                            <>
                              <span className="text-xs text-muted-foreground/50">·</span>
                              <span className="text-xs text-muted-foreground">{ts}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat(ui): redesign sidebar with Lucide icons and card-style items

Replace emoji status icons with Lucide (CheckCircle2, XCircle, Pause,
FileText, Loader2). Add relative timestamps, status labels, empty state,
prominent New Run button with icon."
```

---

### Task 4: Redesign WizardStepper

**Files:**
- Rewrite: `frontend/src/components/WizardStepper.tsx`

- [ ] **Step 1: Rewrite WizardStepper.tsx**

Replace the entire content of `frontend/src/components/WizardStepper.tsx` with:

```tsx
/**
 * Visual step indicator for the wizard flow with connector lines.
 */
import { CheckCircle2 } from "lucide-react";

interface Step {
  label: string;
  path: string;
}

const STEPS: Step[] = [
  { label: "Upload", path: "/" },
  { label: "Configure", path: "/configure" },
  { label: "Review Plan", path: "/plan" },
  { label: "Generate", path: "/progress" },
  { label: "Results", path: "/results" },
];

interface WizardStepperProps {
  currentStep: number;
  onStepClick?: (step: number) => void;
}

export function WizardStepper({ currentStep, onStepClick }: WizardStepperProps) {
  return (
    <nav className="flex items-center gap-0 mb-6" aria-label="Wizard progress">
      {STEPS.map((step, i) => {
        const isCompleted = i < currentStep;
        const isCurrent = i === currentStep;
        const canClick = isCompleted && onStepClick;

        return (
          <div key={step.path} className="flex items-center">
            {/* Step */}
            <button
              type="button"
              onClick={() => canClick && onStepClick(i)}
              disabled={!canClick}
              className={`
                flex items-center gap-2 transition-colors
                ${canClick ? "cursor-pointer hover:opacity-80" : "cursor-default"}
              `}
              aria-current={isCurrent ? "step" : undefined}
            >
              {/* Circle */}
              <div
                className={`
                  flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium transition-all
                  ${isCompleted
                    ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                    : isCurrent
                      ? "bg-primary text-primary-foreground ring-2 ring-primary/20"
                      : "bg-muted text-muted-foreground"
                  }
                `}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  i + 1
                )}
              </div>
              {/* Label */}
              <span
                className={`text-sm whitespace-nowrap ${
                  isCurrent
                    ? "font-medium text-foreground"
                    : isCompleted
                      ? "text-green-700 dark:text-green-300"
                      : "text-muted-foreground"
                }`}
              >
                {step.label}
              </span>
            </button>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div
                className={`mx-3 h-px w-8 ${
                  isCompleted
                    ? "bg-green-400 dark:bg-green-600"
                    : "bg-border border-t border-dashed border-border"
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. The `onStepClick` prop is optional so existing call sites don't break.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WizardStepper.tsx
git commit -m "feat(ui): redesign wizard stepper with connector lines and Lucide icons

Add dashed/solid connector lines between steps, CheckCircle2 for
completed steps, ring highlight on current step, optional click
navigation on completed steps, ARIA attributes."
```

---

### Task 5: Redesign ProgressTracker

**Files:**
- Rewrite: `frontend/src/components/ProgressTracker.tsx`

- [ ] **Step 1: Rewrite ProgressTracker.tsx**

Replace the entire content of `frontend/src/components/ProgressTracker.tsx` with:

```tsx
/**
 * Real-time pipeline progress display with Lucide icons and elapsed time per phase.
 */
import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { PIPELINE_PHASES, PHASE_LABELS } from "@/types";
import type { ProgressEvent } from "@/types";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface ProgressTrackerProps {
  events: ProgressEvent[];
  startTime: number;
  phases?: readonly string[];
}

export function ProgressTracker({ events, startTime, phases }: ProgressTrackerProps) {
  const [elapsed, setElapsed] = useState(0);
  const [expandedError, setExpandedError] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const completedAgents = new Set(events.map((e) => e.agent));
  const currentAttempt = Math.max(0, ...events.map((e) => e.attempt ?? 0));
  const errorEvents = new Map(
    events.filter((e) => e.type === "error").map((e) => [e.agent, e])
  );

  const allPhases = phases ? [...phases] : [...PIPELINE_PHASES];
  const completedCount = allPhases.filter((p) => completedAgents.has(p)).length;
  const progressPct = (completedCount / allPhases.length) * 100;

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  return (
    <Card className="shadow-sm">
      <CardContent className="pt-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-primary animate-spin" />
            <h2 className="text-base font-semibold">
              {currentAttempt > 0 ? `Attempt ${currentAttempt + 1}` : "Pipeline running..."}
            </h2>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            <span className="tabular-nums">{elapsedStr}</span>
          </div>
        </div>

        {/* Progress bar */}
        <Progress value={progressPct} className="mb-1" />
        <p className="text-xs text-muted-foreground mb-5">
          {completedCount}/{allPhases.length} phases complete
        </p>

        {/* Phase checklist */}
        <ul className="space-y-1.5">
          {allPhases.map((phase) => {
            const label = PHASE_LABELS[phase] || phase;
            const isCompleted = completedAgents.has(phase);
            const hasError = errorEvents.has(phase);
            const isNext =
              !isCompleted &&
              !hasError &&
              completedCount > 0 &&
              allPhases.indexOf(phase) ===
                allPhases.findIndex((p) => !completedAgents.has(p));
            const isExpanded = expandedError === phase;

            return (
              <li key={phase}>
                <div className="flex items-center gap-3">
                  {/* Status icon */}
                  {hasError ? (
                    <button
                      onClick={() => setExpandedError(isExpanded ? null : phase)}
                      className="flex items-center gap-0.5 cursor-pointer"
                    >
                      <XCircle className="w-4.5 h-4.5 text-destructive flex-shrink-0" />
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3 text-destructive" />
                      ) : (
                        <ChevronRight className="w-3 h-3 text-destructive" />
                      )}
                    </button>
                  ) : isCompleted ? (
                    <CheckCircle2 className="w-4.5 h-4.5 text-green-500 flex-shrink-0" />
                  ) : isNext ? (
                    <Loader2 className="w-4.5 h-4.5 text-primary animate-spin flex-shrink-0" />
                  ) : (
                    <Circle className="w-4.5 h-4.5 text-muted-foreground/40 flex-shrink-0" />
                  )}

                  {/* Label */}
                  <span
                    className={`text-sm ${
                      hasError
                        ? "text-destructive font-medium"
                        : isCompleted
                          ? "text-foreground"
                          : isNext
                            ? "text-primary font-medium"
                            : "text-muted-foreground"
                    }`}
                  >
                    {label}
                  </span>
                </div>

                {/* Expandable error detail */}
                {hasError && isExpanded && (
                  <div className="ml-8 mt-1 p-2 rounded bg-destructive/5 border border-destructive/20 text-xs font-mono text-destructive max-h-32 overflow-auto">
                    {errorEvents.get(phase)?.message || "Unknown error"}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProgressTracker.tsx
git commit -m "feat(ui): redesign progress tracker with Lucide icons and expandable errors

Replace text symbols with CheckCircle2, Loader2, XCircle, Circle.
Add expandable error detail per failed phase, Clock icon for elapsed
time display."
```

---

### Task 6: Upgrade FileUploader, DataPreview, DataExplorer, CodeViewer, DownloadButton

**Files:**
- Modify: `frontend/src/components/FileUploader.tsx`
- Modify: `frontend/src/components/DataPreview.tsx`
- Modify: `frontend/src/components/DataExplorer.tsx`
- Modify: `frontend/src/components/CodeViewer.tsx`
- Modify: `frontend/src/components/DownloadButton.tsx`

- [ ] **Step 1: Update FileUploader.tsx — replace emoji with Lucide icons**

In `frontend/src/components/FileUploader.tsx`:

Add import at top (after line 4):
```tsx
import { Upload, CheckCircle2, X } from "lucide-react";
```

Replace the selected file display (lines 71-79):
```tsx
          <div className="px-4 py-4">
            <CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400 mx-auto mb-1" />
            <p className="font-medium text-sm text-green-700 dark:text-green-300 truncate max-w-[180px] mx-auto">
              {selectedFile.name}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {(selectedFile.size / 1024).toFixed(1)} KB · click to change
            </p>
          </div>
```

Replace the empty state display (lines 81-90):
```tsx
          <div className="px-4 py-5">
            <Upload className="w-8 h-8 text-muted-foreground/60 mx-auto mb-2" />
            <p className="text-sm font-medium text-muted-foreground">
              Drop {label} here
            </p>
            <p className="text-xs text-muted-foreground mt-1">or click to browse</p>
            {required && (
              <p className="text-xs text-destructive mt-1 font-medium">Required</p>
            )}
          </div>
```

- [ ] **Step 2: Update DataPreview.tsx — better table styling**

Replace the entire content of `frontend/src/components/DataPreview.tsx` with:

```tsx
/**
 * Read-only table preview of uploaded CSV data.
 */
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

interface DataPreviewProps {
  columns: string[];
  rows: Record<string, unknown>[];
  totalRows: number;
  totalColumns: number;
}

export function DataPreview({ columns, rows, totalRows, totalColumns }: DataPreviewProps) {
  return (
    <div className="rounded-md border">
      <div className="px-3 py-2 bg-muted/50 text-xs text-muted-foreground border-b flex items-center justify-between">
        <span>{totalRows.toLocaleString()} rows x {totalColumns} columns</span>
        <span>Showing first {rows.length}</span>
      </div>
      <div className="overflow-auto max-h-64">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-sm font-medium whitespace-nowrap bg-muted/30 sticky top-0">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i} className="even:bg-muted/20">
                {columns.map((col) => (
                  <TableCell key={col} className="text-sm py-1.5 whitespace-nowrap tabular-nums">
                    {String(row[col] ?? "")}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update DataExplorer.tsx — skeleton loading, improved table**

In `frontend/src/components/DataExplorer.tsx`:

Replace the loading state (lines 73-75):
```tsx
        {loading && !data && (
          <div className="border rounded-md overflow-hidden">
            <div className="bg-muted/30 px-3 py-2 border-b">
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            </div>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-3 py-2.5 border-b border-border/50">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div key={j} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${60 + Math.random() * 80}px` }} />
                ))}
              </div>
            ))}
          </div>
        )}
```

Replace the table header cells (lines 83-89) — make them `text-sm`:
```tsx
                    <th
                      key={col}
                      className="px-3 py-2 text-left text-sm font-medium whitespace-nowrap border-b"
                    >
                      {col}
                    </th>
```

Replace the table body cells (lines 96-101) — add tabular-nums:
```tsx
                      <td
                        key={col}
                        className="px-3 py-1.5 text-sm whitespace-nowrap border-b border-border/50 tabular-nums"
                      >
                        {String(row[col] ?? "")}
                      </td>
```

- [ ] **Step 4: Update CodeViewer.tsx — add line numbers and copy icon**

Replace the entire content of `frontend/src/components/CodeViewer.tsx` with:

```tsx
/**
 * Read-only code/text viewer with line numbers and copy button.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Copy, Check } from "lucide-react";

interface CodeViewerProps {
  content: string;
  language?: string;
}

export function CodeViewer({ content }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const lines = content.split("\n");

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative rounded-md border bg-muted/30">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleCopy}
        className="absolute top-2 right-2 text-xs gap-1.5"
      >
        {copied ? (
          <><Check className="w-3.5 h-3.5 text-green-500" /> Copied</>
        ) : (
          <><Copy className="w-3.5 h-3.5" /> Copy</>
        )}
      </Button>
      <ScrollArea className="h-[500px]">
        <div className="flex">
          <div className="select-none text-right pr-3 pl-3 py-4 text-xs font-mono text-muted-foreground/50 border-r bg-muted/20">
            {lines.map((_, i) => (
              <div key={i} className="leading-5">{i + 1}</div>
            ))}
          </div>
          <pre className="p-4 text-sm font-mono whitespace-pre-wrap flex-1 leading-5">{content}</pre>
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 5: Update DownloadButton.tsx — add icon**

Replace the entire content of `frontend/src/components/DownloadButton.tsx` with:

```tsx
/**
 * ZIP download button for pipeline outputs.
 */
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { downloadZip } from "@/lib/api";

interface DownloadButtonProps {
  runId: string;
  datasetName: string;
}

export function DownloadButton({ runId, datasetName }: DownloadButtonProps) {
  const handleDownload = async () => {
    const blob = await downloadZip(runId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${datasetName}_outputs.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="outline" onClick={handleDownload} className="gap-2">
      <Download className="w-4 h-4" />
      Download ZIP
    </Button>
  );
}
```

- [ ] **Step 6: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/FileUploader.tsx frontend/src/components/DataPreview.tsx frontend/src/components/DataExplorer.tsx frontend/src/components/CodeViewer.tsx frontend/src/components/DownloadButton.tsx
git commit -m "feat(ui): upgrade shared components with Lucide icons and better tables

FileUploader: replace emoji with Upload/CheckCircle2 icons.
DataPreview: text-sm, sticky headers, alternating rows.
DataExplorer: skeleton loading, improved table styling.
CodeViewer: add line numbers, Copy/Check icon feedback.
DownloadButton: add Download icon."
```

---

### Task 7: Redesign CsvEditor with Explicit Edit Mode

**Files:**
- Rewrite: `frontend/src/components/CsvEditor.tsx`

- [ ] **Step 1: Rewrite CsvEditor.tsx**

Replace the entire content of `frontend/src/components/CsvEditor.tsx` with:

```tsx
/**
 * CSV table viewer with explicit edit mode toggle.
 * View mode by default. Click "Edit" button to enter edit mode.
 * In edit mode, single-click a cell to edit it. Changed cells are highlighted.
 */
import { useState, useCallback } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, X } from "lucide-react";

interface CsvEditorProps {
  columns: string[];
  rows: Record<string, unknown>[];
  editable?: boolean;
  onChange?: (rows: Record<string, unknown>[]) => void;
}

export function CsvEditor({ columns, rows, editable = false, onChange }: CsvEditorProps) {
  const [editing, setEditing] = useState(false);
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);
  const [changedCells, setChangedCells] = useState<Set<string>>(new Set());
  const [originalRows] = useState(() => rows.map((r) => ({ ...r })));

  const handleCellChange = useCallback((rowIdx: number, col: string, value: string) => {
    if (!onChange) return;
    const newRows = [...rows];
    newRows[rowIdx] = { ...newRows[rowIdx], [col]: value };
    onChange(newRows);

    const cellKey = `${rowIdx}:${col}`;
    const originalValue = String(originalRows[rowIdx]?.[col] ?? "");
    setChangedCells((prev) => {
      const next = new Set(prev);
      if (value !== originalValue) {
        next.add(cellKey);
      } else {
        next.delete(cellKey);
      }
      return next;
    });
  }, [onChange, rows, originalRows]);

  const handleDiscard = () => {
    if (onChange && originalRows.length > 0) {
      onChange(originalRows.map((r) => ({ ...r })));
    }
    setEditing(false);
    setEditingCell(null);
    setChangedCells(new Set());
  };

  return (
    <div>
      {/* Edit mode toggle */}
      {editable && (
        <div className="flex items-center justify-between mb-2">
          {editing ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-amber-600 dark:text-amber-400 font-medium">
                Editing — {changedCells.size} cell{changedCells.size !== 1 ? "s" : ""} changed
              </span>
              <Button variant="ghost" size="sm" onClick={handleDiscard} className="gap-1 text-xs">
                <X className="w-3.5 h-3.5" /> Discard
              </Button>
            </div>
          ) : (
            <div />
          )}
          {!editing && (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)} className="gap-1.5">
              <Pencil className="w-3.5 h-3.5" /> Edit PVMAP
            </Button>
          )}
        </div>
      )}

      <div className="rounded-md border overflow-auto max-h-[500px]">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-sm font-medium whitespace-nowrap bg-muted/30 sticky top-0">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i} className="even:bg-muted/20">
                {columns.map((col) => {
                  const cellKey = `${i}:${col}`;
                  const isChanged = changedCells.has(cellKey);
                  const isEditing = editing && editingCell?.row === i && editingCell?.col === col;

                  return (
                    <TableCell
                      key={col}
                      className={`py-1 px-2 ${isChanged ? "bg-amber-50 dark:bg-amber-950/30" : ""}`}
                    >
                      {isEditing ? (
                        <Input
                          className="h-7 text-sm"
                          value={String(row[col] ?? "")}
                          onChange={(e) => handleCellChange(i, col, e.target.value)}
                          onBlur={() => setEditingCell(null)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") setEditingCell(null);
                            if (e.key === "Escape") setEditingCell(null);
                          }}
                          autoFocus
                        />
                      ) : (
                        <span
                          className={`text-sm block px-1 tabular-nums ${
                            editing ? "cursor-text hover:bg-primary/5 rounded" : "cursor-default"
                          }`}
                          onClick={() => editing && editable && setEditingCell({ row: i, col })}
                        >
                          {String(row[col] ?? "")}
                        </span>
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CsvEditor.tsx
git commit -m "feat(ui): redesign CSV editor with explicit edit mode and change highlighting

Replace double-click editing with explicit Edit PVMAP button. Single-click
to edit cells in edit mode. Changed cells highlighted in amber. Discard
button to revert. Keyboard support (Enter/Escape)."
```

---

### Task 8: Upgrade FeedbackForm and OutputViewer

**Files:**
- Rewrite: `frontend/src/components/FeedbackForm.tsx`
- Rewrite: `frontend/src/components/OutputViewer.tsx`

- [ ] **Step 1: Rewrite FeedbackForm.tsx with shadcn Select and toast**

Replace the entire content of `frontend/src/components/FeedbackForm.tsx` with:

```tsx
/**
 * Feedback submission form with category and severity.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Send } from "lucide-react";
import { toast } from "sonner";
import { submitFeedback } from "@/lib/api";

const CATEGORIES = [
  "Column mapping", "Property names", "Value formatting",
  "Missing mappings", "Incorrect mappings", "Structural issue", "Other",
];

interface FeedbackFormProps {
  runId: string;
  onRerunStarted: (newRunId: string) => void;
}

export function FeedbackForm({ runId, onRerunStarted }: FeedbackFormProps) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [severity, setSeverity] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const resp = await submitFeedback(runId, { text, category, severity });
      toast.success("Feedback submitted — starting new run");
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Feedback submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Feedback & Re-run</h3>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe what needs to be fixed or improved..."
        rows={4}
      />
      <div className="flex items-center gap-4 flex-wrap">
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2 flex-1 min-w-[160px]">
          <Label className="text-sm whitespace-nowrap">Severity: {severity}</Label>
          <Slider
            value={[severity]}
            onValueChange={(v) => {
              const arr = v as number[];
              if (arr.length > 0) setSeverity(arr[0]);
            }}
            min={1}
            max={5}
            step={1}
            className="w-32"
          />
        </div>
        <Button onClick={handleSubmit} disabled={!text.trim() || submitting} className="gap-2">
          {submitting ? (
            "Submitting..."
          ) : (
            <><Send className="w-4 h-4" /> Re-run with Feedback</>
          )}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite OutputViewer.tsx with tab icons and sanitized markdown**

Replace the entire content of `frontend/src/components/OutputViewer.tsx` with:

```tsx
/**
 * Tabbed output file viewer with tab icons and sanitized markdown.
 */
import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CsvEditor } from "./CsvEditor";
import { CodeViewer } from "./CodeViewer";
import { listFiles, getFile, updateFile, revalidate } from "@/lib/api";
import { toast } from "sonner";
import DOMPurify from "dompurify";
import {
  Table2,
  FileText,
  FileCode,
  BarChart3,
  StickyNote,
  Settings,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { FileResponse, CsvFileResponse, TextFileResponse, PipelineResult } from "@/types";

const TAB_CONFIG = [
  { key: "generated_pvmap.csv", label: "PVMAP", icon: Table2 },
  { key: "output_metadata.csv", label: "Metadata", icon: Settings },
  { key: "processed.csv", label: "Processed", icon: Table2 },
  { key: "processed.mcf", label: "MCF", icon: FileCode },
  { key: "processed.tmcf", label: "TMCF", icon: FileCode },
  { key: "processed_stat_vars.mcf", label: "StatVars", icon: FileText },
  { key: "generation_notes.md", label: "Notes", icon: StickyNote },
  { key: "processed_counters.txt", label: "Metrics", icon: BarChart3 },
];

interface OutputViewerProps {
  runId: string;
  result?: PipelineResult;
}

function isCsvResponse(f: FileResponse): f is CsvFileResponse {
  return f.type === "csv";
}

function isTextResponse(f: FileResponse): f is TextFileResponse {
  return f.type === "text";
}

function ResultBanner({ result }: { result: PipelineResult }) {
  const passed = result.validation_passed;
  const attempts = (result.retry_count ?? 0) + 1;
  const exitReason = result.exit_reason ?? "Unknown";
  const score = result.quality_metrics?.heuristic_score;

  return (
    <div className={`mb-4 p-4 rounded-lg border flex items-center justify-between ${
      passed
        ? "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800"
        : "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800"
    }`}>
      <div className="flex items-center gap-3">
        {passed ? (
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        )}
        <div>
          <p className={`text-sm font-medium ${passed ? "text-green-800 dark:text-green-200" : "text-red-800 dark:text-red-200"}`}>
            {passed ? "Validation Passed" : "Validation Failed"}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {attempts} attempt{attempts !== 1 ? "s" : ""} — {exitReason}
          </p>
        </div>
      </div>
      {score != null && (
        <Badge variant="outline" className="text-sm tabular-nums">
          Score: {score.toFixed(1)}/100
        </Badge>
      )}
    </div>
  );
}

export function OutputViewer({ runId, result }: OutputViewerProps) {
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [fileData, setFileData] = useState<Record<string, FileResponse>>({});
  const [editedRows, setEditedRows] = useState<Record<string, unknown>[] | null>(null);
  const [revalidating, setRevalidating] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("");

  useEffect(() => {
    listFiles(runId).then((resp) => {
      setAvailableFiles(resp.files);
    });
  }, [runId]);

  useEffect(() => {
    const tabs = TAB_CONFIG.filter((t) => availableFiles.includes(t.key));
    if (tabs.length === 0) return;
    const firstKey = tabs[0].key;
    if (!fileData[firstKey]) {
      void loadFile(firstKey);
    }
    if (!activeTab) {
      setActiveTab(firstKey);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableFiles]);

  const loadFile = async (filename: string) => {
    if (fileData[filename]) return;
    const data = await getFile(runId, filename);
    setFileData((prev) => ({ ...prev, [filename]: data }));
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    void loadFile(value);
  };

  const tabs = TAB_CONFIG.filter((t) => availableFiles.includes(t.key));

  const handleSaveAndRevalidate = async () => {
    if (editedRows) {
      await updateFile(runId, "generated_pvmap.csv", { rows: editedRows });
    }
    setRevalidating(true);
    try {
      const res = await revalidate(runId);
      if (res.success) {
        toast.success(`Validation passed: ${res.data_rows} data rows`);
      } else {
        toast.error(`Validation failed: ${res.error}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Revalidation failed");
    } finally {
      setRevalidating(false);
    }
  };

  return (
    <div>
      {/* Result banner */}
      {result && <ResultBanner result={result} />}

      {tabs.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
          <p className="text-sm text-muted-foreground">No output files found.</p>
        </div>
      ) : (
        <Tabs value={activeTab || tabs[0]?.key} onValueChange={handleTabChange}>
          <TabsList className="flex-wrap h-auto gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const fd = fileData[tab.key];
              const sizeLabel = fd && isCsvResponse(fd) ? ` (${fd.row_count}r)` : "";
              return (
                <TabsTrigger key={tab.key} value={tab.key} className="text-xs gap-1.5">
                  <Icon className="w-3.5 h-3.5" />
                  {tab.label}{sizeLabel}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {tabs.map((tab) => {
            const fd = fileData[tab.key];
            return (
              <TabsContent key={tab.key} value={tab.key}>
                {fd ? (
                  isCsvResponse(fd) ? (
                    <CsvEditor
                      columns={fd.columns}
                      rows={editedRows && tab.key === "generated_pvmap.csv" ? editedRows : fd.rows}
                      editable={tab.key === "generated_pvmap.csv"}
                      onChange={tab.key === "generated_pvmap.csv" ? setEditedRows : undefined}
                    />
                  ) : tab.key.endsWith(".md") && isTextResponse(fd) ? (
                    <div
                      className="prose dark:prose-invert max-w-none p-4"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(fd.content) }}
                    />
                  ) : isTextResponse(fd) ? (
                    <CodeViewer content={fd.content} />
                  ) : null
                ) : (
                  <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Loading file...</span>
                  </div>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}

      {/* Save & Revalidate button */}
      {availableFiles.includes("generated_pvmap.csv") && editedRows && (
        <div className="flex justify-center mt-4">
          <Button onClick={handleSaveAndRevalidate} disabled={revalidating} className="gap-2">
            {revalidating ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Validating...</>
            ) : (
              "Save & Revalidate"
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/FeedbackForm.tsx frontend/src/components/OutputViewer.tsx
git commit -m "feat(ui): upgrade FeedbackForm and OutputViewer

FeedbackForm: replace raw select with shadcn Select, toast notifications
instead of console.error. OutputViewer: add tab icons, sanitize markdown
with DOMPurify, improved result banner with Lucide icons, toast for
revalidation results."
```

---

### Task 9: Redesign UploadPage

**Files:**
- Rewrite: `frontend/src/pages/UploadPage.tsx`

- [ ] **Step 1: Rewrite UploadPage.tsx**

Replace the entire content of `frontend/src/pages/UploadPage.tsx` with:

```tsx
/**
 * Wizard Step 1: Upload CSV data files.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { FileUploader } from "@/components/FileUploader";
import { DataPreview } from "@/components/DataPreview";
import { uploadFiles } from "@/lib/api";
import { toast } from "sonner";
import { ChevronRight, ChevronDown, ChevronUp, CheckCircle2, AlertTriangle } from "lucide-react";
import type { UploadResponse } from "@/types";

interface UploadPageProps {
  onUploadComplete: (response: UploadResponse) => void;
}

export function UploadPage({ onUploadComplete }: UploadPageProps) {
  const navigate = useNavigate();
  const [inputFile, setInputFile] = useState<File | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [preview, setPreview] = useState<UploadResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMetadata, setShowMetadata] = useState(false);

  const isNameValid = datasetName.trim().length >= 2;

  const handleInputSelect = async (file: File) => {
    setInputFile(file);
    setError(null);
    const name = file.name.replace(".csv", "").replace(/\s+/g, "_");
    if (!datasetName) setDatasetName(name);

    try {
      setUploading(true);
      const response = await uploadFiles(file, metadataFile ?? undefined, name || undefined);
      setPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      toast.error("Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  const handleNext = async () => {
    if (!inputFile) return;
    const finalName = datasetName.trim() || inputFile.name.replace(".csv", "").replace(/\s+/g, "_");
    try {
      setUploading(true);
      setError(null);
      const response = await uploadFiles(inputFile, metadataFile ?? undefined, finalName);
      onUploadComplete(response);
      navigate("/configure");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      toast.error("Upload failed — please try again");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={0} />

      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Upload Your Data</h1>
        <p className="text-muted-foreground mt-1">
          Start by uploading a CSV file to transform into Data Commons StatVarObservations.
        </p>
      </div>

      {/* Main upload card */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="space-y-6">
            {/* File upload */}
            <div>
              <Label className="mb-2 block font-medium">
                Input CSV <span className="text-destructive">*</span>
              </Label>
              <FileUploader
                label="CSV file"
                required
                onFileSelect={handleInputSelect}
                selectedFile={inputFile}
              />
            </div>

            {/* Dataset name */}
            <div>
              <Label htmlFor="dataset-name" className="mb-2 block font-medium">
                Dataset Name
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="dataset-name"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g., census_income_data"
                  className="max-w-sm"
                />
                {datasetName && (
                  isNameValid ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : (
                    <span className="text-xs text-muted-foreground">min 2 characters</span>
                  )
                )}
              </div>
            </div>

            {/* Collapsible metadata section */}
            <div>
              <button
                type="button"
                onClick={() => setShowMetadata(!showMetadata)}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                {showMetadata ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Advanced: Add metadata CSV
                <span className="text-xs">(optional)</span>
              </button>
              {showMetadata && (
                <div className="mt-3">
                  <FileUploader
                    label="metadata CSV"
                    onFileSelect={setMetadataFile}
                    selectedFile={metadataFile}
                  />
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 rounded-md text-sm border bg-destructive/5 text-destructive border-destructive/20 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Data preview */}
      {preview && (
        <Card className="shadow-sm mt-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Data Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <DataPreview
              columns={preview.column_names}
              rows={preview.preview}
              totalRows={preview.rows}
              totalColumns={preview.columns}
            />
          </CardContent>
        </Card>
      )}

      {/* Next button */}
      <div className="flex justify-end mt-6">
        <Button
          onClick={handleNext}
          disabled={!preview || uploading || !isNameValid}
          size="lg"
          className="gap-2"
        >
          {uploading ? "Uploading..." : "Continue to Configure"}
          {!uploading && <ChevronRight className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/UploadPage.tsx
git commit -m "feat(ui): redesign upload page with card layout and collapsible metadata

Remove gradient hero section. Clean card-based layout. Collapsible
metadata upload section. Dataset name validation indicator. Toast
notifications for errors. Lucide icons throughout."
```

---

### Task 10: Redesign ConfigurePage

**Files:**
- Rewrite: `frontend/src/pages/ConfigurePage.tsx`

- [ ] **Step 1: Rewrite ConfigurePage.tsx**

Replace the entire content of `frontend/src/pages/ConfigurePage.tsx` with:

```tsx
/**
 * Wizard Step 2: Configure pipeline settings before running.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { WizardStepper } from "@/components/WizardStepper";
import { DataExplorer } from "@/components/DataExplorer";
import { startRun } from "@/lib/api";
import { toast } from "sonner";
import { ChevronLeft, Play, ChevronDown, ChevronUp, Settings, Cpu, MessageSquare } from "lucide-react";
import type { PipelineConfig } from "@/types";

const GEMINI_MODELS = [
  { value: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro" },
  { value: "gemini-3.0-flash", label: "Gemini 3.0 Flash" },
  { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
] as const;

interface ConfigurePageProps {
  runId: string;
  datasetName: string;
  config: PipelineConfig;
  onConfigChange: (config: PipelineConfig) => void;
  onRunStarted: () => void;
}

export function ConfigurePage({
  runId, datasetName, config, onConfigChange, onRunStarted,
}: ConfigurePageProps) {
  const navigate = useNavigate();
  const [showFeedback, setShowFeedback] = useState(false);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    try {
      await startRun({
        run_id: runId,
        dataset_name: datasetName,
        model: config.model,
        max_retries: config.max_retries,
        enable_mcp: config.enable_mcp,
        use_schema_examples: config.use_schema_examples,
        human_feedback: config.human_feedback,
      });
      onRunStarted();
      navigate(`/runs/${runId}/plan`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start run");
      setStarting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <WizardStepper currentStep={1} />

      <h1 className="text-2xl font-bold mb-1">Configure Pipeline</h1>
      <p className="text-muted-foreground mb-6">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      <div className="space-y-4">
        {/* Model & Retries card */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="w-4 h-4 text-muted-foreground" /> Model & Retries
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <Label className="mb-2 block text-sm">Model</Label>
              <Select
                value={config.model}
                onValueChange={(v) => onConfigChange({ ...config, model: v as string })}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GEMINI_MODELS.map((m) => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-2 block text-sm">Max Retries: {config.max_retries}</Label>
              <Slider
                value={[config.max_retries]}
                onValueChange={(v) => {
                  const arr = v as number[];
                  if (arr.length > 0) onConfigChange({ ...config, max_retries: arr[0] });
                }}
                min={0}
                max={10}
                step={1}
              />
              <p className="text-xs text-muted-foreground mt-1">
                How many validation-feedback-retry cycles to run
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Options card */}
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Settings className="w-4 h-4 text-muted-foreground" /> Options
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm">MCP Discovery</Label>
                  <p className="text-xs text-muted-foreground">Use Model Context Protocol for enhanced mapping</p>
                </div>
                <Switch
                  checked={config.enable_mcp}
                  onCheckedChange={(v) => onConfigChange({ ...config, enable_mcp: v })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm">Schema Examples</Label>
                  <p className="text-xs text-muted-foreground">Include schema vocabulary in the generation prompt</p>
                </div>
                <Switch
                  checked={config.use_schema_examples}
                  onCheckedChange={(v) => onConfigChange({ ...config, use_schema_examples: v })}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Initial feedback (collapsible) */}
        <Card className="shadow-sm">
          <button
            type="button"
            onClick={() => setShowFeedback(!showFeedback)}
            className="w-full px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-muted/30 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Initial Feedback</span>
              <span className="text-xs text-muted-foreground">(optional)</span>
            </div>
            {showFeedback ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showFeedback && (
            <CardContent className="pt-0 pb-4">
              <Textarea
                value={config.human_feedback || ""}
                onChange={(e) =>
                  onConfigChange({ ...config, human_feedback: e.target.value || null })
                }
                placeholder="e.g., 'The date column uses YYYY-MM format' or 'Ignore the footnote rows at the bottom'"
                rows={3}
              />
              <p className="text-xs text-muted-foreground mt-1.5">
                Give the pipeline hints about your data to improve initial results
              </p>
            </CardContent>
          )}
        </Card>
      </div>

      {/* Data Preview */}
      <div className="mt-4">
        <DataExplorer runId={runId} />
      </div>

      {/* Summary strip + actions */}
      <div className="mt-6 p-3 rounded-md bg-muted/50 text-xs text-muted-foreground flex items-center justify-between">
        <span className="font-mono">
          {datasetName} · {config.model.replace("gemini-", "").replace("-preview", "")} · {config.max_retries} retries
        </span>
      </div>
      <div className="flex justify-between mt-4">
        <Button variant="ghost" onClick={() => navigate("/")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleStart} size="lg" disabled={starting} className="gap-2">
          {starting ? "Starting..." : "Generate Plan"}
          {!starting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ConfigurePage.tsx
git commit -m "feat(ui): redesign configure page with card grouping and summary strip

Group settings into Model/Retries, Options, and collapsible Feedback
cards with icons and descriptions. Add summary strip showing config
at a glance. Toast error on start failure."
```

---

### Task 11: Redesign ReviewPlanPage

**Files:**
- Rewrite: `frontend/src/pages/ReviewPlanPage.tsx`

- [ ] **Step 1: Rewrite ReviewPlanPage.tsx**

Replace the entire content of `frontend/src/pages/ReviewPlanPage.tsx` with:

```tsx
/**
 * Wizard Step 3: Review and edit the mapping plan.
 *
 * Two states:
 * 1. Phase 1 running — shows progress tracker with skeleton placeholder
 * 2. Phase 1 complete — shows formatted plan with edit toggle
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getFile, generatePvmap, stopRun } from "@/lib/api";
import { toast } from "sonner";
import { PLAN_PHASES } from "@/types";
import {
  ChevronLeft,
  Play,
  Square,
  Pencil,
  Eye,
  CheckCircle2,
} from "lucide-react";
import DOMPurify from "dompurify";

interface ReviewPlanPageProps {
  datasetName: string;
  startTime: number;
  onGenerateStarted: () => void;
  onError: (event: import("@/types").ProgressEvent) => void;
}

export function ReviewPlanPage({
  datasetName, startTime, onGenerateStarted, onError,
}: ReviewPlanPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState("");
  const [planReady, setPlanReady] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const { events } = useWebSocket({
    runId: runId ?? null,
    enabled: !planReady,
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        toast.info("Plan ready for review");
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
    onError,
  });

  useEffect(() => {
    if (!planReady || !runId) return;
    setLoadingPlan(true);
    getFile(runId, "mapping_plan.md")
      .then((file) => {
        if (file.type === "text") setPlan(file.content);
      })
      .catch(() => toast.error("Failed to load plan"))
      .finally(() => setLoadingPlan(false));
  }, [planReady, runId]);

  useEffect(() => {
    if (!runId) return;
    getFile(runId, "mapping_plan.md")
      .then((file) => {
        if (file.type === "text" && file.content) {
          setPlan(file.content);
          setPlanReady(true);
        }
      })
      .catch(() => {});
  }, [runId]);

  const handleApprove = async () => {
    if (!runId) return;
    setSubmitting(true);
    try {
      await generatePvmap(runId, plan);
      onGenerateStarted();
      navigate(`/runs/${runId}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start generation");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async () => {
    if (!runId || stopping) return;
    if (!window.confirm("Stop this run?")) return;
    setStopping(true);
    try {
      await stopRun(runId);
      navigate(`/runs/${runId}/results`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to stop");
      setStopping(false);
    }
  };

  // Simple markdown-to-HTML converter (for rendering plan)
  const renderMarkdown = (text: string): string => {
    let html = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    html = `<p>${html}</p>`;
    return DOMPurify.sanitize(html);
  };

  // Phase 1 still running
  if (!planReady) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <WizardStepper currentStep={2} />
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Preparing Your Plan</h1>
          <Button
            variant="outline"
            size="sm"
            onClick={handleStop}
            disabled={stopping}
            className="text-destructive border-destructive/50 hover:bg-destructive/10 gap-1.5"
          >
            <Square className="w-3.5 h-3.5" />
            {stopping ? "Stopping..." : "Stop"}
          </Button>
        </div>
        <ProgressTracker events={events} startTime={startTime} phases={PLAN_PHASES} />

        {/* Skeleton placeholder for plan */}
        <Card className="shadow-sm mt-4">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${50 + Math.random() * 50}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Loading plan from API
  if (loadingPlan) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={2} />
        <Card className="shadow-sm mt-6">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${40 + Math.random() * 60}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={2} />

      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold">Review Mapping Plan</h1>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-600 dark:text-green-400 font-medium">Plan Ready</span>
        </div>
      </div>
      <p className="text-muted-foreground mb-4">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      {/* Plan viewer/editor */}
      <Card className="shadow-sm">
        <div className="px-4 py-2 border-b flex items-center justify-between bg-muted/30">
          <span className="text-sm font-medium">Mapping Plan</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsEditing(!isEditing)}
            className="gap-1.5 text-xs"
          >
            {isEditing ? (
              <><Eye className="w-3.5 h-3.5" /> Preview</>
            ) : (
              <><Pencil className="w-3.5 h-3.5" /> Edit</>
            )}
          </Button>
        </div>
        <CardContent className="pt-4">
          {isEditing ? (
            <Textarea
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="font-mono text-sm min-h-[500px]"
              rows={30}
            />
          ) : (
            <div
              className="prose dark:prose-invert max-w-none text-sm min-h-[200px]"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(plan) }}
            />
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between mt-6">
        <Button variant="ghost" onClick={() => navigate("/configure")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleApprove} disabled={submitting || !plan} size="lg" className="gap-2">
          {submitting ? "Starting..." : "Approve & Generate PVMAP"}
          {!submitting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReviewPlanPage.tsx
git commit -m "feat(ui): redesign review plan page with markdown rendering and edit toggle

Show plan as rendered markdown by default. Toggle to textarea for editing.
Skeleton placeholder during Phase 1. Toast notifications. Lucide icons
for stop/edit/preview actions."
```

---

### Task 12: Redesign ProgressPage

**Files:**
- Rewrite: `frontend/src/pages/ProgressPage.tsx`

- [ ] **Step 1: Rewrite ProgressPage.tsx**

Replace the entire content of `frontend/src/pages/ProgressPage.tsx` with:

```tsx
/**
 * Wizard Step 4: Real-time pipeline progress with status header and activity log.
 */
import { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import { stopRun } from "@/lib/api";
import { toast } from "sonner";
import { GENERATE_PHASES } from "@/types";
import type { ProgressEvent } from "@/types";
import {
  Square,
  Loader2,
  Clock,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Info,
  CheckCircle2,
} from "lucide-react";

interface ProgressPageProps {
  startTime: number;
  onComplete: (result: ProgressEvent) => void;
  onError: (event: ProgressEvent) => void;
}

function EventIcon({ type }: { type: string }) {
  if (type === "error") return <AlertTriangle className="w-3 h-3 text-destructive flex-shrink-0" />;
  if (type === "complete") return <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />;
  return <Info className="w-3 h-3 text-muted-foreground flex-shrink-0" />;
}

export function ProgressPage({ startTime, onComplete, onError }: ProgressPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [stopping, setStopping] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const logRef = useRef<HTMLDivElement>(null);

  const { events } = useWebSocket({
    runId: runId ?? null,
    onComplete: (event) => {
      onComplete(event);
      toast.success("Pipeline complete!");
      setTimeout(() => navigate(`/runs/${runId}/results`), 1500);
    },
    onError: (event) => {
      onError(event);
      toast.error("Pipeline encountered an error");
    },
  });

  // Elapsed timer
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current && showLog) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events, showLog]);

  const currentAttempt = Math.max(0, ...events.map((e) => e.attempt ?? 0));
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  const handleStop = async () => {
    if (!runId || stopping) return;
    if (!window.confirm("Stop this run? You can resume later from the last checkpoint.")) return;
    setStopping(true);
    try {
      await stopRun(runId);
      navigate(`/runs/${runId}/results`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to stop run");
      setStopping(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper currentStep={3} />

      {/* Status header */}
      <Card className="shadow-sm mb-4">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
              <div>
                <h1 className="text-lg font-semibold">Generating PVMAP</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  {currentAttempt > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      Attempt {currentAttempt + 1}
                    </Badge>
                  )}
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span className="tabular-nums">{elapsedStr}</span>
                  </div>
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStop}
              disabled={stopping}
              className="text-destructive border-destructive/50 hover:bg-destructive/10 gap-1.5"
            >
              <Square className="w-3.5 h-3.5" />
              {stopping ? "Stopping..." : "Stop"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Progress tracker */}
      <ProgressTracker events={events} startTime={startTime} phases={GENERATE_PHASES} />

      {/* Activity log (collapsible) */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowLog(!showLog)}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer mb-2"
        >
          {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          Activity Log ({events.length} events)
        </button>
        {showLog && (
          <Card className="shadow-sm">
            <div
              ref={logRef}
              className="max-h-64 overflow-auto p-3 space-y-1"
            >
              {events.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">Waiting for events...</p>
              ) : (
                events.map((event, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono">
                    <EventIcon type={event.type} />
                    <span className="text-muted-foreground tabular-nums whitespace-nowrap">
                      {event.agent}
                    </span>
                    <span className={
                      event.type === "error" ? "text-destructive" :
                      event.type === "complete" ? "text-green-600 dark:text-green-400" :
                      "text-foreground"
                    }>
                      {event.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProgressPage.tsx
git commit -m "feat(ui): redesign progress page with status header and activity log

Add status header card with attempt badge and elapsed timer. Collapsible
activity log showing WebSocket events with type-colored icons. Toast
notification on completion with auto-redirect. Lucide icons throughout."
```

---

### Task 13: Update ResultsPage

**Files:**
- Modify: `frontend/src/pages/ResultsPage.tsx`

- [ ] **Step 1: Update ResultsPage.tsx with Lucide icons and toast**

Replace the entire content of `frontend/src/pages/ResultsPage.tsx` with:

```tsx
/**
 * Wizard Step 5: View results, edit PVMAP, provide feedback.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import { Button } from "@/components/ui/button";
import { DataExplorer } from "@/components/DataExplorer";
import { getRun, resumeRun } from "@/lib/api";
import { toast } from "sonner";
import { Play, Pause, Loader2 } from "lucide-react";
import type { PipelineResult } from "@/types";

interface ResultsPageProps {
  datasetName: string;
  result?: PipelineResult;
  onRerunStarted: (newRunId: string) => void;
}

export function ResultsPage({ datasetName: propDatasetName, result: propResult, onRerunStarted }: ResultsPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const [datasetName, setDatasetName] = useState(propDatasetName);
  const [result, setResult] = useState<PipelineResult | undefined>(propResult);
  const [loading, setLoading] = useState(false);
  const [runStatus, setRunStatus] = useState<string>("");
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    if (propDatasetName) setDatasetName(propDatasetName);
    if (propResult) setResult(propResult);
  }, [propDatasetName, propResult]);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getRun(runId)
      .then((run) => {
        setRunStatus(run.status);
        if (!propDatasetName) setDatasetName(run.dataset_name ?? "");
        if (!propResult && run.result && Object.keys(run.result).length > 0) {
          setResult(run.result as PipelineResult);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  const handleResume = async () => {
    if (!runId || resuming) return;
    setResuming(true);
    try {
      await resumeRun(runId);
      toast.info("Resuming pipeline...");
      onRerunStarted(runId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to resume");
      setResuming(false);
    }
  };

  if (!runId) return null;

  return (
    <div className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-6xl mx-auto">
        <WizardStepper currentStep={4} />

        {/* Page header */}
        <div className="flex items-center justify-between mt-6 mb-5">
          <div>
            {loading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="text-lg text-muted-foreground">Loading results...</span>
              </div>
            ) : (
              <>
                <h1 className="text-2xl font-bold">
                  Results
                  {datasetName && (
                    <span className="text-muted-foreground font-mono ml-2 text-xl">
                      — {datasetName}
                    </span>
                  )}
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Run ID: <span className="font-mono">{runId.slice(0, 12)}</span>
                </p>
              </>
            )}
          </div>
          <DownloadButton runId={runId} datasetName={datasetName} />
        </div>

        {/* Stopped banner */}
        {runStatus === "stopped" && (
          <Card className="shadow-sm mb-6 border-amber-200 dark:border-amber-800">
            <CardContent className="pt-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Pause className="w-5 h-5 text-amber-500" />
                <div>
                  <p className="font-medium">Run was stopped</p>
                  <p className="text-sm text-muted-foreground">
                    Partial results shown below. Resume to continue from the last checkpoint.
                  </p>
                </div>
              </div>
              <Button onClick={handleResume} disabled={resuming} className="gap-2">
                {resuming ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Resuming...</>
                ) : (
                  <><Play className="w-4 h-4" /> Resume Run</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Input data preview */}
        <div className="mb-6">
          <DataExplorer runId={runId} />
        </div>

        {/* Output files section */}
        <Card className="shadow-sm mb-6">
          <CardContent className="pt-6">
            <OutputViewer runId={runId} result={result} />
          </CardContent>
        </Card>

        <Separator className="my-6" />

        {/* Feedback section */}
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ResultsPage.tsx
git commit -m "feat(ui): update results page with Lucide icons and toast notifications

Replace text-based loading with spinner icon. Add Pause/Play icons for
stopped banner. Toast for resume action. Truncate run ID display."
```

---

### Task 14: Final Build Verification

**Files:** None (verification only)

- [ ] **Step 1: Clean build**

```bash
cd frontend && rm -rf dist && npm run build
```

Expected: Build succeeds with no errors or warnings.

- [ ] **Step 2: Start dev server and verify**

```bash
cd frontend && npm run dev &
sleep 3
curl -s http://localhost:5173/ | head -20
kill %1
```

Expected: HTML response with React app entry point.

- [ ] **Step 3: Remove old Geist font package**

```bash
cd frontend && npm uninstall @fontsource-variable/geist
```

- [ ] **Step 4: Final build after cleanup**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(ui): remove unused Geist font dependency"
```
