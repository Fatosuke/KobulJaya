# Sinyal Harian Saham IDX — AI Agent + PWA

Sistem yang setiap hari mengambil data harga saham IDX + berita (pasar, ekonomi, politik),
menganalisisnya lewat Claude API, lalu mengirim notifikasi ke HP kamu berisi rekomendasi
untuk 3 profil trading: **day trade**, **swing trade**, dan **investasi jangka panjang**,
dengan profil risiko **agresif**.

## Struktur proyek

```
saham-ai-agent/
├── .github/workflows/daily.yml   # jadwal otomatis 3x/hari (GitHub Actions, gratis)
├── backend/
│   ├── config.py          # universe saham, sumber berita, jadwal, parameter
│   ├── data_ingestion.py  # ambil harga (yfinance) + berita (RSS) + IHSG
│   ├── market_hours.py    # cek hari bursa (skip weekend/libur)
│   ├── ai_agent.py        # prompt + panggilan ke Claude API
│   ├── notify.py          # kirim push notification via Firebase (FCM)
│   ├── scheduler.py       # entry point (ingestion -> AI -> notify)
│   └── requirements.txt
└── docs/                   # <- ini yang di-hosting jadi PWA (nama "docs" wajib
    │                          untuk GitHub Pages, lihat langkah instalasi)
    ├── index.html          # UI digest harian
    ├── manifest.json       # supaya bisa di-"Add to Home Screen" di Android
    └── service-worker.js   # offline cache + terima push notification
```

**Coba dulu di komputer:** buka `docs/index.html` langsung di browser — ini jalan
dengan data contoh (ditandai "Mode demo") supaya kamu bisa lihat tampilannya dulu
tanpa setup apa pun. Untuk instalasi sungguhan ke HP dengan data asli, ikuti bagian
**Instalasi ke HP** di bawah.

## Cara kerja alur data

1. `data_ingestion.py` ambil harga 90 hari terakhir untuk ~45 saham likuid/volatil
   (default: LQ45 + beberapa saham momentum), hitung indikator (RSI, SMA, rasio volume),
   lalu ambil berita pasar & politik 48 jam terakhir dari RSS.
2. `ai_agent.py` mengirim data itu ke Claude dengan instruksi ketat: **hanya** boleh
   memakai data yang diberikan, tidak boleh mengarang, wajib sertakan level risiko dan
   stop loss, dan wajib output JSON terstruktur.
3. `scheduler.py` menyimpan hasilnya dan memicu `notify.py` untuk push notification.
4. App Android (PWA) menampilkan hasil JSON tersebut dalam UI seperti prototype.

## Setup

```bash
cd backend
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."   # dari console.anthropic.com

python scheduler.py    # jalankan sekali secara manual untuk tes
```

Hasilnya akan tersimpan di `backend/output/daily_digest.json` — file inilah yang
nanti dibaca oleh `pwa/index.html` (ganti `MOCK_DIGEST` di index.html dengan
`fetch('daily_digest.json')`, atau serve lewat endpoint backend kecil).

## Instalasi ke HP — Step by Step

Ini langkah lengkap dari nol sampai app-nya ada di HP kamu dengan data asli
(bukan mode demo). Butuh komputer untuk langkah 1-5 (setup awal), langkah 6
dilakukan di HP.

### 1. Buat API key Anthropic
Buka [console.anthropic.com](https://console.anthropic.com) → menu **API Keys** →
**Create Key**. Simpan key-nya (formatnya `sk-ant-...`), akan dipakai di langkah 3.

### 2. Upload project ke GitHub
Buat akun GitHub kalau belum punya (github.com, gratis), lalu buat repository baru
(**New repository**, boleh **Private**, nama bebas misal `saham-ai-agent`, JANGAN
centang "Add README").

Ada 2 cara upload isi folder `saham-ai-agent` ini ke repo tersebut:
- **Tanpa install apa pun:** buka halaman repo kosongmu di GitHub → klik
  "uploading an existing file" → drag & drop semua folder/file dari hasil download
  tadi → commit.
- **Pakai git (lebih rapi untuk update berkala):**
  ```bash
  cd saham-ai-agent
  git init
  git add .
  git commit -m "Initial commit"
  git branch -M main
  git remote add origin https://github.com/USERNAME/saham-ai-agent.git
  git push -u origin main
  ```

### 3. Simpan API key sebagai GitHub Secret
Di halaman repo → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**. Name: `ANTHROPIC_API_KEY`, Value: key dari langkah 1.

### 4. Tes jalankan pipeline
Tab **Actions** di repo → pilih workflow **"Sinyal Saham Harian"** → klik
**Run workflow** → tunggu 1-2 menit. Kalau sukses (centang hijau), berarti
`backend/output/daily_digest.json` sudah otomatis ter-generate dan ter-commit.
Mulai sekarang ini akan jalan otomatis sendiri jam 09:00, 13:00, 16:00 WIB
tiap hari kerja.

### 5. Sambungkan app ke data asli & aktifkan hosting
Edit `docs/index.html` di GitHub (klik file → ikon pensil) → cari baris:
```js
const GITHUB_USER = "USERNAME_GITHUB_KAMU";
const GITHUB_REPO = "saham-ai-agent";
```
Ganti `USERNAME_GITHUB_KAMU` dengan username GitHub kamu, commit.

Lalu aktifkan hosting gratis: **Settings** → **Pages** → Source: **Deploy from a
branch** → Branch: **main**, folder **/docs** → **Save**. Tunggu ~1 menit, GitHub
akan kasih URL seperti `https://USERNAME.github.io/saham-ai-agent/`.

### 6. Install ke HP
Di HP, buka URL dari langkah 5 pakai **Chrome**. Ketuk menu titik tiga (⋮) di
pojok kanan atas → **"Add to Home screen" / "Instal aplikasi"** → konfirmasi.
Ikon app akan muncul di home screen dan bisa dibuka seperti app biasa, lengkap
offline cache. Banner di atas akan berubah dari "Mode demo" jadi "Data live"
kalau langkah 5 sudah benar.

**Soal notifikasi push (opsional, lebih advanced):** kode yang saya buat
(`backend/notify.py`, `docs/service-worker.js`) sudah siap menerima & mengirim
push lewat Firebase Cloud Messaging, tapi bagian "device mendaftarkan diri ke
Firebase" perlu project Firebase milik kamu sendiri untuk saya sambungkan
(lihat bagian **Opsi deployment** di bawah). Bilang aja kalau kamu mau saya
lanjutkan bagian ini.



## Opsi sumber data saham

| Opsi | Real-time? | Biaya | Kapan pakai |
|---|---|---|---|
| **yfinance** (default di kode) | Delayed ~15-20 menit | Gratis | MVP, swing/long-term |
| **Sectors.app (DataSectors)** | Real-time OHLCV, smart money, corporate action | Gratis (terbatas) → berbayar | Upgrade untuk day trading & fundamental lebih dalam |
| **Invezgo** | Real-time, update 5 detik | Freemium | Alternatif Sectors.app, ada foreign flow |
| **RapidAPI "IDX Market Intelligence"** | Real-time + analitik | Berbayar per-call | Kalau butuh insight/analitik siap pakai |
| **Scraper open-source (idx-bei dsb di GitHub)** | Sesuai update IDX | Gratis, DIY | Kalau mau full kontrol, tapi perlu maintenance sendiri |

Untuk ganti sumber data: cukup ubah fungsi `fetch_price_data()` di `data_ingestion.py`,
struktur output (list of dict per saham) sudah dibuat konsisten supaya `ai_agent.py`
tidak perlu diubah.

## Jadwal: 3x sehari, hanya saat bursa buka

Pipeline diatur jalan jam **09:00, 13:00, dan 16:00 WIB**, Senin-Jumat saja
(`backend/config.py` -> `SCHEDULE_TIMES_WIB`). ada 2 lapis pengaman:

1. **Cron/GitHub Actions** cuma dipicu di hari kerja (`1-5`) pada jam-jam itu.
2. **`backend/market_hours.py`** dicek ulang di awal `scheduler.py` -- kalau kebetulan
   ke-trigger di hari libur bursa (weekend, atau tanggal di `config.IDX_HOLIDAYS`),
   pipeline otomatis skip tanpa memanggil Claude API sama sekali (hemat biaya API).

**Penting:** update `config.IDX_HOLIDAYS` tiap tahun sesuai kalender libur bursa resmi
dari idx.co.id (Lebaran, Natal, cuti bersama, dll) -- kalau tidak diisi, sistem cuma
tahu Sabtu/Minggu sebagai hari libur.

## Alternatif deployment & notifikasi push

Bagian **Instalasi ke HP** di atas sudah cukup untuk versi tanpa push notification
(kamu buka app-nya untuk lihat update terbaru). Kalau mau notifikasi otomatis
muncul di HP:

**Kalau tidak mau pakai GitHub Actions, opsi server sendiri:**
VPS kecil (mis. $5/bulan) + 3 baris cron job Linux:
```
0 9,13,16 * * 1-5 cd /path/ke/backend && python3 scheduler.py
```
(pipeline tetap otomatis skip di hari libur bursa lewat `market_hours.py`, jadi baris
cron ini cukup diset hari kerja saja).

**Notifikasi push ke HP (opsional):**
1. Buat project Firebase (gratis) → aktifkan Cloud Messaging.
2. Download service account key, simpan sebagai `backend/firebase-service-account.json`.
3. Di `docs/`, daftarkan device token lewat Firebase Web SDK saat user pertama buka app
   (kode ini belum disertakan, karena butuh Firebase project ID milik kamu sendiri —
   dokumentasinya ada di firebase.google.com/docs/cloud-messaging/js/client. Minta saya
   buatkan kalau sudah punya project ID-nya).
4. PWA yang sudah di-hosting di GitHub Pages (langkah 5 & 6 di atas) sudah otomatis
   punya service worker yang siap terima push -- tinggal sambungkan device token-nya.

## Catatan penting

- **Ini bukan aplikasi berlisensi penasihat investasi.** Rekomendasi dihasilkan AI
  berdasarkan data yang tersedia, bukan analisis manusia bersertifikat. Disclaimer
  sudah ditanam otomatis di setiap output (`ai_agent.py`).
- Kalau nanti aplikasi ini didistribusikan ke orang lain (bukan cuma dipakai sendiri),
  cek dulu ketentuan OJK soal penyediaan rekomendasi investasi ke publik — untuk
  pemakaian pribadi tidak masalah.
- Profil "agresif" berarti sistem akan merekomendasikan saham dengan volatilitas/risiko
  lebih tinggi. Selalu perhatikan `stop_loss` yang disertakan di tiap rekomendasi.
- Data harga & berita yang diambil scraper/RSS bisa berubah struktur kapan saja — kalau
  `data_ingestion.py` mulai gagal ambil data, cek dulu apakah sumbernya masih valid.
