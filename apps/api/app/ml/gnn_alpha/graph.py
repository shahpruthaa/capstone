from __future__ import annotations
import logging
from typing import Any
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.instrument import Instrument
from app.services.instrument_master import INSTRUMENT_MASTER

logger = logging.getLogger(__name__)

def build_sector_graph(db: Session, symbols: list[str]) -> dict[str, Any]:
    """
    Build a sector correlation graph using the instrument master.
    Nodes = stocks, edges = same sector (fully connected within sector).
    """
    symbol_to_sector: dict[str, str] = {}
    for sym in symbols:
        entry = INSTRUMENT_MASTER.get(sym.upper())
        if entry and entry.sector:
            symbol_to_sector[sym] = entry.sector
        else:
            # fallback to DB sector
            row = db.execute(
                select(Instrument.sector).where(Instrument.symbol == sym)
            ).first()
            symbol_to_sector[sym] = (row[0] if row and row[0] else "Unknown")

    sectors = sorted(set(symbol_to_sector.values()))
    sector_to_idx = {s: i for i, s in enumerate(sectors)}

    node_symbols = list(symbols)
    node_features = []
    for sym in node_symbols:
        sector = symbol_to_sector.get(sym, "Unknown")
        onehot = [0.0] * len(sectors)
        onehot[sector_to_idx[sector]] = 1.0
        node_features.append(onehot)

    edges_src: list[int] = []
    edges_dst: list[int] = []
    sector_groups: dict[str, list[int]] = {}
    for idx, sym in enumerate(node_symbols):
        sec = symbol_to_sector.get(sym, "Unknown")
        sector_groups.setdefault(sec, []).append(idx)

    for sec, idxs in sector_groups.items():
        for i in idxs:
            for j in idxs:
                if i != j:
                    edges_src.append(i)
                    edges_dst.append(j)

    sector_counts = {s: len(idxs) for s, idxs in sector_groups.items()}
    logger.info(f"Graph: {len(node_symbols)} nodes, {len(edges_src)} edges, {len(sectors)} sectors")
    logger.info(f"Sector breakdown: {sector_counts}")

    return {
        "node_symbols": node_symbols,
        "node_features": np.array(node_features, dtype=np.float32),
        "edges_src": np.array(edges_src, dtype=np.int64),
        "edges_dst": np.array(edges_dst, dtype=np.int64),
        "sector_to_idx": sector_to_idx,
        "symbol_to_sector": symbol_to_sector,
    }
