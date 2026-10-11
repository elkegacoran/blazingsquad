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
    '//footer//div[@contenteditable="true"]',
    '//div[@data-tab="10"][@contenteditable="true"]',
    '//div[@contenteditable="true"][@data-tab="10"]',
    '//div[@role="textbox"][@contenteditable="true"]',
    '//div[@aria-placeholder][@contenteditable="true"]',
]

XPATHS_ATTACH = [
    '//span[@data-icon="plus"]',
    '//span[@data-icon="attach-menu-plus"]',
    '//span[@data-icon="clip"]',
    '//button[@aria-label="Attach"]',
    '//button[@aria-label="Lampirkan"]',
    '//div[@title="Attach"]',
    '//div[@title="Lampirkan"]',
    '//div[@aria-label="Attach"]',
    '//div[@aria-label="Lampirkan"]',
    '//*[@data-testid="clip"]',
    '//*[@data-testid="attach-menu-icon"]',
]

XPATHS_FILE_INPUT = [
    '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]',
    '//input[@type="file"]',
]

XPATHS_SEND_BTN = [
    '//span[@data-icon="wds-ic-send-filled"]',
    '//span[@data-icon="round-send-inverted"]',
    '//span[@data-icon="send"]',
    '//span[@data-icon="send"]/ancestor::div[@role="button"]',
    '//span[@data-icon="send"]/ancestor::button',
    '//div[@aria-label="Send"]',
    '//button[@aria-label="Send"]',
    '//div[@aria-label="Kirim"]',
    '//button[@aria-label="Kirim"]',
    '//*[@data-testid="send"]',
    '//span[@data-testid="send"]',
]

XPATHS_CHAT_LIST = [
    '//div[@id="pane-side"]',
    '//div[@data-testid="chat-list"]',
    '//div[@aria-label="Chat list"]',
    '//div[@aria-label="Daftar chat"]',
]

XPATHS_INVALID_POPUP = [
    '//div[contains(text(), "tidak valid")]',
    '//div[contains(text(), "invalid")]',
    '//div[contains(text(), "Phone number shared via url")]',
    '//div[contains(text(), "Nomor telepon yang dibagikan")]',
]

XPATHS_POPUP_OK_BTN = [
    '//div[@role="dialog"]//button',
    '//div[@role="dialog"]//div[@role="button"]',
    '//button[contains(., "OK") or contains(., "Ok")]',
    '//div[@role="button"][contains(., "OK") or contains(., "Ok")]',
]


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


# ─── Normalisasi Nomor Telepon ────────────────────────────────────────────────
def normalize_phone_number(raw_num) -> Optional[str]:
    """
    Normalisasi nomor telepon ke format internasional WhatsApp (62 untuk Indonesia).
    Menangani kasus:
      - 8119072423   -> 628119072423 (angka 0 terpotong oleh Excel)
      - 08119072423  -> 628119072423
      - +628119072423 -> 628119072423
      - 628119072423 -> 628119072423
    """
    if pd.isna(raw_num):
        return None

    s = str(raw_num).strip()
    if s.endswith(".0"):
        s = s[:-2]

    # Ambil hanya karakter angka
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return None

    if digits.startswith("08"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    elif digits.startswith("62"):
        pass

    if len(digits) < 9 or len(digits) > 16:
        log.warning(f"Panjang nomor tidak lazim: '{digits}' (asli: '{raw_num}')")

    return digits


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

    profile_mode = getattr(config, "PROFILE_MODE", "SEPARATE").upper()

    if profile_mode == "DEFAULT":
        # Gunakan profil Chrome utama komputer (sudah ter-login WA Web)
        if platform.system() == "Windows":
            user_data_dir = os.path.join(
                home, "AppData", "Local", "Google", "Chrome", "User Data"
            )
        else:  # Linux & macOS
            user_data_dir = os.path.join(home, ".config", "google-chrome")

        lock_file = os.path.join(user_data_dir, "SingletonLock")
        if os.path.exists(lock_file):
            log.warning(
                "⚠️ PERINGATAN: Profil Chrome utama sedang terkunci (Google Chrome sedang terbuka). "
                "Tutup Google Chrome Anda terlebih dahulu atau ganti PROFILE_MODE = 'SEPARATE' di config.py!"
            )
        log.info(f"Menggunakan profil Chrome UTAMA: {user_data_dir}")
    else:
        # Gunakan profil Chrome terpisah khusus bot (aman & bebas bentrok)
        default_separate_dir = getattr(
            config,
            "CHROME_PROFILE_DIR",
            os.path.join(config.BASE_DIR, ".chrome_profile")
        )
        user_data_dir = default_separate_dir
        os.makedirs(user_data_dir, exist_ok=True)
        log.info(f"Menggunakan profil Chrome TERPISAH (Bebas Bentrok): {user_data_dir}")

    options.add_argument(f"user-data-dir={user_data_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")

    # Anti-deteksi automation sederhana
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Flag stabilitas untuk Linux & headless
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

    wait_login = WebDriverWait(driver, config.LOGIN_TIMEOUT)
    for xpath in XPATHS_CHAT_LIST:
        try:
            wait_login.until(EC.presence_of_element_located((By.XPATH, xpath)))
            log.info("WhatsApp Web siap dan ter-autentikasi.")
            return
        except Exception:
            continue

    log.warning(
        "Timeout menunggu WA Web. Pastikan sudah scan QR Code (jika mode terpisah), lalu jalankan ulang script."
    )


# ─── Deteksi Nomor Invalid ────────────────────────────────────────────────────
def cek_nomor_invalid(driver: webdriver.Chrome) -> bool:
    """Periksa apakah WhatsApp Web menampilkan modal nomor tidak valid."""
    for xpath in XPATHS_INVALID_POPUP:
        elems = driver.find_elements(By.XPATH, xpath)
        if elems and any(e.is_displayed() for e in elems):
            log.warning("Peringatan dari WhatsApp: Nomor telepon tidak valid / tidak terdaftar.")
            # Coba klik tombol OK/Tutup agar dialog hilang
            for btn_xpath in XPATHS_POPUP_OK_BTN:
                btns = driver.find_elements(By.XPATH, btn_xpath)
                if btns:
                    try:
                        btns[0].click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btns[0])
                    break
            return True
    return False


def tunggu_chat_ready(driver: webdriver.Chrome, timeout: int = 20):
    """
    Tunggu kotak pesan siap, atau tangkap lebih awal jika muncul dialog nomor invalid.
    Return: WebElement kotak pesan jika siap, None jika nomor tidak valid/gagal.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        if cek_nomor_invalid(driver):
            return None

        for xpath in XPATHS_MSG_BOX:
            elems = driver.find_elements(By.XPATH, xpath)
            if elems and elems[0].is_displayed():
                return elems[0]

        time.sleep(0.5)

    if cek_nomor_invalid(driver):
        return None

    raise TimeoutError(f"Timeout {timeout} detik menunggu kotak pesan WhatsApp.")


# ─── Full Selenium File Upload ─────────────────────────────────────────────────
def upload_files_selenium(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    file_paths: list,
) -> bool:
    """
    Upload satu atau lebih file via Selenium secara andal.
    Mendukung format gambar & dokumen.
    """
    valid_paths = [os.path.abspath(p) for p in file_paths if os.path.exists(p)]
    if not valid_paths:
        log.warning("Tidak ada file valid untuk diupload, lewati upload.")
        return False

    wait_short = WebDriverWait(driver, config.ATTACH_WAIT_TIMEOUT)

    def klik_tombol_send() -> bool:
        """Cari dan klik tombol Send di layar preview media."""
        time.sleep(2)  # Beri waktu render modal preview
        for xpath in XPATHS_SEND_BTN:
            try:
                send_btn = wait_short.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                try:
                    send_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", send_btn)
                log.info(f"Tombol Send diklik via XPath: {xpath}")
                time.sleep(3)
                return True
            except Exception:
                continue
        return False

    try:
        # ── Strategi 1: Direct File Input jika sudah ada di DOM ────────────────
        for xpath in XPATHS_FILE_INPUT:
            inputs = driver.find_elements(By.XPATH, xpath)
            if inputs:
                try:
                    for p in valid_paths:
                        inputs[0].send_keys(p)
                    log.info(f"File diinput langsung: {[os.path.basename(p) for p in valid_paths]}")
                    if klik_tombol_send():
                        log.info("File berhasil dikirim (Strategi 1: Direct Input).")
                        return True
                except Exception:
                    pass

        # ── Strategi 2: Klik tombol Attach (+ / klip) -> upload ke file input ──
        attach_clicked = False
        for xpath in XPATHS_ATTACH:
            try:
                btn = wait_short.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                attach_clicked = True
                log.info(f"Tombol attach diklik via XPath: {xpath}")
                time.sleep(1.5)
                break
            except Exception:
                continue

        if attach_clicked:
            for xpath in XPATHS_FILE_INPUT:
                try:
                    fi = wait_short.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    for p in valid_paths:
                        fi.send_keys(p)
                    log.info(f"File dipilih setelah klik attach: {[os.path.basename(p) for p in valid_paths]}")
                    if klik_tombol_send():
                        log.info("File berhasil dikirim (Strategi 2: Klik Attach).")
                        return True
                except Exception:
                    continue

        # ── Strategi 3: JS Fallback unhide input file ──────────────────────────
        log.info("Mencoba JS Fallback untuk upload file...")
        file_inputs = driver.execute_script(
            "return Array.from(document.querySelectorAll('input[type=\"file\"]'));"
        )
        if file_inputs:
            for fi in file_inputs:
                try:
                    driver.execute_script(
                        "arguments[0].style.display='block';"
                        "arguments[0].style.visibility='visible';"
                        "arguments[0].style.opacity='1';"
                        "arguments[0].style.width='10px';"
                        "arguments[0].style.height='10px';",
                        fi,
                    )
                    for p in valid_paths:
                        fi.send_keys(p)
                    log.info(f"File dipilih via JS fallback: {[os.path.basename(p) for p in valid_paths]}")
                    if klik_tombol_send():
                        log.info("File berhasil dikirim via JS fallback.")
                        return True
                except Exception:
                    continue

        log.error("Semua strategi upload file gagal.")
        return False

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
) -> bool:
    """
    Kirim daftar baris pesan ke satu nomor WA (1 baris = 1 pesan terpisah).
    Selanjutnya kirim lampiran jika ATTACHMENT_ENABLED = True.
    Return True jika sukses, False jika gagal (nomor invalid, dll).
    """
    if not lines:
        log.warning(f"Tidak ada baris teks untuk dikirim ke {nama} ({nomor_wa})")
        return False

    # 1. Buka chat dengan baris pertama di URL (di-encode)
    pesan_pertama_encoded = quote(lines[0])
    driver.get(
        f"https://web.whatsapp.com/send?phone={nomor_wa}&text={pesan_pertama_encoded}"
    )

    # 2. Tunggu kotak pesan siap atau deteksi nomor tidak valid
    msg_box = tunggu_chat_ready(driver, config.WA_WAIT_TIMEOUT)
    if msg_box is None:
        log.error(f"[✗] Nomor tidak valid / tidak terdaftar di WA → {nama} ({nomor_wa})")
        return False

    time.sleep(1.5)

    # Kirim baris ke-1
    msg_box.send_keys(Keys.ENTER)
    log.info(f"[✓] Pesan (1/{len(lines)}) terkirim → {nama} ({nomor_wa})")

    # 3. Kirim baris ke-2, 3, dst. sebagai pesan terpisah
    for idx, line in enumerate(lines[1:], start=2):
        time.sleep(getattr(config, "LINE_DELAY", 1))
        msg_box.send_keys(line)
        msg_box.send_keys(Keys.ENTER)
        log.info(f"[✓] Pesan ({idx}/{len(lines)}) terkirim → {nama} ({nomor_wa})")

    time.sleep(1.5)

    # 4. Upload file HANYA jika saklar ATTACHMENT_ENABLED = True
    if config.ATTACHMENT_ENABLED and file_paths:
        upload_ok = upload_files_selenium(driver, wait, file_paths)
        if not upload_ok:
            log.warning(f"Pesan teks terkirim tapi lampiran gagal untuk {nama} ({nomor_wa})")

    return True


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
    driver = None
    sukses, gagal = 0, 0

    try:
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

        # 4. Init browser & WebDriverWait dengan proteksi error
        try:
            driver = init_driver(headless=headless or config.HEADLESS_MODE)
        except Exception as e:
            log.exception(f"FATAL: Gagal membuka browser Chrome: {e}")
            log.error(
                "TIPS: Pastikan Google Chrome tidak sedang dibuka jika PROFILE_MODE='DEFAULT', "
                "atau gunakan PROFILE_MODE='SEPARATE' di config.py agar bot memiliki profil tersendiri."
            )
            return

        wait = WebDriverWait(driver, config.WA_WAIT_TIMEOUT)
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
                    raw_wa       = row["nomor_wa"]
                    status       = row["status"]
                    teks_pesan   = "" if pd.isna(row["teks"]) else str(row["teks"]).strip()

                    nomor_wa = normalize_phone_number(raw_wa)
                    if not nomor_wa:
                        log.error(f"[✗] Nomor WA kosong atau tidak valid untuk {nama} ({raw_wa}), lewati.")
                        gagal += 1
                        pbar.update(1)
                        pbar.set_postfix(sukses=sukses, gagal=gagal)
                        continue

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
                        berhasil = kirim_pesan(
                            driver, wait, nomor_wa, nama, lines_to_send,
                            file_paths=file_paths,
                        )
                        if berhasil:
                            sukses += 1
                            save_checkpoint(global_idx + 1)
                        else:
                            gagal += 1

                    except Exception as e:
                        log.error(f"[✗] Gagal → {nama} ({nomor_wa}): {e}")
                        gagal += 1

                    pbar.update(1)
                    pbar.set_postfix(sukses=sukses, gagal=gagal)

                    # Jeda random antar orang (hanya jika belum mencapai pesan terakhir)
                    if local_idx < len(df_run) - 1:
                        jeda = random.randint(config.MSG_DELAY_MIN, config.MSG_DELAY_MAX)
                        log.info(f"Jeda {jeda} detik sebelum penerima berikutnya...")
                        time.sleep(jeda)

                    # Jeda batch
                    if (local_idx + 1) % config.BATCH_SIZE == 0 and (local_idx < len(df_run) - 1):
                        log.info(
                            f"Jeda batch {config.BATCH_DELAY} detik "
                            f"(setelah {config.BATCH_SIZE} pesan)..."
                        )
                        time.sleep(config.BATCH_DELAY)

        log.info(f"=== SELESAI | Sukses: {sukses} | Gagal: {gagal} ===")

        # Reset checkpoint jika semua sukses
        if gagal == 0:
            reset_checkpoint()

    except Exception as e:
        log.exception(f"FATAL: Terjadi kesalahan tak terduga: {e}")

    finally:
        if driver is not None:
            try:
                driver.quit()
                log.info("Browser ditutup.")
            except Exception as e:
                log.debug(f"Error saat menutup browser: {e}")

        log.info(f"Log tersimpan: {log_file}")
        # Kirim notifikasi (email + Telegram) jika dikonfigurasi
        try:
            kirim_semua_notif(sukses, gagal, log_file)
        except Exception as e:
            log.error(f"Gagal mengirim notifikasi laporan: {e}")


if __name__ == "__main__":
    main()
