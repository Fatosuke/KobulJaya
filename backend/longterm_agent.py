"""
longterm_agent.py
Riset MINGGUAN (bukan 3x sehari) khusus untuk Investasi Jangka Panjang (~6 bulan).

Kenapa terpisah dari scheduler.py/ai_agent.py: rekomendasi jangka panjang
seharusnya STABIL -- tidak masuk akal kalau daftarnya berubah tiap beberapa jam
kayak day trade/swing trade. Script ini jalan 1x seminggu (lihat
.github/workflows/weekly-longterm.yml), melakukan riset lebih dalam karena
punya waktu lebih longgar:
1. Ambil fundamental untuk seluruh universe saham.
2. Saring kasar (heuristik sederhana, BUKAN AI) jadi shortlist kandidat kuat.
3. Ambil berita SPESIFIK per perusahaan (bukan cuma berita pasar umum) untuk
   tiap kandidat di shortlist.
4. Kirim semua itu ke Gemini, minta RANKING 1-10 dengan skor "worth to buy".

Hasilnya disimpan di backend/output/longterm_digest.json, terpisah dari
daily_digest.json (yang isinya day_trade & swing_trade, tetap update 3x/hari).
"""

import datetime as dt
import json
import logging
import os
import time
import urllib.parse

import feedparser
from google import genai
from google.genai import types

import config
import data_ingestion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(_BACKEND_DIR, "output", "longterm_digest.json")

SHORTLIST_SIZE = 20  # jumlah kandidat yang lolos saringan kasar & dapat riset berita
COMPANY_NEWS_LOOKBACK_DAYS = 30

DISCLAIMER = (
    "Ini adalah hasil analisis otomatis berbasis AI, BUKAN nasihat investasi resmi. "
    "Skor 'worth to buy' adalah estimasi kualitatif AI, bukan jaminan/prediksi ilmiah. "
    "Selalu lakukan riset mandiri (DYOR) dan pertimbangkan risiko sebelum bertransaksi."
)

SYSTEM_PROMPT = """Kamu adalah analis ekuitas untuk investor Indonesia dengan horizon INVESTASI
JANGKA PANJANG (sekitar 6 bulan ke depan), profil risiko agresif tapi tetap berbasis fundamental.

PENTING: Analisis ini di-review MINGGUAN (bukan tiap beberapa jam), jadi harus benar-benar
mempertimbangkan hal yang relevan untuk horizon panjang -- BUKAN sekadar momentum harga hari ini.

Tugasmu: dari daftar kandidat saham yang diberikan (lengkap dengan data fundamental & berita
spesifik masing-masing perusahaan), pilih dan RANKING 1 sampai 10 saham paling layak
dipertimbangkan untuk investasi jangka panjang, urut dari #1 (paling worth-to-buy) sampai #10.

Pertimbangkan untuk tiap kandidat:
- Fundamental: P/E, PBV, ROE, DER, dividend yield -- kalau data kosong, boleh tetap
  dipertimbangkan dari sisi lain, tapi JANGAN mengarang angka yang tidak ada di data.
- Proyek/inisiatif perusahaan yang disebut di berita spesifik perusahaan tsb (ekspansi,
  akuisisi, produk baru, dll) -- kalau tidak ada berita relevan, katakan itu apa adanya.
- Kondisi ekonomi & politik Indonesia saat ini sebagai tailwind/headwind sektor tsb.
- Profil dividen (histori & yield) sebagai bagian dari total return jangka panjang.

Untuk tiap saham, berikan "worth_to_buy_pct" (0-100) sebagai skor keyakinan AI -- BUKAN
prediksi ilmiah/jaminan, murni estimasi kualitatif berdasarkan data yang ada.

Boleh mengembalikan kurang dari 10 saham kalau memang tidak cukup kandidat meyakinkan --
jangan memaksakan skor tinggi ke saham yang datanya lemah.

Balas HANYA dengan JSON valid sesuai skema di bawah, tanpa teks lain, tanpa markdown fences:
{
  "ranking": [
    {
      "rank": 1,
      "ticker": "",
      "worth_to_buy_pct": 82,
      "fundamental_note": "ringkasan 1 kalimat",
      "company_project_note": "ringkasan 1 kalimat dari berita perusahaan, atau catat kalau memang tidak ada berita signifikan",
      "economic_note": "ringkasan 1 kalimat soal konteks ekonomi/sektor",
      "dividend_note": "ringkasan 1 kalimat soal profil dividen"
    }
  ]
}
"""


def prefilter_candidates(price_data: list[dict], fundamentals: dict[str, dict], top_n: int) -> list[str]:
    """Saringan kasar berbasis ATURAN SEDERHANA (bukan AI) -- cuma buat mempersempit
    daftar sebelum riset berita per-perusahaan yang lebih berat, supaya nggak
    boros memanggil sumber berita untuk 60+ saham sekaligus.
    """
    scored = []
    for p in price_data:
        ticker = p["ticker"]
        f = fundamentals.get(ticker, {})
        score = 0
        if p.get("trend") == "above_sma20":
            score += 1
        if (p.get("change_20d_pct") or 0) > 0:
            score += 1
        roe = f.get("roe_pct")
        if roe is not None and roe > 10:
            score += 2
        pe = f.get("pe_ratio")
        if pe is not None and 0 < pe < 30:
            score += 1
        der = f.get("der_pct")
        if der is not None and der < 150:
            score += 1
        div_yield = f.get("dividend_yield_pct")
        if div_yield is not None and div_yield > 1:
            score += 1
        scored.append((score, ticker))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ticker for _, ticker in scored[:top_n]]


def fetch_company_news(ticker: str) -> list[dict]:
    """Berita SPESIFIK per perusahaan (bukan berita pasar umum) lewat pencarian
    Google News RSS -- gratis, tanpa API key.
    """
    try:
        query = f"{ticker} saham"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=id-ID&gl=ID&ceid=ID:id"
        parsed = feedparser.parse(url)
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=COMPANY_NEWS_LOOKBACK_DAYS)

        items = []
        for entry in parsed.entries[:8]:
            published = entry.get("published_parsed")
            if published:
                pub_dt = dt.datetime(*published[:6], tzinfo=dt.timezone.utc)
                if pub_dt < cutoff:
                    continue
            items.append({"title": entry.get("title", "").strip()})
        return items
    except Exception as e:
        log.warning("Gagal ambil berita perusahaan %s: %s", ticker, e)
        return []


def build_longterm_prompt(candidates_data, company_news, market_news, politics_news) -> str:
    return f"""KANDIDAT SAHAM (data teknikal + fundamental):
{json.dumps(candidates_data, ensure_ascii=False, indent=2)}

BERITA SPESIFIK PER PERUSAHAAN ({COMPANY_NEWS_LOOKBACK_DAYS} hari terakhir, per ticker):
{json.dumps(company_news, ensure_ascii=False, indent=2)}

BERITA EKONOMI UMUM:
{json.dumps(market_news, ensure_ascii=False, indent=2)}

BERITA POLITIK:
{json.dumps(politics_news, ensure_ascii=False, indent=2)}

Tanggal analisis: {dt.date.today().isoformat()}
Horizon: sekitar 6 bulan ke depan, akan di-review lagi minggu depan.

Hasilkan ranking sesuai skema JSON yang dijelaskan di system prompt.
"""


def call_gemini(prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY belum di-set.")

    client = genai.Client(api_key=api_key)
    last_error = None

    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            log.warning("Percobaan %d/3 gagal manggil Gemini: %s", attempt, e)
            if attempt < 3:
                time.sleep(5 * attempt)

    raise RuntimeError(f"Gagal manggil Gemini setelah 3x percobaan: {last_error}") from last_error


def run_longterm_pipeline():
    log.info("=== Mulai riset mingguan Investasi Jangka Panjang ===")

    price_data = data_ingestion.fetch_price_data()
    price_lookup = {p["ticker"]: p for p in price_data}

    log.info("Mengambil data fundamental untuk %d saham di universe...", len(price_data))
    fundamentals = data_ingestion.fetch_fundamentals_batch([p["ticker"] for p in price_data])

    shortlist = prefilter_candidates(price_data, fundamentals, SHORTLIST_SIZE)
    log.info("Shortlist %d kandidat: %s", len(shortlist), ", ".join(shortlist))

    candidates_data = [
        {
            "ticker": t,
            "last_close": price_lookup[t]["last_close"],
            "change_20d_pct": price_lookup[t]["change_20d_pct"],
            "trend": price_lookup[t]["trend"],
            "fundamentals": fundamentals.get(t, {}),
        }
        for t in shortlist
    ]

    log.info("Mengambil berita spesifik per perusahaan untuk shortlist...")
    company_news = {t: fetch_company_news(t) for t in shortlist}

    market_news = data_ingestion.fetch_market_news()[:10]
    politics_news = data_ingestion.fetch_politics_news()[:10]

    prompt = build_longterm_prompt(candidates_data, company_news, market_news, politics_news)
    log.info("Memanggil Gemini untuk ranking...")
    result = call_gemini(prompt)

    # Tempel harga & fundamental AKURAT (bukan dari tulisan AI)
    for item in result.get("ranking", []):
        ticker = item.get("ticker")
        item["price_at_review"] = price_lookup.get(ticker, {}).get("last_close")
        item["fundamentals"] = fundamentals.get(ticker, {})

    today = dt.date.today()
    output = {
        "generated_at": dt.datetime.now().isoformat(),
        "review_date": today.isoformat(),
        "next_review_date": (today + dt.timedelta(days=7)).isoformat(),
        "horizon_note": (
            "Analisis untuk horizon investasi ~6 bulan. Di-review ulang tiap minggu "
            "(bukan tiap beberapa jam) supaya rankingnya stabil dan bisa dijadikan "
            "pegangan jangka panjang, bukan gonta-ganti tiap saat."
        ),
        "disclaimer": DISCLAIMER,
        "ranking": result.get("ranking", []),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("Selesai. Disimpan ke %s (%d saham di-ranking)", OUTPUT_PATH, len(output["ranking"]))

    return output


if __name__ == "__main__":
    run_longterm_pipeline()
