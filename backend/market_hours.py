"""
market_hours.py
Cek apakah hari ini hari bursa (Senin-Jumat, bukan tanggal libur IDX).

Pengecekan JAM (09:00/13:00/16:00) sengaja diserahkan ke penjadwal (cron/GitHub
Actions) -- lihat .github/workflows/daily.yml. Modul ini jadi lapisan pengaman
kedua supaya kalau cron kepicu di hari libur (yang cron sendiri tidak tahu),
pipeline tetap skip dan tidak buang-buang API call.
"""

import datetime as dt

import config


def is_trading_day(date: dt.date = None) -> bool:
    date = date or dt.date.today()
    if date.weekday() not in config.MARKET_OPEN_WEEKDAYS:
        return False
    if date.isoformat() in config.IDX_HOLIDAYS:
        return False
    return True


def skip_reason(date: dt.date = None) -> str | None:
    """Return alasan skip kalau bukan hari bursa, atau None kalau boleh jalan."""
    date = date or dt.date.today()
    if date.weekday() not in config.MARKET_OPEN_WEEKDAYS:
        return f"{date.isoformat()} adalah akhir pekan, bursa tutup."
    if date.isoformat() in config.IDX_HOLIDAYS:
        return f"{date.isoformat()} adalah tanggal libur bursa (lihat config.IDX_HOLIDAYS)."
    return None
