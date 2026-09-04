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
# Berita pasar/ekonomi
NEWS_FEEDS = [
    "https://www.cnbcindonesia.com/market/rss",
    "https://www.cnbcindonesia.com/news/rss",
    "https://www.antaranews.com/rss/ekonomi.xml",
]

# Berita politik (penting karena user minta pertimbangan gejolak politik)
POLITICS_FEEDS = [
    "https://www.antaranews.com/rss/politik.xml",
    "https://www.cnbcindonesia.com/news/rss",
]

# Berapa jam ke belakang berita yang dianggap relevan ("hari ini dan kemarin")
NEWS_LOOKBACK_HOURS = 48

# --- PARAMETER TEKNIKAL ---
PRICE_HISTORY_DAYS = 90          # ambil 90 hari data harga untuk hitung indikator
TOP_N_MOVERS = 15                # jumlah saham "paling menarik" yang dikirim ke AI agent
RSI_PERIOD = 14

# --- PROFIL RISIKO ---
# Ditetapkan tetap "agresif" sesuai permintaan user. Bisa dibuat dinamis nanti
# kalau mau multi-profil per user.
RISK_PROFILE = "agresif"

# --- JADWAL ---
# Jam berapa saja pipeline boleh jalan (WIB, format 24 jam). Sesuaikan waktu
# cron/GitHub Actions di .github/workflows/daily.yml supaya cocok dengan ini.
SCHEDULE_TIMES_WIB = ["09:00", "13:00", "16:00"]

# IDX buka Senin-Jumat, sesi 1 ~09:00-11:30 WIB, sesi 2 ~13:30-15:00+ WIB
# (Jumat sedikit beda). Pipeline akan skip otomatis di luar hari bursa.
MARKET_OPEN_WEEKDAYS = {0, 1, 2, 3, 4}  # Senin=0 ... Jumat=4 (Sabtu/Minggu libur)

# Tanggal libur bursa IDX (hari kerja yang TETAP libur karena hari besar dsb).
# WAJIB diupdate tiap tahun -- cek kalender libur bursa resmi dari idx.co.id.
# Format: "YYYY-MM-DD"
IDX_HOLIDAYS = [
    # Contoh -- isi/ganti sesuai kalender libur bursa IDX tahun berjalan
    # "2026-01-01",
    # "2026-03-19",
]

# --- OUTPUT ---
OUTPUT_JSON_PATH = "output/daily_digest.json"

# --- ANTHROPIC API ---
# Model Claude yang dipakai AI agent. Diisi lewat environment variable
# ANTHROPIC_API_KEY, jangan hardcode di sini.
CLAUDE_MODEL = "claude-sonnet-4-6"
