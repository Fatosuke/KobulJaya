"""
scheduler.py
Entry point yang dijalankan terjadwal setiap hari (lewat cron / GitHub Actions /
Cloud Scheduler -- lihat README untuk opsi deployment).

Alur: ambil data -> analisis AI -> simpan hasil -> kirim notifikasi.
"""

import json
import logging
import os

import data_ingestion
import market_hours
import notify
from ai_agent import run_analysis

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run_daily_pipeline():
    reason = market_hours.skip_reason()
    if reason:
        log.info("Skip pipeline: %s", reason)
        return None

    log.info("=== Mulai pipeline (jam berjalan sesuai jadwal cron) ===")

    bundle = data_ingestion.build_context_bundle()
    digest = run_analysis(bundle)

    # Tempel data faktual langsung (bukan lewat AI) supaya angka indeks & tanggal
    # selalu akurat, tidak berisiko salah ditulis ulang oleh model.
    digest["market_index"] = bundle.get("market_index")
    digest["date"] = bundle["generated_at"][:10]

    os.makedirs(os.path.dirname(config.OUTPUT_JSON_PATH), exist_ok=True)
    with open(config.OUTPUT_JSON_PATH, "w") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    log.info("Digest disimpan ke %s", config.OUTPUT_JSON_PATH)

    try:
        tokens = notify.load_device_tokens()
        notify.send_daily_notification(digest, tokens)
    except Exception as e:
        # Jangan sampai kegagalan notifikasi menggagalkan seluruh pipeline
        log.error("Gagal kirim notifikasi: %s", e)

    log.info("=== Pipeline selesai ===")
    return digest


if __name__ == "__main__":
    run_daily_pipeline()
