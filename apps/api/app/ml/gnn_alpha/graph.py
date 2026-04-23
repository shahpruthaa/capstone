from __future__ import annotations
import logging
from typing import Any
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.instrument import Instrument
from app.services.instrument_master import INSTRUMENT_MASTER, UNKNOWN_SECTOR, normalize_macro_sector

logger = logging.getLogger(__name__)

def build_sector_graph(db: Session, symbols: list[str]) -> dict[str, Any]:
    """
    Build a sector correlation graph using the instrument master.
    Nodes = stocks, edges = same sector (fully connected within sector).
    """
    upper_symbols = [sym.upper() for sym in symbols]
    db_rows = db.execute(
        select(func.upper(Instrument.symbol), Instrument.sector).where(func.upper(Instrument.symbol).in_(upper_symbols))
    ).all()
    db_symbol_to_sector = {row[0]: row[1] for row in db_rows}

    symbol_to_sector: dict[str, str] = {}
    for sym in symbols:
        sym_upper = sym.upper()
        entry = INSTRUMENT_MASTER.get(sym_upper)
        if entry and entry.sector:
            raw_sector = entry.sector
        else:
            raw_sector = db_symbol_to_sector.get(sym_upper)
        symbol_to_sector[sym] = normalize_macro_sector(raw_sector) or UNKNOWN_SECTOR

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
        sec = symbol_to_sector.get(sym, UNKNOWN_SECTOR)
        sector_groups.setdefault(sec, []).append(idx)

    for sec, idxs in sector_groups.items():
        if sec == UNKNOWN_SECTOR:
            # Strict topology: unknown sectors are isolated from message passing.
            continue
        for i in idxs:
            for j in idxs:
                if i != j:
                    edges_src.append(i)
                    edges_dst.append(j)

    sector_counts = {s: len(idxs) for s, idxs in sector_groups.items() if s != UNKNOWN_SECTOR}
    unknown_symbols = [sym for sym, sec in symbol_to_sector.items() if sec == UNKNOWN_SECTOR]

    logger.info(
        "Graph topology: %d nodes, %d edges, %d resolved sectors, %d unknown-sector nodes",
        len(node_symbols),
        len(edges_src),
        len(sector_counts),
        len(unknown_symbols),
    )
    logger.info("Resolved sector breakdown: %s", sector_counts)

    for sec, idxs in sector_groups.items():
        if sec == UNKNOWN_SECTOR:
            continue
        expected = len(idxs) * (len(idxs) - 1)
        logger.info(
            "Sector subgraph '%s': nodes=%d directed_edges=%d complete=%s",
            sec,
            len(idxs),
            expected,
            "yes",
        )

    if unknown_symbols:
        preview = ", ".join(sorted(unknown_symbols)[:25])
        suffix = "..." if len(unknown_symbols) > 25 else ""
        logger.warning("Unknown-sector nodes isolated (no edges): %s%s", preview, suffix)

    return {
        "node_symbols": node_symbols,
        "node_features": np.array(node_features, dtype=np.float32),
        "edges_src": np.array(edges_src, dtype=np.int64),
        "edges_dst": np.array(edges_dst, dtype=np.int64),
        "sector_to_idx": sector_to_idx,
        "symbol_to_sector": symbol_to_sector,
    }
