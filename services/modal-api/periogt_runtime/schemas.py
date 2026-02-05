"""Pydantic request/response models for the PerioGT API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Request Models ---


class PredictRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=2000, description="Polymer repeat-unit SMILES with * connection points")
    property: str = Field(..., min_length=1, max_length=64, description="Property ID (e.g., 'eps', 'tg', 'density')")
    return_embedding: bool = Field(default=False, description="Also return the graph embedding vector")


class EmbeddingRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=2000, description="Polymer repeat-unit SMILES with * connection points")


class BatchPredictRequest(BaseModel):
    items: list[PredictRequest] = Field(..., max_length=100, description="List of prediction requests (max 100)")


# --- Response Models ---


class PredictionValue(BaseModel):
    value: float
    units: str


class ModelInfo(BaseModel):
    name: str = "PerioGT"
    checkpoint: str


class PredictResponse(BaseModel):
    smiles: str
    property: str
    prediction: PredictionValue
    embedding: list[float] | None = None
    model: ModelInfo
    request_id: str


class EmbeddingResponse(BaseModel):
    smiles: str
    embedding: list[float]
    dim: int
    request_id: str


class BatchPredictResponse(BaseModel):
    results: list[PredictResponse | ErrorDetail]
    request_id: str


class PropertyInfo(BaseModel):
    id: str
    label: str
    units: str


class PropertiesResponse(BaseModel):
    properties: list[PropertyInfo]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    checkpoints_present: bool
    gpu_available: bool


# --- Error Models ---


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | list | str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str
