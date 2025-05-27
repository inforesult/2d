import time
import random
from playwright.sync_api import Playwright, sync_playwright, TimeoutError
from datetime import datetime
import pytz
import requests
import os
import re

# ───── ENV ──────────────────────────────────────────────
pw               = os.getenv("pw")
telegram_token   = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# ───── UTIL ─────────────────────────────────────────────
def get_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M WIB")

def log_status(emoji: str, message: str):
    print(f"{emoji} {message}")

def baca_file(file_name: str) -> str:
    with open(file_name, "r") as file:
        return file.read().strip()

def kirim_telegram_log(status: str, pesan: str):
    print(pesan)
    if telegram_token and telegram_chat_id:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                data={
                    "chat_id": telegram_chat_id,
                    "text": pesan,
                    "parse_mode": "HTML",
                },
            )
            if response.status_code != 200:
                print(f"Gagal kirim ke Telegram. Status: {response.status_code}")
                print(f"Respon Telegram: {response.text}")
        except Exception as e:
            print("Error saat mengirim ke Telegram:", e)

def parse_saldo(saldo_text: str) -> float:
    saldo_text = (
        saldo_text.replace("Rp.", "")
        .replace("Rp", "")
        .strip()
        .replace(",", "")
    )
    return float(saldo_text)

# ───── FUNGSI BARU: ambil nomor periode-23 ──────────────
def ambil_nomor_23_periode_lalu(page1):
    ROWS_SEL = "table#historyTable tbody tr"
    page1.wait_for_selector(ROWS_SEL)

    first_period = int(
        page1.locator(ROWS_SEL).first.locator("td").nth(0).inner_text().strip()
    )
    target_period = first_period - 23

    for _ in range(5):
        rows = page1.locator(ROWS_SEL)
        for i in range(rows.count()):
            periode = int(rows.nth(i).locator("td").nth(0).inner_text().strip())
            if periode == target_period:
                nomor = rows.nth(i).locator("td").nth(3).inner_text().strip()
                return nomor

        # ganti ke pencarian tombol berdasarkan role (name="›")
        next_btn = page1.get_by_role("link", name="›")
        if next_btn.is_disabled():
            break
        next_btn.click()
        page1.wait_for_selector(ROWS_SEL)

    raise ValueError(f"Periode {target_period} tidak ditemukan dalam 5 halaman")


# ───── CORE RUN ─────────────────────────────────────────
def run(playwright: Playwright, situs: str, userid: str, bet_raw: str = ""):
    wib = get_wib()
    try:
        log_status("🌐", f"Login ke situs {situs} dengan userid {userid}...")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/113.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(f"https://{situs}/#/index?category=lottery")
        time.sleep(3)
        time.sleep(5)

        # hapus overlay jika ada
        log_status("🧹", "Mengecek dan menghapus overlay jika ada...")
        removed = page.evaluate(
            """() => {
            const mask = document.querySelector('#mask');
            if (mask) { mask.remove(); return 1; }
            return 0;
        }"""
        )
        log_status("🧾", f"Overlay dihapus: {'YA' if removed else 'TIDAK'}")

        # buka popup login
        log_status("🔓", "Menunggu popup login terbuka...")
        with page.expect_popup() as popup_info:
            page.get_by_role("heading", name="HOKI DRAW").click()
        page1 = popup_info.value

        # login
        log_status("🔐", "Mengisi form login...")
        page1.locator("input#loginUser").wait_for()
        page1.locator("input#loginUser").type(userid, delay=100)
        page1.locator("input#loginPsw").type(pw, delay=120)
        page1.locator("div.login-btn").click()

        # persetujuan (jika ada)
        try:
            page1.get_by_role("link", name="Saya Setuju").wait_for(timeout=10000)
            page1.get_by_role("link", name="Saya Setuju").click()
        except:
            log_status("✅", "Tidak ada persetujuan, lanjut...")

        # saldo awal
        log_status("💰", "Mengambil saldo awal...")
        try:
            saldo_text = page1.locator("span.overage-num").inner_text().strip()
            saldo_value = parse_saldo(saldo_text)
        except:
            saldo_text = "tidak diketahui"
            saldo_value = 0.0

        # buka history
        page1.get_by_role("link", name="NOMOR HISTORY NOMOR").dblclick()
        page1.wait_for_selector("table#historyTable")

        # ─── ambil nomor 23 periode sebelumnya ───
        nomor_target = ambil_nomor_23_periode_lalu(page1)
        digit_hapus = nomor_target[-3:]

        print(f"Nomor periode-23: {nomor_target}, digit akhir: {digit_hapus}")

        # ─── Buat digit_isi acak dengan 3 angka dihapus ───
        all_digits = list("0123456789")
        random.shuffle(all_digits)

        # Ambil angka unik dari digit_hapus (3 digit akhir dari periode-23)
        angka_dihapus = list(set(digit_hapus))

        # Tambahkan angka acak dari sisa angka jika kurang dari 3
        sisa_angka = [d for d in all_digits if d not in angka_dihapus]
        random.shuffle(sisa_angka)

        while len(angka_dihapus) < 3 and sisa_angka:
            angka_dihapus.append(sisa_angka.pop())

        # Buat digit_isi: maksimal 7 angka dari all_digits, tanpa angka_dihapus
        digit_isi = "".join(d for d in all_digits if d not in angka_dihapus)[:7]

        # Debug info
        print(f"Nomor periode-23: {nomor_target}, tiga digit akhir: {digit_hapus}")
        print(f"Digit dihapus: {angka_dihapus}")
        print(f"Angka untuk diisi: {digit_isi}")
        print(f"Angka untuk diisi: {digit_isi}")
        time.sleep(3)

        # menu betting
        log_status("🎯", "Masuk ke menu betting 5dFast...")
        page1.get_by_role("link", name="5D BB Campuran").click()
        time.sleep(3)
        for _ in range(5):
            page1.get_by_role("listitem").filter(
                has_text=re.compile(r"^FULL$")
            ).click()

        # isi betting
        log_status("✍️", "Mengisi form betting...")
        page1.get_by_role("textbox", name="digit - 8 digit").click()
        page1.get_by_role("textbox", name="digit - 8 digit").fill(digit_isi)
        input3d = page1.locator("input#buy3d")
        input3d.fill("")
        input3d.type(str(bet_raw), delay=80)
        page1.get_by_role("button", name="Calculate").click()
        time.sleep(3)
        page1.get_by_role("button", name="Submit").click()

        # konfirmasi
        log_status("⏳", "Menunggu konfirmasi betting...")
        try:
            page1.wait_for_selector(
                "text=Bettingan anda berhasil dikirim.", timeout=15000
            )
            betting_berhasil = True
        except:
            betting_berhasil = False

        # saldo akhir
        try:
            saldo_text = page1.locator("span.overage-num").inner_text().strip()
            saldo_value = parse_saldo(saldo_text)
        except:
            saldo_value = 0.0

        # kirim telegram
        if betting_berhasil:
            pesan = (
                f"<b>[SUKSES]</b>\n"
                f"👤 {userid}\n"
                f"🎯 PERIOD-23: {digit_hapus}\n"
                f"🚫 DIHAPUS: <b>{', '.join(angka_dihapus)}</b>\n"
                f"💰 SALDO KAMU Rp. <b>{saldo_value:,.0f}</b>\n"
                f"⌚ {wib}"
            )
            kirim_telegram_log("SUKSES", pesan)
        else:
            pesan = (
                f"<b>[GAGAL]</b>\n"
                f"👤 {userid}\n"
                f"🎯 PERIOD-23: {digit_hapus}\n"
                f"🚫 DIHAPUS: <b>{', '.join(angka_dihapus)}</b>\n"
                f"💰 SALDO KAMU Rp. <b>{saldo_value:,.0f}</b>\n"
                f"⌚ {wib}"
            )
            kirim_telegram_log("GAGAL", pesan)

        context.close()
        browser.close()

    except Exception as e:
        kirim_telegram_log(
            "GAGAL",
            f"<b>[ERROR]</b>\n{userid}@{situs}\n❌ {str(e)}\n⌚ {wib}",
        )

# ───── MAIN MULTI-AKUN ─────────────────────────────────
def main():
    log_status("🚀", "Mulai eksekusi multi akun...")
    bets = baca_file("multi.txt").splitlines()
    with sync_playwright() as playwright:
        for baris in bets:
            if "|" not in baris or baris.strip().startswith("#"):
                continue
            parts = baris.strip().split("|")
            if len(parts) < 3:
                continue
            situs, userid, bet_raw = (parts + [""] * 3)[:3]
            run(playwright, situs.strip(), userid.strip(), bet_raw.strip())

if __name__ == "__main__":
    main()
