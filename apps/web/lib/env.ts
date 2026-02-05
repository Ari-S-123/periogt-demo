import { z } from "zod/v4";

const serverEnvSchema = z.object({
  MODAL_PERIOGT_URL: z.url(),
  MODAL_KEY: z.string().min(1),
  MODAL_SECRET: z.string().min(1),
});

type ServerEnv = z.infer<typeof serverEnvSchema>;

let _cached: ServerEnv | null = null;

/**
 * Parse and validate server environment variables.
 * Lazily evaluated on first access so `next build` doesn't crash
 * when env vars are missing at build time.
 */
export function getServerEnv(): ServerEnv {
  if (_cached) return _cached;

  const result = serverEnvSchema.safeParse({
    MODAL_PERIOGT_URL: process.env.MODAL_PERIOGT_URL,
    MODAL_KEY: process.env.MODAL_KEY,
    MODAL_SECRET: process.env.MODAL_SECRET,
  });

  if (!result.success) {
    console.error(
      "Missing or invalid server environment variables:",
      result.error.format(),
    );
    throw new Error("Server environment validation failed. Check .env.local");
  }

  _cached = result.data;
  return _cached;
}
