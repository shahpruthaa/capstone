from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F


class GCNLayer(nn.Module):
    """Simple graph convolution: aggregates neighbour features."""
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        agg = torch.matmul(adj, x)
        return F.relu(self.linear(agg))


class GCNEncoder(nn.Module):
    """
    Two-layer GCN that maps node features -> embeddings.
    Used to encode inter-stock sector relationships.
    """
    def __init__(self, in_dim: int, hidden_dim: int = 32, out_dim: int = 16):
        super().__init__()
        self.conv1 = GCNLayer(in_dim, hidden_dim)
        self.conv2 = GCNLayer(hidden_dim, out_dim)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, adj)
        x = self.conv2(x, adj)
        return x


def build_adjacency_matrix(edges_src: list[int], edges_dst: list[int], n_nodes: int) -> torch.Tensor:
    """Build normalised adjacency matrix with self-loops."""
    adj = torch.zeros(n_nodes, n_nodes)
    for s, d in zip(edges_src, edges_dst):
        adj[s, d] = 1.0
    adj = adj + torch.eye(n_nodes)
    deg = adj.sum(dim=1, keepdim=True).clamp(min=1.0)
    return adj / deg
