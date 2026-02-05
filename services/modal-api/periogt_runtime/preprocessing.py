"""SMILES preprocessing for PerioGT inference.

Wraps the vendored PerioGT source code to convert SMILES strings into
DGL graph objects ready for model consumption.
"""

from __future__ import annotations

import logging
import sys

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Add vendored PerioGT source to path
sys.path.insert(0, "/root/periogt_src/source_code/PerioGT_common")


def validate_smiles(smiles: str) -> tuple[bool, str]:
    """
    Validate a polymer repeat-unit SMILES string.

    Returns (is_valid, error_message).
    """
    from rdkit import Chem

    if not smiles or not smiles.strip():
        return False, "SMILES string is empty."

    if len(smiles) > 2000:
        return False, f"SMILES too long ({len(smiles)} chars, max 2000)."

    if "*" not in smiles:
        return False, "SMILES must include polymer connection points using '*'."

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False, "Invalid SMILES: RDKit could not parse this structure."

    # Check exactly 2 * atoms
    star_count = sum(1 for atom in mol.GetAtoms() if atom.GetSymbol() == "*")
    if star_count != 2:
        return False, f"Expected exactly 2 '*' connection points, found {star_count}."

    return True, ""


def compute_fingerprints_and_descriptors(
    base_smiles: str,
    units: tuple[int, ...] = (3, 6, 9),
) -> dict[tuple[str, int], tuple[np.ndarray | None, np.ndarray | None]]:
    """
    Compute MACCS+ECFP fingerprints and Mordred molecular descriptors
    for oligomer representations of the given base SMILES.

    Returns a feature cache: {(base_smiles, n_units): (fp_array, md_array)}.
    """
    from utils.features import precompute_features

    feat_cache = precompute_features([base_smiles], units=units, workers=1)
    return feat_cache


def smiles_to_inference_graph(
    smiles: str,
    pretrained_model: torch.nn.Module,
    scaler,
    device: torch.device,
    feat_cache: dict,
) -> "dgl.DGLGraph":
    """
    Convert a polymer SMILES into a DGL graph with node embedding prompts,
    ready for finetuned model inference via forward_tune().

    This wraps PerioGT's smiles_to_graph_with_prompt().

    Args:
        smiles: Base polymer repeat-unit SMILES.
        pretrained_model: Loaded pretrained LiGhTPredictor for generating node embeddings.
        scaler: Fitted sklearn StandardScaler for molecular descriptor normalization.
        device: Torch device.
        feat_cache: Pre-computed features from compute_fingerprints_and_descriptors().

    Returns:
        DGL graph with 'prompt' node data attached.
    """
    import dgl
    from data.smiles2g_light import smiles_to_graph_with_prompt
    from utils.function import preprocess_batch_light

    with torch.no_grad():
        graph = smiles_to_graph_with_prompt(
            smiles, pretrained_model, scaler, device, feat_cache
        )

    return graph


def prepare_single_inference(
    smiles: str,
    pretrained_model: torch.nn.Module,
    scaler,
    device: torch.device,
) -> tuple["dgl.DGLGraph", torch.Tensor, torch.Tensor]:
    """
    Full preprocessing pipeline for a single SMILES: compute features,
    build graph with prompts, prepare fingerprints and descriptors tensors.

    Returns (graph, fps_tensor, mds_tensor) ready for forward_tune().
    """
    import dgl
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys, AllChem
    from mordred import Calculator, descriptors
    from utils.aug import generate_oligomer_smiles
    from utils.function import preprocess_batch_light

    # Compute features for oligomers
    feat_cache = compute_fingerprints_and_descriptors(smiles)

    # Build graph with prompts
    graph = smiles_to_inference_graph(smiles, pretrained_model, scaler, device, feat_cache)

    # Compute base monomer fingerprint and descriptor for the base SMILES (1-mer)
    mol = Chem.MolFromSmiles(generate_oligomer_smiles(num_repeat_units=3, smiles=smiles))
    if mol is None:
        raise ValueError(f"Could not create molecule from oligomer of: {smiles}")

    maccs_fp = MACCSkeys.GenMACCSKeys(mol)
    ec_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 4, nBits=1024)
    fp = np.array(list(map(int, list(maccs_fp + ec_fp))), dtype=np.float32)

    calc = Calculator(descriptors, ignore_3D=True)
    md = np.array(list(calc(mol).values()), dtype=np.float32)
    md = np.where(np.isnan(md), 0, md)
    md = np.where(md > 1e12, 1e12, md)

    # Normalize descriptors
    md_norm = scaler.transform(md.reshape(1, -1)).astype(np.float32)

    fps = torch.from_numpy(fp.reshape(1, -1)).to(device)
    mds = torch.from_numpy(md_norm).to(device)

    # Prepare graph for batched processing
    graph.edata["path"][:, :] = preprocess_batch_light(
        graph.batch_num_nodes() if hasattr(graph, "batch_num_nodes") and callable(graph.batch_num_nodes) else torch.tensor([graph.number_of_nodes()]),
        graph.batch_num_edges() if hasattr(graph, "batch_num_edges") and callable(graph.batch_num_edges) else torch.tensor([graph.number_of_edges()]),
        graph.edata["path"][:, :],
    )
    graph = graph.to(device)

    return graph, fps, mds
