from __future__ import annotations

from dataclasses import dataclass

from app.models.instrument import Instrument


@dataclass(frozen=True)
class InstrumentMasterEntry:
    name: str
    sector: str
    instrument_type: str
    market_cap_bucket: str


INSTRUMENT_MASTER: dict[str, InstrumentMasterEntry] = {
    "ADANIGREEN": InstrumentMasterEntry("Adani Green Energy", "Energy", "EQUITY", "Large"),
    "BHARTIARTL": InstrumentMasterEntry("Bharti Airtel", "Telecom", "EQUITY", "Large"),
    "BHEL": InstrumentMasterEntry("BHEL", "Infra", "EQUITY", "Large"),
    "CIPLA": InstrumentMasterEntry("Cipla", "Pharma", "EQUITY", "Large"),
    "COFORGE": InstrumentMasterEntry("Coforge", "IT", "EQUITY", "Mid"),
    "DIVISLAB": InstrumentMasterEntry("Divis Laboratories", "Pharma", "EQUITY", "Large"),
    "DLF": InstrumentMasterEntry("DLF", "Real Estate", "EQUITY", "Large"),
    "DRREDDY": InstrumentMasterEntry("Dr Reddys Laboratories", "Pharma", "EQUITY", "Large"),
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
    "MUTHOOTFIN": InstrumentMasterEntry("Muthoot Finance", "Finance", "EQUITY", "Mid"),
    "NIFTYBEES": InstrumentMasterEntry("Nifty 50 ETF", "Index", "ETF", "Large"),
    "NTPC": InstrumentMasterEntry("NTPC", "Energy", "EQUITY", "Large"),
    "PERSISTENT": InstrumentMasterEntry("Persistent Systems", "IT", "EQUITY", "Mid"),
    "POWERGRID": InstrumentMasterEntry("Power Grid Corporation", "Energy", "EQUITY", "Large"),
    "RELIANCE": InstrumentMasterEntry("Reliance Industries", "Energy", "EQUITY", "Large"),
    "SBIN": InstrumentMasterEntry("State Bank of India", "Banking", "EQUITY", "Large"),
    "SILVERBEES": InstrumentMasterEntry("Silver ETF", "Silver", "ETF", "Large"),
    "SUNPHARMA": InstrumentMasterEntry("Sun Pharma", "Pharma", "EQUITY", "Large"),
    "TATAMOTORS": InstrumentMasterEntry("Tata Motors", "Auto", "EQUITY", "Large"),
    "TCS": InstrumentMasterEntry("Tata Consultancy Services", "IT", "EQUITY", "Large"),
    "ZOMATO": InstrumentMasterEntry("Zomato", "Tech/Internet", "EQUITY", "Mid"),
}


def enrich_instrument_from_master(instrument: Instrument) -> None:
    entry = INSTRUMENT_MASTER.get(instrument.symbol.upper())
    if entry is None:
        if not instrument.instrument_type:
            instrument.instrument_type = "ETF" if instrument.symbol.upper().endswith("BEES") else "EQUITY"
        return

    if not instrument.name:
        instrument.name = entry.name
    if not instrument.sector:
        instrument.sector = entry.sector
    if not instrument.instrument_type:
        instrument.instrument_type = entry.instrument_type
    if not instrument.market_cap_bucket:
        instrument.market_cap_bucket = entry.market_cap_bucket
