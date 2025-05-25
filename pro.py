import os, re, time, pytz, requests
from datetime import datetime
from playwright.sync_api import Playwright, sync_playwright, TimeoutError

PW = os.getenv("pw")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
ALL_DIGITS = "1234567890"
MAX_PAGES_SEARCH = 5

# ─── UTIL ──────────────────────────────────────────────
def get_wib() -> str:
    return datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M WIB")

def log_status(emoji: str, msg: str):
    print(f"{emoji} {msg}")

def read_file(name: str) -> str:
    with open(name, "r", encoding="utf-8") as f:
        return f.read().strip()

def tg_send(msg: str):
    print(msg)
    if TG_TOKEN and TG_CHAT:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
                timeout=15,
            )
            if r.status_code != 200:
                print("❌ Telegram gagal:", r.text)
        except Exception as e:
            print("❌ Error Telegram:", e)

def parse_rupiah(text: str) -> float:
    return float(re.sub(r"[^\d]", "", text))


# ─── AMBIL 23 NOMOR TERAKHIR ───────────────────────────
def ambil_nomor_23_periode_lalu(page):
    hasil = []

    try:
        # Klik "HOKIDRAW"
        page.get_by_role("button", name="HOKIDRAW").click(timeout=5000)
        time.sleep(3)
        
        # Baca periode sekarang
        periode_sekarang_elem = page.locator("//table//tr[1]/td[3]")
        periode_sekarang = int(periode_sekarang_elem.inner_text(timeout=7000).strip())

        # Klik tombol angka "3"
        page.get_by_text("3", exact=True).click(timeout=5000)
        time.sleep(3)

        # Ambil semua baris dari tabel
        rows = page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            tgl = row.locator("td").nth(0).inner_text().strip()
            periode = int(row.locator("td").nth(2).inner_text().strip())
            result = row.locator("td").nth(3).locator("a").inner_text().strip()

            hasil.append({
                "tanggal": tgl,
                "periode": periode,
                "result": result
            })

        target_periode = periode_sekarang - 23
        hasil_terakhir = [h for h in hasil if h["periode"] == target_periode]

        return hasil_terakhir

    except Exception as e:
        print("❌ Error parsing periode:", e)
        return []

# ─── BETTING ────────────────────────────────────────────
def run_single(playwright: Playwright, situs: str, userid: str, bet_raw: str):
    wib_now = get_wib()
    try:
        log_status("🌐", f"{userid}@{situs} — membuka browser…")
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(**playwright.devices["Pixel 7"])
        page = context.new_page()

        # LOGIN
        page.goto(f"https://{situs}/", timeout=60000)
        try:
            page.locator(".owl-wrapper").click(timeout=3000)
        except:
            pass
        page.get_by_role("textbox", name="Username").fill(userid)
        page.get_by_role("textbox", name="Password").fill(PW)
        page.get_by_role("button", name="Log in").click()
        page.get_by_role("button", name="Saya Setuju").click(timeout=15000)

        # Ambil saldo awal
        try:
            saldo_text = page.locator("#bal-text").inner_text(timeout=7000)
            saldo_awal = parse_rupiah(saldo_text)
        except:
            saldo_awal = 0.0

        saldo_akhir = saldo_awal  # Set default agar tidak unbound

        # HISTORY
        page.goto(f"https://{situs}/history/v2", timeout=30000)
        time.sleep(3)
        nomor_target = ambil_nomor_23_periode_lalu(page)
        if not nomor_target:
            raise Exception("Gagal ambil 23 periode terakhir!")

        dua_digit = [n["result"][-2:] for n in nomor_target]
        dua_digit_flat = "".join(set("".join(dua_digit)))
        digit_isi = "".join(d for d in ALL_DIGITS if d not in dua_digit_flat)

        log_status("🔢", f"Periode-23 = {nomor_target[-1] if nomor_target else '-'} → dua digit: {dua_digit} → digit_isi: {digit_isi}")

        # BET
        page.goto(f"https://{situs}/lobby", timeout=60000)
        page.locator("#game-togel-all div").filter(has_text="HOKIDRAW").nth(1).click()
        time.sleep(3)
        page.get_by_role("button", name="BB Campuran").click()
        time.sleep(3)
        page.get_by_role("cell", name="BET FULL").click()
        page.get_by_role("cell", name="BET FULL").click()
        page.get_by_role("textbox", name=re.compile(r"Digit.*9", re.I)).fill(digit_isi)
        page.locator('input[name="uang2d"]').fill(bet_raw)
        # Kirim taruhan
        page.get_by_role("button", name="Submit").click()
        # hanya satu handler
        page.get_by_role("button", name="Kirim").click()
        page.once("dialog", lambda d: d.accept())


        try:
            page.wait_for_selector("text=/Bet Sukses/i", timeout=15000)
            sukses = True
        except TimeoutError:
            sukses = False

        # Ambil saldo setelah bet (harus kembali ke halaman lobby)
        try:
            page.goto(f"https://{situs}/lobby", timeout=60000)
            time.sleep(3)
            saldo_text = page.locator("#bal-text").inner_text(timeout=7000)
            saldo_akhir = parse_rupiah(saldo_text)
        except Exception as e:
            print("❌ Gagal ambil saldo akhir:", e)

        status = "SUKSES" if sukses else "GAGAL"
        emoji = "✅" if sukses else "❌"
        tg_send(
            f"<b>[{status}]</b> {emoji}\n"
            f"👤 {userid}\n"
            f"🎯 {dua_digit[-1] if dua_digit else '-'}\n"
            f"💰 SALDO Rp <b>{saldo_akhir:,.0f}</b>\n"
            f"⌚ {wib_now}"
        )

    except Exception as e:
        tg_send(f"<b>[ERROR]</b>\n{userid}@{situs}\n❌ {e}\n⌚ {wib_now}")
    finally:
        try:
            context.close()
            browser.close()
        except:
            pass

# ─── MAIN ───────────────────────────────────────────────
def main():
    log_status("🚀", "Mulai eksekusi multi-akun…")
    rows = read_file("multi.txt").splitlines()
    with sync_playwright() as p:
        for line in rows:
            if line.strip().startswith("#") or "|" not in line:
                continue
            situs, userid, bet = (line.split("|") + [""])[:3]
            run_single(p, situs.strip(), userid.strip(), bet.strip())

if __name__ == "__main__":
    if not PW:
        print("❗ ENV pw belum di-set.")
    else:
        main()
