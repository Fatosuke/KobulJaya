"""
ai_agent.py
"Otak" analisis: mengubah data mentah (harga + berita) jadi rekomendasi
terstruktur untuk 3 profil trader, lewat panggilan ke Google Gemini API
(gratis, tanpa kartu kredit -- lihat README untuk cara ambil API key-nya).

Penting: agent ini HANYA boleh menganalisis berdasarkan data yang diberikan
di prompt (tidak boleh mengarang harga/berita), dan wajib menyertakan
disclaimer di setiap output.
"""

import json
import logging
import os
import time
import urllib.request

from google import genai
from google.genai import types

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_JOURNAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal.json")


def load_journal_summary() -> str:
    """Ambil jurnal transaksi kamu -- dari spreadsheet Google (kalau
    config.JOURNAL_SHEET_URL sudah diisi) atau dari backend/journal.json
    (fallback manual) -- lalu ringkas jadi teks singkat buat AI, supaya
    rekomendasi kedepannya bisa menyesuaikan gaya & histori kamu. Kalau
    dua-duanya tidak tersedia, AI jalan seperti biasa tanpa personalisasi.
    """
    entries = []
    sheet_url = getattr(config, "JOURNAL_SHEET_URL", "")

    if sheet_url:
        try:
            with urllib.request.urlopen(sheet_url, timeout=15) as resp:
                raw = json.loads(resp.read().decode())
            entries = [
                {
                    "ticker": r.get("Ticker"),
                    "buy_price": r.get("HargaBeli"),
                    "sell_price": r.get("HargaJual") or None,
                }
                for r in raw
                if r.get("Ticker")
            ]
        except Exception as e:
            log.warning("Gagal ambil jurnal dari spreadsheet: %s", e)
    elif os.path.exists(_JOURNAL_PATH):
        try:
            with open(_JOURNAL_PATH) as f:
                entries = json.load(f)
        except Exception as e:
            log.warning("Gagal baca journal.json, dilewati: %s", e)

    if not entries:
        return ""

    closed = [e for e in entries if e.get("sell_price")]
    wins = [e for e in closed if float(e["sell_price"]) > float(e["buy_price"])]
    tickers_bought = sorted(set(e["ticker"] for e in entries if e.get("ticker")))
    return (
        f"Histori transaksi user: {len(entries)} catatan, {len(closed)} sudah ditutup "
        f"({len(wins)} untung dari {len(closed)} kalau ada). "
        f"Saham yang pernah dibeli user: {', '.join(tickers_bought[:20])}."
    )

DISCLAIMER = (
    "Ini adalah hasil analisis otomatis berbasis AI, BUKAN nasihat investasi resmi. "
    "Selalu lakukan riset mandiri (DYOR) dan pertimbangkan risiko sebelum bertransaksi. "
    "Saham berisiko tinggi bisa menyebabkan kerugian besar, termasuk kehilangan modal."
)

SYSTEM_PROMPT = f"""Kamu adalah analis saham Indonesia (Bursa Efek Indonesia/IDX) untuk seorang
trader dengan profil risiko AGRESIF. Kamu akan menerima data harga/teknikal saham
dan ringkasan berita (pasar, ekonomi, politik) hari ini & kemarin.

Tugasmu: hasilkan rekomendasi saham untuk TIGA horizon trading:
1. day_trade -- dipegang dalam hitungan jam/1 hari, fokus momentum & volume.
2. swing_trade -- dipegang beberapa hari sampai beberapa minggu, fokus tren teknikal + katalis berita.
3. long_term -- dipegang berbulan-bulan+, fokus fundamental & tema makro/sektor.

Aturan penting:
- HANYA gunakan data yang diberikan di prompt. Jangan mengarang angka, berita, atau saham
  yang tidak ada di data.
- Pertimbangkan konteks politik & ekonomi Indonesia yang diberikan sebagai faktor risiko/katalis,
  terutama untuk swing_trade dan long_term.
- Profil agresif = boleh merekomendasikan saham volatil/momentum, TAPI tetap wajib mencantumkan
  level risiko dan stop loss yang jelas untuk tiap rekomendasi.
- STOP LOSS BERBASIS VOLATILITAS: setiap saham di data teknikal punya nilai "atr14" (Average
  True Range 14 hari, dalam Rupiah -- ukuran seberapa liar saham itu bergerak harian). Gunakan
  ini untuk menentukan stop_loss yang PROPORSIONAL per saham, BUKAN persentase tetap yang sama
  untuk semua saham. Panduan kasar: day_trade stop_loss sekitar entry - (1 sampai 1.5 x atr14),
  swing_trade sekitar entry - (1.5 sampai 2.5 x atr14). Saham dengan atr14 besar (lebih volatil)
  wajar diberi jarak stop loss lebih lebar, saham dengan atr14 kecil diberi jarak lebih sempit.
- UNTUK LONG_TERM: pertimbangkan data fundamental yang diberikan (P/E, PBV, ROE, DER, dividend
  yield) kalau tersedia -- prioritaskan saham dengan fundamental sehat (ROE tinggi, DER wajar,
  valuasi tidak terlalu mahal dibanding sektornya) dibanding yang murni momentum harga. Kalau
  data fundamental suatu saham kosong/tidak lengkap, tetap boleh dipertimbangkan berdasarkan
  data teknikal & tema sektor, tapi jangan mengarang angka fundamental yang tidak ada di data.
- Maksimal 6 saham per kategori, urutkan dari keyakinan tertinggi (3 teratas akan
  ditampilkan sebagai rekomendasi utama, sisanya dipakai untuk penyaringan berdasarkan
  harga per lot di sisi aplikasi).
- Jika data tidak cukup meyakinkan untuk suatu kategori, boleh mengembalikan lebih sedikit
  saham (bahkan 0) daripada memaksakan rekomendasi lemah.
- Balas HANYA dengan JSON valid sesuai skema di bawah, tanpa teks lain, tanpa markdown fences.

Skema JSON:
{{
  "date": "YYYY-MM-DD",
  "market_context_summary": "ringkasan 2-3 kalimat kondisi pasar, ekonomi, politik hari ini",
  "profiles": {{
    "day_trade": [
      {{"ticker": "", "action": "BUY", "entry_range": "", "target": "", "stop_loss": "",
        "risk_level": "tinggi/sedang", "reason": "", "catalyst": ""}}
    ],
    "swing_trade": [ ... struktur sama ... ],
    "long_term": [ ... struktur sama, boleh tanpa entry_range presisi ... ]
  }},
  "top_pick_of_the_day": {{"ticker": "", "profile": "day_trade/swing_trade/long_term", "reason": ""}}
}}
"""


def build_user_prompt(context_bundle: dict) -> str:
    journal_summary = load_journal_summary()
    journal_section = (
        f"\nCATATAN GAYA TRADING USER (dari histori transaksi mereka):\n{journal_summary}\n"
        "Pertimbangkan ini untuk menyesuaikan gaya rekomendasi (mis. sektor yang sering "
        "mereka pegang, toleransi risiko yang terlihat dari histori), TAPI tetap ikuti "
        "aturan utama di atas (jangan mengarang, tetap sertakan risiko & stop loss).\n"
    ) if journal_summary else ""

    return f"""DATA SAHAM TERPILIH (top movers hari ini, termasuk atr14 untuk sizing stop loss):
{json.dumps(context_bundle['top_movers'], ensure_ascii=False, indent=2)}

DATA FUNDAMENTAL (untuk pertimbangan long_term, field kosong = data tidak tersedia):
{json.dumps(context_bundle.get('fundamentals', {}), ensure_ascii=False, indent=2)}

BERITA PASAR & EKONOMI (48 jam terakhir):
{json.dumps(context_bundle['market_news'], ensure_ascii=False, indent=2)}

BERITA POLITIK (48 jam terakhir):
{json.dumps(context_bundle['politics_news'], ensure_ascii=False, indent=2)}
{journal_section}
Profil risiko: {config.RISK_PROFILE}
Tanggal analisis: {context_bundle['generated_at'][:10]}

Hasilkan rekomendasi sesuai skema JSON yang sudah dijelaskan di system prompt.
"""


def run_analysis(context_bundle: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY belum di-set. Simpan sebagai environment variable/secret, "
            "jangan hardcode di kode. Ambil gratis di aistudio.google.com."
        )

    client = genai.Client(api_key=api_key)

    log.info("Memanggil Gemini API untuk analisis harian...")

    last_error = None
    response = None
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=build_user_prompt(context_bundle),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            last_error = None
            break
        except Exception as e:
            last_error = e
            log.warning("Percobaan %d/3 gagal manggil Gemini API: %s", attempt, e)
            if attempt < 3:
                time.sleep(5 * attempt)  # tunggu 5s, lalu 10s sebelum coba lagi

    if last_error is not None:
        raise RuntimeError(
            "Gagal manggil Gemini API setelah 3x percobaan. Ini bisa karena jaringan "
            "sesaat, kunci API salah, atau jatah gratis harian abis. "
            f"Detail asli: {last_error}"
        ) from last_error

    raw_text = response.text

    try:
        digest = json.loads(raw_text)
    except json.JSONDecodeError:
        log.error("Respons AI bukan JSON valid, cek raw_text di bawah:")
        log.error(raw_text)
        raise

    digest["disclaimer"] = DISCLAIMER
    return digest


if __name__ == "__main__":
    import data_ingestion

    bundle = data_ingestion.build_context_bundle()
    result = run_analysis(bundle)
    print(json.dumps(result, ensure_ascii=False, indent=2))
