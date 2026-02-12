# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PerioGT Demo is a web prototype that lets chemists submit polymer repeat-unit SMILES and receive property predictions and graph embeddings using PerioGT model weights from Zenodo. It follows a Backend-for-Frontend (BFF) architecture where the browser never talks directly to the GPU backend.

## Repository Structure

Bun monorepo with two main components:

- `apps/web/` — Next.js 16 App Router frontend (TypeScript, React 19, shadcn/ui, Tailwind v4)
- `services/modal-api/` — Modal GPU backend (Python 3.11, FastAPI, PyTorch 2.6 + DGL)

The backend is **not** a Bun workspace — it's a standalone Python project deployed via Modal.

## Commands

```bash
# Frontend development
bun dev              # Start dev server (Turbopack)
bun build            # Production build
bun lint             # ESLint + Prettier check
bun format           # Format all files with Prettier

# These are equivalent (root scripts filter to web workspace)
bun run --filter web dev
bun run --filter web build

# Modal backend
modal serve services/modal-api/periogt_modal_app.py    # Local dev serving
modal deploy services/modal-api/periogt_modal_app.py   # Deploy to Modal

# Smoke tests (requires Modal proxy auth credentials)
bash scripts/smoke_test.sh <MODAL_BASE_URL>
```

## Architecture

### Data Flow

```
Browser → Next.js Route Handler (/api/*) → Modal FastAPI (/v1/*) → PerioGT GPU inference
```

Route handlers in `apps/web/app/api/` validate requests with Zod, inject Modal auth headers (`Modal-Key`, `Modal-Secret`), and proxy to the backend. Secrets never reach the browser.

### Backend (services/modal-api/)

- **Entry point**: `periogt_modal_app.py` — defines the Modal App, image (Debian + CUDA 12.6 torch + DGL), Volume mount, and FastAPI application via `@modal.asgi_app(requires_proxy_auth=True)`
- **Container state**: Module-level `_state` dict populated on first request by `_ensure_ready()`. Loads checkpoints, label stats (mean/std for denormalization), descriptor scaler, and all models.
- **Runtime modules** (`periogt_runtime/`):
  - `checkpoint_manager.py` — Downloads zips from Zenodo, MD5 verification, extraction, builds `index.json` mapping property → checkpoint path
  - `model_loader.py` — Loads `LiGhTPredictor` models (pretrained for embeddings, finetuned per-property for predictions). Uses vendored PerioGT source at `/root/periogt_src/source_code/PerioGT_common`
  - `inference.py` — SMILES → graph → prediction with denormalization (`raw * std + mean`)
  - `preprocessing.py` — SMILES validation (RDKit, exactly 2 `*` atoms), fingerprint/descriptor computation (MACCS+ECFP, Mordred), DGL graph construction
  - `schemas.py` — Pydantic request/response models mirroring frontend Zod schemas

**Key detail**: The ML stack uses **DGL** (Deep Graph Library), **not** PyTorch Geometric. Dependencies include DGL, DGLLife, Mordred, RDKit, and `numpy<2`.

**Volume artifacts** at `/vol/checkpoints`:
- `pretrained_ckpt.zip` / `finetuned_ckpt.zip` — downloaded from Zenodo on first boot
- `index.json` — auto-generated property → checkpoint mapping
- `label_stats.json` — per-property mean/std for denormalization (must be placed manually)
- `descriptor_scaler.pkl` — pre-fitted StandardScaler for Mordred descriptors (must be placed manually)

### Frontend (apps/web/)

- **Schemas**: `lib/schemas.ts` — Zod v4 (`zod/v4` import) request/response schemas, single source of truth for types. `predictRequestSchema` for API validation (has `.default(false)` on `return_embedding`), `predictFormSchema` for react-hook-form (no `.default()` to avoid RHF type mismatch)
- **Proxy layer**: `lib/modal-proxy.ts` — `modalFetch()` adds auth headers and 60s timeout; `proxyResponse()` reads body as text then `JSON.parse()` (avoids double body consumption); `handleProxyError()` normalizes timeouts/network errors
- **Env validation**: `lib/env.ts` — lazy `getServerEnv()` so `next build` works without env vars
- **API client**: `lib/api.ts` — browser-side typed fetch wrappers calling `/api/*` routes
- **Constants**: `lib/constants.ts` — 12 supported property metadata and example SMILES
- **Hooks**: `hooks/use-properties.ts` — shared hook for fetching available properties (used by both predict and batch pages)
- **Forms**: Predict page uses react-hook-form with `zodResolver(predictFormSchema)` + shadcn `Form`/`FormField`/`FormMessage` components for client-side Zod validation with inline errors
- **UI**: shadcn/ui components (Radix UI + Tailwind v4), Sonner toasts, PapaParse for CSV

### API Endpoints

Frontend routes (`/api/*`) proxy 1:1 to Modal routes (`/v1/*`):

| Frontend | Modal | Method |
|----------|-------|--------|
| `/api/predict` | `/v1/predict` | POST |
| `/api/batch` | `/v1/predict/batch` | POST |
| `/api/embeddings` | `/v1/embeddings` | POST |
| `/api/properties` | `/v1/properties` | GET |
| `/api/health` | `/v1/health` | GET |

Batch endpoint accepts JSON (array of predict requests, max 100), not multipart CSV.

## Environment Variables

Stored in `apps/web/.env.local` (git-ignored). See `apps/web/.env.example`:

```
MODAL_PERIOGT_URL=https://your-workspace--periogt-api-periogt-api.modal.run
MODAL_KEY=wk_your_proxy_token_id
MODAL_SECRET=ws_your_proxy_token_secret
# Optional aliases accepted by smoke tests:
# MODAL_TOKEN_ID=wk_your_proxy_token_id
# MODAL_TOKEN_SECRET=ws_your_proxy_token_secret
```

These are **server-only** (no `NEXT_PUBLIC_` prefix).

Proxy auth token requirements:
- Use workspace Proxy Auth tokens (`wk...` / `ws...`) for Modal proxy auth.
- Account API tokens (`ak...` / `as...`) return `401 modal-http: invalid credentials for proxy authorization`.
- Smoke test scripts auto-load `apps/web/.env.local` when shell env vars are unset.

## Conventions

- Zod v4 imported as `zod/v4` (not `zod`)
- Tailwind v4 uses PostCSS config only — no `tailwind.config.ts`
- shadcn/ui components live in `apps/web/components/ui/`
- Client components use `"use client"` directive; pages with interactivity are client components
- Request IDs (UUID v4) generated per request in route handlers, propagated via `x-request-id` header
- API route handlers export `dynamic = "force-dynamic"` to prevent caching proxy responses
- ESLint uses flat config (`eslint.config.mjs`) with `eslint-config-next/core-web-vitals`, `eslint-config-next/typescript`, and `eslint-config-prettier`
- Prettier for code formatting — `bun format` to write, `bun lint` checks both ESLint and Prettier
- Per-page metadata: server components export `metadata` directly; client component pages use a sibling `layout.tsx` with the metadata export
- Python source vendored into Modal image via `add_local_dir`; `sys.path.insert` for imports
