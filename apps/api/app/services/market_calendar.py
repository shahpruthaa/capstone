from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")
PRE_OPEN_START = time(9, 0)
NORMAL_OPEN = time(9, 15)
NORMAL_CLOSE = time(15, 30)
POST_CLOSE_END = time(16, 0)
BHAVCOPY_READY_AFTER = time(18, 30)

# Sources:
# - NSE CM trading holidays circular dated 2024-12-13 for calendar year 2025.
# - NSE CM trading holidays circular dated 2025-12-12 for calendar year 2026.
NSE_CM_TRADING_HOLIDAYS: dict[int, dict[date, str]] = {
    2025: {
        date(2025, 2, 26): "Mahashivratri",
        date(2025, 3, 14): "Holi",
        date(2025, 3, 31): "Id-Ul-Fitr (Ramadan Eid)",
        date(2025, 4, 10): "Shri Mahavir Jayanti",
        date(2025, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
        date(2025, 4, 18): "Good Friday",
        date(2025, 5, 1): "Maharashtra Day",
        date(2025, 8, 15): "Independence Day",
        date(2025, 8, 27): "Ganesh Chaturthi",
        date(2025, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
        date(2025, 10, 21): "Diwali Laxmi Pujan (Muhurat trading only)",
        date(2025, 10, 22): "Diwali-Balipratipada",
        date(2025, 11, 5): "Prakash Gurpurb Sri Guru Nanak Dev",
        date(2025, 12, 25): "Christmas",
    },
    2026: {
        date(2026, 1, 26): "Republic Day",
        date(2026, 3, 3): "Holi",
        date(2026, 3, 26): "Shri Ram Navami",
        date(2026, 3, 31): "Shri Mahavir Jayanti",
        date(2026, 4, 3): "Good Friday",
        date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
        date(2026, 5, 1): "Maharashtra Day",
        date(2026, 5, 28): "Bakri Id",
        date(2026, 6, 26): "Muharram",
        date(2026, 9, 14): "Ganesh Chaturthi",
        date(2026, 10, 2): "Mahatma Gandhi Jayanti",
        date(2026, 10, 20): "Dussehra",
        date(2026, 11, 10): "Diwali-Balipratipada",
        date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
        date(2026, 12, 25): "Christmas",
    },
}

SPECIAL_TRADING_DAYS: dict[date, str] = {
    date(2026, 2, 1): "Union Budget live trading session",
}

CALENDAR_SOURCE = "Official NSE capital-market holiday circulars for 2025 and 2026."


@dataclass(frozen=True)
class MarketSessionStatus:
    exchange: str
    timezone: str
    status: str
    label: str
    reason: str
    is_trading_day: bool
    session_date: date
    current_time: datetime
    next_open_at: datetime | None
    next_close_at: datetime | None
    holiday_name: str | None = None
    calendar_source: str = CALENDAR_SOURCE

    def to_payload(self) -> dict[str, object]:
        return {
            "exchange": self.exchange,
            "timezone": self.timezone,
            "status": self.status,
            "label": self.label,
            "reason": self.reason,
            "is_trading_day": self.is_trading_day,
            "session_date": self.session_date,
            "current_time": self.current_time,
            "next_open_at": self.next_open_at,
            "next_close_at": self.next_close_at,
            "holiday_name": self.holiday_name,
            "calendar_source": self.calendar_source,
        }


def _now_ist(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(IST)
    if now.tzinfo is None:
        return now.replace(tzinfo=IST)
    return now.astimezone(IST)


def get_holiday_name(trade_date: date) -> str | None:
    return NSE_CM_TRADING_HOLIDAYS.get(trade_date.year, {}).get(trade_date)


def is_nse_trading_day(trade_date: date) -> bool:
    if trade_date in SPECIAL_TRADING_DAYS:
        return True
    if trade_date.weekday() >= 5:
        return False
    return get_holiday_name(trade_date) is None


def previous_trading_day(anchor: date) -> date:
    current = anchor
    while not is_nse_trading_day(current):
        current -= timedelta(days=1)
    return current


def next_trading_day(anchor: date) -> date:
    current = anchor
    while not is_nse_trading_day(current):
        current += timedelta(days=1)
    return current


def latest_completed_trading_day(now: datetime | None = None) -> date:
    current_time = _now_ist(now)
    today = current_time.date()
    if is_nse_trading_day(today) and current_time.time() >= BHAVCOPY_READY_AFTER:
        return today
    return previous_trading_day(today - timedelta(days=1))


def get_market_session_status(now: datetime | None = None) -> MarketSessionStatus:
    current_time = _now_ist(now)
    today = current_time.date()
    holiday_name = get_holiday_name(today)
    special_day_note = SPECIAL_TRADING_DAYS.get(today)
    trading_day = is_nse_trading_day(today)

    if not trading_day:
        status = "HOLIDAY" if holiday_name else "WEEKEND"
        reason = holiday_name or "Weekend - NSE cash market closed."
        next_open_day = next_trading_day(today + timedelta(days=1))
        return MarketSessionStatus(
            exchange="NSE Capital Market",
            timezone="Asia/Kolkata",
            status=status,
            label="NSE Closed",
            reason=reason,
            is_trading_day=False,
            session_date=today,
            current_time=current_time,
            next_open_at=datetime.combine(next_open_day, PRE_OPEN_START, tzinfo=IST),
            next_close_at=datetime.combine(next_open_day, NORMAL_CLOSE, tzinfo=IST),
            holiday_name=holiday_name,
        )

    current_clock = current_time.time()
    if current_clock < PRE_OPEN_START:
        status = "CLOSED"
        label = "NSE Closed"
        reason = "Next session has not opened yet."
        next_open_at = datetime.combine(today, PRE_OPEN_START, tzinfo=IST)
        next_close_at = datetime.combine(today, NORMAL_CLOSE, tzinfo=IST)
    elif current_clock < NORMAL_OPEN:
        status = "PRE_OPEN"
        label = "NSE Pre-open"
        reason = "Pre-open auction is in progress."
        next_open_at = datetime.combine(today, PRE_OPEN_START, tzinfo=IST)
        next_close_at = datetime.combine(today, NORMAL_CLOSE, tzinfo=IST)
    elif current_clock <= NORMAL_CLOSE:
        status = "OPEN"
        label = "NSE Open"
        reason = "Normal market session is live."
        next_open_at = datetime.combine(today, PRE_OPEN_START, tzinfo=IST)
        next_close_at = datetime.combine(today, NORMAL_CLOSE, tzinfo=IST)
    elif current_clock <= POST_CLOSE_END:
        status = "POST_CLOSE"
        label = "NSE Post-close"
        reason = "Normal trading has ended; post-close session is active."
        next_open_day = next_trading_day(today + timedelta(days=1))
        next_open_at = datetime.combine(next_open_day, PRE_OPEN_START, tzinfo=IST)
        next_close_at = datetime.combine(today, POST_CLOSE_END, tzinfo=IST)
    else:
        status = "CLOSED"
        label = "NSE Closed"
        reason = "Today's trading session has ended."
        next_open_day = next_trading_day(today + timedelta(days=1))
        next_open_at = datetime.combine(next_open_day, PRE_OPEN_START, tzinfo=IST)
        next_close_at = datetime.combine(next_open_day, NORMAL_CLOSE, tzinfo=IST)

    if special_day_note:
        reason = f"{reason} {special_day_note}."

    return MarketSessionStatus(
        exchange="NSE Capital Market",
        timezone="Asia/Kolkata",
        status=status,
        label=label,
        reason=reason,
        is_trading_day=True,
        session_date=today,
        current_time=current_time,
        next_open_at=next_open_at,
        next_close_at=next_close_at,
        holiday_name=holiday_name,
    )
