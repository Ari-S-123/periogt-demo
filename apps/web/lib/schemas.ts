import { z } from "zod/v4";

// --- Request schemas ---

export const smilesSchema = z
  .string()
  .transform((s) => s.trim())
  .pipe(
    z
      .string()
      .min(1, "SMILES is required")
      .max(2000, "SMILES too long (max 2000 characters)")
      .refine((s) => s.includes("*"), {
        message: "Polymer SMILES must include '*' connection points",
      }),
  );

export const predictRequestSchema = z.object({
  smiles: smilesSchema,
  property: z.string().min(1, "Property is required"),
  return_embedding: z.boolean().default(false),
});

export const embeddingRequestSchema = z.object({
  smiles: smilesSchema,
});

export const batchPredictRequestSchema = z.object({
  items: z
    .array(predictRequestSchema)
    .min(1, "At least one item required")
    .max(100, "Maximum 100 items per batch"),
});

// --- Response schemas ---

export const predictionValueSchema = z.object({
  value: z.number(),
  units: z.string(),
});

export const modelInfoSchema = z.object({
  name: z.string(),
  checkpoint: z.string(),
});

export const predictResponseSchema = z.object({
  smiles: z.string(),
  property: z.string(),
  prediction: predictionValueSchema,
  embedding: z.array(z.number()).nullable().optional(),
  model: modelInfoSchema,
  request_id: z.string(),
});

export const embeddingResponseSchema = z.object({
  smiles: z.string(),
  embedding: z.array(z.number()),
  dim: z.number(),
  request_id: z.string(),
});

export const errorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.unknown().optional(),
});

export const batchPredictResponseSchema = z.object({
  results: z.array(z.union([predictResponseSchema, errorDetailSchema])),
  request_id: z.string(),
});

export const propertyInfoSchema = z.object({
  id: z.string(),
  label: z.string(),
  units: z.string(),
});

export const propertiesResponseSchema = z.object({
  properties: z.array(propertyInfoSchema),
});

export const healthResponseSchema = z.object({
  status: z.string(),
  model_loaded: z.boolean(),
  checkpoints_present: z.boolean(),
  gpu_available: z.boolean(),
});

// --- Inferred types ---

export type PredictRequest = z.infer<typeof predictRequestSchema>;
export type PredictResponse = z.infer<typeof predictResponseSchema>;
export type EmbeddingRequest = z.infer<typeof embeddingRequestSchema>;
export type EmbeddingResponse = z.infer<typeof embeddingResponseSchema>;
export type BatchPredictRequest = z.infer<typeof batchPredictRequestSchema>;
export type BatchPredictResponse = z.infer<typeof batchPredictResponseSchema>;
export type PropertyInfo = z.infer<typeof propertyInfoSchema>;
export type PropertiesResponse = z.infer<typeof propertiesResponseSchema>;
export type HealthResponse = z.infer<typeof healthResponseSchema>;
export type ErrorDetail = z.infer<typeof errorDetailSchema>;
