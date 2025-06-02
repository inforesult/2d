import os, re, time, pytz, requests
from datetime import datetime
from playwright.sync_api import Playwright, sync_playwright, TimeoutError

PW = os.getenv("pw")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
ALL_DIGITS = "1234567890"

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


# ─── BETTING ────────────────────────────────────────────
def run_single(playwright: Playwright, situs: str, userid: str, bet_raw: str, digit_hapus: str):
    wib_now = get_wib()
    try:
        log_status("🌐", f"{userid}@{situs} — membuka browser…")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(**playwright.devices["Pixel 7"])
        page = context.new_page()

        log_status("🔐", f"{userid}@{situs} — login ke situs…")
        page.goto(f"https://{situs}/lobby", timeout=60000)
        try:
            page.locator(".owl-wrapper").click(timeout=3000)
        except:
            pass
        page.get_by_role("textbox", name="Username").fill(userid)
        page.get_by_role("textbox", name="Password").fill(PW)
        page.get_by_role("button", name="Log in").click()
        page.get_by_role("button", name="Saya Setuju").click(timeout=15000)

        log_status("💰", f"{userid}@{situs} — mengambil saldo awal…")
        try:
            saldo_text = page.locator("#bal-text").inner_text(timeout=7000)
            saldo_awal = parse_rupiah(saldo_text)
            log_status("💸", f"{userid}@{situs} — saldo awal: Rp {saldo_awal:,.0f}")
        except:
            saldo_awal = 0.0
            log_status("⚠️", f"{userid}@{situs} — gagal ambil saldo awal!")

        saldo_akhir = saldo_awal

        log_status("🎮", f"{userid}@{situs} — membuka halaman bet HOKIDRAW…")
        page.goto(f"https://{situs}/lobby", timeout=60000)
        page.locator("#game-togel-all div").filter(has_text="HOKIDRAW").nth(1).click()
        time.sleep(3)
        page.get_by_role("button", name="Angka Tarung").click()
        time.sleep(3)
        page.get_by_role("cell", name="BET FULL").click()
        page.get_by_role("cell", name="BET FULL").click()

        # Hitung digit taruhan (hapus dari ALL_DIGITS)
        digit_bet = "".join([d for d in ALL_DIGITS if d not in digit_hapus])

        log_status("📝", f"{userid}@{situs} — mengisi form taruhan…")
        page.locator("input[name=\"r4\"]").click()
        page.locator("input[name=\"r4\"]").type(digit_bet, delay=50)
        page.locator("input[name=\"r3\"]").click()
        page.locator("input[name=\"r3\"]").type(digit_bet, delay=50)
        page.locator("input[name=\"r2\"]").click()        
        page.locator("input[name=\"r2\"]").type(digit_bet, delay=50)
        page.locator("#beli-3dset").fill(bet_raw)

        log_status("📤", f"{userid}@{situs} — mengirim taruhan…")
        page.get_by_role("button", name="Submit").click()
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Kirim").click()

        try:
            page.wait_for_selector("text=/Bet Sukses/i", timeout=15000)
            sukses = True
            log_status("✅", f"{userid}@{situs} — bet berhasil dikirim.")
        except TimeoutError:
            sukses = False
            log_status("❌", f"{userid}@{situs} — bet gagal atau timeout.")

        log_status("💰", f"{userid}@{situs} — mengambil saldo akhir…")
        try:
            page.goto(f"https://{situs}/lobby", timeout=60000)
            time.sleep(1)
            page.get_by_text("Refresh").click()
            time.sleep(2)
            saldo_text = page.locator("#bal-text").inner_text(timeout=7000)
            saldo_akhir = parse_rupiah(saldo_text)
            log_status("💸", f"{userid}@{situs} — saldo akhir: Rp {saldo_akhir:,.0f}")
        except Exception as e:
            log_status("⚠️", f"{userid}@{situs} — gagal ambil saldo akhir: {e}")

        status = "SUKSES" if sukses else "GAGAL"
        emoji = "✅" if sukses else "❌"
        tg_send(
            f"<b>[{status}]</b> {emoji}\n"
            f"👤 {userid}\n"
            f"🎯 {digit_bet}\n"
            f"💰 SALDO Rp <b>{saldo_akhir:,.0f}</b>\n"
            f"⌚ {wib_now}"
        )

    except Exception as e:
        tg_send(f"<b>[ERROR]</b>\n{userid}@{situs}\n❌ {e}\n⌚ {wib_now}")
        log_status("🔥", f"{userid}@{situs} — ERROR: {e}")
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
            situs, userid, bet, digit_hapus = (line.split("|") + [""])[:4]
            run_single(p, situs.strip(), userid.strip(), bet.strip(), digit_hapus.strip())

if __name__ == "__main__":
    if not PW:
        print("❗ ENV pw belum di-set.")
    else:
        main()
