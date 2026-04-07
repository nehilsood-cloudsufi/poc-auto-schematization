/**
 * Drag-and-drop file upload component.
 */
import { useCallback, useRef, useState } from "react";
import { Card } from "@/components/ui/card";

interface FileUploaderProps {
  label: string;
  accept?: string;
  required?: boolean;
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
}

export function FileUploader({
  label,
  accept = ".csv",
  required = false,
  onFileSelect,
  selectedFile,
}: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFileSelect(file);
    },
    [onFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelect(file);
        }}
      />
      <Card
        className={`
          border-2 border-dashed cursor-pointer transition-all text-center
          min-h-[120px] flex items-center justify-center
          ${isDragging
            ? "border-blue-500 bg-blue-50 dark:bg-blue-950 scale-[1.01]"
            : selectedFile
              ? "border-green-400 bg-green-50/50 dark:bg-green-950/30 hover:border-green-500"
              : "border-border hover:border-muted-foreground hover:bg-muted/30"
          }
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        {selectedFile ? (
          <div className="px-4 py-4">
            <div className="text-2xl mb-1">✅</div>
            <p className="font-medium text-sm text-green-700 dark:text-green-300 truncate max-w-[180px]">
              {selectedFile.name}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {(selectedFile.size / 1024).toFixed(1)} KB · click to change
            </p>
          </div>
        ) : (
          <div className="px-4 py-5">
            <div className="text-3xl mb-2">📤</div>
            <p className="text-sm font-medium text-muted-foreground">
              Drop {label} here
            </p>
            <p className="text-xs text-muted-foreground mt-1">or click to browse</p>
            {required && (
              <p className="text-xs text-destructive mt-1 font-medium">Required</p>
            )}
          </div>
        )}
      </Card>
    </>
  );
}
