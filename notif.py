import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import requests

import config

log = logging.getLogger(__name__)


# ─── Email ────────────────────────────────────────────────────────────────────
def kirim_notif_email(sukses: int, gagal: int, log_file: str) -> None:
    """
    Kirim notifikasi email setelah blast selesai.
    File log otomatis dilampirkan sebagai attachment.
    
    Setup:
    1. Aktifkan config.EMAIL_ENABLED = True
    2. Isi config.EMAIL_SENDER, EMAIL_PASSWORD (App Password Google), EMAIL_RECEIVER
    3. Cara buat App Password: myaccount.google.com → Security → App Passwords
    """
    if not config.EMAIL_ENABLED:
        return

    try:
        status_icon = "✅" if gagal == 0 else "⚠️"
        msg = MIMEMultipart()
        msg["Subject"] = f"{status_icon} WA Blast Selesai | Sukses: {sukses} | Gagal: {gagal}"
        msg["From"]    = config.EMAIL_SENDER
        msg["To"]      = config.EMAIL_RECEIVER

        body = (
            f"WA Blast telah selesai dijalankan.\n\n"
            f"📊 Ringkasan:\n"
            f"  ✓ Berhasil : {sukses}\n"
            f"  ✗ Gagal    : {gagal}\n\n"
            f"File log terlampir sebagai attachment."
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Lampirkan file log
        if os.path.exists(log_file):
            with open(log_file, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{os.path.basename(log_file)}"',
                )
                msg.attach(part)

        with smtplib.SMTP_SSL(config.EMAIL_SMTP, config.EMAIL_PORT) as server:
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)

        log.info(f"✉  Notifikasi email terkirim ke {config.EMAIL_RECEIVER}")

    except Exception as e:
        log.error(f"Gagal kirim email: {e}")


# ─── Telegram ─────────────────────────────────────────────────────────────────
def kirim_notif_telegram(sukses: int, gagal: int, log_file: str) -> None:
    """
    Kirim notifikasi Telegram setelah blast selesai.
    Pesan + file log dikirim ke chat/group yang dikonfigurasi.
    
    Setup:
    1. Buat bot via @BotFather → salin token ke config.TELEGRAM_BOT_TOKEN
    2. Dapatkan chat ID via @userinfobot atau endpoint getUpdates
    3. Aktifkan config.TELEGRAM_ENABLED = True
    """
    if not config.TELEGRAM_ENABLED:
        return

    try:
        status_icon = "✅" if gagal == 0 else "⚠️"
        text = (
            f"{status_icon} *WA Blast Selesai*\n\n"
            f"📊 *Ringkasan:*\n"
            f"  ✓ Berhasil : `{sukses}`\n"
            f"  ✗ Gagal    : `{gagal}`\n"
            f"  📁 Log     : `{os.path.basename(log_file)}`"
        )

        base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

        # Kirim pesan teks
        resp = requests.post(
            f"{base_url}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        resp.raise_for_status()

        # Kirim file log sebagai dokumen
        if os.path.exists(log_file):
            with open(log_file, "rb") as f:
                doc_resp = requests.post(
                    f"{base_url}/sendDocument",
                    data={
                        "chat_id": config.TELEGRAM_CHAT_ID,
                        "caption": "📄 File Log WA Blast",
                    },
                    files={"document": f},
                    timeout=30,
                )
                doc_resp.raise_for_status()

        log.info("📱 Notifikasi Telegram terkirim.")

    except Exception as e:
        log.error(f"Gagal kirim Telegram: {e}")


# ─── Dispatch Semua Notifikasi ────────────────────────────────────────────────
def kirim_semua_notif(sukses: int, gagal: int, log_file: str) -> None:
    """Jalankan semua notifikasi yang aktif (email + Telegram)."""
    kirim_notif_email(sukses, gagal, log_file)
    kirim_notif_telegram(sukses, gagal, log_file)
