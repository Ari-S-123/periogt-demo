"use client";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type {
  BatchPredictResponse,
  PredictResponse,
  ErrorDetail,
} from "@/lib/schemas";

interface BatchResultsTableProps {
  response: BatchPredictResponse;
}

function isError(item: PredictResponse | ErrorDetail): item is ErrorDetail {
  return "code" in item && "message" in item && !("prediction" in item);
}

export function BatchResultsTable({ response }: BatchResultsTableProps) {
  const results = response.results;

  function handleDownloadCSV() {
    const header = "smiles,property,value,units,status\n";
    const rows = results
      .map((r) => {
        if (isError(r)) {
          const details = r.details as
            | { smiles?: string; property?: string }
            | undefined;
          return `"${details?.smiles ?? ""}","${details?.property ?? ""}","","","error: ${r.message}"`;
        }
        return `"${r.smiles}","${r.property}","${r.prediction.value}","${r.prediction.units}","ok"`;
      })
      .join("\n");

    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "periogt_batch_results.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const errCount = results.reduce((n, r) => n + (isError(r) ? 1 : 0), 0);
  const okCount = results.length - errCount;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{okCount} success</Badge>
          {errCount > 0 && (
            <Badge variant="destructive">{errCount} errors</Badge>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={handleDownloadCSV}>
          Download CSV
        </Button>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>SMILES</TableHead>
              <TableHead>Property</TableHead>
              <TableHead className="text-right">Value</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((r, i) => {
              if (isError(r)) {
                const details = r.details as
                  | { smiles?: string; property?: string }
                  | undefined;
                return (
                  <TableRow key={i}>
                    <TableCell className="text-muted-foreground">
                      {i + 1}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-48 truncate">
                      {details?.smiles ?? "—"}
                    </TableCell>
                    <TableCell>{details?.property ?? "—"}</TableCell>
                    <TableCell className="text-right">—</TableCell>
                    <TableCell>
                      <Badge variant="destructive">Error</Badge>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {r.message}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              }
              return (
                <TableRow key={i}>
                  <TableCell className="text-muted-foreground">
                    {i + 1}
                  </TableCell>
                  <TableCell className="font-mono text-xs max-w-48 truncate">
                    {r.smiles}
                  </TableCell>
                  <TableCell>{r.property}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.prediction.value.toFixed(4)}
                    {r.prediction.units && (
                      <span className="ml-1 text-muted-foreground">
                        {r.prediction.units}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">OK</Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
