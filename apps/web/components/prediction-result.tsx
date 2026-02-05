import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PredictResponse } from "@/lib/schemas";
import { PROPERTY_DISPLAY } from "@/lib/constants";
import { EmbeddingViewer } from "./embedding-viewer";

interface PredictionResultProps {
  result: PredictResponse;
}

export function PredictionResult({ result }: PredictionResultProps) {
  const display = PROPERTY_DISPLAY[result.property];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Prediction Result</CardTitle>
          <Badge variant="secondary">{result.model.name}</Badge>
        </div>
        <CardDescription className="font-mono text-xs break-all">
          {result.smiles}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground">
            {display?.label ?? result.property}
          </p>
          <p className="text-3xl font-bold tabular-nums">
            {result.prediction.value.toFixed(4)}
            {result.prediction.units && (
              <span className="ml-2 text-base font-normal text-muted-foreground">
                {result.prediction.units}
              </span>
            )}
          </p>
        </div>
        {result.embedding && <EmbeddingViewer embedding={result.embedding} />}
        <p className="text-xs text-muted-foreground">
          Request ID: {result.request_id}
        </p>
      </CardContent>
    </Card>
  );
}
