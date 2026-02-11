"""Optional FastAPI server mode for HPC deployment."""

from __future__ import annotations

import logging
import os
import uuid

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import ensure_runtime_package_path, resolve_config
from .errors import PerioGTError, map_exception
from .log import configure_logging
from .runtime import RuntimeState, load_runtime_state

logger = logging.getLogger(__name__)

_cfg = resolve_config(require_checkpoint_dir=True, require_source_dir=True)
ensure_runtime_package_path(_cfg.runtime_package_dir)

from periogt_runtime.schemas import (  # noqa: E402
    BatchPredictRequest,
    BatchPredictResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PredictRequest,
    PredictResponse,
    PropertiesResponse,
    PropertyInfo,
)

_state: dict[str, RuntimeState | None] = {"runtime": None}


def _auth_guard(x_api_key: str | None) -> None:
    configured = os.environ.get("PERIOGT_API_KEY")
    if not configured:
        return
    if x_api_key != configured:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Api-Key")


def _ensure_runtime() -> RuntimeState:
    if _state["runtime"] is None:
        _state["runtime"] = load_runtime_state(_cfg)
    return _state["runtime"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="PerioGT HPC API",
        version="0.2.0",
        docs_url="/v1/docs",
        redoc_url=None,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # noqa: ANN001
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        err = ErrorResponse(
            error=ErrorDetail(code=str(exc.status_code), message=str(exc.detail)),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=err.model_dump())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):  # noqa: ANN001
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        mapped = map_exception(exc)
        payload = ErrorResponse(
            error=ErrorDetail(
                code=mapped.code,
                message=mapped.message,
                details=mapped.details,
            ),
            request_id=request_id,
        )
        logger.exception("Unhandled error %s", request_id)
        return JSONResponse(status_code=mapped.http_status, content=payload.model_dump())

    @app.get("/v1/health")
    async def health() -> HealthResponse:
        ready = _state["runtime"] is not None
        return HealthResponse(
            status="ok" if ready else "initializing",
            model_loaded=ready,
            checkpoints_present=_cfg.checkpoint_dir.exists(),
            gpu_available=(_cfg.device.type == "cuda"),
        )

    @app.get("/v1/properties")
    async def properties(x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> PropertiesResponse:
        _auth_guard(x_api_key)
        runtime = _ensure_runtime()
        props = [
            PropertyInfo(
                id=pid,
                label=meta.get("label", pid),
                units=meta.get("units", ""),
            )
            for pid, meta in runtime.property_index.items()
        ]
        return PropertiesResponse(properties=props)

    @app.post("/v1/predict")
    async def predict(
        body: PredictRequest,
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    ) -> PredictResponse:
        _auth_guard(x_api_key)
        runtime = _ensure_runtime()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        from periogt_runtime.inference import predict_property

        try:
            return predict_property(
                smiles=body.smiles,
                property_id=body.property,
                models=runtime.models,
                scaler=runtime.scaler,
                label_mean=runtime.label_mean,
                label_std=runtime.label_std,
                return_embedding=body.return_embedding,
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception(exc)
            raise PerioGTError(mapped.code, mapped.message, mapped.details) from exc

    @app.post("/v1/embeddings")
    async def embeddings(
        body: EmbeddingRequest,
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    ) -> EmbeddingResponse:
        _auth_guard(x_api_key)
        runtime = _ensure_runtime()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        from periogt_runtime.inference import compute_embedding

        try:
            return compute_embedding(
                smiles=body.smiles,
                models=runtime.models,
                scaler=runtime.scaler,
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception(exc)
            raise PerioGTError(mapped.code, mapped.message, mapped.details) from exc

    @app.post("/v1/predict/batch")
    async def predict_batch(
        body: BatchPredictRequest,
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    ) -> BatchPredictResponse:
        _auth_guard(x_api_key)
        runtime = _ensure_runtime()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        from periogt_runtime.inference import predict_property

        results: list[PredictResponse | ErrorDetail] = []
        for item in body.items:
            try:
                result = predict_property(
                    smiles=item.smiles,
                    property_id=item.property,
                    models=runtime.models,
                    scaler=runtime.scaler,
                    label_mean=runtime.label_mean,
                    label_std=runtime.label_std,
                    return_embedding=item.return_embedding,
                    request_id=request_id,
                )
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                mapped = map_exception(exc)
                results.append(
                    ErrorDetail(
                        code=mapped.code,
                        message=mapped.message,
                        details={"smiles": item.smiles, "property": item.property},
                    )
                )

        return BatchPredictResponse(results=results, request_id=request_id)

    return app


app = create_app()


def main() -> None:
    configure_logging()
    host = os.environ.get("PERIOGT_HOST", "0.0.0.0")
    port = int(os.environ.get("PERIOGT_PORT", "8000"))
    uvicorn.run("periogt_hpc.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

