"""PerioGT inference: SMILES → property prediction or embedding vector."""

from __future__ import annotations

import logging
import uuid

import numpy as np
import torch

from .model_loader import LoadedModels
from .preprocessing import prepare_single_inference, validate_smiles
from .schemas import (
    EmbeddingResponse,
    ErrorDetail,
    ModelInfo,
    PredictResponse,
    PredictionValue,
)

logger = logging.getLogger(__name__)


def predict_property(
    smiles: str,
    property_id: str,
    models: LoadedModels,
    scaler,
    label_mean: dict[str, float],
    label_std: dict[str, float],
    return_embedding: bool = False,
    request_id: str | None = None,
) -> PredictResponse:
    """
    Run a single property prediction for a polymer SMILES.

    Args:
        smiles: Polymer repeat-unit SMILES with * connection points.
        property_id: Property to predict (e.g., 'eps', 'tg').
        models: Loaded pretrained + finetuned models.
        scaler: Fitted StandardScaler for molecular descriptor normalization.
        label_mean: Per-property label mean for denormalization.
        label_std: Per-property label std for denormalization.
        return_embedding: Whether to include the embedding vector.
        request_id: Request correlation ID.

    Returns:
        PredictResponse with the predicted value.

    Raises:
        ValueError: If SMILES is invalid or property is unsupported.
    """
    request_id = request_id or str(uuid.uuid4())

    # Validate SMILES
    is_valid, error_msg = validate_smiles(smiles)
    if not is_valid:
        raise ValueError(error_msg)

    # Check property is supported
    if property_id not in models.property_index:
        supported = sorted(models.property_index.keys())
        raise ValueError(
            f"Unsupported property '{property_id}'. Supported: {supported}"
        )

    if property_id not in models.finetuned_models:
        raise RuntimeError(
            f"Model for property '{property_id}' is not loaded."
        )

    finetuned_model = models.finetuned_models[property_id]
    pretrained_model = models.pretrained_model
    device = models.device

    # Preprocess SMILES into graph
    graph, fps, mds = prepare_single_inference(smiles, pretrained_model, scaler, device)

    # Run finetuned inference
    with torch.no_grad():
        raw_prediction = finetuned_model.forward_tune(graph, fps, mds)

    # Denormalize prediction
    raw_value = raw_prediction.item()
    mean = label_mean.get(property_id, 0.0)
    std = label_std.get(property_id, 1.0)
    denormalized_value = raw_value * std + mean

    # Get property metadata
    prop_info = models.property_index.get(property_id, {})
    units = prop_info.get("units", "")

    # Optionally compute embedding
    embedding = None
    if return_embedding:
        embedding = _compute_embedding(smiles, pretrained_model, scaler, device)

    return PredictResponse(
        smiles=smiles,
        property=property_id,
        prediction=PredictionValue(value=round(denormalized_value, 6), units=units),
        embedding=embedding,
        model=ModelInfo(checkpoint=prop_info.get("checkpoint", "unknown")),
        request_id=request_id,
    )


def compute_embedding(
    smiles: str,
    models: LoadedModels,
    scaler,
    request_id: str | None = None,
) -> EmbeddingResponse:
    """
    Compute the PerioGT graph embedding for a polymer SMILES.

    Uses the pretrained model's generate_node_emb() to produce embeddings,
    then aggregates via readout.

    Args:
        smiles: Polymer repeat-unit SMILES with * connection points.
        models: Loaded models (pretrained model needed).
        scaler: Fitted StandardScaler for molecular descriptor normalization.
        request_id: Request correlation ID.

    Returns:
        EmbeddingResponse with the embedding vector.
    """
    request_id = request_id or str(uuid.uuid4())

    is_valid, error_msg = validate_smiles(smiles)
    if not is_valid:
        raise ValueError(error_msg)

    embedding = _compute_embedding(smiles, models.pretrained_model, scaler, models.device)

    return EmbeddingResponse(
        smiles=smiles,
        embedding=embedding,
        dim=len(embedding),
        request_id=request_id,
    )


def _compute_embedding(
    smiles: str,
    pretrained_model: torch.nn.Module,
    scaler,
    device: torch.device,
) -> list[float]:
    """
    Internal: compute embedding vector for a SMILES using the pretrained model.

    Uses generate_node_emb() then aggregates fp_vn, md_vn, and mean readout
    into a single vector (d_g_feats * 3 dimensions).
    """
    import dgl
    from .preprocessing import compute_fingerprints_and_descriptors
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys, AllChem
    from mordred import Calculator, descriptors
    from utils.aug import generate_oligomer_smiles
    from utils.function import preprocess_batch_light
    from data.smiles2g_light import smiles_to_graph_with_prompt

    feat_cache = compute_fingerprints_and_descriptors(smiles)

    # Build the prompt graph (this internally uses generate_node_emb)
    graph = smiles_to_graph_with_prompt(smiles, pretrained_model, scaler, device, feat_cache)

    # Compute base fingerprint and descriptor
    mol = Chem.MolFromSmiles(generate_oligomer_smiles(num_repeat_units=3, smiles=smiles))
    maccs_fp = MACCSkeys.GenMACCSKeys(mol)
    ec_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 4, nBits=1024)
    fp = np.array(list(map(int, list(maccs_fp + ec_fp))), dtype=np.float32)

    calc = Calculator(descriptors, ignore_3D=True)
    md = np.array(list(calc(mol).values()), dtype=np.float32)
    md = np.where(np.isnan(md), 0, md)
    md = np.where(md > 1e12, 1e12, md)
    md_norm = scaler.transform(md.reshape(1, -1)).astype(np.float32)

    fps = torch.from_numpy(fp.reshape(1, -1)).to(device)
    mds = torch.from_numpy(md_norm).to(device)

    # Prepare graph
    graph.edata["path"][:, :] = preprocess_batch_light(
        torch.tensor([graph.number_of_nodes()]),
        torch.tensor([graph.number_of_edges()]),
        graph.edata["path"][:, :],
    )
    graph = graph.to(device)

    # Forward through pretrained model to get embedding
    with torch.no_grad():
        indicators = graph.ndata["vavn"]
        node_h = pretrained_model.node_emb(graph.ndata["begin_end"], indicators)
        edge_h = pretrained_model.edge_emb(graph.ndata["edge"], indicators)
        triplet_h = pretrained_model.triplet_emb(node_h, edge_h, fps, mds, indicators)
        triplet_h = pretrained_model.model(graph, triplet_h)

        graph.ndata["ht"] = triplet_h
        fp_vn = triplet_h[indicators == 1]
        md_vn = triplet_h[indicators == 2]
        graph.remove_nodes(np.where(indicators.detach().cpu().numpy() >= 1)[0])
        readout = dgl.readout_nodes(graph, "ht", op="mean")
        g_feats = torch.cat([fp_vn, md_vn, readout], dim=-1)

    embedding = g_feats.squeeze(0).detach().cpu().numpy().tolist()
    return embedding
