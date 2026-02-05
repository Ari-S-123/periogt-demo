# PerioGT Demo — Implementation Progress

## Status: Milestones 0–2 Complete, Milestone 3 In Progress

---

## Completed

### Milestone 0.1: Monorepo Scaffolding (Complete)

- [x] Created root `package.json` with bun workspaces config (`apps/*`)
- [x] Scaffolded Next.js 16.1.6 in `apps/web/` via `bunx create-next-app@latest`
  - TypeScript, App Router, Tailwind v4, Turbopack, React 19.2.3
- [x] `bun install` working (user fixed Windows segfault issue)
- [x] shadcn/ui initialized (`components.json`, OKLCH theme in `globals.css`)
- [x] Installed shadcn/ui components: button, input, textarea, select, card, tabs, table, badge, alert, dialog, form, sonner, label
- [x] Installed additional deps: zod v4, react-hook-form, @hookform/resolvers, papaparse, lucide-react, sonner, next-themes, clsx, tailwind-merge, tw-animate-css, class-variance-authority
- [x] Created `services/modal-api/` directory structure
- [x] Created `.env.example` with Modal credentials template
- [x] Updated `.gitignore` with Python entries

### Milestone 0.2: PerioGT Source Code Inspection (Complete)

- [x] Downloaded and verified `source_code.zip` from Zenodo
- [x] Full code inspection — DGL (not PyG), two-stage inference, mordred descriptors

### Milestone 1: Modal Inference API Backend (Complete)

All backend files created and reviewed:

- [x] `services/modal-api/periogt_modal_app.py` — Modal App + FastAPI with 5 routes
  - `/v1/health`, `/v1/properties`, `/v1/predict`, `/v1/embeddings`, `/v1/predict/batch`
  - L4 GPU, `requires_proxy_auth=True`, `keep_warm=1`, `@modal.concurrent(max_inputs=4)`
  - Lazy label stats + scaler loading from Volume
- [x] `services/modal-api/periogt_runtime/schemas.py` — Pydantic request/response models
- [x] `services/modal-api/periogt_runtime/checkpoint_manager.py` — Zenodo download + MD5 verify + Volume handling
- [x] `services/modal-api/periogt_runtime/model_loader.py` — Two-stage model loading (pretrained + finetuned)
- [x] `services/modal-api/periogt_runtime/inference.py` — SMILES → prediction/embedding
- [x] `services/modal-api/periogt_runtime/preprocessing.py` — SMILES → DGL graph conversion

### Milestone 2: Next.js Frontend (Complete)

All frontend files created, TypeScript compilation passes, `next build` succeeds.

**Library files:**
- [x] `apps/web/lib/env.ts` — Lazy server env validation (zod v4)
- [x] `apps/web/lib/schemas.ts` — Shared zod schemas + inferred types
- [x] `apps/web/lib/api.ts` — Typed fetch wrappers for client → BFF calls
- [x] `apps/web/lib/constants.ts` — Property display names, example SMILES
- [x] `apps/web/lib/modal-proxy.ts` — Server-side Modal proxy with auth

**BFF route handlers (5 routes):**
- [x] `apps/web/app/api/predict/route.ts` — POST, zod validation, Modal proxy
- [x] `apps/web/app/api/embeddings/route.ts` — POST, zod validation, Modal proxy
- [x] `apps/web/app/api/properties/route.ts` — GET, Modal proxy
- [x] `apps/web/app/api/batch/route.ts` — POST, zod validation, Modal proxy
- [x] `apps/web/app/api/health/route.ts` — GET, Modal proxy

**Pages:**
- [x] `apps/web/app/page.tsx` — Single prediction (SMILES input, property selector, result card)
- [x] `apps/web/app/batch/page.tsx` — Batch prediction (CSV upload, results table, CSV download)
- [x] `apps/web/app/about/page.tsx` — Model info, properties table, citation, limitations
- [x] `apps/web/app/layout.tsx` — Root layout with SiteHeader + Toaster
- [x] `apps/web/app/error.tsx` — Error boundary
- [x] `apps/web/app/loading.tsx` — Root loading state
- [x] `apps/web/app/batch/loading.tsx` — Batch loading state

**Components:**
- [x] `apps/web/components/site-header.tsx` — Navigation with Predict/Batch/About links
- [x] `apps/web/components/smiles-input.tsx` — Textarea with example SMILES buttons
- [x] `apps/web/components/property-selector.tsx` — Dropdown from API properties
- [x] `apps/web/components/prediction-result.tsx` — Card with value, units, model info
- [x] `apps/web/components/embedding-viewer.tsx` — Collapsible embedding display + copy
- [x] `apps/web/components/batch-uploader.tsx` — CSV drag-and-drop with papaparse
- [x] `apps/web/components/batch-results-table.tsx` — Results table with CSV export

**Scripts:**
- [x] `scripts/smoke_test.sh` — curl-based endpoint smoke tests

---

## In Progress

### Milestone 3: Hardening

- [ ] Rate limiting on BFF routes
- [ ] Structured logging
- [ ] Unit tests (Python: SMILES validation, schemas; TypeScript: zod schemas)
- [ ] Golden tests (known SMILES → expected outputs)

---

## Known Limitations

1. **Label stats not bundled**: The `label_mean` and `label_std` per property (needed for denormalization) aren't included in the Zenodo checkpoints. Operators must provide a `label_stats.json` on the Modal Volume, or predictions will be raw normalized values.

2. **Scaler not bundled**: The sklearn StandardScaler for molecular descriptor normalization needs to be provided as `descriptor_scaler.pkl` on the Volume.

3. **React Compiler**: Not enabled during Next.js scaffold (bun defaulted to No). Can be enabled later in `next.config.ts`.

---

## File Structure

```
periogt-demo/
├── package.json                              # Root bun workspace config
├── PROGRESS.md                               # This file
├── .gitignore                                # Python + Node + env
├── apps/
│   └── web/                                  # Next.js 16.1.6
│       ├── .env.example                      # Modal credentials template
│       ├── app/
│       │   ├── globals.css                   # Tailwind v4 + OKLCH theme
│       │   ├── layout.tsx                    # Root layout
│       │   ├── page.tsx                      # Single prediction page
│       │   ├── error.tsx                     # Error boundary
│       │   ├── loading.tsx                   # Loading state
│       │   ├── about/page.tsx                # About page
│       │   ├── batch/page.tsx                # Batch prediction page
│       │   └── api/                          # BFF route handlers
│       │       ├── predict/route.ts
│       │       ├── embeddings/route.ts
│       │       ├── properties/route.ts
│       │       ├── batch/route.ts
│       │       └── health/route.ts
│       ├── components/
│       │   ├── site-header.tsx
│       │   ├── smiles-input.tsx
│       │   ├── property-selector.tsx
│       │   ├── prediction-result.tsx
│       │   ├── embedding-viewer.tsx
│       │   ├── batch-uploader.tsx
│       │   ├── batch-results-table.tsx
│       │   └── ui/                           # shadcn/ui (13 components)
│       ├── lib/
│       │   ├── env.ts                        # Server env validation
│       │   ├── schemas.ts                    # Shared zod schemas
│       │   ├── api.ts                        # Client fetch wrappers
│       │   ├── constants.ts                  # Property metadata
│       │   ├── modal-proxy.ts                # Modal auth proxy
│       │   └── utils.ts                      # cn() utility
│       ├── components.json                   # shadcn/ui config
│       ├── package.json
│       ├── tsconfig.json
│       ├── next.config.ts
│       └── postcss.config.mjs
├── services/
│   └── modal-api/
│       ├── periogt_modal_app.py              # Modal App entry point
│       ├── requirements.txt
│       ├── periogt_src/                      # Vendored PerioGT source
│       │   └── source_code/
│       │       ├── PerioGT_common/           # Main target
│       │       ├── PerioGT_copolym/
│       │       └── PerioGT_with_cond/
│       └── periogt_runtime/
│           ├── __init__.py
│           ├── schemas.py                    # Pydantic models
│           ├── checkpoint_manager.py         # Zenodo download + verify
│           ├── model_loader.py               # Model loading
│           ├── inference.py                  # Prediction + embedding
│           └── preprocessing.py              # SMILES → DGL graph
└── scripts/
    └── smoke_test.sh                         # Endpoint smoke tests
```
