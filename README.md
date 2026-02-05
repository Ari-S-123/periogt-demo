# PerioGT Demo

Web prototype that lets chemists submit polymer repeat-unit SMILES and receive property predictions and graph embeddings using the PerioGT graph transformer model.

## Architecture

```
Browser -> Next.js Route Handler (/api/*) -> Modal FastAPI (/v1/*) -> PerioGT GPU inference
```

- **Frontend:** Next.js 16 App Router, React 19, shadcn/ui, Tailwind v4, react-hook-form + Zod v4
- **Backend:** Modal GPU service, FastAPI, PyTorch 2.6 + DGL, RDKit, Mordred
- **Weights:** Downloaded from Zenodo at runtime into a persistent Modal Volume

The browser never talks directly to the GPU backend. Route handlers in `/api/*` validate requests with Zod, inject Modal auth headers, and proxy to the backend.

## Quick Start

```bash
# Install dependencies
bun install

# Set up environment (copy and fill in values)
cp apps/web/.env.example apps/web/.env.local

# Start dev server
bun dev
```

## Commands

```bash
# Frontend
bun dev              # Dev server (Turbopack)
bun build            # Production build
bun lint             # ESLint + Prettier check
bun format           # Format with Prettier

# Backend
modal serve services/modal-api/periogt_modal_app.py    # Local dev
modal deploy services/modal-api/periogt_modal_app.py   # Deploy

# Smoke tests
bash scripts/smoke_test.sh <MODAL_BASE_URL>
```

## Repository Structure

```
periogt-demo/
  apps/web/           Next.js 16 frontend (Bun workspace)
  services/modal-api/ Modal GPU backend (standalone Python)
  scripts/            Smoke tests
```

## Environment Variables

Stored in `apps/web/.env.local` (git-ignored):

```
MODAL_PERIOGT_URL=https://your-workspace--periogt-api-periogt-api.modal.run
MODAL_KEY=your-modal-key
MODAL_SECRET=your-modal-secret
```

## License

Model artifacts available from [Zenodo](https://zenodo.org/records/17035498) under CC-BY 4.0.
