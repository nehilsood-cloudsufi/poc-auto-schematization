/**
 * ZIP download button for pipeline outputs.
 */
import { Button } from "@/components/ui/button";
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
    <Button variant="outline" onClick={handleDownload}>
      Download ZIP
    </Button>
  );
}
