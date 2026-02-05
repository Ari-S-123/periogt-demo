# PerioGT Web Frontend

Next.js 16 App Router frontend for the PerioGT polymer property prediction demo.

## Stack

- Next.js 16.1.6 (App Router, Turbopack)
- React 19, TypeScript 5
- shadcn/ui (Radix UI + Tailwind v4)
- react-hook-form + Zod v4 for form validation
- PapaParse for CSV parsing

## Pages

| Route | Description |
|-------|-------------|
| `/` | Single property prediction (react-hook-form + inline Zod validation) |
| `/batch` | CSV upload for batch prediction |
| `/about` | Model info, supported properties, citation |

## API Routes

All routes proxy to the Modal backend via `lib/modal-proxy.ts`:

| Route | Modal Endpoint | Method |
|-------|---------------|--------|
| `/api/predict` | `/v1/predict` | POST |
| `/api/batch` | `/v1/predict/batch` | POST |
| `/api/embeddings` | `/v1/embeddings` | POST |
| `/api/properties` | `/v1/properties` | GET |
| `/api/health` | `/v1/health` | GET |

## Development

```bash
bun dev       # Start dev server
bun build     # Production build
bun lint      # ESLint + Prettier check
bun format    # Format with Prettier
```
