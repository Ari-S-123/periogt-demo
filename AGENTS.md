# Repository Guidelines

## Project Structure & Module Organization
- `apps/web/`: Next.js 16 frontend (App Router).
- `apps/web/app/`: pages, layouts, and Route Handlers (`app/api/*/route.ts`).
- `apps/web/components/`: feature UI; `components/ui/` contains shadcn/ui primitives.
- `apps/web/lib/`: shared utilities, schemas, env validation, and Modal proxy logic.
- `apps/web/hooks/`: reusable React hooks.
- `apps/web/public/`: static assets.
- `services/modal-api/`: Modal/FastAPI backend and shared runtime source.
- `services/modal-api/periogt_runtime/`: shared inference runtime used by Modal and HPC surfaces.
- `services/hpc/`: HPC deployment surface (`periogt_hpc` package, Slurm templates, Apptainer/Conda assets, tests).
- `services/hpc/periogt_hpc/`: Click CLI, optional FastAPI server mode, CSV I/O, config/doctor diagnostics, error mapping.
- `services/hpc/slurm/`: cluster job templates + shared `setup_env.sh`.
- `services/hpc/apptainer/`: Apptainer definition and build helper.
- `services/hpc/conda/`: Conda fallback environment and installer.
- `scripts/`: shell and PowerShell smoke tests for API and HPC CLI flows.
- `periogt-hpc-backend-feature-spec-reviewed.md`: reviewed implementation spec and operational constraints for HPC mode.

## Build, Test, and Development Commands
- `bun install`: install workspace dependencies.
- `bun dev`: start frontend dev server (`apps/web`) with Turbopack.
- `bun build`: production build for the frontend.
- `bun lint`: run ESLint + Prettier checks.
- `bun format`: format frontend files with Prettier.
- `python -m unittest services/modal-api/test_local_paths.py`: run backend unit tests.
- `pytest services/modal-api/tests`: run shared runtime regression tests.
- `pytest services/hpc/tests`: run HPC package unit tests.
- `bash scripts/smoke_test.sh <BASE_URL>`: run API smoke tests (`/v1/health`, `/v1/predict`, etc.).
- `pwsh scripts/smoke_test.ps1 <BASE_URL>`: PowerShell API smoke tests (Windows-friendly path).
- `bash scripts/hpc_cli_smoke_test.sh <PERIOGT_CHECKPOINT_DIR>`: run HPC CLI smoke test (`doctor`, `predict`, `batch`).
- `pwsh scripts/hpc_cli_smoke_test.ps1 <PERIOGT_CHECKPOINT_DIR>`: PowerShell HPC CLI smoke test.
- `modal serve services/modal-api/periogt_modal_app.py`: run backend in Modal dev mode.
- `modal deploy services/modal-api/periogt_modal_app.py`: deploy backend.
- `bash services/hpc/apptainer/build.sh --fakeroot`: build HPC Apptainer image.
- `bash services/hpc/conda/install.sh <ENV_NAME>`: install/update HPC Conda fallback env.

## Coding Style & Naming Conventions
- TypeScript uses strict mode; prefer explicit types at API boundaries.
- Formatting/linting is enforced by Prettier + ESLint (`bun lint`, `bun format`).
- Use `zod/v4` imports for schemas and keep shared schema logic in `apps/web/lib/schemas.ts`.
- React component files use kebab-case filenames (for example, `prediction-result.tsx`) with PascalCase component exports.
- Python follows PEP 8: 4-space indentation, snake_case functions/modules, PascalCase classes.
- PowerShell scripts should remain ASCII-safe and use explicit cmdlet-parentheses patterns in complex boolean expressions.

## Testing Guidelines
- Primary checks are frontend linting, Python tests (`services/modal-api/tests`, `services/hpc/tests`), and smoke tests.
- Name Python tests as `test_*.py`; keep tests near the owning package.
- For API/schema/runtime changes, run all of: `bun lint`, Python tests, and at least one smoke path (`.sh` or `.ps1`).
- For HPC changes, include `python -m periogt_hpc doctor` validation in your manual verification notes.
- No hard coverage threshold is configured; prioritize meaningful tests for touched behavior.

## Commit & Pull Request Guidelines
- Existing history uses short imperative messages (`cleanup`, `initial commit`); keep commits concise and action-oriented.
- Prefer one logical change per commit; include scope when useful (example: `web: validate batch payload`).
- PRs should include: purpose, key changes, manual verification steps, and linked issue/ticket.
- For UI/API behavior changes, attach screenshots or sample request/response payloads.
- For HPC behavior changes, include sample CLI invocations and expected exit behavior (`0`, `1`, `2`) when relevant.

## Security & Configuration Tips
- Keep secrets in `apps/web/.env.local`; never commit `MODAL_KEY` or `MODAL_SECRET`.
- Server-only env vars should not use `NEXT_PUBLIC_` prefixes.
- Validate proxy/auth behavior in `app/api/*` routes before exposing new backend endpoints.
- In HPC server mode, `PERIOGT_API_KEY` is optional; if set, clients must send `X-Api-Key`.
- For CUDA 12.6 environments, ensure driver version `>= 560.28` and document cluster-specific storage choices (`/projects` vs purgeable `/scratch` on Explorer).
