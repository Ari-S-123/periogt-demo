import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PropertyInfo } from "@/lib/schemas";

export function useProperties() {
  const [properties, setProperties] = useState<PropertyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .properties()
      .then((res) => {
        setProperties(res.properties);
      })
      .catch((err) => {
        console.error("Failed to load properties:", err);
        setError("Failed to load available properties from the backend.");
      })
      .finally(() => setLoading(false));
  }, []);

  return { properties, loading, error };
}
