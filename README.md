# WhatsApp Automation Script — PLN UP3 Makassar Selatan

## Deskripsi
Script otomatisasi pengiriman pesan WhatsApp via WhatsApp Web menggunakan **Selenium** dan **Pandas**.
Membaca data pelanggan dari Excel, mengirim pesan + gambar yang dipersonalisasi, dilengkapi:
- ✅ **Progress bar** real-time (tqdm)
- ✅ **Resume otomatis** jika crash (checkpoint)
- ✅ **Notifikasi** selesai via Email dan/atau Telegram
- ✅ **Full Selenium upload** — tanpa pyautogui, tanpa screenshot PNG
- ✅ **Multi-XPath fallback** — tidak mudah rusak saat WA update

---

## Struktur Proyek

```
WA_Blast/
├── main.py              # Entry point (CLI dengan argparse)
├── whatsapp_blast.py    # Logic utama blast
├── config.py            # ⚙️ SEMUA KONFIGURASI DI SINI
├── notif.py             # Modul notifikasi (Email + Telegram)
├── data_user.xlsx       # Data pelanggan
├── sebaran.png          # Gambar lampiran yang dikirim
├── logs/                # Auto-dibuat — log per eksekusi
├── checkpoint.txt       # Auto-dibuat — posisi resume
└── README.md
```

---

## Instalasi

```bash
pip install -r requirements.txt
```

> **Python 3.9+** diperlukan. Disarankan menggunakan Virtual Environment (`python3 -m venv venv && source venv/bin/activate`).

---

## Format File Excel (`data_user.xlsx`)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id_pelanggan` | string/int | ID unik pelanggan |
| `nama` | string | Nama pelanggan |
| `nomor_wa` | string | Nomor WA format internasional tanpa `+` (contoh: `628123456789`) |
| `status` | string | Status pelanggan (mis. Aktif, Tunggakan) |
| `teks` | string | Teks tambahan yang disertakan dalam pesan |

---

## Konfigurasi (`config.py`)

Edit file [`config.py`](config.py) sesuai kebutuhan sebelum menjalankan script.

### Blast Settings
```python
BATCH_SIZE    = 3    # Jumlah pesan per batch
BATCH_DELAY   = 120  # Jeda antar batch (detik)
MSG_DELAY_MIN = 7    # Minimum jeda antar pesan (detik)
MSG_DELAY_MAX = 15   # Maximum jeda antar pesan (detik)
```

### Notifikasi Email
```python
EMAIL_ENABLED  = True
EMAIL_SENDER   = "sender@gmail.com"
EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"  # App Password Google
EMAIL_RECEIVER = "receiver@gmail.com"
```
> **Cara buat App Password:** [myaccount.google.com](https://myaccount.google.com) → Security → App Passwords

### Notifikasi Telegram
```python
TELEGRAM_ENABLED   = True
TELEGRAM_BOT_TOKEN = "1234567890:AAFxxxxxx"  # Dari @BotFather
TELEGRAM_CHAT_ID   = "123456789"             # Dari @userinfobot
```

### Headless Mode
```python
HEADLESS_MODE = False  # Set False agar browser terbuka di layar (Direkomendasikan)
```
> ⚠️ WA Web kadang memblokir sesi headless. Test dulu sebelum production.

### Profil Chrome (Bebas Bentrok / Anti SingletonLock)
```python
PROFILE_MODE = "SEPARATE"  # Direkomendasikan: Sesi tersimpan di .chrome_profile/
```
- **`SEPARATE`**: Bot menggunakan folder profil sendiri (`.chrome_profile/`). Anda bisa bebas membuka browser Chrome biasa untuk browsing tanpa khawatir bot crash karena bentrok.
- **`DEFAULT`**: Menggunakan profil Chrome utama. Wajib menutup semua jendela Google Chrome sebelum script dijalankan.

---

## Cara Menjalankan

### Normal (dari awal)
```bash
python main.py
```

### Headless (tanpa tampilan browser)
```bash
python main.py --headless
```

### Resume setelah crash
```bash
python main.py --resume
```

### Mulai ulang dari awal (hapus checkpoint)
```bash
python main.py --reset
```

### Kombinasi
```bash
python main.py --headless --resume
```

---

## Fitur Detail

### 📊 Progress Bar
Menampilkan nama penerima saat ini, jumlah sukses/gagal, dan estimasi waktu sisa secara real-time:
```
📨 Budi (628123456789): 100%|████████| 50/50 [sukses=48, gagal=2]
```

### 💾 Resume / Checkpoint
Jika script crash di tengah jalan, jalankan ulang dengan `--resume` untuk melanjutkan dari baris terakhir yang sukses.
File `checkpoint.txt` otomatis dihapus jika semua pesan berhasil dikirim.

### 📎 Upload Multiple File
Tambahkan path file ke variabel `file_paths` di fungsi `main()`:
```python
file_paths = [
    os.path.join(BASE_DIR, "sebaran.png"),
    os.path.join(BASE_DIR, "brosur.pdf"),
]
```

### 🔄 Multi-XPath Fallback
Setiap elemen WA Web memiliki daftar XPath fallback. Jika WA update dan XPath pertama gagal, otomatis dicoba XPath berikutnya. Untuk update manual, edit konstanta `XPATHS_*` di `whatsapp_blast.py`.

### 🔔 Notifikasi
- **Email**: Pesan ringkasan + file log terlampir
- **Telegram**: Pesan ringkasan + file log sebagai dokumen

---

## Logging
Setiap eksekusi membuat file log di `logs/` dengan format:
```
blast_YYYYMMDD_HHMMSS.log
```
Log mencatat status tiap pesan, jeda, error detail, dan ringkasan akhir.

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| Browser buka tapi muncul QR Code | Login manual via Chrome biasa, lalu jalankan ulang |
| `FileNotFoundError: data_user.xlsx` | Pastikan file ada di folder `WA_Blast/` |
| `ValueError: Kolom Excel tidak lengkap` | Cek nama kolom sesuai format di atas |
| Upload file gagal | Cek file `sebaran.png` ada. XPath WA bisa berubah setelah update — cek `XPATHS_*` |
| Email/Telegram tidak terkirim | Cek koneksi internet & konfigurasi di `config.py` |
| Script crash di tengah jalan | Jalankan ulang dengan `--resume` |

---

## File Tidak Digunakan Lagi
File-file PNG berikut **bisa dihapus** setelah upload via Selenium terkonfirmasi berjalan:

| File | Fungsi Lama (pyautogui) |
|---|---|
| `lampir.png` | Screenshot tombol attach |
| `ft.png` | Screenshot menu foto/video |
| `open.png` | Screenshot tombol Open dialog |
| `send.png` | Screenshot tombol Send |
