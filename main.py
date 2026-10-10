import argparse
from whatsapp_blast import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wa_blast",
        description="WA Blast — Kirim pesan WhatsApp otomatis ke pelanggan PLN UP3 Makassar Selatan",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Jalankan Chrome tanpa tampilan visual (headless mode).\n"
            "⚠️  WA Web kadang memblokir sesi headless — test dulu sebelum production."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Lanjutkan pengiriman dari baris terakhir sebelum crash.\n"
            "Membaca posisi dari file checkpoint.txt."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Hapus checkpoint dan mulai ulang dari baris pertama.\n"
            "Gunakan jika ingin kirim ulang semua data dari awal."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(headless=args.headless, resume=args.resume, reset=args.reset)
