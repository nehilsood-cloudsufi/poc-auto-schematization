/**
 * Wizard Step 1: Upload CSV data files.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { FileUploader } from "@/components/FileUploader";
import { DataPreview } from "@/components/DataPreview";
import { uploadFiles } from "@/lib/api";
import { toast } from "sonner";
import { ChevronRight, ChevronDown, ChevronUp, CheckCircle2, AlertTriangle } from "lucide-react";
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
  const [showMetadata, setShowMetadata] = useState(false);

  const isNameValid = datasetName.trim().length >= 2;

  const handleInputSelect = async (file: File) => {
    setInputFile(file);
    setError(null);
    const name = file.name.replace(".csv", "").replace(/\s+/g, "_");
    if (!datasetName) setDatasetName(name);

    try {
      setUploading(true);
      const response = await uploadFiles(file, metadataFile ?? undefined, name || undefined);
      setPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      toast.error("Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  const handleNext = async () => {
    if (!inputFile) return;
    const finalName = datasetName.trim() || inputFile.name.replace(".csv", "").replace(/\s+/g, "_");
    try {
      setUploading(true);
      setError(null);
      const response = await uploadFiles(inputFile, metadataFile ?? undefined, finalName);
      onUploadComplete(response);
      navigate("/configure");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      toast.error("Upload failed — please try again");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={0} />

      <div className="mb-6">
        <h1 className="text-2xl font-bold">Upload Your Data</h1>
        <p className="text-muted-foreground mt-1">
          Start by uploading a CSV file to transform into Data Commons StatVarObservations.
        </p>
      </div>

      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="space-y-6">
            <div>
              <Label className="mb-2 block font-medium">
                Input CSV <span className="text-destructive">*</span>
              </Label>
              <FileUploader
                label="CSV file"
                required
                onFileSelect={handleInputSelect}
                selectedFile={inputFile}
              />
            </div>

            <div>
              <Label htmlFor="dataset-name" className="mb-2 block font-medium">
                Dataset Name
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="dataset-name"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g., census_income_data"
                  className="max-w-sm"
                />
                {datasetName && (
                  isNameValid ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : (
                    <span className="text-xs text-muted-foreground">min 2 characters</span>
                  )
                )}
              </div>
            </div>

            <div>
              <button
                type="button"
                onClick={() => setShowMetadata(!showMetadata)}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                {showMetadata ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                Advanced: Add metadata CSV
                <span className="text-xs">(optional)</span>
              </button>
              {showMetadata && (
                <div className="mt-3">
                  <FileUploader
                    label="metadata CSV"
                    onFileSelect={setMetadataFile}
                    selectedFile={metadataFile}
                  />
                </div>
              )}
            </div>

            {error && (
              <div className="p-3 rounded-md text-sm border bg-destructive/5 text-destructive border-destructive/20 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {preview && (
        <Card className="shadow-sm mt-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Data Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <DataPreview
              columns={preview.column_names}
              rows={preview.preview}
              totalRows={preview.rows}
              totalColumns={preview.columns}
            />
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end mt-6">
        <Button
          onClick={handleNext}
          disabled={!preview || uploading || !isNameValid}
          size="lg"
          className="gap-2"
        >
          {uploading ? "Uploading..." : "Continue to Configure"}
          {!uploading && <ChevronRight className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
