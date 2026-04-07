/**
 * Drag-and-drop file upload component.
 */
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
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
    <Card
      className={`
        p-6 border-2 border-dashed cursor-pointer transition-colors text-center
        ${isDragging ? "border-blue-500 bg-blue-50 dark:bg-blue-950" : "border-border hover:border-muted-foreground"}
      `}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
    >
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

      {selectedFile ? (
        <div>
          <p className="font-medium">{selectedFile.name}</p>
          <p className="text-sm text-muted-foreground">
            {(selectedFile.size / 1024).toFixed(1)} KB
          </p>
        </div>
      ) : (
        <div>
          <p className="text-muted-foreground">
            Drop {label} here or click to browse
          </p>
          {required && (
            <p className="text-xs text-muted-foreground mt-1">Required</p>
          )}
        </div>
      )}
      {/* Hidden button to prevent Card click propagation issues */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="mt-2 text-xs pointer-events-none"
        tabIndex={-1}
      >
        Browse
      </Button>
    </Card>
  );
}
