# PerioGT Web Frontend

Next.js 16 App Router frontend and backend-for-frontend (BFF) proxy for PerioGT inference.

## Stack

- Next.js `16.1.6` (App Router + Turbopack)
- React `19.2.3`, TypeScript `5`
- shadcn/ui primitives + Tailwind CSS v4
- `react-hook-form` + `zod/v4` for validation
- PapaParse for CSV batch input handling

## App Routes

| Route    | Description                                                       |
| -------- | ----------------------------------------------------------------- |
| `/`      | Single prediction form (`smiles`, `property`, optional embedding) |
| `/batch` | Batch prediction workflow from CSV                                |
| `/about` | Model description and property metadata                           |

## API Routes (BFF)

All route handlers are `dynamic = "force-dynamic"` and proxy to Modal via `lib/modal-proxy.ts`.
Each handler generates a request id, validates request payloads with Zod, and forwards `x-request-id` downstream.

| Route             | Method | Validation                                  | Upstream            |
| ----------------- | ------ | ------------------------------------------- | ------------------- |
| `/api/predict`    | POST   | `predictRequestSchema`                      | `/v1/predict`       |
| `/api/batch`      | POST   | `batchPredictRequestSchema` (max 100 items) | `/v1/predict/batch` |
| `/api/embeddings` | POST   | `embeddingRequestSchema`                    | `/v1/embeddings`    |
| `/api/properties` | GET    | None                                        | `/v1/properties`    |
| `/api/health`     | GET    | None                                        | `/v1/health`        |

Proxy error behavior:

- Timeout returns HTTP `504` (`timeout` error code).
- Backend/network failures return HTTP `502` (`proxy_error` or `backend_error`).

## Required Environment

Defined in `apps/web/lib/env.ts` and loaded server-side:

```dotenv
MODAL_PERIOGT_URL=...
MODAL_KEY=...
MODAL_SECRET=...
```

## Development

```bash
# from repo root
bun dev
bun build
bun lint
bun format
```
