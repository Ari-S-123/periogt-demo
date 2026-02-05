"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { SmilesInput } from "@/components/smiles-input";
import { PropertySelector } from "@/components/property-selector";
import { PredictionResult } from "@/components/prediction-result";
import { api, ApiError } from "@/lib/api";
import type { PropertyInfo, PredictResponse } from "@/lib/schemas";

export default function PredictPage() {
  const [smiles, setSmiles] = useState("");
  const [property, setProperty] = useState("");
  const [returnEmbedding, setReturnEmbedding] = useState(false);
  const [properties, setProperties] = useState<PropertyInfo[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
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

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setResult(null);
      setLoading(true);

      try {
        const res = await api.predict({
          smiles: smiles.trim(),
          property,
          return_embedding: returnEmbedding,
        });
        setResult(res);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail.message);
        } else {
          setError("An unexpected error occurred.");
        }
      } finally {
        setLoading(false);
      }
    },
    [smiles, property, returnEmbedding],
  );

  const canSubmit = smiles.trim().length > 0 && property.length > 0 && !loading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Property Prediction</h1>
        <p className="text-muted-foreground">
          Predict a polymer property from its repeat-unit SMILES using PerioGT.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Input</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <SmilesInput
              value={smiles}
              onChange={setSmiles}
              disabled={loading}
            />
            <PropertySelector
              properties={properties}
              value={property}
              onChange={setProperty}
              disabled={loading}
              loading={propertiesLoading}
            />
            <div className="flex items-center gap-2">
              <input
                id="return-embedding"
                type="checkbox"
                checked={returnEmbedding}
                onChange={(e) => setReturnEmbedding(e.target.checked)}
                disabled={loading}
                className="rounded border-input"
              />
              <Label htmlFor="return-embedding" className="text-sm font-normal">
                Also return graph embedding vector
              </Label>
            </div>
            <Button type="submit" disabled={!canSubmit}>
              {loading ? "Predicting..." : "Predict"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && <PredictionResult result={result} />}
    </div>
  );
}
