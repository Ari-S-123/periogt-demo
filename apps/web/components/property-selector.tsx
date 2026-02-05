"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { PropertyInfo } from "@/lib/schemas";

interface PropertySelectorProps {
  properties: PropertyInfo[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function PropertySelector({
  properties,
  value,
  onChange,
  disabled,
  loading,
}: PropertySelectorProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor="property">Target Property</Label>
      <Select value={value} onValueChange={onChange} disabled={disabled || loading}>
        <SelectTrigger id="property" className="w-full">
          <SelectValue placeholder={loading ? "Loading properties..." : "Select a property"} />
        </SelectTrigger>
        <SelectContent>
          {properties.map((prop) => (
            <SelectItem key={prop.id} value={prop.id}>
              {prop.label}
              {prop.units ? ` (${prop.units})` : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
