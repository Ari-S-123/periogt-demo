# PerioGT Web Prototype PRD (Improved) — Property Prediction API + UI
**Version:** 1.1  
**Date:** February 04, 2026  
**Author:** Ari (with AI-assisted review)

---

## 1. Executive summary

Build a web-based prototype that lets chemists submit polymer repeat-unit SMILES and receive **(a)** PerioGT embeddings and **(b)** PerioGT **property predictions** using the **original pretrained + finetuned weights** published with the model. The system consists of:

- **Frontend:** Next.js App Router + React, styled with **shadcn/ui** (Tailwind v4) and using **native `fetch`** (no Axios).
- **Backend:** A GPU-backed inference service on **Modal** exposing a small REST API using **FastAPI**.
- **Weights:** Downloaded from **Zenodo** at runtime into a persistent Modal Volume and validated via checksums.

This PRD focuses on correctness, reproducibility, and “works for chemists” UX, while avoiding fragile re-implementations of PerioGT’s preprocessing.

---

## 2. Goals and non-goals

### 2.1 Goals (MVP)

1. **Property prediction** for the finetuned tasks provided by the PerioGT release artifacts (see §6).
2. **Embeddings endpoint** for feature extraction / downstream analysis.
3. Chemist-friendly UI supporting:
   - Single query prediction
   - Batch prediction (CSV upload + download results)
   - Clear error messages when SMILES are invalid or out-of-distribution
4. Deployable without local NVIDIA hardware: inference runs on Modal GPUs.

### 2.2 Non-goals (explicit)

- Training new finetuned models in-app (can be a follow-on milestone).
- Multi-tenant enterprise auth + billing.
- Guaranteeing scientific validity beyond faithfully reproducing the released PerioGT inference pipeline.

---

## 3. Key corrections vs the attached PRD

The attached PRD includes several choices that will either break deployment or violate your stated constraints, including:
- Using **Axios** in the frontend and API client wrappers instead of Next.js-native `fetch`.  
- Defining custom UI components rather than using **shadcn/ui**’s generated component patterns.  
- Using Modal’s deprecated concurrency knobs (`allow_concurrent_inputs`) instead of the newer `@modal.concurrent` approach.  
- Treating PyTorch + PyTorch Geometric installation as “`pip install torch` / `pip install torch-geometric`”, which is frequently wrong on GPU due to wheel variants and compiled extension wheels.

This version fixes those decisions and tightens versions, security controls, and deployment patterns.

---

## 4. System architecture (high level)

### 4.1 Component diagram

**Browser (chemist)**
→ **Next.js app (Vercel)**
→ **Next.js Route Handler (BFF)**
→ **Modal FastAPI endpoint**
→ **PerioGT runtime (GPU)**
→ JSON response
→ UI renders + CSV downloads

### 4.2 Why “BFF” (Backend-for-Frontend) is required

Direct browser calls to Modal complicate:
- protecting secrets / auth headers,
- CORS policy management,
- request throttling and payload limits.

Instead, the browser calls `/api/predict` on Next.js, and the server-side route calls Modal with secrets.

---

## 5. Technology stack (pinned baselines)

> **Important:** exact patches should be pinned by lockfiles (`pnpm-lock.yaml`, `uv.lock`/`requirements.lock`) in the implementation repo. This PRD pins **known-good baselines** and constrains majors/minors to avoid breakage.

### 5.1 Frontend

- **Next.js:** 16.1.6 (App Router)
- **Node.js:** >= 20.9 (align with current Next.js system requirements)
- **React:** >= 19.2.1 (see security note in §11.4)
- **TypeScript:** >= 5.7
- **UI:** shadcn/ui (Tailwind v4)
- **Validation:** zod
- **Forms:** react-hook-form
- **CSV:** papaparse (client parsing) + server-side streaming CSV generation for downloads

### 5.2 Backend (Modal)

- **Python:** 3.11.x (wide ecosystem support for torch + scientific libs)
- **modal:** 1.3.2
- **fastapi:** 0.128.0
- **pydantic:** >= 2.8,<3
- **PyTorch:** 2.6.x (see §7.2, PyG compatibility)
- **PyTorch Geometric:** 2.7.0
- **RDKit:** installed from PyPI (see §7.3)
- **uv** (optional): for fast, reproducible dependency sync in CI

### 5.3 Storage

- **Modal Volume** for checkpoints + model artifacts.
- **Optional (MVP+):** Postgres (Supabase) for prediction history / audit trail.

---

## 6. Model artifacts and checkpoint strategy (Zenodo)

PerioGT publishes official artifacts on Zenodo. These are the files you must support:

- `pretrained_ckpt.zip` (~361.6 MB)  
- `finetuned_ckpt.zip` (~5.9 GB)  

### 6.1 Storage decision

Do **not** bake these artifacts into the Modal image:
- it increases build times dramatically,
- it bloats cold starts,
- it makes updates painful.

Instead:
- create a **Modal Volume** mounted at e.g. `/vol/checkpoints`,
- on first startup, download missing zips, verify checksum, then unzip to stable paths.

### 6.2 Checksum verification requirement

At download time:
1. Download zip to a temp path.
2. Compute MD5.
3. Compare against Zenodo’s published MD5.
4. Only then unzip and “activate” the checkpoint directory.

If checksum fails, delete the file and raise a 500 with a clear operator message.

### 6.3 Runtime mapping of “property → checkpoint”

The finetuned zip’s internal structure must be inspected once, then a mapping file is generated and stored in the Volume, e.g.:

`/vol/checkpoints/finetuned/index.json`:
```json
{
  "eps": "finetuned/light/eps.pth",
  "density": "finetuned/light/density.pth",
  "tg": "finetuned/light/tg.pth"
}
```

The mapping is loaded at runtime to determine which finetuned checkpoint to load for a given requested property.

> This avoids hardcoding guessed filenames and keeps the deployment faithful to the released artifact structure.

---

## 7. Backend implementation details (Modal + FastAPI)

### 7.1 Modal application shape

- One Modal `App`
- One GPU-backed class `PerioGTService` holding:
  - loaded checkpoints
  - loaded PerioGT model objects
  - a prediction method
- One **FastAPI** request handler function decorated with `@modal.fastapi_endpoint(...)` that delegates into the class.

### 7.2 Torch + PyG installation (GPU correctness)

PyTorch Geometric relies on compiled extension wheels (e.g., `torch_scatter`, `torch_sparse`). The correct install pattern is:

1. Install **GPU-enabled torch** from the official CUDA wheel index (choose a CUDA variant supported by Modal’s GPU runtime).
2. Install PyG wheels using the PyG wheel index for the exact `torch` + `cuda` combination.

**Baseline recommendation for reliability:**
- Use torch **2.6.x** + CUDA 12.6 wheels (cu126), because this combination is explicitly supported by the PyG installation docs.
- Freeze the exact torch patch and wheel URL in the implementation lockfile.

### 7.3 RDKit installation

Install RDKit via pip (PyPI wheels). Ensure system packages include the common runtime libs (`libstdc++`, `libgl1`, etc.) if needed.

### 7.4 Concurrency and cold-start behavior

- Use `@modal.concurrent(max_inputs=...)` to control per-container concurrency.
- Use `keep_warm` to keep 1–N containers hot for interactive usage.
- For batch CSV jobs, prefer an async job queue endpoint (`/v1/predict/batch`) and stream results.

### 7.5 Auth between Next.js and Modal

Use Modal’s built-in proxy auth:
- set `requires_proxy_auth=True` on `@modal.fastapi_endpoint`,
- send `Modal-Key` and `Modal-Secret` headers from the Next.js server route handler.
Never expose these headers to the browser.

---

## 8. REST API specification (Modal service)

### 8.1 Conventions

- All endpoints are versioned under `/v1`.
- All errors return JSON with:
  - `error.code`
  - `error.message`
  - `error.details` (optional)
  - `request_id`

### 8.2 Endpoints

#### GET `/v1/health`
Returns readiness:
- model loaded
- checkpoints present
- GPU available (best-effort)

#### GET `/v1/properties`
Returns supported properties based on the finetuned index mapping:
```json
{
  "properties": [
    { "id": "eps", "label": "Dielectric constant (ε)", "units": "" },
    { "id": "tg", "label": "Glass transition temperature (Tg)", "units": "K" }
  ]
}
```

#### POST `/v1/predict`
**Body**
```json
{
  "smiles": "*CC(=O)O*",
  "property": "eps",
  "return_embedding": false
}
```

**Response**
```json
{
  "smiles": "*CC(=O)O*",
  "property": "eps",
  "prediction": {
    "value": 2.73,
    "units": ""
  },
  "model": {
    "name": "PerioGT",
    "checkpoint": "finetuned/light/eps.pth"
  },
  "request_id": "..."
}
```

#### POST `/v1/embeddings`
**Body**
```json
{ "smiles": "*CC(=O)O*" }
```

**Response**
```json
{
  "smiles": "*CC(=O)O*",
  "embedding": [0.12, -0.03, ...],
  "dim": 1024,
  "request_id": "..."
}
```

#### POST `/v1/predict/batch`
Accept CSV upload (multipart) or JSON list. Returns:
- either an immediate CSV file response (if small),
- or a job ID (if large), then poll `/v1/jobs/:id`.

---

## 9. Input validation rules (critical for chemists)

### 9.1 SMILES format (polymer repeat unit)

- Must be valid SMILES under RDKit parsing.
- Must include polymer connection points using `*` in the format expected by PerioGT datasets.
- Enforce max length (e.g., 2,000 chars) and max atom count (to protect service).

### 9.2 Property validation

- `property` must be one of the IDs returned by `/v1/properties`.
- If unsupported, return 400 with `error.code="UNSUPPORTED_PROPERTY"`.

### 9.3 Error taxonomy

- 400: validation errors (bad smiles, unsupported property, payload too large)
- 429: rate limit
- 500: internal errors (checkpoint missing, model load failure, checksum mismatch)

---

## 10. Frontend UX (Next.js + shadcn/ui)

### 10.1 Pages

1. `/` — Single prediction
2. `/batch` — CSV upload and batch prediction
3. `/about` — Model + citation + limitations
4. `/history` (optional) — prior predictions (requires DB)

### 10.2 Core UI components (shadcn/ui)

Use shadcn/ui generated components (do not hand-roll clones):
- `Button`, `Input`, `Textarea`, `Select`, `Card`, `Tabs`, `Table`, `Badge`, `Alert`, `Dialog`
- Use `Form` components with react-hook-form
- Toasts via `sonner` (if you choose the shadcn default toast solution)

### 10.3 Frontend data flow (no Axios)

All network calls use `fetch`:

- Client → Next route handler:
  - `POST /api/predict`
  - `POST /api/batch`
  - `GET /api/properties`

- Next route handler → Modal:
  - `fetch(MODAL_URL, { headers: { "Modal-Key": ..., "Modal-Secret": ... } })`

**Never** call Modal from the browser.

### 10.4 Next.js API routes (App Router)

Implement as route handlers:

- `app/api/properties/route.ts`
- `app/api/predict/route.ts`
- `app/api/batch/route.ts`

These handlers:
- validate input with zod,
- forward to Modal using server-side `fetch`,
- normalize errors for consistent UI rendering.

---

## 11. Security, compliance, and safety

### 11.1 Secrets management

- Vercel: store Modal auth headers as server-only environment variables (no `NEXT_PUBLIC_` prefix).
- Modal: store any Zenodo tokens (if needed) as Modal Secrets.

### 11.2 Rate limiting

At minimum:
- rate-limit Next.js route handlers (IP-based).
- enforce body size limits for batch uploads.

### 11.3 Supply chain

- Use lockfiles.
- Enable Dependabot / Renovate.
- Pin patched versions promptly.

### 11.4 Known React Server Components advisory

There is a published advisory affecting `react-server-dom-turbopack` and related packages used by React/Next.js in certain setups. Mitigation is to run patched React packages (>= 19.2.1) and keep Next.js patched as well.

---

## 12. Observability

### 12.1 Backend

- Structured logs per request:
  - request_id
  - property
  - inference latency (ms)
  - model checkpoint
  - errors

### 12.2 Frontend

- Minimal client analytics (optional):
  - count predictions
  - error rates
  - latency bucket (do not log SMILES by default)

---

## 13. Testing and validation plan

### 13.1 Golden tests (must-have)

Use PerioGT’s own scripts to generate golden outputs for a small set of SMILES + properties and assert:

- API outputs match script outputs within tolerance.
- Embedding dimensionality matches expected.
- Batch mode matches single mode for identical inputs.

### 13.2 Unit tests

- SMILES validation
- Property mapping loading
- Checksum verification
- Route handler input validation (zod)

### 13.3 Integration tests

- Vercel preview deploy calls staging Modal app and performs a real prediction.

---

## 14. Deployment plan

### 14.1 Modal

1. Create Modal app and Volume.
2. Implement checkpoint bootstrap:
   - download + md5 verify + unzip
3. Deploy:
   - `modal deploy`
4. Record the web endpoint URL in an environment variable for Vercel.

### 14.2 Vercel

1. Create Next.js project.
2. Configure environment variables:
   - `MODAL_PERIOGT_URL`
   - `MODAL_KEY`
   - `MODAL_SECRET`
3. Deploy preview → run integration test
4. Promote to production

---

## 15. Milestones (recommended)

### Milestone 0 — Repo readiness (0.5 day)
- Confirm PerioGT code imports and checkpoint paths work in a clean environment.

### Milestone 1 — Modal inference API (2–3 days)
- Health + properties + single predict endpoints
- Checkpoint bootstrap + checksum validation
- Concurrency + keep-warm tuning

### Milestone 2 — Next.js UI (2–3 days)
- Single prediction page
- Batch upload page
- Error handling polish

### Milestone 3 — Hardening (1–2 days)
- Golden tests
- Rate limiting
- Observability improvements

---

## 16. References (source of truth)

- Modal docs: https://modal.com/docs/
- Modal LLM reference: https://modal.com/llms.txt
- Next.js docs (LLM full): https://nextjs.org/docs/llms-full.txt
- shadcn/ui docs (LLM): https://ui.shadcn.com/llms.txt
- shadcn CLI docs: https://v3.shadcn.com/docs/cli
- PerioGT paper + artifacts (Zenodo): https://zenodo.org/records/17035498
- PyTorch: https://pytorch.org/
- PyTorch Geometric installation: https://pytorch-geometric.readthedocs.io/en/stable/install/installation.html
- RDKit install (PyPI wheels): https://www.rdkit.org/docs/Install.html


---

## Appendix A — Recommended repository layout (implementation)

### A.1 Monorepo layout (recommended)

```
periogt-platform/
  apps/
    web/                        # Next.js 16 App Router UI (Vercel)
      app/
        api/
          predict/route.ts      # BFF -> Modal (server-side fetch)
          properties/route.ts
          batch/route.ts
        (pages)/                # Route groups
          page.tsx              # single prediction
          batch/page.tsx
          about/page.tsx
      components/
        smiles-input.tsx
        prediction-result.tsx
        batch-uploader.tsx
        ui/                     # shadcn/ui generated components (lowercase files)
      lib/
        api.ts                  # typed fetch wrappers (no axios)
        env.ts                  # env parsing (zod)
        schemas.ts              # shared zod schemas
      styles/
      package.json
      pnpm-lock.yaml
      next.config.ts
      tailwind.config.ts
      components.json
  services/
    modal-api/
      periogt_modal_app.py      # Modal app entry
      periogt_runtime/          # thin wrapper around PerioGT repo code
      requirements.txt
      README.md                 # operator notes
  scripts/
    smoke_test.sh
```

### A.2 Why not “backend inside Next.js”

PerioGT requires GPU + heavy scientific deps. Keeping inference on Modal avoids:
- Vercel runtime limits,
- huge cold-start bundle sizes,
- multi-GB model artifacts inside a serverless runtime.

---

## Appendix B — Concrete frontend implementation patterns (no Axios)

### B.1 Environment parsing (server-only secrets)

Create a single source-of-truth env parser so missing secrets fail fast.

`apps/web/lib/env.ts`
```ts
import { z } from "zod";

/**
 * Server-only environment variables (do NOT expose to browser).
 * Throw at import time if invalid to fail deployments early.
 */
const serverEnvSchema = z.object({
  MODAL_PERIOGT_URL: z.string().url(),
  MODAL_KEY: z.string().min(1),
  MODAL_SECRET: z.string().min(1),
});

export const serverEnv = serverEnvSchema.parse({
  MODAL_PERIOGT_URL: process.env.MODAL_PERIOGT_URL,
  MODAL_KEY: process.env.MODAL_KEY,
  MODAL_SECRET: process.env.MODAL_SECRET,
});
```

### B.2 Shared schemas

`apps/web/lib/schemas.ts`
```ts
import { z } from "zod";

/** Keep conservative bounds; update only if chemist workflows require more. */
export const smilesSchema = z
  .string()
  .min(1)
  .max(2000)
  .refine((s) => s.includes("*"), "SMILES must include polymer connection points using '*'");

export const propertyIdSchema = z.string().min(1).max(64);

export const predictRequestSchema = z.object({
  smiles: smilesSchema,
  property: propertyIdSchema,
  return_embedding: z.boolean().optional().default(false),
});

export type PredictRequest = z.infer<typeof predictRequestSchema>;

export const predictResponseSchema = z.object({
  smiles: z.string(),
  property: z.string(),
  prediction: z.object({
    value: z.number(),
    units: z.string(),
  }),
  model: z.object({
    name: z.string(),
    checkpoint: z.string(),
  }),
  request_id: z.string(),
});

export type PredictResponse = z.infer<typeof predictResponseSchema>;
```

### B.3 Server-side proxy route handler (BFF)

`apps/web/app/api/predict/route.ts`
```ts
import { NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";
import { predictRequestSchema, predictResponseSchema } from "@/lib/schemas";

/**
 * POST /api/predict
 * Validates input with zod, forwards request to Modal using server-only auth headers,
 * normalizes error formats, and validates response shape.
 */
export async function POST(req: Request): Promise<Response> {
  const requestId = crypto.randomUUID();

  let bodyJson: unknown;
  try {
    bodyJson = await req.json();
  } catch {
    return NextResponse.json(
      { error: { code: "INVALID_JSON", message: "Request body must be valid JSON." }, request_id: requestId },
      { status: 400 },
    );
  }

  const parsed = predictRequestSchema.safeParse(bodyJson);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: { code: "VALIDATION_ERROR", message: "Invalid request body.", details: parsed.error.flatten() },
        request_id: requestId,
      },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  try {
    const upstream = await fetch(`${serverEnv.MODAL_PERIOGT_URL}/v1/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Modal-Key": serverEnv.MODAL_KEY,
        "Modal-Secret": serverEnv.MODAL_SECRET,
      },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
      signal: controller.signal,
    });

    const upstreamText = await upstream.text();
    const upstreamJson = upstreamText ? (JSON.parse(upstreamText) as unknown) : undefined;

    if (!upstream.ok) {
      return NextResponse.json(
        {
          error: {
            code: "UPSTREAM_ERROR",
            message: "Inference service returned an error.",
            details: upstreamJson ?? upstreamText,
          },
          request_id: requestId,
        },
        { status: upstream.status },
      );
    }

    const validated = predictResponseSchema.safeParse(upstreamJson);
    if (!validated.success) {
      return NextResponse.json(
        {
          error: {
            code: "BAD_UPSTREAM_SHAPE",
            message: "Inference service returned an unexpected response shape.",
            details: validated.error.flatten(),
          },
          request_id: requestId,
        },
        { status: 502 },
      );
    }

    // Attach our request_id for frontend correlation (keep upstream request_id too).
    return NextResponse.json({ ...validated.data, request_id: requestId }, { status: 200 });
  } catch (err: unknown) {
    const message =
      err instanceof DOMException && err.name === "AbortError"
        ? "Inference request timed out."
        : err instanceof Error
          ? err.message
          : "Unknown error.";

    return NextResponse.json(
      { error: { code: "NETWORK_ERROR", message }, request_id: requestId },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }
}
```

### B.4 UI form pattern (react-hook-form + shadcn/ui)

Use shadcn/ui’s `Form` primitives and RHF for validated submission.

---

## Appendix C — Operator checklist (Modal)

1. ✅ Confirm Zenodo download URLs and MD5 match what you expect before deploying.
2. ✅ Ensure the Modal Volume is mounted and writable.
3. ✅ Ensure GPU type selection matches your latency/cost goals (L4 is usually a good default).
4. ✅ Run `scripts/smoke_test.sh` against the deployed endpoint before enabling the UI.
5. ✅ Set `requires_proxy_auth=True` so the endpoint cannot be used without auth headers.

