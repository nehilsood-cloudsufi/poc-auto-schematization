/**
 * Wizard Step 1: Upload CSV data files.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { FileUploader } from "@/components/FileUploader";
import { DataPreview } from "@/components/DataPreview";
import { uploadFiles } from "@/lib/api";
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

  // When a CSV is selected, upload immediately to get preview
  const handleInputSelect = async (file: File) => {
    setInputFile(file);
    setError(null);

    // Auto-fill dataset name from filename
    const name = file.name.replace(".csv", "").replace(/\s+/g, "_");
    if (!datasetName) setDatasetName(name);

    // Upload to get preview
    try {
      setUploading(true);
      const response = await uploadFiles(file, metadataFile ?? undefined, name || undefined);
      setPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleNext = () => {
    if (preview) {
      onUploadComplete(preview);
      navigate("/configure");
    }
  };

  return (
    <div className="min-h-screen bg-muted/20">
      {/* Hero section */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 text-white px-8 py-10">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-4xl">🤖</span>
            <h1 className="text-3xl font-bold tracking-tight">Agent B</h1>
          </div>
          <p className="text-slate-300 text-lg leading-relaxed max-w-2xl">
            Auto Schematization — Transform your CSV datasets into Data Commons
            StatVarObservations using AI-powered PVMAP generation.
          </p>
          <div className="flex gap-6 mt-5 text-sm text-slate-400">
            <span>✦ Intelligent column mapping</span>
            <span>✦ Schema validation</span>
            <span>✦ Self-correcting retry loop</span>
          </div>
        </div>
      </div>

      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={0} />

        <Card className="mt-6 shadow-sm">
          <CardContent className="pt-6">
            <h2 className="text-xl font-semibold mb-5">Upload Your Data</h2>

            <div className="grid grid-cols-2 gap-6 mb-6">
              <div>
                <Label className="mb-2 block font-medium">Input CSV <span className="text-destructive">*</span></Label>
                <FileUploader
                  label="CSV file"
                  required
                  onFileSelect={handleInputSelect}
                  selectedFile={inputFile}
                />
              </div>
              <div>
                <Label className="mb-2 block font-medium">
                  Metadata CSV <span className="text-muted-foreground text-xs font-normal">(optional)</span>
                </Label>
                <FileUploader
                  label="metadata CSV"
                  onFileSelect={setMetadataFile}
                  selectedFile={metadataFile}
                />
              </div>
            </div>

            {/* Dataset name */}
            <div className="mb-6">
              <Label htmlFor="dataset-name" className="mb-2 block font-medium">
                Dataset Name
              </Label>
              <Input
                id="dataset-name"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder="e.g., census_income_data"
                className="max-w-sm"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="mb-4 p-3 bg-destructive/10 text-destructive rounded-md text-sm border border-destructive/20">
                ⚠ {error}
              </div>
            )}

            {/* Data preview */}
            {preview && (
              <div className="mb-6">
                <Label className="mb-2 block font-medium">Data Preview</Label>
                <DataPreview
                  columns={preview.column_names}
                  rows={preview.preview}
                  totalRows={preview.rows}
                  totalColumns={preview.columns}
                />
              </div>
            )}

            {/* Next button */}
            <div className="flex justify-end">
              <Button
                onClick={handleNext}
                disabled={!preview || uploading}
                size="lg"
              >
                {uploading ? "Uploading..." : "Next: Configure →"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
