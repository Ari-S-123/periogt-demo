"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface EmbeddingViewerProps {
  embedding: number[];
}

export function EmbeddingViewer({ embedding }: EmbeddingViewerProps) {
  const [expanded, setExpanded] = useState(false);

  const preview = embedding.slice(0, 10);
  const text = expanded
    ? `[${embedding.map((v) => v.toFixed(6)).join(", ")}]`
    : `[${preview.map((v) => v.toFixed(6)).join(", ")}${embedding.length > 10 ? ", ..." : ""}]`;

  function handleCopy() {
    navigator.clipboard.writeText(JSON.stringify(embedding));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">
          Embedding ({embedding.length}d)
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Collapse" : "Expand"}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            Copy
          </Button>
        </div>
      </div>
      <pre className="max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs font-mono break-all whitespace-pre-wrap">
        {text}
      </pre>
    </div>
  );
}
