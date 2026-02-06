"""PerioGT Modal inference API.

Serves polymer property prediction and graph embedding endpoints
via FastAPI on Modal GPU infrastructure.

Local source paths are resolved relative to this file to avoid
working-directory dependent deployments.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

import modal

from local_paths import PERIOGT_RUNTIME_DIR, PERIOGT_SRC_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modal app + image
# ---------------------------------------------------------------------------

app = modal.App("periogt-api")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    # PyTorch with CUDA 12.6
    .pip_install("torch==2.6.0", index_url="https://download.pytorch.org/whl/cu126")
    # DGL (CUDA 12.6 build)
    .pip_install("dgl", find_links="https://data.dgl.ai/wheels/torch-2.6/cu126/repo.html")
    # Scientific stack
    .pip_install(
        "dgllife",
        "mordred",
        "rdkit",
        "networkx",
        "scipy",
        "scikit-learn",
        "pandas",
        "pyyaml",
        "numpy<2",
    )
    # API deps
    .pip_install("fastapi[standard]", "pydantic>=2.8,<3")
    # Vendor PerioGT source and runtime into the image
    .add_local_dir(PERIOGT_SRC_DIR, remote_path="/root/periogt_src")
    .add_local_dir(PERIOGT_RUNTIME_DIR, remote_path="/root/periogt_runtime")
)

volume = modal.Volume.from_name("periogt-checkpoints", create_if_missing=True)

VOLUME_ROOT = "/vol/checkpoints"
LABEL_STATS_PATH = os.path.join(VOLUME_ROOT, "label_stats.json")
SCALER_PATH = os.path.join(VOLUME_ROOT, "descriptor_scaler.pkl")

# ---------------------------------------------------------------------------
# Container-level state (populated on first request)
# ---------------------------------------------------------------------------

_state: dict = {
    "models": None,
    "scaler": None,
    "label_mean": {},
    "label_std": {},
    "property_index": {},
    "ready": False,
}


def _ensure_ready() -> None:
    """Bootstrap models on first request (runs once per container)."""
    if _state["ready"]:
        return

    import pickle
    import sys

    import torch

    # Ensure vendored PerioGT source is importable
    sys.path.insert(0, "/root/periogt_src/source_code/PerioGT_common")

    from periogt_runtime.checkpoint_manager import ensure_checkpoints
    from periogt_runtime.model_loader import load_all_models

    # Download / verify checkpoints
    property_index = ensure_checkpoints(volume)
    _state["property_index"] = property_index

    # Load label stats (mean/std per property for denormalization)
    volume.reload()
    if os.path.exists(LABEL_STATS_PATH):
        with open(LABEL_STATS_PATH) as f:
            stats = json.load(f)
        _state["label_mean"] = {k: v["mean"] for k, v in stats.items()}
        _state["label_std"] = {k: v["std"] for k, v in stats.items()}
        logger.info("Loaded label stats for %d properties", len(stats))
    else:
        logger.warning(
            "No label_stats.json found at %s. "
            "Predictions will be raw (normalized) model outputs. "
            "To enable denormalization, place a label_stats.json on the Volume.",
            LABEL_STATS_PATH,
        )

    # Load scaler for molecular descriptor normalization
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, "rb") as f:
            _state["scaler"] = pickle.load(f)
        logger.info("Loaded descriptor scaler from %s", SCALER_PATH)
    else:
        logger.warning(
            "No descriptor_scaler.pkl found at %s. "
            "A scaler will be fitted from scratch on first request (less accurate). "
            "For production use, place a pre-fitted scaler on the Volume.",
            SCALER_PATH,
        )

    # Load all models
    device = "cuda" if torch.cuda.is_available() else "cpu"
    models = load_all_models(property_index, VOLUME_ROOT, device=device)
    _state["models"] = models
    _state["ready"] = True

    logger.info(
        "Container ready. Properties: %s, GPU: %s",
        list(models.finetuned_models.keys()),
        torch.cuda.is_available(),
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@app.function(
    image=image,
    gpu="L4",
    volumes={VOLUME_ROOT: volume},
    min_containers=1,
    timeout=300,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app(requires_proxy_auth=True)
def periogt_api():
    import torch
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    from periogt_runtime.schemas import (
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

    web_app = FastAPI(
        title="PerioGT Inference API",
        version="0.1.0",
        docs_url="/v1/docs",
        redoc_url=None,
    )

    # --- Error handler ---

    @web_app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(code=str(exc.status_code), message=str(exc.detail)),
                request_id=request_id,
            ).model_dump(),
        )

    @web_app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        logger.exception("Unhandled error for request %s", request_id)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="internal_error",
                    message="An unexpected error occurred.",
                ),
                request_id=request_id,
            ).model_dump(),
        )

    # --- Routes ---

    @web_app.get("/v1/health")
    async def health() -> HealthResponse:
        try:
            _ensure_ready()
        except Exception:
            pass

        return HealthResponse(
            status="ok" if _state["ready"] else "initializing",
            model_loaded=_state["models"] is not None
            and _state["models"].pretrained_model is not None,
            checkpoints_present=bool(_state["property_index"]),
            gpu_available=torch.cuda.is_available(),
        )

    @web_app.get("/v1/properties")
    async def list_properties() -> PropertiesResponse:
        _ensure_ready()
        properties = []
        for prop_id, info in _state["property_index"].items():
            properties.append(
                PropertyInfo(
                    id=prop_id,
                    label=info.get("label", prop_id),
                    units=info.get("units", ""),
                )
            )
        return PropertiesResponse(properties=properties)

    @web_app.post("/v1/predict")
    async def predict(body: PredictRequest, request: Request) -> PredictResponse:
        _ensure_ready()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        from periogt_runtime.inference import predict_property

        try:
            result = predict_property(
                smiles=body.smiles,
                property_id=body.property,
                models=_state["models"],
                scaler=_state["scaler"],
                label_mean=_state["label_mean"],
                label_std=_state["label_std"],
                return_embedding=body.return_embedding,
                request_id=request_id,
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @web_app.post("/v1/embeddings")
    async def embeddings(
        body: EmbeddingRequest, request: Request
    ) -> EmbeddingResponse:
        _ensure_ready()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        from periogt_runtime.inference import compute_embedding

        try:
            result = compute_embedding(
                smiles=body.smiles,
                models=_state["models"],
                scaler=_state["scaler"],
                request_id=request_id,
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @web_app.post("/v1/predict/batch")
    async def predict_batch(
        body: BatchPredictRequest, request: Request
    ) -> BatchPredictResponse:
        _ensure_ready()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        from periogt_runtime.inference import predict_property

        results: list[PredictResponse | ErrorDetail] = []
        for item in body.items:
            try:
                result = predict_property(
                    smiles=item.smiles,
                    property_id=item.property,
                    models=_state["models"],
                    scaler=_state["scaler"],
                    label_mean=_state["label_mean"],
                    label_std=_state["label_std"],
                    return_embedding=item.return_embedding,
                    request_id=request_id,
                )
                results.append(result)
            except ValueError as e:
                results.append(
                    ErrorDetail(
                        code="validation_error",
                        message=str(e),
                        details={"smiles": item.smiles, "property": item.property},
                    )
                )
            except Exception as e:
                logger.exception("Batch item error for %s", item.smiles)
                results.append(
                    ErrorDetail(
                        code="inference_error",
                        message=str(e),
                        details={"smiles": item.smiles, "property": item.property},
                    )
                )

        return BatchPredictResponse(results=results, request_id=request_id)

    return web_app
