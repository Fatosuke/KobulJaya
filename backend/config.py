"""
config.py
Konfigurasi pusat: universe saham yang di-screening, sumber berita,
dan parameter lain. Ubah di sini kalau mau ganti sumber data / cakupan saham.
"""

# --- UNIVERSE SAHAM ---
# Default: konstituen LQ45 + beberapa saham likuid populer (kode + suffix .JK
# untuk kompatibilitas yfinance). Untuk profil "agresif", universe ini sengaja
# mencakup saham dengan volatilitas lebih tinggi, bukan cuma blue chip.
STOCK_UNIVERSE = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "ICBP", "INDF",
    "KLBF", "ADRO", "PTBA", "ITMG", "ANTM", "INCO", "MDKA", "TINS",
    "GOTO", "BUKA", "EMTK", "BRPT", "TPIA", "AVIA", "AMRT", "MAPI",
    "CPIN", "JPFA", "SMGR", "INTP", "PGAS", "MEDC", "ELSA", "PGEO",
    "BRIS", "ARTO", "BBTN", "AKRA", "UNTR", "HRUM", "DEWA", "BUMI",
    "ACES", "ERAA", "SCMA", "MNCN", "CTRA",
]

# --- SUMBER BERITA (RSS) ---
NEWS_FEEDS = [
    "https://www.cnbcindonesia.com/market/rss",
    "https://www.cnbcindonesia.com/news/rss",
    "https://www.antaranews.com/rss/ekonomi.xml",
]

POLITICS_FEEDS = [
    "https://www.antaranews.com/rss/politik.xml",
    "https://www.cnbcindonesia.com/news/rss",
]

NEWS_LOOKBACK_HOURS = 48

# --- PARAMETER TEKNIKAL ---
PRICE_HISTORY_DAYS = 90
TOP_N_MOVERS = 15
RSI_PERIOD = 14

# --- PROFIL RISIKO ---
RISK_PROFILE = "agresif"

# --- JADWAL ---
SCHEDULE_TIMES_WIB = ["09:00", "13:00", "16:00"]
MARKET_OPEN_WEEKDAYS = {0, 1, 2, 3, 4}

IDX_HOLIDAYS = [
    # "2026-01-01",
    # "2026-03-19",
]

# --- OUTPUT ---
import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON_PATH = os.path.join(_BACKEND_DIR, "output", "daily_digest.json")

# --- GOOGLE GEMINI API (gratis, tanpa kartu kredit) ---
# Ambil API key gratis di aistudio.google.com -> "Get API key".
# Model "gemini-2.5-flash" ada di jatah gratis permanen Google (bukan trial).
GEMINI_MODEL = "gemini-3.6-flash"
