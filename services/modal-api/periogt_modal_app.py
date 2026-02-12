"""PerioGT Modal inference API.

Serves polymer property prediction and graph embedding endpoints
via FastAPI on Modal GPU infrastructure.

Local source paths are resolved relative to this file to avoid
working-directory dependent deployments.
"""

import json
import logging
import os
import posixpath
import threading
import time
import uuid
from pathlib import Path

import modal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _resolve_sibling_dir(name: str) -> Path:
    path = (Path(__file__).resolve().parent / name).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Local directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Expected directory at: {path}")
    return path


PERIOGT_SRC_DIR = _resolve_sibling_dir("periogt_src")
PERIOGT_RUNTIME_DIR = _resolve_sibling_dir("periogt_runtime")

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

from periogt_runtime.runtime_config import (
    DEFAULT_CHECKPOINT_DIR,
    add_src_dir_to_syspath,
)
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


def _canonical_modal_mount_path(raw_path: str) -> str:
    """
    Return a canonical absolute POSIX path for Modal Volume mounts.

    Modal validates mount points as canonical Unix-style absolute paths.
    On Windows hosts, values like "/vol/checkpoints" can be rewritten to
    "C:/vol/checkpoints" when resolved via pathlib, which Modal rejects.
    """
    path = raw_path.replace("\\", "/").strip()
    if not path:
        path = DEFAULT_CHECKPOINT_DIR

    # Convert Windows drive paths (e.g. C:/vol/checkpoints) to POSIX.
    if len(path) >= 2 and path[1] == ":":
        path = path[2:]

    path = "/" + path.lstrip("/")
    while "//" in path:
        path = path.replace("//", "/")

    return path.rstrip("/") or "/"


VOLUME_ROOT = _canonical_modal_mount_path(
    os.environ.get("PERIOGT_CHECKPOINT_DIR", DEFAULT_CHECKPOINT_DIR)
)
INDEX_PATH = posixpath.join(VOLUME_ROOT, "index.json")
LABEL_STATS_PATH = posixpath.join(VOLUME_ROOT, "label_stats.json")
SCALER_PATH = posixpath.join(VOLUME_ROOT, "descriptor_scaler.pkl")

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
_bootstrap_lock = threading.Lock()
_property_model_locks: dict[str, threading.Lock] = {}


def _supported_properties() -> list[str]:
    return sorted(_state["property_index"].keys())


def _ensure_property_model_loaded(property_id: str) -> None:
    models = _state["models"]
    if models is None:
        raise RuntimeError("Runtime is not initialized.")

    if property_id in models.finetuned_models:
        return

    if property_id not in _state["property_index"]:
        raise ValueError(
            f"Unsupported property '{property_id}'. Supported: {_supported_properties()}"
        )

    lock = _property_model_locks.setdefault(property_id, threading.Lock())
    with lock:
        if property_id in models.finetuned_models:
            return

        info = _state["property_index"][property_id]
        ckpt_path = info.get("checkpoint")
        if not ckpt_path or not os.path.exists(ckpt_path):
            raise RuntimeError(
                f"Checkpoint not found for property '{property_id}': {ckpt_path}"
            )

        from periogt_runtime.model_loader import load_finetuned_model

        started = time.monotonic()
        model = load_finetuned_model(ckpt_path, device=str(models.device))
        models.finetuned_models[property_id] = model
        logger.info(
            "Loaded finetuned model for '%s' in %.2fs",
            property_id,
            time.monotonic() - started,
        )


def _ensure_ready() -> None:
    """Bootstrap base runtime state on first request (runs once per container)."""
    if _state["ready"]:
        return

    with _bootstrap_lock:
        if _state["ready"]:
            return

        import pickle
        import torch

        started = time.monotonic()

        # Ensure vendored PerioGT source is importable
        add_src_dir_to_syspath()

        from periogt_runtime.checkpoint_manager import ensure_checkpoints
        from periogt_runtime.model_loader import load_all_models

        # Download / verify checkpoints. If another container is already
        # bootstrapping, wait until it finishes instead of failing this request.
        wait_timeout_s = _parse_positive_float_env(
            "PERIOGT_CHECKPOINT_WAIT_TIMEOUT_SECONDS",
            5.0,
            minimum=1.0,
        )
        wait_poll_s = _parse_positive_float_env(
            "PERIOGT_CHECKPOINT_WAIT_POLL_SECONDS",
            1.0,
            minimum=0.1,
        )
        wait_started = time.monotonic()
        while True:
            try:
                property_index = ensure_checkpoints(volume)
                break
            except RuntimeError as exc:
                if "Another container is currently downloading checkpoints" not in str(exc):
                    raise

                elapsed = time.monotonic() - wait_started
                if elapsed >= wait_timeout_s:
                    raise RuntimeError(
                        "Timed out waiting for checkpoint bootstrap in another container."
                    ) from exc

                logger.info(
                    "Checkpoint bootstrap in progress in another container; "
                    "waiting %.1fs (elapsed %.1fs / %.1fs).",
                    wait_poll_s,
                    elapsed,
                    wait_timeout_s,
                )
                time.sleep(wait_poll_s)
                volume.reload()
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

        # Load only the pretrained backbone; finetuned heads are loaded lazily per property.
        device = "cuda" if torch.cuda.is_available() else "cpu"
        models = load_all_models(
            property_index,
            VOLUME_ROOT,
            device=device,
            load_finetuned=False,
        )
        _state["models"] = models
        _state["ready"] = True

        logger.info(
            "Container base runtime ready in %.2fs. Indexed properties: %d, GPU: %s",
            time.monotonic() - started,
            len(property_index),
            torch.cuda.is_available(),
        )


def _parse_positive_float_env(name: str, default: float, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.2f", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%r is too small; using minimum %.2f", name, raw, minimum)
        return minimum
    return value


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@app.function(
    image=image,
    gpu="L4",
    env={"PERIOGT_CHECKPOINT_DIR": VOLUME_ROOT},
    volumes={VOLUME_ROOT: volume},
    min_containers=1,
    timeout=300,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app(requires_proxy_auth=True)
def periogt_api():
    import torch

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

    def ensure_ready_or_503() -> None:
        try:
            _ensure_ready()
        except RuntimeError as exc:
            message = str(exc)
            if "checkpoint" in message.lower():
                raise HTTPException(
                    status_code=503,
                    detail="Model initialization in progress. Please retry shortly.",
                ) from exc
            raise

    @web_app.get("/v1/health")
    async def health() -> HealthResponse:
        # Keep health non-blocking: do not trigger model loading here.
        checkpoints_present = bool(_state["property_index"]) or os.path.exists(INDEX_PATH)

        return HealthResponse(
            status="ok" if _state["ready"] else "initializing",
            model_loaded=_state["models"] is not None
            and _state["models"].pretrained_model is not None,
            checkpoints_present=checkpoints_present,
            gpu_available=torch.cuda.is_available(),
        )

    @web_app.get("/v1/properties")
    async def list_properties() -> PropertiesResponse:
        ensure_ready_or_503()
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
        ensure_ready_or_503()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        from periogt_runtime.inference import predict_property

        try:
            _ensure_property_model_loaded(body.property)
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
        ensure_ready_or_503()
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
        ensure_ready_or_503()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        from periogt_runtime.inference import predict_property

        results: list[PredictResponse | ErrorDetail] = []
        for item in body.items:
            try:
                _ensure_property_model_loaded(item.property)
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
