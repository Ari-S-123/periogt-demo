"use client";

import { useCallback, useRef, useState } from "react";
import Papa from "papaparse";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MAX_BATCH_SIZE } from "@/lib/constants";

interface BatchRow {
  smiles: string;
}

interface BatchUploaderProps {
  onParsed: (rows: BatchRow[]) => void;
  disabled?: boolean;
}

export function BatchUploader({ onParsed, disabled }: BatchUploaderProps) {
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      setFileName(file.name);

      Papa.parse<Record<string, string>>(file, {
        header: true,
        skipEmptyLines: true,
        complete(results) {
          const smilesCol = results.meta.fields?.find(
            (f) => f.toLowerCase() === "smiles",
          );

          if (!smilesCol) {
            setError("CSV must have a 'smiles' column header.");
            return;
          }

          const rows = results.data
            .map((row) => ({ smiles: row[smilesCol]?.trim() }))
            .filter((row) => row.smiles && row.smiles.length > 0);

          if (rows.length === 0) {
            setError("No valid SMILES found in the CSV.");
            return;
          }

          if (rows.length > MAX_BATCH_SIZE) {
            setError(
              `Too many rows (${rows.length}). Maximum is ${MAX_BATCH_SIZE}.`,
            );
            return;
          }

          onParsed(rows);
        },
        error(err) {
          setError(`Failed to parse CSV: ${err.message}`);
        },
      });
    },
    [onParsed],
  );

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-2">
      <Card
        className={`border-dashed ${disabled ? "opacity-50" : "cursor-pointer hover:border-foreground/30"}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={disabled ? undefined : handleDrop}
        onClick={disabled ? undefined : () => fileRef.current?.click()}
      >
        <CardContent className="flex flex-col items-center justify-center py-8 text-center">
          <p className="text-sm text-muted-foreground">
            {fileName
              ? `Loaded: ${fileName}`
              : "Drop a CSV file here, or click to browse"}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            CSV must have a &quot;smiles&quot; column (max {MAX_BATCH_SIZE} rows)
          </p>
        </CardContent>
      </Card>
      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      {fileName && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setError(null);
            setFileName(null);
            onParsed([]);
            if (fileRef.current) fileRef.current.value = "";
          }}
          disabled={disabled}
        >
          Clear
        </Button>
      )}
    </div>
  );
}
