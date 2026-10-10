import os
import sys
import time
import random
import logging
import platform
from datetime import datetime
from urllib.parse import quote
from typing import Optional

from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import pandas as pd

import config
from notif import kirim_semua_notif

# ─── Logging Setup ────────────────────────────────────────────────────────────
os.makedirs(config.LOG_DIR, exist_ok=True)
log_file = os.path.join(
    config.LOG_DIR, f"blast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ─── Multi-XPath Constants ────────────────────────────────────────────────────
# Setiap key menyimpan daftar XPath fallback, diurutkan dari yang paling andal.
# Jika WA update dan XPath pertama gagal, otomatis dicoba XPath berikutnya.

XPATHS_MSG_BOX = [
    '//div[@data-tab="10"][@contenteditable="true"]',
    '//div[@contenteditable="true"][@data-tab="10"]',
    '//div[@aria-placeholder][@contenteditable="true"]',
]

XPATHS_ATTACH = [
    '//span[@data-icon="clip"]',           # paling stabil — data-icon jarang berubah
    '//button[@aria-label="Attach"]',
    '//*[@data-testid="clip"]',
    '//*[@data-testid="attach-menu-icon"]',
    '//div[@title="Attach"]',
    '//div[@aria-label="Attach"]',
    '//span[@data-testid="clip"]',
]

XPATHS_FILE_INPUT = [
    '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]',
    '//input[@type="file"]',
]

XPATHS_SEND_BTN = [
    '//span[@data-icon="send"]',
    '//span[@data-icon="send"]/ancestor::div[@role="button"]',
    '//span[@data-icon="send"]/ancestor::button',
    '//*[@data-testid="send"]',
    '//span[@data-testid="send"]',
    '//div[@aria-label="Send"]',
    '//button[@aria-label="Send"]',
]

XPATH_CHAT_LIST = '//div[@data-testid="chat-list"]'


# ─── Multi-XPath Fallback Helper ─────────────────────────────────────────────
def find_element_any(
    wait: WebDriverWait,
    xpaths: list,
    condition=None,
) -> webdriver.remote.webelement.WebElement:
    """
    Coba setiap XPath secara berurutan sampai ada yang berhasil.
    Menggunakan condition EC.presence_of_element_located secara default.
    Raise Exception jika semua XPath gagal.
    """
    if condition is None:
        condition = EC.presence_of_element_located

    last_exc = None
    for xpath in xpaths:
        try:
            return wait.until(condition((By.XPATH, xpath)))
        except Exception as e:
            last_exc = e
            continue
    raise Exception(
        f"Semua XPath fallback gagal. XPath dicoba: {xpaths}. Error terakhir: {last_exc}"
    )


def click_element_any(wait: WebDriverWait, xpaths: list):
    """Coba klik elemen dari daftar XPath fallback."""
    return find_element_any(wait, xpaths, condition=EC.element_to_be_clickable)


# ─── Checkpoint ───────────────────────────────────────────────────────────────
def save_checkpoint(index: int) -> None:
    """Simpan index baris terakhir yang sukses terkirim."""
    with open(config.CHECKPOINT_FILE, "w") as f:
        f.write(str(index))


def load_checkpoint() -> int:
    """Baca index baris terakhir dari file checkpoint. Return 0 jika tidak ada."""
    if os.path.exists(config.CHECKPOINT_FILE):
        try:
            with open(config.CHECKPOINT_FILE) as f:
                val = int(f.read().strip())
            log.info(f"Checkpoint ditemukan — melanjutkan dari baris ke-{val + 1}.")
            return val
        except (ValueError, IOError):
            pass
    return 0


def reset_checkpoint() -> None:
    """Hapus file checkpoint agar mulai dari awal."""
    if os.path.exists(config.CHECKPOINT_FILE):
        os.remove(config.CHECKPOINT_FILE)
        log.info("Checkpoint dihapus — memulai dari awal.")


# ─── Chrome Setup ─────────────────────────────────────────────────────────────
def get_chrome_options(headless: bool = False) -> webdriver.ChromeOptions:
    home = os.path.expanduser("~")
    options = webdriver.ChromeOptions()

    profile_mode = getattr(config, "PROFILE_MODE", "DEFAULT").upper()

    if profile_mode == "DEFAULT":
        # Gunakan profil Chrome utama komputer (sudah ter-login WA Web)
        if platform.system() == "Windows":
            user_data_dir = os.path.join(
                home, "AppData", "Local", "Google", "Chrome", "User Data"
            )
        else:  # Linux & macOS
            user_data_dir = os.path.join(home, ".config", "google-chrome")
        log.info(f"Menggunakan profil Chrome UTAMA: {user_data_dir}")
    else:
        # Gunakan profil Chrome terpisah khusus bot
        if platform.system() == "Windows":
            user_data_dir = os.path.join(
                home, "AppData", "Local", "Google", "Chrome", "SeleniumWABlast"
            )
        else:  # Linux & macOS
            user_data_dir = os.path.join(home, ".config", "selenium-wa-blast")
        log.info(f"Menggunakan profil Chrome TERPISAH: {user_data_dir}")

    options.add_argument(f"user-data-dir={user_data_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")

    # Flag stabilitas untuk Linux
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=0")

    is_headless = headless or getattr(config, "HEADLESS_MODE", False)
    if is_headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        log.warning(
            "Mode headless aktif. WA Web mungkin memblokir sesi headless — test dulu sebelum production."
        )

    return options


def init_driver(headless: bool = False) -> webdriver.Chrome:
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=get_chrome_options(headless),
    )


# ─── Login Helper ─────────────────────────────────────────────────────────────
def tunggu_login(driver: webdriver.Chrome) -> None:
    """Buka WA Web dan tunggu chat-list muncul (tanda sudah login)."""
    log.info("Membuka WhatsApp Web...")
    driver.get("https://web.whatsapp.com/")
    try:
        WebDriverWait(driver, config.LOGIN_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, XPATH_CHAT_LIST))
        )
        log.info("WhatsApp Web siap.")
    except Exception:
        log.warning(
            "Timeout menunggu WA Web. Pastikan sudah scan QR Code, lalu jalankan ulang."
        )


# ─── Full Selenium File Upload ─────────────────────────────────────────────────
def upload_files_selenium(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    file_paths: list,
) -> bool:
    """
    Upload satu atau lebih file via Selenium — tanpa pyautogui, tanpa screenshot.

    Strategi (urutan):
    1. Klik attach button (XPath fallback) → send_keys ke file input → klik Send (preview modal)
    2. JS fallback: inject langsung ke hidden <input type=file> tanpa klik attach → klik Send (preview modal)
    """
    valid_paths = [p for p in file_paths if os.path.exists(p)]
    if not valid_paths:
        log.warning("Tidak ada file valid untuk diupload, skip.")
        return False

    # Wait khusus attach & send button — timeout pendek agar fallback cepat
    wait_short = WebDriverWait(driver, config.ATTACH_WAIT_TIMEOUT)

    def klik_tombol_send() -> bool:
        """Cari tombol kirim di layar preview media dan klik."""
        for xpath in XPATHS_SEND_BTN:
            try:
                send_btn = wait_short.until(EC.presence_of_element_located((By.XPATH, xpath)))
                try:
                    send_btn.click()
                except Exception:
                    # Jika .click() biasa terhalang overlay, gunakan JS click
                    driver.execute_script("arguments[0].click();", send_btn)
                log.info(f"Tombol Send diklik via XPath: {xpath}")
                time.sleep(2)
                return True
            except Exception:
                continue
        return False

    try:
        # ── Strategi 1: Klik attach button → pilih file → kirim ──────────────
        attach_clicked = False
        for xpath in XPATHS_ATTACH:
            try:
                btn = wait_short.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                btn.click()
                attach_clicked = True
                log.info(f"Tombol attach diklik via XPath: {xpath}")
                time.sleep(1)
                break
            except Exception:
                continue

        if attach_clicked:
            for xpath in XPATHS_FILE_INPUT:
                try:
                    fi = wait_short.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    fi.send_keys("\n".join(valid_paths))
                    log.info(f"File dipilih ({len(valid_paths)}): {[os.path.basename(p) for p in valid_paths]}")
                    time.sleep(2)
                    if klik_tombol_send():
                        log.info("File berhasil dikirim.")
                        return True
                except Exception:
                    continue

        # ── Strategi 2: JS fallback — inject ke hidden input tanpa klik attach ─
        log.info("XPath attach gagal, mencoba JS fallback...")
        file_inputs = driver.execute_script(
            "return Array.from(document.querySelectorAll('input[type=\"file\"]'));"
        )
        if not file_inputs:
            raise Exception("Tidak ada <input type=file> ditemukan via JS.")

        for fi in file_inputs:
            try:
                driver.execute_script(
                    "arguments[0].style.display='block';"
                    "arguments[0].style.visibility='visible';"
                    "arguments[0].style.opacity='1';",
                    fi,
                )
                fi.send_keys("\n".join(valid_paths))
                log.info(f"File dipilih via JS fallback: {[os.path.basename(p) for p in valid_paths]}")
                time.sleep(2)

                if klik_tombol_send():
                    log.info("File berhasil dikirim via JS fallback.")
                    return True
            except Exception:
                continue

        raise Exception("Semua strategi upload gagal (gagal klik tombol Send di preview).")

    except Exception as e:
        log.error(f"Gagal upload file: {e}")
        return False




# ─── Kirim Pesan ──────────────────────────────────────────────────────────────
def kirim_pesan(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    nomor_wa: str,
    nama: str,
    lines: list,
    file_paths: Optional[list] = None,
) -> None:
    """
    Kirim daftar baris pesan ke satu nomor WA (1 baris = 1 pesan terpisah).
    Selanjutnya kirim lampiran jika ATTACHMENT_ENABLED = True.
    """
    if not lines:
        log.warning(f"Tidak ada baris teks untuk dikirim ke {nama} ({nomor_wa})")
        return

    # 1. Buka chat dengan baris pertama di URL (di-encode)
    pesan_pertama_encoded = quote(lines[0])
    driver.get(
        f"https://web.whatsapp.com/send?phone={nomor_wa}&text={pesan_pertama_encoded}"
    )

    # Tunggu kotak pesan siap
    msg_box = find_element_any(wait, XPATHS_MSG_BOX)
    time.sleep(1.5)

    # Kirim baris ke-1
    msg_box.send_keys(Keys.ENTER)
    log.info(f"[✓] Pesan (1/{len(lines)}) terkirim → {nama} ({nomor_wa})")

    # 2. Kirim baris ke-2, 3, dst. sebagai pesan terpisah
    for idx, line in enumerate(lines[1:], start=2):
        time.sleep(getattr(config, "LINE_DELAY", 1))
        msg_box.send_keys(line)
        msg_box.send_keys(Keys.ENTER)
        log.info(f"[✓] Pesan ({idx}/{len(lines)}) terkirim → {nama} ({nomor_wa})")

    time.sleep(1)

    # 3. Upload file HANYA jika saklar ATTACHMENT_ENABLED = True
    if config.ATTACHMENT_ENABLED and file_paths:
        upload_files_selenium(driver, wait, file_paths)


# ─── Load & Validasi Data ─────────────────────────────────────────────────────
def load_data(file_path: str) -> pd.DataFrame:
    """Load Excel dan validasi kolom yang diperlukan sebelum mulai blast."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File Excel tidak ditemukan: {file_path}")

    df = pd.read_excel(file_path)
    required_cols = {"id_pelanggan", "nama", "nomor_wa", "status", "teks"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Kolom Excel tidak lengkap. Kolom hilang: {missing}")

    log.info(f"Data dimuat: {len(df)} baris dari {os.path.basename(file_path)}.")
    return df


# ─── Main ─────────────────────────────────────────────────────────────────────
def main(
    headless: bool = False,
    resume: bool = False,
    reset: bool = False,
) -> None:
    """
    Entry point utama WA Blast.
    """
    log.info("=== WA Blast Dimulai ===")

    # 1. Fail-fast: validasi data SEBELUM buka browser
    df = load_data(config.EXCEL_PATH)

    # 2. Handle checkpoint
    if reset:
        reset_checkpoint()

    start_index = load_checkpoint() if resume else 0

    if start_index >= len(df):
        log.info("Semua baris sudah terkirim (checkpoint = akhir data). Gunakan --reset untuk mulai ulang.")
        return

    df_run = df.iloc[start_index:].reset_index(drop=True)
    log.info(
        f"Akan memproses {len(df_run)} baris "
        f"(baris {start_index + 1}–{len(df)} dari total {len(df)})."
    )

    # 3. Resolusi file lampiran (jika ON)
    file_paths = []
    if config.ATTACHMENT_ENABLED:
        file_paths = [p for p in config.ATTACHMENT_FILES if os.path.exists(p)]
        if file_paths:
            log.info(f"Pengiriman lampiran AKTIF: {[os.path.basename(p) for p in file_paths]}")
        else:
            log.warning(
                "ATTACHMENT_ENABLED = True tapi tidak ada file valid yang ditemukan di ATTACHMENT_FILES."
            )
    else:
        log.info("Pengiriman lampiran MATI (ATTACHMENT_ENABLED = False).")

    # 4. Init browser & WebDriverWait
    driver = init_driver(headless=headless or config.HEADLESS_MODE)
    wait   = WebDriverWait(driver, config.WA_WAIT_TIMEOUT)
    sukses, gagal = 0, 0

    try:
        tunggu_login(driver)

        # 5. Loop pengiriman dengan progress bar tqdm
        with logging_redirect_tqdm():
            with tqdm(
                total=len(df_run),
                desc="📨 Blast",
                unit="pesan",
                file=sys.stdout,
                colour="green",
                dynamic_ncols=True,
            ) as pbar:
                for local_idx, row in df_run.iterrows():
                    global_idx = start_index + local_idx

                    id_pelanggan = row["id_pelanggan"]
                    nama         = str(row["nama"]).strip()
                    nomor_wa     = str(row["nomor_wa"]).strip()
                    status       = row["status"]
                    teks_pesan   = "" if pd.isna(row["teks"]) else str(row["teks"]).strip()

                    # Format setiap baris template di config.MSG_LINES
                    lines_to_send = []
                    for line_template in config.MSG_LINES:
                        formatted_line = line_template.format(
                            nama=nama,
                            id_pelanggan=id_pelanggan,
                            status=status,
                            teks=teks_pesan,
                        ).strip()
                        if formatted_line:  # Abaikan baris kosong
                            lines_to_send.append(formatted_line)

                    pbar.set_description(f"📨 {nama[:20]} ({nomor_wa})")

                    try:
                        kirim_pesan(
                            driver, wait, nomor_wa, nama, lines_to_send,
                            file_paths=file_paths,
                        )
                        sukses += 1
                        save_checkpoint(global_idx + 1)

                    except Exception as e:
                        log.error(f"[✗] Gagal → {nama} ({nomor_wa}): {e}")
                        gagal += 1

                    pbar.update(1)
                    pbar.set_postfix(sukses=sukses, gagal=gagal)

                    # Jeda random antar orang
                    jeda = random.randint(config.MSG_DELAY_MIN, config.MSG_DELAY_MAX)
                    log.info(f"Jeda {jeda} detik sebelum penerima berikutnya...")
                    time.sleep(jeda)

                    # Jeda batch
                    if (local_idx + 1) % config.BATCH_SIZE == 0:
                        log.info(
                            f"Jeda batch {config.BATCH_DELAY} detik "
                            f"(setelah {config.BATCH_SIZE} pesan)..."
                        )
                        time.sleep(config.BATCH_DELAY)

        log.info(f"=== SELESAI | Sukses: {sukses} | Gagal: {gagal} ===")

        # Reset checkpoint jika semua sukses (tidak ada yang perlu di-resume)
        if gagal == 0:
            reset_checkpoint()

    finally:
        driver.quit()
        log.info("Browser ditutup.")
        log.info(f"Log tersimpan: {log_file}")
        # Kirim notifikasi (email + Telegram) jika dikonfigurasi
        kirim_semua_notif(sukses, gagal, log_file)


if __name__ == "__main__":
    main()
