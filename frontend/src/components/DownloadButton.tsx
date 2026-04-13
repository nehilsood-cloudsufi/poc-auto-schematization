/**
 * ZIP download button for pipeline outputs.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Download, Loader2 } from "lucide-react";
import { downloadZip } from "@/lib/api";
import { toast } from "sonner";

interface DownloadButtonProps {
  runId: string;
  datasetName: string;
}

export function DownloadButton({ runId, datasetName }: DownloadButtonProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadZip(runId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${datasetName}_outputs.zip`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 100);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Button variant="outline" onClick={handleDownload} disabled={downloading} className="gap-2">
      {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
      {downloading ? "Downloading..." : "Download ZIP"}
    </Button>
  );
}
