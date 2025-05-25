def run(playwright: Playwright) -> int:
    sites = baca_file_list("multi.txt")
    pw_env = os.getenv("pw")
    ada_error = False

    for entry in sites:
        try:
            # Format: situs|userid|bet3D|bet4D|config1,config2,...
            parts = entry.split('|')
            if len(parts) < 2:
                print(f"❌ Format tidak valid: {entry}")
                continue

            site, userid_site = parts[0].strip(), parts[1].strip()
            full_url = f"https://{site}/lite"

            print(f"🌐 Membuka browser untuk {site}...")
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(**playwright.devices["Pixel 7"])
            page = context.new_page()

            page.goto(full_url, timeout=60000)

            if not userid_site or not pw_env:
                raise Exception("Username atau Password kosong!")

            page.locator("#entered_login").fill(userid_site)
            page.locator("#entered_password").fill(pw_env)
            page.get_by_role("button", name="Login").click()
            time.sleep(1)
            page.get_by_role("link", name="Transaction").click()
            print(f"🔎 Mengecek saldo dan riwayat kemenangan di {site}...")
            time.sleep(1)
            page.wait_for_selector("table.history tbody#transaction", timeout=30000)

            rows = page.locator("table.history tbody#transaction tr").all()

            if not rows:
                print(f"Tabel kosong di {site}")
                continue

            first_row = rows[0]
            cols = first_row.locator("td").all()

            if len(cols) >= 5:
                raw_saldo = cols[4].inner_text().strip()
                current_saldo = int(float(raw_saldo))

                keterangan = cols[2].inner_text().strip()
                status_full = cols[3].inner_text().strip()

                if "Menang Pool HOKIDRAW" in keterangan:
                    match = re.search(r"Menang\s*([\d.,]+)", status_full)
                    nilai_menang = match.group(1) if match else "Tidak ditemukan"

                    pesan_menang = (
                        f"<b>{userid_site}</b>\n"
                        f"<b>🏆 Menang</b>\n"
                        f"🎯 Menang {format_rupiah(nilai_menang)}\n"
                        f"💰 Saldo: {format_rupiah(current_saldo)}\n"
                        f"⌚ {wib()}"
                    )
                    kirim_telegram_log(pesan_menang, parse_mode="HTML")
                else:
                    pesan_kalah = (
                        f"<b>{userid_site}</b>\n"
                        f"<b>😢 Tidak Menang</b>\n"
                        f"💰 Saldo: {format_rupiah(current_saldo)}\n"
                        f"⌚ {wib()}"
                    )
                    kirim_telegram_log(pesan_kalah, parse_mode="HTML")

                # ==== AUTO WD LOGIC ====
                try:
                    if os.path.exists("autowd.txt"):
                        autowd_config = baca_file("autowd.txt")
                        if ':' in autowd_config:
                            batas_str, wd_amount_str = autowd_config.split(":")
                            batas_saldo = int(batas_str.strip())
                            wd_amount = wd_amount_str.strip()

                            if current_saldo >= batas_saldo:
                                print(f"💳 Saldo {current_saldo} >= {batas_saldo}, melakukan auto withdraw {wd_amount}")
                                page.get_by_role("link", name="Back to Menu").click()
                                time.sleep(1)
                                page.get_by_role("link", name="Withdraw").click()
                                time.sleep(1)
                                page.get_by_role("textbox", name="Withdraw").click()
                                time.sleep(1)
                                page.get_by_role("textbox", name="Withdraw").fill(wd_amount)
                                time.sleep(1)
                                page.get_by_role("button", name="Kirim").click()
                                time.sleep(2)

                                page.wait_for_selector("text=berhasil", timeout=15000)

                                kirim_telegram_log(
                                    f"<b>{userid_site}</b>\n"
                                    f"✅ Auto WD {format_rupiah(wd_amount)} berhasil\n"
                                    f"💰 Saldo sisa: {format_rupiah(current_saldo - int(wd_amount))}\n"
                                    f"⌚ {wib()}",
                                    parse_mode="HTML"
                                )
                except Exception as e:
                    print(f"⚠️ Gagal auto WD: {e}")

            context.close()
            browser.close()

        except Exception as e:
            ada_error = True
            print(f"❌ Error di {site}: {e}")
            try:
                context.close()
                browser.close()
            except:
                pass
            continue

    return 1 if ada_error else 0
