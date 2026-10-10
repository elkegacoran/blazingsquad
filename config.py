import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
# 📂 1. PENGATURAN FILE & LAMPIRAN (ATTACHMENT)
# ==============================================================================

# Path file Excel berisi data penerima
EXCEL_PATH = os.path.join(BASE_DIR, "data_user.xlsx")

# 🟢 ON / OFF Pengiriman Gambar / File:
# Set True  -> Gambar/file AKAN dikirim bersama pesan.
# Set False -> Gambar/file TIDAK dikirim (hanya pesan teks saja).
ATTACHMENT_ENABLED = False

# List file yang ingin dikirim jika ATTACHMENT_ENABLED = True.
# Anda bisa menambah lebih dari satu file (misal: gambar + PDF).
ATTACHMENT_FILES = [
    os.path.join(BASE_DIR, "sebaran.png"),
    # os.path.join(BASE_DIR, "lampiran_2.pdf"),  # Hapus tanda # untuk mengaktifkan file ke-2
]

# Path folder log & checkpoint (tidak perlu diubah)
LOG_DIR         = os.path.join(BASE_DIR, "logs")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "checkpoint.txt")


# ==============================================================================
# 💬 2. TEMPLATE PESAN (1 Pesan = 1 Baris Terpisah)
# ==============================================================================
# Setiap item dalam list MSG_LINES di bawah ini akan dikirim sebagai 1 PESAN TERPISAH (1 chat bubble).
#
# Variable otomatis dari Excel yang bisa digunakan:
#   {nama}         -> Mengambil isi kolom 'nama'
#   {id_pelanggan} -> Mengambil isi kolom 'id_pelanggan'
#   {status}       -> Mengambil isi kolom 'status'
#   {teks}         -> Mengambil isi kolom 'teks'
#
# Cara ubah: Tambah, hapus, atau ubah baris teks di dalam tanda [ ... ]
MSG_LINES = [
    "HELLO peneriama {nama},",
    "Ini adalah pesan otomatis untuk pelanggan PLN UP3 lhokseumawe dengan ID: {id_pelanggan}",
    "Status Anda saat ini adalah: {status}",
    "{teks}",
]

# Jeda (detik) antar baris pesan untuk kontak yang sama (misal dari baris 1 ke baris 2)
LINE_DELAY = 1


# ==============================================================================
# 🖥️ 3. PENGATURAN BROWSER & PROFIL CHROME (BROWSER MODE)
# ==============================================================================
# Pilihan PROFILE_MODE:
#   "DEFAULT"  -> Menggunakan profil Chrome utama komputer Anda (yang sudah login WA Web).
#                 *PENTING: Tutup jendela Chrome biasa Anda sebelum menjalankan script ini agar tidak bentrok!
#   "SEPARATE" -> Menggunakan profil Chrome terpisah khusus bot (bebas bentrok, tapi perlu scan QR 1x di awal).
PROFILE_MODE = "DEFAULT"   # Opsi: "DEFAULT" atau "SEPARATE"

# Mode Headless (Tampilan Browser):
# Set True  -> Chrome berjalan di latar belakang tanpa jendela tampilan.
# Set False -> Jendela Chrome terbuka dan terlihat di layar (Direkomendasikan).
HEADLESS_MODE = False


# ==============================================================================
# ⚡ 4. KECEPATAN & ANTI-BAN SETTINGS
# ==============================================================================
# Jeda acak (random) antara pengiriman ke ORANG KE-1 dan ORANG KE-2.
# Nilai diacak antara MIN dan MAX agar tidak terdeteksi sebagai bot.
MSG_DELAY_MIN = 7    # Minimum jeda antar orang (detik)
MSG_DELAY_MAX = 15   # Maksimum jeda antar orang (detik)

# Jeda Istirahat (Batch):
# Bot akan berhenti sementara setelah mengirim ke N orang.
BATCH_SIZE  = 3     # Kirim ke 3 orang -> istirahat -> lanjut 3 orang lagi
BATCH_DELAY = 60    # Durasi istirahat (detik). 60 = 1 menit, 120 = 2 menit.


# ==============================================================================
# ⏱️ 5. TIMEOUT (BATAS WAKTU TUNGGU SCRIPT)
# ==============================================================================
WA_WAIT_TIMEOUT     = 20  # Waktu tunggu loading utama WhatsApp Web (detik)
ATTACH_WAIT_TIMEOUT = 5   # Waktu tunggu tiap percobaan tombol attach (detik)
LOGIN_TIMEOUT       = 60  # Waktu tunggu scan QR Code / login (detik)


# ==============================================================================
# 🔔 6. NOTIFIKASI LAPORAN (EMAIL & TELEGRAM)
# ==============================================================================

# --- EMAIL NOTIFICATION ---
EMAIL_ENABLED  = False                 # Set True jika ingin dapat email laporan setelah selesai
EMAIL_SENDER   = "sender@gmail.com"     # Email pengirim
EMAIL_PASSWORD = "your-app-password"   # App Password dari akun Google (bukan pass biasa)
EMAIL_RECEIVER = "receiver@gmail.com"   # Email penerima laporan
EMAIL_SMTP     = "smtp.gmail.com"
EMAIL_PORT     = 465

# --- TELEGRAM NOTIFICATION ---
TELEGRAM_ENABLED   = False              # Set True jika ingin laporan dikirim ke Telegram
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"   # Token dari @BotFather
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID"     # ID Chat dari @userinfobot
