# Repository Guidelines

## Project Structure & Module Organization
- `apps/web/`: Next.js 16 frontend (App Router).
- `apps/web/app/`: pages, layouts, and Route Handlers (`app/api/*/route.ts`).
- `apps/web/components/`: feature UI; `components/ui/` contains shadcn/ui primitives.
- `apps/web/lib/`: shared utilities, schemas, env validation, and Modal proxy logic.
- `apps/web/hooks/`: reusable React hooks.
- `apps/web/public/`: static assets.
- `services/modal-api/`: standalone Python backend for Modal/FastAPI inference.
- `services/modal-api/periogt_runtime/`: preprocessing, model loading, inference, schemas.
- `scripts/smoke_test.sh`: endpoint smoke tests for deployed or locally served backend.

## Build, Test, and Development Commands
- `bun install`: install workspace dependencies.
- `bun dev`: start frontend dev server (`apps/web`) with Turbopack.
- `bun build`: production build for the frontend.
- `bun lint`: run ESLint + Prettier checks.
- `bun format`: format frontend files with Prettier.
- `python -m unittest services/modal-api/test_local_paths.py`: run backend unit tests.
- `bash scripts/smoke_test.sh <MODAL_BASE_URL>`: run API smoke tests (`/v1/health`, `/v1/predict`, etc.).
- `modal serve services/modal-api/periogt_modal_app.py`: run backend in Modal dev mode.
- `modal deploy services/modal-api/periogt_modal_app.py`: deploy backend.

## Coding Style & Naming Conventions
- TypeScript uses strict mode; prefer explicit types at API boundaries.
- Formatting/linting is enforced by Prettier + ESLint (`bun lint`, `bun format`).
- Use `zod/v4` imports for schemas and keep shared schema logic in `apps/web/lib/schemas.ts`.
- React component files use kebab-case filenames (for example, `prediction-result.tsx`) with PascalCase component exports.
- Python follows PEP 8: 4-space indentation, snake_case functions/modules, PascalCase classes.

## Testing Guidelines
- Primary checks are frontend linting, backend unit tests, and API smoke tests.
- Name Python tests as `test_*.py`; keep tests near the backend package (`services/modal-api/`).
- For API or schema changes, run all of: `bun lint`, unit test command above, and smoke tests.
- No hard coverage threshold is configured; prioritize meaningful tests for touched behavior.

## Commit & Pull Request Guidelines
- Existing history uses short imperative messages (`cleanup`, `initial commit`); keep commits concise and action-oriented.
- Prefer one logical change per commit; include scope when useful (example: `web: validate batch payload`).
- PRs should include: purpose, key changes, manual verification steps, and linked issue/ticket.
- For UI/API behavior changes, attach screenshots or sample request/response payloads.

## Security & Configuration Tips
- Keep secrets in `apps/web/.env.local`; never commit `MODAL_KEY` or `MODAL_SECRET`.
- Server-only env vars should not use `NEXT_PUBLIC_` prefixes.
- Validate proxy/auth behavior in `app/api/*` routes before exposing new backend endpoints.
