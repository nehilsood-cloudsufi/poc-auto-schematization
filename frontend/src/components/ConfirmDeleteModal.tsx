import { useEffect, useRef } from "react";
import { Button } from "./ui/button";
import { AlertTriangle } from "lucide-react";

interface ConfirmDeleteModalProps {
  datasetName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDeleteModal({
  datasetName,
  onConfirm,
  onCancel,
}: ConfirmDeleteModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus dialog on mount only
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  // Keyboard handler — use ref to avoid re-subscription on prop change
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancelRef.current();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onCancel}
      />
      {/* Dialog */}
      <div ref={dialogRef} tabIndex={-1} className="relative bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4 outline-none">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 p-2 bg-red-100 rounded-full">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <h3 id="delete-dialog-title" className="text-lg font-semibold text-gray-900">
              Delete Run
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Permanently delete{" "}
              <span className="font-medium">{datasetName}</span> and all its
              files? This cannot be undone.
            </p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
