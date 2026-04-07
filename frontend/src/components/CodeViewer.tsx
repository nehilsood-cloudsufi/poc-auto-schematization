/**
 * Read-only code/text viewer with copy button.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface CodeViewerProps {
  content: string;
  language?: string;
}

export function CodeViewer({ content }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);

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
        className="absolute top-2 right-2 text-xs"
      >
        {copied ? "Copied" : "Copy"}
      </Button>
      <ScrollArea className="h-[500px]">
        <pre className="p-4 text-xs font-mono whitespace-pre-wrap">{content}</pre>
      </ScrollArea>
    </div>
  );
}
