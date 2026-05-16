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
import { ChevronRight, ChevronDown, ChevronUp, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { SdmxMetadataViewer } from "@/components/SdmxMetadataViewer";
import type { UploadResponse, SdmxMetadata } from "@/types";

interface UploadPageProps {
  onUploadComplete: (response: UploadResponse) => void;
}

type DatasetType = "normal" | "sdmx";

export function UploadPage({ onUploadComplete }: UploadPageProps) {
  const navigate = useNavigate();
  const [inputFile, setInputFile] = useState<File | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [sdmxXmlFile, setSdmxXmlFile] = useState<File | null>(null);
  const [datasetType, setDatasetType] = useState<DatasetType>("normal");
  const [datasetName, setDatasetName] = useState("");
  const [preview, setPreview] = useState<UploadResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMetadata, setShowMetadata] = useState(false);
  const [sdmxMetadataJson, setSdmxMetadataJson] = useState<SdmxMetadata | null>(null);
  // After a successful SDMX upload the page stays visible so the user can
  // inspect the extracted JSON; the second click on "Continue" navigates.
  const [uploadedResponse, setUploadedResponse] = useState<UploadResponse | null>(null);

  const validateDatasetName = (name: string): string | null => {
    const trimmed = name.trim();
    if (!trimmed) return null; // empty = no validation shown yet
    if (trimmed.length < 2) return "Must be at least 2 characters";
    if (trimmed.length > 100) return "Must be 100 characters or fewer";
    if (/^[.\-_]/.test(trimmed)) return "Cannot start with a dot, dash, or underscore";
    if (/[/\\]/.test(trimmed)) return "Cannot contain slashes";
    if (/\.\./.test(trimmed)) return "Cannot contain '..'";
    if (/[<>:"|?*\x00-\x1F]/.test(trimmed)) return "Contains invalid characters";
    if (/\s/.test(trimmed)) return "Use underscores instead of spaces";
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(trimmed))
      return "Only letters, numbers, underscores, hyphens, and dots allowed";
    return null; // valid
  };

  const nameError = datasetName ? validateDatasetName(datasetName) : null;
  const isNameValid = datasetName.trim().length >= 2 && nameError === null;

  const handleInputSelect = (file: File) => {
    setInputFile(file);
    setError(null);
    setPreview(null);
    const name = file.name
      .replace(/\.csv$/i, "")
      .replace(/\s+/g, "_")
      .replace(/[<>:"/\\|?*]/g, "_")
      .replace(/^[.\-_]+/, "");
    if (!datasetName) setDatasetName(name);

    // Client-side preview only — no server upload yet.
    // This avoids creating an orphaned run when the user changes the dataset name.
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (!text) return;
      const lines = text.split("\n").filter((l) => l.trim());
      const headers = lines[0]?.split(",").map((h) => h.trim().replace(/^"|"$/g, "")) ?? [];
      const previewRows = lines.slice(1, 11).map((line) => {
        const vals = line.split(",");
        const row: Record<string, string> = {};
        headers.forEach((h, i) => (row[h] = (vals[i] ?? "").trim().replace(/^"|"$/g, "")));
        return row;
      });
      setPreview({
        run_id: "",
        dataset_name: name,
        run_dir: "",
        input_path: "",
        metadata_path: null,
        rows: lines.length - 1,
        columns: headers.length,
        column_names: headers,
        preview: previewRows,
      });
    };
    reader.readAsText(file);
  };

  const sdmxReady = datasetType !== "sdmx" || sdmxXmlFile !== null;

  // If an SDMX upload already completed, the second click just navigates.
  const handleNext = async () => {
    if (uploading) return;

    if (uploadedResponse) {
      // Already uploaded — proceed to configure.
      navigate("/configure");
      return;
    }

    if (!inputFile) return;
    if (datasetType === "sdmx" && !sdmxXmlFile) {
      setError("SDMX datasets require an XML metadata file.");
      return;
    }
    const finalName = datasetName.trim() || inputFile.name.replace(".csv", "").replace(/\s+/g, "_");

    try {
      setUploading(true);
      setError(null);
      const response = await uploadFiles(inputFile, {
        metadataCsv: metadataFile ?? undefined,
        sdmxMetadataXml: sdmxXmlFile ?? undefined,
        datasetName: finalName,
        sdmxMode: datasetType === "sdmx",
      });
      onUploadComplete(response);

      if (response.sdmx_metadata_json) {
        // SDMX run: stay on page so user can review the extracted metadata.
        setSdmxMetadataJson(response.sdmx_metadata_json);
        setUploadedResponse(response);
        toast.success("Upload complete — review the SDMX metadata below, then continue.");
      } else {
        navigate("/configure");
      }
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
              <Label className="mb-2 block font-medium">Dataset Type</Label>
              <div
                role="radiogroup"
                aria-label="Dataset type"
                className="inline-flex rounded-md border bg-muted/40 p-1"
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={datasetType === "normal"}
                  onClick={() => setDatasetType("normal")}
                  className={`px-4 py-1.5 text-sm rounded-sm transition-colors ${
                    datasetType === "normal"
                      ? "bg-background shadow-sm font-medium"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Normal CSV
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={datasetType === "sdmx"}
                  onClick={() => setDatasetType("sdmx")}
                  className={`px-4 py-1.5 text-sm rounded-sm transition-colors ${
                    datasetType === "sdmx"
                      ? "bg-background shadow-sm font-medium"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  SDMX
                </button>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                {datasetType === "sdmx"
                  ? "An SDMX DSD (XML) will be extracted and fed into the LLM as authoritative context."
                  : "Structure and units are inferred from the CSV + an optional metadata CSV."}
              </p>
            </div>

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

            {datasetType === "sdmx" && (
              <div>
                <Label className="mb-2 block font-medium">
                  SDMX Metadata XML <span className="text-destructive">*</span>
                </Label>
                <FileUploader
                  label="SDMX structure XML (DSD + codelists)"
                  accept=".xml"
                  required
                  onFileSelect={setSdmxXmlFile}
                  selectedFile={sdmxXmlFile}
                />
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Download from your SDMX endpoint with{" "}
                  <code className="font-mono text-[11px]">references=all</code>.
                </p>
              </div>
            )}

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
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                      <span className="text-xs text-red-600">{nameError}</span>
                    </div>
                  )
                )}
              </div>
            </div>

            {datasetType !== "sdmx" && (
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
            )}

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

      {sdmxMetadataJson && (
        <div className="mt-4">
          <SdmxMetadataViewer metadata={sdmxMetadataJson} defaultExpanded />
        </div>
      )}

      <div className="flex justify-end mt-6">
        <Button
          onClick={handleNext}
          disabled={(!preview && !uploadedResponse) || uploading || !isNameValid || !sdmxReady}
          size="lg"
          className="gap-2"
        >
          {uploading
            ? "Uploading..."
            : uploadedResponse
              ? "Continue to Configure"
              : "Upload & Continue"}
          {!uploading && <ChevronRight className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
