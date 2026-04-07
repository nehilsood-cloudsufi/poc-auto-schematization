/**
 * Visual step indicator for the wizard flow.
 */

interface Step {
  label: string;
  path: string;
}

const STEPS: Step[] = [
  { label: "Upload", path: "/" },
  { label: "Configure", path: "/configure" },
  { label: "Running", path: "/progress" },
  { label: "Results", path: "/results" },
];

interface WizardStepperProps {
  currentStep: number; // 0-indexed
}

export function WizardStepper({ currentStep }: WizardStepperProps) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((step, i) => (
        <div key={step.path} className="flex items-center">
          {/* Step circle */}
          <div
            className={`
              flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium
              ${i < currentStep
                ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                : i === currentStep
                  ? "bg-blue-600 text-white"
                  : "bg-muted text-muted-foreground"
              }
            `}
          >
            {i < currentStep ? "✓" : i + 1}
          </div>
          {/* Step label */}
          <span
            className={`ml-2 text-sm ${
              i === currentStep ? "font-medium" : "text-muted-foreground"
            }`}
          >
            {step.label}
          </span>
          {/* Connector line */}
          {i < STEPS.length - 1 && (
            <div
              className={`mx-3 h-px w-8 ${
                i < currentStep ? "bg-green-400" : "bg-border"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
