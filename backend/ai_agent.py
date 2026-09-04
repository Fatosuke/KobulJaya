"""
ai_agent.py
"Otak" analisis: mengubah data mentah (harga + berita) jadi rekomendasi
terstruktur untuk 3 profil trader, lewat panggilan ke Claude API.

Penting: agent ini HANYA boleh menganalisis berdasarkan data yang diberikan
di prompt (tidak boleh mengarang harga/berita), dan wajib menyertakan
disclaimer di setiap output.
"""

import json
import logging
import os

import anthropic

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

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
- Maksimal 3 saham per kategori, urutkan dari keyakinan tertinggi.
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
    return f"""DATA SAHAM TERPILIH (top movers hari ini):
{json.dumps(context_bundle['top_movers'], ensure_ascii=False, indent=2)}

BERITA PASAR & EKONOMI (48 jam terakhir):
{json.dumps(context_bundle['market_news'], ensure_ascii=False, indent=2)}

BERITA POLITIK (48 jam terakhir):
{json.dumps(context_bundle['politics_news'], ensure_ascii=False, indent=2)}

Profil risiko: {config.RISK_PROFILE}
Tanggal analisis: {context_bundle['generated_at'][:10]}

Hasilkan rekomendasi sesuai skema JSON yang sudah dijelaskan di system prompt.
"""


def run_analysis(context_bundle: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY belum di-set. Simpan sebagai environment variable, "
            "jangan hardcode di kode."
        )

    client = anthropic.Anthropic(api_key=api_key)

    log.info("Memanggil Claude API untuk analisis harian...")
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(context_bundle)}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")

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
