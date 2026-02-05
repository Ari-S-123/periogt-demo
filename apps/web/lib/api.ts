import type {
  PredictRequest,
  PredictResponse,
  EmbeddingRequest,
  EmbeddingResponse,
  BatchPredictRequest,
  BatchPredictResponse,
  PropertiesResponse,
  HealthResponse,
  ErrorDetail,
} from "./schemas";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: ErrorDetail,
  ) {
    super(detail.message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, {
      code: String(res.status),
      message: body?.error?.message ?? res.statusText,
      details: body?.error?.details,
    });
  }

  return res.json() as Promise<T>;
}

export const api = {
  predict(body: PredictRequest): Promise<PredictResponse> {
    return request<PredictResponse>("/api/predict", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  embedding(body: EmbeddingRequest): Promise<EmbeddingResponse> {
    return request<EmbeddingResponse>("/api/embeddings", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  batchPredict(body: BatchPredictRequest): Promise<BatchPredictResponse> {
    return request<BatchPredictResponse>("/api/batch", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  properties(): Promise<PropertiesResponse> {
    return request<PropertiesResponse>("/api/properties");
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/api/health");
  },
};

export { ApiError };
