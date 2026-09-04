"""
notify.py
Mengirim push notification harian ke aplikasi Android lewat Firebase Cloud
Messaging (FCM), berisi ringkasan top pick hari ini.

Setup yang dibutuhkan (sekali saja):
1. Buat project di https://console.firebase.google.com
2. Aktifkan Cloud Messaging, download service account JSON
   (Project Settings > Service Accounts > Generate new private key)
3. Simpan file itu sebagai backend/firebase-service-account.json (JANGAN commit ke git)
4. Daftarkan device token dari app Android/PWA (lihat pwa/app.js untuk sisi client)
"""

import logging
import os

import firebase_admin
from firebase_admin import credentials, messaging

log = logging.getLogger(__name__)

_SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")


def _init_firebase():
    if not firebase_admin._apps:
        if not os.path.exists(_SERVICE_ACCOUNT_PATH):
            raise RuntimeError(
                f"File {_SERVICE_ACCOUNT_PATH} tidak ditemukan. "
                "Download dari Firebase Console > Project Settings > Service Accounts."
            )
        cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)


def send_daily_notification(digest: dict, device_tokens: list[str]):
    """Kirim notifikasi ke satu atau banyak device token yang sudah terdaftar."""
    _init_firebase()

    top_pick = digest.get("top_pick_of_the_day", {})
    title = "Rekomendasi Saham Hari Ini"
    body = (
        f"Top pick: {top_pick.get('ticker', '-')} ({top_pick.get('profile', '-')}). "
        "Buka app untuk detail 3 profil trading."
    )

    if not device_tokens:
        log.warning("Tidak ada device token terdaftar, notifikasi tidak dikirim.")
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={"digest_date": digest.get("date", "")},
        tokens=device_tokens,
    )
    response = messaging.send_multicast(message)
    log.info("Notifikasi terkirim: %d sukses, %d gagal", response.success_count, response.failure_count)


def load_device_tokens(path: str = "device_tokens.txt") -> list[str]:
    """Baca daftar device token dari file teks (satu token per baris).
    Di produksi sebaiknya ini disimpan di database (Firestore/SQLite), bukan file teks.
    """
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]
