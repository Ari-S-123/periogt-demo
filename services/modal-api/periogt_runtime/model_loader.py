"""Load PerioGT pretrained and finetuned models from checkpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace

import torch

from .runtime_config import (
    add_src_dir_to_syspath,
    get_model_config_path,
    resolve_torch_device,
)

logger = logging.getLogger(__name__)

# Add vendored PerioGT source to path
add_src_dir_to_syspath()


@dataclass
class LoadedModels:
    """Container for loaded PerioGT models and metadata."""

    pretrained_model: torch.nn.Module | None = None
    finetuned_models: dict[str, torch.nn.Module] = field(default_factory=dict)
    property_index: dict = field(default_factory=dict)
    device: torch.device = field(default_factory=lambda: torch.device("cpu"))


def _make_args(backbone: str = "light", config: str = "base",
               model_path: str = "", dropout: float = 0.0,
               device: str = "cuda") -> SimpleNamespace:
    """Create an args namespace matching what PerioGT's get_model() expects."""
    return SimpleNamespace(
        backbone=backbone,
        config=config,
        model_path=model_path,
        dropout=dropout,
        device=device,
        max_prompt=20,
    )


def load_pretrained_model(pretrained_ckpt_path: str, device: str = "cuda") -> torch.nn.Module:
    """
    Load the pretrained LiGhTPredictor model for embedding generation.

    The pretrained model retains all heads (node_predictor, fp_predictor,
    md_predictor, cl_projector) and is used via generate_node_emb().
    """
    from data.vocab import Vocab
    from models.light import LiGhTPredictor
    from utils.function import load_config

    args = _make_args(model_path=pretrained_ckpt_path, device=device)

    # Load config from the vendored config.yaml
    config = load_config(args, file_path=str(get_model_config_path()))

    vocab = Vocab()
    dev = resolve_torch_device(device)

    model = LiGhTPredictor(
        d_node_feats=config["d_node_feats"],
        d_edge_feats=config["d_edge_feats"],
        d_g_feats=config["d_g_feats"],
        d_fp_feats=1191,
        d_md_feats=1613,
        d_hpath_ratio=config["d_hpath_ratio"],
        n_mol_layers=config["n_mol_layers"],
        path_length=config["path_length"],
        n_heads=config["n_heads"],
        n_ffn_dense_layers=config["n_ffn_dense_layers"],
        input_drop=0,
        attn_drop=0,
        feat_drop=0,
        n_node_types=vocab.vocab_size,
    ).to(dev)

    state_dict = torch.load(pretrained_ckpt_path, map_location=dev)
    # Strip 'module.' prefix from DataParallel keys
    state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
    model.load_state_dict(state_dict, strict=False)
    model.eval()

    logger.info("Pretrained model loaded from %s", pretrained_ckpt_path)
    return model


def load_finetuned_model(finetuned_ckpt_path: str, device: str = "cuda",
                         dropout: float = 0.0) -> torch.nn.Module:
    """
    Load a finetuned LiGhTPredictor model for property prediction.

    This follows the same pattern as get_model_evaluation.py:
    - Creates a fresh LiGhTPredictor
    - Replaces pretrain heads with predictor + node_attn
    - Loads finetuned weights
    """
    from models.get_model_evaluation import get_model

    args = _make_args(
        model_path=finetuned_ckpt_path,
        device=device,
        dropout=dropout,
    )

    model = get_model(args)
    model.eval()

    logger.info("Finetuned model loaded from %s", finetuned_ckpt_path)
    return model


def load_all_models(property_index: dict, pretrained_dir: str,
                    device: str = "cuda") -> LoadedModels:
    """
    Load pretrained model and all finetuned models specified in the property index.

    Args:
        property_index: Mapping from property ID to checkpoint info.
        pretrained_dir: Directory containing pretrained checkpoint(s).
        device: Device to load models onto.

    Returns:
        LoadedModels with pretrained and finetuned models ready for inference.
    """
    import glob
    import os

    dev = resolve_torch_device(device)
    loaded = LoadedModels(property_index=property_index, device=dev)

    # Find pretrained checkpoint
    pretrained_candidates = glob.glob(os.path.join(pretrained_dir, "**/*.pth"), recursive=True)
    if not pretrained_candidates:
        logger.error("No pretrained checkpoint found in %s", pretrained_dir)
        return loaded

    pretrained_path = pretrained_candidates[0]
    loaded.pretrained_model = load_pretrained_model(pretrained_path, device)

    # Load finetuned models for each property
    for prop_id, info in property_index.items():
        ckpt_path = info["checkpoint"]
        if os.path.exists(ckpt_path):
            try:
                model = load_finetuned_model(ckpt_path, device)
                loaded.finetuned_models[prop_id] = model
                logger.info("Loaded finetuned model for property: %s", prop_id)
            except Exception as e:
                logger.error("Failed to load model for %s: %s", prop_id, e)
        else:
            logger.warning("Checkpoint not found for %s: %s", prop_id, ckpt_path)

    logger.info(
        "Model loading complete. Pretrained: %s, Finetuned properties: %s",
        pretrained_path,
        list(loaded.finetuned_models.keys()),
    )
    return loaded
