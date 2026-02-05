"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { BatchUploader } from "@/components/batch-uploader";
import { BatchResultsTable } from "@/components/batch-results-table";
import { PropertySelector } from "@/components/property-selector";
import { api, ApiError } from "@/lib/api";
import type { PropertyInfo, BatchPredictResponse } from "@/lib/schemas";

interface BatchRow {
  smiles: string;
}

export default function BatchPage() {
  const [rows, setRows] = useState<BatchRow[]>([]);
  const [property, setProperty] = useState("");
  const [properties, setProperties] = useState<PropertyInfo[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<BatchPredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .properties()
      .then((res) => {
        setProperties(res.properties);
        if (res.properties.length > 0) {
          setProperty(res.properties[0].id);
        }
      })
      .catch((err) => {
        console.error("Failed to load properties:", err);
        setError("Failed to load available properties from the backend.");
      })
      .finally(() => setPropertiesLoading(false));
  }, []);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setResponse(null);
    setLoading(true);

    try {
      const items = rows.map((row) => ({
        smiles: row.smiles,
        property,
        return_embedding: false,
      }));
      const res = await api.batchPredict({ items });
      setResponse(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail.message);
      } else {
        setError("An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }, [rows, property]);

  const canSubmit = rows.length > 0 && property.length > 0 && !loading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Batch Prediction</h1>
        <p className="text-muted-foreground">
          Upload a CSV of polymer SMILES to predict properties in bulk.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload CSV</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <BatchUploader onParsed={setRows} disabled={loading} />
          {rows.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {rows.length} SMILES loaded
            </p>
          )}
          <PropertySelector
            properties={properties}
            value={property}
            onChange={setProperty}
            disabled={loading}
            loading={propertiesLoading}
          />
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {loading
              ? `Processing ${rows.length} items...`
              : `Predict ${rows.length} items`}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {response && <BatchResultsTable response={response} />}
    </div>
  );
}
