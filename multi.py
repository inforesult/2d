import os
import time
from playwright.sync_api import Playwright, sync_playwright, TimeoutError
from dotenv import load_dotenv
from datetime import datetime
import requests

# ====== LOAD ENVIRONMENT ======
load_dotenv()
pw = os.getenv("PW")  # password login
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")


# ====== FUNGSI UTILITAS ======
def get_wib():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_status(icon, msg):
    print(f"{icon} {msg}")


import re

def parse_saldo(saldo_text: str) -> float:
    saldo_text = saldo_text.replace("Rp.", "").replace("Rp", "").strip().replace(",", "")
    return float(saldo_text)


def kirim_telegram_log(status: str, pesan: str):
    """Kirim log ke Telegram + print ke konsol."""
    print(pesan)
    if not telegram_token or not telegram_chat_id:
        print("[⚠️] Token Telegram tidak ditemukan, lewati pengiriman.")
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{telegram_token}/sendMessage",
            data={
                "chat_id": telegram_chat_id,
                "text": pesan,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        if response.status_code != 200:
            print(f"[✗] Gagal kirim ke Telegram: {response.status_code}")
            print(f"Respon Telegram: {response.text}")
    except Exception as e:
        print(f"[!] Error kirim ke Telegram: {e}")


# ====== FUNGSI UTAMA ======
def run(playwright: Playwright, situs: str, userid: str, bet2D: str):
    wib = get_wib()
    try:
        log_status("🌐", f"Login ke situs {situs} dengan userid {userid}...")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/113.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(f"https://{situs}/#/index?category=lottery")
        time.sleep(3)

        # Hapus overlay jika ada
        page.evaluate("""() => { const mask = document.querySelector('#mask'); if (mask) mask.remove(); }""")

        # Popup login
        log_status("🔐", "Membuka popup login...")
        with page.expect_popup() as popup_info:
            page.get_by_role("heading", name="HOKI DRAW").click()
        page1 = popup_info.value

        # Login
        log_status("🔑", "Login dan navigasi ke HKDW...")
        page1.locator("input#loginUser").fill(userid)
        page1.locator("input#loginPsw").fill(pw)
        page1.get_by_text("Masuk").click()
        page1.get_by_role("link", name="Saya Setuju").click()

        # Buka menu nomor history
        page1.get_by_role("link", name="NOMOR HISTORY NOMOR").click()
        page1.locator("#marketSelect").select_option("HKDW")
        time.sleep(2)

        # Ambil nomor terbaru (baris pertama)
        nomor_terbaru = page1.locator("#historyTable tbody tr:first-child td[data-changekey='nomor']").inner_text().strip()
        log_status("📋", f"Nomor terbaru HKDW: {nomor_terbaru}")

        if len(nomor_terbaru) < 5:
            raise ValueError(f"Nomor tidak valid: {nomor_terbaru}")

        angka_ke4 = nomor_terbaru[-2]  # digit ke-4
        angka_ke5 = nomor_terbaru[-1]  # digit ke-5
        log_status("🔢", f"Digit ke-4: {angka_ke4}, Digit ke-5: {angka_ke5}")

        # Masuk ke menu 5D Angka Tarung
        page1.get_by_role("link", name="5D Angka Tarung").click()
        page1.get_by_text("FULL", exact=True).click()
        time.sleep(2)

        all_digits = ['1','2','3','4','5','6','7','8','9','0']

        # === ISI R5 (lewati angka ke-4) ===
        digits_r5 = [d for d in all_digits if d != angka_ke4]
        log_status("✏️", f"Mengisi r5[1..9] dengan melewati angka {angka_ke4}")
        for i in range(9):
            val = digits_r5[i % len(digits_r5)]
            page1.locator(f'input[name="r5\\[{i+1}\\]"]').fill(val)
            print(f"r5[{i+1}] = {val}")

        # === ISI R4 (lewati angka ke-5) ===
        digits_r4 = [d for d in all_digits if d != angka_ke5]
        log_status("✏️", f"Mengisi r4[1..9] dengan melewati angka {angka_ke5}")
        for i in range(9):
            val = digits_r4[i % len(digits_r4)]
            page1.locator(f'input[name="r4\\[{i+1}\\]"]').fill(val)
            print(f"r4[{i+1}] = {val}")

        # === ISI BET ===
        log_status("💸", f"Mengisi nilai bet dari multi.txt: {bet2D}")
        page1.locator('input[name="buy2d"]').fill(bet2D)

        # === SUBMIT TARUHAN ===
        page1.get_by_role("button", name="Calculate").click()
        page1.get_by_role("button", name="Submit").click()
        log_status("📤", "Mengirim taruhan...")

        # Tunggu konfirmasi
        try:
            page1.wait_for_selector("text=Bettingan anda berhasil dikirim.", timeout=15000)
            betting_berhasil = True
        except TimeoutError:
            betting_berhasil = False

        # Ambil saldo terakhir
        try:
            saldo_text = page1.locator("span.overage-num").inner_text().strip()
            saldo_value = parse_saldo(saldo_text)
        except:
            saldo_value = 0.0

        # Kirim hasil ke Telegram
        status_text = "SUKSES" if betting_berhasil else "GAGAL"
        pesan = (
            f"<b>[{status_text}]</b>\n"
            f"👤 {userid}\n"
            f"💰 SALDO Rp. <b>{saldo_value:,.1f}</b>\n"
            f"Nomor HKDW: {nomor_terbaru}\n"
            f"Digit ke-4: {angka_ke4}\n"
            f"Digit ke-5: {angka_ke5}\n"
            f"⌚ {wib}"
        )
        kirim_telegram_log(status_text, pesan)

        context.close()
        browser.close()

    except Exception as e:
        kirim_telegram_log("ERROR", f"<b>[ERROR]</b>\n{userid}@{situs}\n❌ {e}\n⌚ {wib}")



# ====== PEMBACA FILE MULTI.TXT ======
def main():
    if not os.path.exists("multi.txt"):
        print("❌ File multi.txt tidak ditemukan!")
        return

    with open("multi.txt", "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith("#")]

    if not lines:
        print("❌ Tidak ada data aktif di multi.txt")
        return

    with sync_playwright() as playwright:
        for line in lines:
            try:
                situs, userid, bet2D = line.split("|")
                run(playwright, situs.strip(), userid.strip(), bet2D.strip())
            except Exception as e:
                print(f"❌ Gagal membaca baris: {line} -> {e}")


if __name__ == "__main__":
    main()
