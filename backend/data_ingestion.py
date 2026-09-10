"""
data_ingestion.py
Mengambil data harga saham (yfinance, ticker .JK) + berita (RSS) yang akan
dipakai AI agent untuk analisis harian.

Ganti fungsi fetch_price_data() kalau nanti upgrade ke provider berbayar
(Sectors.app / Invezgo / dll) -- struktur output (list of dict) dibuat
konsisten supaya ai_agent.py tidak perlu diubah.
"""

import datetime as dt
import logging
from typing import Any

import feedparser
import pandas as pd
import yfinance as yf

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _atr(hist: pd.DataFrame, period: int = 14) -> float:
    """Average True Range -- ukuran seberapa 'liar' saham bergerak harian
    (dalam Rupiah). Dipakai AI untuk menentukan stop loss yang proporsional
    per saham, bukan persentase tetap yang sama untuk semua saham.
    """
    high = hist["High"]
    low = hist["Low"]
    prev_close = hist["Close"].shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = true_range.rolling(period).mean()
    return round(float(atr.iloc[-1]), 1) if not atr.empty and not pd.isna(atr.iloc[-1]) else None


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else None


def fetch_price_data(tickers: list[str] = None) -> list[dict[str, Any]]:
    """Ambil harga historis + hitung indikator teknikal dasar per saham.

    Return: list of dict, satu dict per saham, siap dikirim ke AI agent.
    """
    tickers = tickers or config.STOCK_UNIVERSE
    results = []

    for code in tickers:
        yf_ticker = f"{code}.JK"
        try:
            hist = yf.Ticker(yf_ticker).history(period=f"{config.PRICE_HISTORY_DAYS}d")
            if hist.empty or len(hist) < 20:
                log.warning("Data kosong/terlalu pendek untuk %s, skip", code)
                continue

            close = hist["Close"]
            volume = hist["Volume"]

            last_close = float(close.iloc[-1])
            change_1d = round((last_close / float(close.iloc[-2]) - 1) * 100, 2) if len(close) > 1 else 0
            change_5d = round((last_close / float(close.iloc[-6]) - 1) * 100, 2) if len(close) > 5 else None
            change_20d = round((last_close / float(close.iloc[-21]) - 1) * 100, 2) if len(close) > 20 else None

            sma5 = round(float(close.rolling(5).mean().iloc[-1]), 1)
            sma20 = round(float(close.rolling(20).mean().iloc[-1]), 1)
            avg_vol_20 = float(volume.rolling(20).mean().iloc[-1])
            last_vol = float(volume.iloc[-1])
            vol_ratio = round(last_vol / avg_vol_20, 2) if avg_vol_20 else None

            results.append({
                "ticker": code,
                "last_close": last_close,
                "change_1d_pct": change_1d,
                "change_5d_pct": change_5d,
                "change_20d_pct": change_20d,
                "sma5": sma5,
                "sma20": sma20,
                "trend": "above_sma20" if last_close > sma20 else "below_sma20",
                "volume_vs_avg20": vol_ratio,
                "rsi14": _rsi(close, config.RSI_PERIOD),
                "atr14": _atr(hist),
            })
        except Exception as e:
            log.warning("Gagal ambil data %s: %s", code, e)
            continue

    return results


def fetch_market_index() -> dict[str, Any] | None:
    """Ambil level & perubahan IHSG (^JKSE) hari ini. Dipakai apa adanya (tidak
    lewat AI) supaya angka indeks selalu akurat, tidak berisiko salah ditulis ulang.
    """
    try:
        hist = yf.Ticker("^JKSE").history(period="5d")
        if hist.empty or len(hist) < 2:
            return None
        last = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        return {"value": round(last, 1), "change_pct": round((last / prev - 1) * 100, 2)}
    except Exception as e:
        log.warning("Gagal ambil data IHSG: %s", e)
        return None


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    """Ambil data fundamental dasar (P/E, PBV, ROE, DER, dividen) untuk 1 saham.
    Data yfinance untuk saham Indonesia kadang tidak lengkap -- field yang
    kosong diisi None, dan dicatat ringkasannya di 'data_note' biar transparan.
    """
    result = {
        "pe_ratio": None, "pbv_ratio": None, "roe_pct": None, "der_pct": None,
        "dividend_yield_pct": None, "last_dividend_value": None,
        "ex_dividend_date": None, "cum_dividend_date": None, "data_note": None,
    }
    missing = []
    try:
        info = yf.Ticker(f"{ticker}.JK").info
    except Exception as e:
        result["data_note"] = f"Gagal ambil data fundamental: {e}"
        return result

    def as_pct(key):
        v = info.get(key)
        return round(v * 100, 2) if isinstance(v, (int, float)) else None

    result["pe_ratio"] = info.get("trailingPE")
    if result["pe_ratio"] is None:
        missing.append("P/E")

    result["pbv_ratio"] = info.get("priceToBook")
    if result["pbv_ratio"] is None:
        missing.append("PBV")

    result["roe_pct"] = as_pct("returnOnEquity")
    if result["roe_pct"] is None:
        missing.append("ROE")

    der_raw = info.get("debtToEquity")
    result["der_pct"] = round(der_raw, 1) if isinstance(der_raw, (int, float)) else None
    if result["der_pct"] is None:
        missing.append("DER")

    result["dividend_yield_pct"] = as_pct("dividendYield")
    result["last_dividend_value"] = info.get("lastDividendValue")

    ex_ts = info.get("exDividendDate")
    if isinstance(ex_ts, (int, float)) and ex_ts > 0:
        ex_date = dt.datetime.utcfromtimestamp(ex_ts).date()
        result["ex_dividend_date"] = ex_date.isoformat()
        cum_date = ex_date - dt.timedelta(days=1)
        while cum_date.weekday() >= 5:  # mundur kalau kena Sabtu/Minggu
            cum_date -= dt.timedelta(days=1)
        result["cum_dividend_date"] = cum_date.isoformat()
    else:
        missing.append("tanggal dividen")

    if missing:
        result["data_note"] = "Data tidak lengkap dari sumber untuk: " + ", ".join(missing)

    return result


def fetch_fundamentals_batch(tickers: list[str]) -> dict[str, dict]:
    """Ambil fundamental untuk beberapa saham sekaligus -> dict {ticker: data}."""
    out = {}
    for t in tickers:
        try:
            out[t] = fetch_fundamentals(t)
        except Exception as e:
            log.warning("Gagal ambil fundamental %s: %s", t, e)
            out[t] = {"data_note": f"Gagal ambil data fundamental: {e}"}
    return out


def rank_top_movers(price_data: list[dict[str, Any]], top_n: int = None) -> list[dict[str, Any]]:
    """Pilih saham paling 'menarik' untuk profil agresif: gabungan volatilitas
    harian + lonjakan volume, supaya prompt ke AI agent tidak kebanyakan data.
    """
    top_n = top_n or config.TOP_N_MOVERS

    def score(d):
        vol_ratio = d.get("volume_vs_avg20") or 1
        change = abs(d.get("change_1d_pct") or 0)
        return (vol_ratio * 0.6) + (change * 0.4)

    ranked = sorted(price_data, key=score, reverse=True)
    return ranked[:top_n]


def _fetch_rss(feed_urls: list[str], lookback_hours: int) -> list[dict[str, str]]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    items = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                items.append({
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:300].strip(),
                    "source": parsed.feed.get("title", url),
                })
        except Exception as e:
            log.warning("Gagal ambil RSS %s: %s", url, e)
    return items


def fetch_market_news() -> list[dict[str, str]]:
    return _fetch_rss(config.NEWS_FEEDS, config.NEWS_LOOKBACK_HOURS)


def fetch_politics_news() -> list[dict[str, str]]:
    return _fetch_rss(config.POLITICS_FEEDS, config.NEWS_LOOKBACK_HOURS)


def build_context_bundle() -> dict[str, Any]:
    """Kumpulkan semua data mentah jadi satu bundle siap pakai oleh ai_agent.py."""
    log.info("Mengambil data harga saham...")
    price_data = fetch_price_data()
    top_movers = rank_top_movers(price_data)
    market_index = fetch_market_index()

    log.info("Mengambil data fundamental untuk kandidat teratas...")
    fundamentals = fetch_fundamentals_batch([m["ticker"] for m in top_movers])

    log.info("Mengambil berita pasar & ekonomi...")
    market_news = fetch_market_news()

    log.info("Mengambil berita politik...")
    politics_news = fetch_politics_news()

    return {
        "generated_at": dt.datetime.now().isoformat(),
        "market_index": market_index,
        "all_price_data": price_data,
        "top_movers": top_movers,
        "fundamentals": fundamentals,
        "market_news": market_news[:10],
        "politics_news": politics_news[:10],
    }


if __name__ == "__main__":
    bundle = build_context_bundle()
    log.info("Selesai. %d saham, %d berita pasar, %d berita politik.",
              len(bundle["all_price_data"]), len(bundle["market_news"]), len(bundle["politics_news"]))
