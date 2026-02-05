"use client";

import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { EXAMPLE_SMILES } from "@/lib/constants";

interface SmilesInputProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}

export function SmilesInput({ value, onChange, error, disabled }: SmilesInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="smiles">Polymer SMILES</Label>
      <Textarea
        id="smiles"
        placeholder="Enter polymer repeat-unit SMILES with * connection points, e.g. *CC*"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="font-mono text-sm"
        rows={3}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-muted-foreground">Examples:</span>
        {EXAMPLE_SMILES.map((ex) => (
          <button
            key={ex.smiles}
            type="button"
            onClick={() => onChange(ex.smiles)}
            disabled={disabled}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline disabled:opacity-50"
          >
            {ex.name}
          </button>
        ))}
      </div>
    </div>
  );
}
