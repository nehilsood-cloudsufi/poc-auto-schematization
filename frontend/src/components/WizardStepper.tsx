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
