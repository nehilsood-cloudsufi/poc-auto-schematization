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
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      // Fallback for when clipboard API is blocked (e.g., iframe, permissions)
      const textarea = document.createElement("textarea");
      textarea.value = content;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
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
