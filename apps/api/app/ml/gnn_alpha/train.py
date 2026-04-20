from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
import numpy as np
import torch
import torch.nn as nn
from torch.optim import Adam
from app.ml.gnn_alpha.model import GCNEncoder, build_adjacency_matrix

logger = logging.getLogger(__name__)


def train_gnn(
    graph: dict[str, Any],
    epochs: int = 100,
    hidden_dim: int = 32,
    out_dim: int = 16,
    lr: float = 0.01,
) -> dict[str, Any]:
    """
    Self-supervised GNN training.
    Objective: reconstruct the adjacency matrix (link prediction).
    Output: per-stock embeddings of shape [N, out_dim].
    """
    node_features = torch.tensor(graph["node_features"], dtype=torch.float32)
    edges_src = graph["edges_src"].tolist()
    edges_dst = graph["edges_dst"].tolist()
    n_nodes = len(graph["node_symbols"])
    in_dim = node_features.shape[1]

    adj = build_adjacency_matrix(edges_src, edges_dst, n_nodes)

    model = GCNEncoder(in_dim=in_dim, hidden_dim=hidden_dim, out_dim=out_dim)
    optimizer = Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    adj_binary = (adj > 0).float()

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        embeddings = model(node_features, adj)
        logits = torch.matmul(embeddings, embeddings.T)
        loss = criterion(logits, adj_binary)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 20 == 0:
            logger.info(f"GNN epoch {epoch+1}/{epochs}: loss={loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        final_embeddings = model(node_features, adj).numpy()

    symbol_to_embedding = {
        sym: final_embeddings[i].tolist()
        for i, sym in enumerate(graph["node_symbols"])
    }
    logger.info(f"GNN training complete. Embedding shape: {final_embeddings.shape}")
    return {
        "model": model,
        "embeddings": final_embeddings,
        "symbol_to_embedding": symbol_to_embedding,
        "loss": float(loss.item()),
    }


def save_gnn_artifacts(result: dict[str, Any], graph: dict[str, Any], artifact_dir: str | Path) -> None:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    torch.save(result["model"].state_dict(), artifact_dir / "gnn_model.pt")

    with (artifact_dir / "gnn_embeddings.json").open("w") as f:
        json.dump(result["symbol_to_embedding"], f, indent=2)

    meta = {
        "n_nodes": len(graph["node_symbols"]),
        "node_symbols": graph["node_symbols"],
        "out_dim": result["embeddings"].shape[1],
        "final_loss": result["loss"],
        "sector_to_idx": graph["sector_to_idx"],
    }
    with (artifact_dir / "gnn_metadata.json").open("w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"GNN artifacts saved to {artifact_dir}")
