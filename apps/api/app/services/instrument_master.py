from __future__ import annotations

from dataclasses import dataclass
import logging

from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

UNKNOWN_SECTOR = "Unknown"

# Canonical macro-sector labels used across ingestion, risk and graph topology.
VALID_MACRO_SECTORS: set[str] = {
    "IT",
    "Banking",
    "Finance",
    "FMCG",
    "Energy",
    "Pharma",
    "Auto",
    "Metals",
    "Consumer Durables",
    "Infra",
    "Telecom",
    "Cement",
    "Insurance",
    "Real Estate",
    "Chemicals",
    "Tech/Internet",
    "Logistics",
    "Tourism",
    "Gold",
    "Liquid",
    "Index",
    "Silver",
}

SECTOR_ALIASES: dict[str, str] = {
    "Consumer Staples": "FMCG",
}


@dataclass(frozen=True)
class InstrumentMasterEntry:
    name: str
    sector: str
    instrument_type: str
    market_cap_bucket: str


INSTRUMENT_MASTER: dict[str, InstrumentMasterEntry] = {
    "ADANIGREEN": InstrumentMasterEntry("Adani Green Energy", "Energy", "EQUITY", "Large"),
    "AETHER": InstrumentMasterEntry("Aether Industries", "Chemicals", "EQUITY", "Unknown"),
    "BHARTIARTL": InstrumentMasterEntry("Bharti Airtel", "Telecom", "EQUITY", "Large"),
    "BHEL": InstrumentMasterEntry("BHEL", "Infra", "EQUITY", "Large"),
    "CIPLA": InstrumentMasterEntry("Cipla", "Pharma", "EQUITY", "Large"),
    "COFORGE": InstrumentMasterEntry("Coforge", "IT", "EQUITY", "Mid"),
    "CONSOFINVT": InstrumentMasterEntry("Consolidated Finvest & Holdings", "Finance", "EQUITY", "Unknown"),
    "DIVISLAB": InstrumentMasterEntry("Divis Laboratories", "Pharma", "EQUITY", "Large"),
    "DLF": InstrumentMasterEntry("DLF", "Real Estate", "EQUITY", "Large"),
    "DRREDDY": InstrumentMasterEntry("Dr Reddys Laboratories", "Pharma", "EQUITY", "Large"),
    "GESHIP": InstrumentMasterEntry("Great Eastern Shipping", "Logistics", "EQUITY", "Unknown"),
    "GOLDBEES": InstrumentMasterEntry("Nippon Gold ETF", "Gold", "ETF", "Large"),
    "HDFCBANK": InstrumentMasterEntry("HDFC Bank", "Banking", "EQUITY", "Large"),
    "HINDUNILVR": InstrumentMasterEntry("Hindustan Unilever", "FMCG", "EQUITY", "Large"),
    "ICICIBANK": InstrumentMasterEntry("ICICI Bank", "Banking", "EQUITY", "Large"),
    "INDUSINDBK": InstrumentMasterEntry("IndusInd Bank", "Banking", "EQUITY", "Large"),
    "INFY": InstrumentMasterEntry("Infosys", "IT", "EQUITY", "Large"),
    "ITC": InstrumentMasterEntry("ITC", "FMCG", "EQUITY", "Large"),
    "JUNIORBEES": InstrumentMasterEntry("Nifty Next 50 ETF", "Index", "ETF", "Large"),
    "KPITTECH": InstrumentMasterEntry("KPIT Technologies", "IT", "EQUITY", "Mid"),
    "LIQUIDBEES": InstrumentMasterEntry("Nippon Liquid ETF", "Liquid", "ETF", "Large"),
    "LT": InstrumentMasterEntry("Larsen & Toubro", "Infra", "EQUITY", "Large"),
    "MARUTI": InstrumentMasterEntry("Maruti Suzuki", "Auto", "EQUITY", "Large"),
    "MBAPL": InstrumentMasterEntry("Madhya Bharat Agro Products", "Chemicals", "EQUITY", "Unknown"),
    "MUTHOOTFIN": InstrumentMasterEntry("Muthoot Finance", "Finance", "EQUITY", "Mid"),
    "NATIONALUM": InstrumentMasterEntry("National Aluminium Company", "Metals", "EQUITY", "Unknown"),
    "NIFTYBEES": InstrumentMasterEntry("Nifty 50 ETF", "Index", "ETF", "Large"),
    "NTPC": InstrumentMasterEntry("NTPC", "Energy", "EQUITY", "Large"),
    "PERSISTENT": InstrumentMasterEntry("Persistent Systems", "IT", "EQUITY", "Mid"),
    "PFIZER": InstrumentMasterEntry("Pfizer", "Pharma", "EQUITY", "Unknown"),
    "POWERGRID": InstrumentMasterEntry("Power Grid Corporation", "Energy", "EQUITY", "Large"),
    "RELIANCE": InstrumentMasterEntry("Reliance Industries", "Energy", "EQUITY", "Large"),
    "SANSERA": InstrumentMasterEntry("Sansera Engineering", "Auto", "EQUITY", "Unknown"),
    "SBIN": InstrumentMasterEntry("State Bank of India", "Banking", "EQUITY", "Large"),
    "SEAMECLTD": InstrumentMasterEntry("Seamec", "Logistics", "EQUITY", "Unknown"),
    "SILVERBEES": InstrumentMasterEntry("Silver ETF", "Silver", "ETF", "Large"),
    "SUNPHARMA": InstrumentMasterEntry("Sun Pharma", "Pharma", "EQUITY", "Large"),
    "TATAMOTORS": InstrumentMasterEntry("Tata Motors", "Auto", "EQUITY", "Large"),
    "TCS": InstrumentMasterEntry("Tata Consultancy Services", "IT", "EQUITY", "Large"),
    "TMB": InstrumentMasterEntry("Tamilnad Mercantile Bank", "Banking", "EQUITY", "Unknown"),
    "UJJIVANSFB": InstrumentMasterEntry("Ujjivan Small Finance Bank", "Banking", "EQUITY", "Unknown"),
    "ZOMATO": InstrumentMasterEntry("Zomato", "Tech/Internet", "EQUITY", "Mid"),
}


def normalize_macro_sector(sector: str | None) -> str | None:
    if sector is None:
        return None
    cleaned = sector.strip()
    if not cleaned:
        return None
    if cleaned.casefold() == UNKNOWN_SECTOR.casefold():
        return UNKNOWN_SECTOR
    canonical = SECTOR_ALIASES.get(cleaned, cleaned)
    return canonical if canonical in VALID_MACRO_SECTORS else None


def enrich_instrument_from_master(instrument: Instrument) -> None:
    entry = INSTRUMENT_MASTER.get(instrument.symbol.upper())
    if entry is None:
        if not instrument.instrument_type:
            instrument.instrument_type = "ETF" if instrument.symbol.upper().endswith("BEES") else "EQUITY"
        normalized_sector = normalize_macro_sector(instrument.sector)
        if normalized_sector is None:
            if (instrument.sector or "").strip().casefold() != UNKNOWN_SECTOR.casefold():
                logger.warning(
                    "Instrument %s ingested without valid macro-sector; flagging as Unknown",
                    instrument.symbol.upper(),
                )
            instrument.sector = UNKNOWN_SECTOR
        else:
            instrument.sector = normalized_sector
        return

    if not instrument.name:
        instrument.name = entry.name
    if not instrument.sector:
        instrument.sector = entry.sector
    if not instrument.instrument_type:
        instrument.instrument_type = entry.instrument_type
    if not instrument.market_cap_bucket:
        instrument.market_cap_bucket = entry.market_cap_bucket

    normalized_sector = normalize_macro_sector(instrument.sector)
    if normalized_sector is None:
        if (instrument.sector or "").strip().casefold() != UNKNOWN_SECTOR.casefold():
            logger.warning(
                "Instrument %s has invalid macro-sector '%s'; flagging as Unknown",
                instrument.symbol.upper(),
                instrument.sector,
            )
        instrument.sector = UNKNOWN_SECTOR
    else:
        instrument.sector = normalized_sector
