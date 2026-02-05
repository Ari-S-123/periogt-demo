# PerioGT Web Prototype PRD (Improved) — Property Prediction API + UI
**Version:** 1.2
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
- Treating PyTorch + graph library installation as "`pip install torch`", which is frequently wrong on GPU due to wheel variants and compiled extension wheels.

This version fixes those decisions and tightens versions, security controls, and deployment patterns.

> **Note (v1.2):** The implementation uses **DGL** (Deep Graph Library) rather than PyTorch Geometric, matching PerioGT's actual upstream dependencies. References to PyG in the original PRD have been corrected.

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

> **Important:** exact patches should be pinned by lockfiles (`bun.lock`) in the implementation repo. This PRD pins **known-good baselines** and constrains majors/minors to avoid breakage.

### 5.1 Frontend

- **Package manager:** Bun (monorepo workspaces)
- **Next.js:** 16.1.6 (App Router, Turbopack dev server)
- **React:** 19.2.3
- **TypeScript:** >= 5
- **UI:** shadcn/ui (Radix UI + Tailwind v4, PostCSS — no `tailwind.config.ts`)
- **Validation:** zod v4 (imported as `zod/v4`)
- **Forms:** react-hook-form
- **CSV:** papaparse (client-side parsing only; results exported client-side)

### 5.2 Backend (Modal)

- **Python:** 3.11.x (wide ecosystem support for torch + scientific libs)
- **modal:** 1.3.2
- **fastapi:** 0.128.0 (with `[standard]` extras)
- **pydantic:** >= 2.8,<3
- **PyTorch:** 2.6.0 (CUDA 12.6 wheels from `https://download.pytorch.org/whl/cu126`)
- **DGL:** Deep Graph Library (CUDA 12.6 build from `https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html`)
- **DGLLife:** molecular featurizers
- **Mordred:** molecular descriptor calculator
- **RDKit:** installed from PyPI
- **numpy:** < 2 (compatibility constraint)
- **Other scientific:** scipy, scikit-learn, pandas, networkx, pyyaml

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

### 6.3 Runtime mapping of "property → checkpoint"

The finetuned zip's internal structure is scanned on first boot by `checkpoint_manager.py`, which generates `/vol/checkpoints/index.json`:

```json
{
  "eps": {
    "checkpoint": "/vol/checkpoints/finetuned_ckpt/eps/best_model.pth",
    "label": "Dielectric constant (ε)",
    "units": ""
  },
  "tg": {
    "checkpoint": "/vol/checkpoints/finetuned_ckpt/tg/best_model.pth",
    "label": "Glass transition temperature (Tg)",
    "units": "K"
  }
}
```

The scan looks for `best_model*.pth` files within property-named subdirectories under `finetuned_ckpt/`. Property metadata (labels, units) is defined in `PROPERTY_METADATA` within `checkpoint_manager.py`.

### 6.4 Additional Volume artifacts

Beyond checkpoints, two additional files must be placed on the Volume for production accuracy:

- **`/vol/checkpoints/label_stats.json`** — Per-property mean and std used for denormalization: `{"eps": {"mean": ..., "std": ...}, ...}`. Without this, predictions are raw normalized model outputs.
- **`/vol/checkpoints/descriptor_scaler.pkl`** — Pre-fitted `sklearn.preprocessing.StandardScaler` for Mordred molecular descriptor normalization. Without this, a scaler is fitted from scratch per request (less accurate).

> This avoids hardcoding guessed filenames and keeps the deployment faithful to the released artifact structure.

---

## 7. Backend implementation details (Modal + FastAPI)

### 7.1 Modal application shape

- One Modal `App` (`"periogt-api"`)
- One GPU-backed function `periogt_api()` decorated with `@modal.asgi_app(requires_proxy_auth=True)` that returns a FastAPI application
- Module-level `_state` dict holding loaded models, scaler, label stats, and property index
- `_ensure_ready()` bootstraps all state on first request (checkpoints, models, label stats, scaler)
- `@modal.concurrent(max_inputs=4)` for per-container concurrency
- L4 GPU, `keep_warm=1`, 300s timeout

### 7.2 Torch + DGL installation (GPU correctness)

PerioGT uses **DGL** (Deep Graph Library), not PyTorch Geometric. The correct install pattern in the Modal image is:

1. Install **GPU-enabled torch** from the official CUDA wheel index:
   `.pip_install("torch==2.6.0", index_url="https://download.pytorch.org/whl/cu126")`
2. Install DGL using CUDA-matched wheels:
   `.pip_install("dgl", find_links="https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html")`
3. Install scientific stack including `dgllife`, `mordred`, `rdkit`, `networkx`, `scipy`, `scikit-learn`, `pandas`, `pyyaml`, and `numpy<2`.
4. System packages: `libgl1-mesa-glx`, `libglib2.0-0` (for OpenCV/RDKit rendering deps).

The vendored PerioGT source and runtime are added to the image via `add_local_dir`.

### 7.3 RDKit installation

Install RDKit via pip (PyPI wheels). Ensure system packages include the common runtime libs (`libstdc++`, `libgl1`, etc.) if needed.

### 7.4 Concurrency and cold-start behavior

- Use `@modal.concurrent(max_inputs=4)` to control per-container concurrency.
- Use `keep_warm=1` to keep 1 container hot for interactive usage.
- Batch endpoint (`/v1/predict/batch`) processes items synchronously in a loop within a single request, returning a JSON response with mixed success/error results. No async job queue or streaming.

### 7.5 Auth between Next.js and Modal

Use Modal's built-in proxy auth:
- set `requires_proxy_auth=True` on `@modal.asgi_app`,
- send `Modal-Key` and `Modal-Secret` headers from the Next.js server route handler via `modalFetch()` in `lib/modal-proxy.ts`.
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
**Body**
```json
{
  "items": [
    { "smiles": "*CC*", "property": "tg", "return_embedding": false },
    { "smiles": "*CC(=O)O*", "property": "eps" }
  ]
}
```
Accepts a JSON list of predict requests (max 100 items). Returns a synchronous JSON response with mixed results:
```json
{
  "results": [
    { "smiles": "...", "property": "...", "prediction": {...}, "model": {...}, "request_id": "..." },
    { "code": "validation_error", "message": "...", "details": {...} }
  ],
  "request_id": "..."
}
```
Each item is either a `PredictResponse` (success) or `ErrorDetail` (failure). No CSV upload or job queue.

---

## 9. Input validation rules (critical for chemists)

### 9.1 SMILES format (polymer repeat unit)

- Must be valid SMILES under RDKit parsing.
- Must include exactly 2 polymer connection points using `*` (enforced server-side via atom count check).
- Enforce max length (2,000 chars).

### 9.2 Property validation

- `property` must be one of the IDs returned by `/v1/properties`.
- If unsupported, return 422 with a ValueError message listing supported properties.

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
  - `POST /api/embeddings`
  - `GET /api/properties`
  - `GET /api/health`

- Next route handler → Modal (via `modalFetch()` in `lib/modal-proxy.ts`):
  - Adds `Modal-Key` and `Modal-Secret` headers, 60s timeout

**Never** call Modal from the browser.

### 10.4 Next.js API routes (App Router)

Implement as route handlers:

- `app/api/predict/route.ts`
- `app/api/batch/route.ts`
- `app/api/embeddings/route.ts`
- `app/api/properties/route.ts`
- `app/api/health/route.ts`

These handlers:
- validate input with zod (via schemas in `lib/schemas.ts`),
- forward to Modal using `modalFetch()` from `lib/modal-proxy.ts`,
- normalize errors via `proxyResponse()` and `handleProxyError()` for consistent UI rendering.

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
- DGL (Deep Graph Library): https://www.dgl.ai/
- DGL installation: https://www.dgl.ai/pages/start.html
- RDKit install (PyPI wheels): https://www.rdkit.org/docs/Install.html


---

## Appendix A — Recommended repository layout (implementation)

### A.1 Monorepo layout (actual)

```
periogt-demo/
  apps/
    web/                        # Next.js 16 App Router UI (Bun workspace)
      app/
        api/
          predict/route.ts      # BFF -> Modal via modalFetch()
          batch/route.ts
          embeddings/route.ts
          properties/route.ts
          health/route.ts
        page.tsx                # Single prediction (home) — react-hook-form + zodResolver
        batch/
          page.tsx              # Batch prediction (CSV upload)
          layout.tsx            # Metadata export (page is a client component)
          loading.tsx           # Spinner loading state
        about/page.tsx          # Static info page (server component, exports metadata)
        layout.tsx
        error.tsx
        loading.tsx             # Spinner loading state
        not-found.tsx           # Custom 404 page
      components/
        smiles-input.tsx
        prediction-result.tsx
        batch-uploader.tsx      # Keyboard-accessible drop zone
        batch-results-table.tsx
        embedding-viewer.tsx
        property-selector.tsx
        site-header.tsx
        ui/                     # shadcn/ui generated components (incl. form, checkbox)
      hooks/
        use-properties.ts       # Shared hook for fetching property list
      lib/
        api.ts                  # typed fetch wrappers (no axios)
        modal-proxy.ts          # modalFetch(), proxyResponse(), handleProxyError()
        env.ts                  # lazy env parsing (zod/v4)
        schemas.ts              # shared zod schemas + predictFormSchema for RHF
        constants.ts            # property metadata, example SMILES
        utils.ts                # cn() utility
      package.json
      next.config.ts
      eslint.config.mjs         # ESLint flat config (core-web-vitals + typescript + prettier)
      postcss.config.mjs        # Tailwind v4 (no tailwind.config.ts)
      components.json
  services/
    modal-api/
      periogt_modal_app.py      # Modal app entry + FastAPI
      periogt_runtime/          # inference, preprocessing, schemas, model_loader, checkpoint_manager
      periogt_src/              # vendored PerioGT source code
      requirements.txt
  scripts/
    smoke_test.sh
  package.json                  # Bun monorepo root
  bun.lock
```

### A.2 Why not “backend inside Next.js”

PerioGT requires GPU + heavy scientific deps. Keeping inference on Modal avoids:
- Vercel runtime limits,
- huge cold-start bundle sizes,
- multi-GB model artifacts inside a serverless runtime.

---

## Appendix B — Concrete frontend implementation patterns (no Axios)

### B.1 Environment parsing (server-only secrets)

Create a single source-of-truth env parser. Uses **lazy evaluation** so `next build` works without env vars — validation happens on first server request, not at import time.

`apps/web/lib/env.ts`
```ts
import { z } from "zod/v4";

const serverEnvSchema = z.object({
  MODAL_PERIOGT_URL: z.url(),
  MODAL_KEY: z.string().min(1),
  MODAL_SECRET: z.string().min(1),
});

type ServerEnv = z.infer<typeof serverEnvSchema>;
let _cached: ServerEnv | null = null;

export function getServerEnv(): ServerEnv {
  if (_cached) return _cached;
  const result = serverEnvSchema.safeParse({
    MODAL_PERIOGT_URL: process.env.MODAL_PERIOGT_URL,
    MODAL_KEY: process.env.MODAL_KEY,
    MODAL_SECRET: process.env.MODAL_SECRET,
  });
  if (!result.success) {
    throw new Error("Server environment validation failed. Check .env.local");
  }
  _cached = result.data;
  return _cached;
}
```

### B.2 Shared schemas

`apps/web/lib/schemas.ts` — Uses `zod/v4` import. The SMILES schema applies `.transform(trim).pipe(...)` for whitespace handling. Full schemas cover predict, embedding, batch, properties, health requests and responses, plus error types. TypeScript types are inferred via `z.infer<>`.

Key pattern:
```ts
import { z } from "zod/v4";

export const smilesSchema = z
  .string()
  .transform((s) => s.trim())
  .pipe(
    z.string()
      .min(1, "SMILES is required")
      .max(2000, "SMILES too long (max 2000 characters)")
      .refine((s) => s.includes("*"), {
        message: "Polymer SMILES must include '*' connection points",
      }),
  );
```

### B.3 Server-side proxy route handler (BFF)

Route handlers use the shared `modalFetch()`, `proxyResponse()`, and `handleProxyError()` helpers from `lib/modal-proxy.ts` instead of inline fetch logic. Pattern:

```ts
import { NextResponse } from "next/server";
import { predictRequestSchema } from "@/lib/schemas";
import { modalFetch, proxyResponse, handleProxyError } from "@/lib/modal-proxy";

export async function POST(req: Request): Promise<Response> {
  const requestId = crypto.randomUUID();
  const body = await req.json();
  const parsed = predictRequestSchema.safeParse(body);
  if (!parsed.success) { /* return 400 */ }

  try {
    const res = await modalFetch("/v1/predict", {
      method: "POST",
      body: JSON.stringify(parsed.data),
      headers: { "x-request-id": requestId },
    });
    return proxyResponse(res, requestId);
  } catch (error) {
    return handleProxyError(error, "predict", requestId);
  }
}
```

### B.4 UI form pattern (react-hook-form + shadcn/ui)

The predict page uses react-hook-form with `zodResolver` and shadcn's `Form`/`FormField`/`FormMessage` components for client-side Zod validation with inline error messages. Key pattern:

- `predictFormSchema` (no `.default()`) is used with `zodResolver` to avoid type mismatch between Zod input/output types and RHF generics. `predictRequestSchema` (with `.default(false)` on `return_embedding`) remains the API validation schema.
- `SmilesInput` and `PropertySelector` accept `value`/`onChange` props compatible with RHF's `field` object.
- `form.formState.isSubmitting` replaces manual loading state.
- Properties are loaded via the shared `useProperties()` hook; the default property is set via `form.setValue()` once available.

---

## Appendix C — Operator checklist (Modal)

1. ✅ Confirm Zenodo download URLs and MD5 match what you expect before deploying.
2. ✅ Ensure the Modal Volume is mounted and writable.
3. ✅ Place `label_stats.json` and `descriptor_scaler.pkl` on the Volume at `/vol/checkpoints/` for production-quality predictions.
4. ✅ Ensure GPU type selection matches your latency/cost goals (L4 is the current default).
5. ✅ Run `scripts/smoke_test.sh` against the deployed endpoint before enabling the UI.
6. ✅ Set `requires_proxy_auth=True` on `@modal.asgi_app` so the endpoint cannot be used without auth headers.

