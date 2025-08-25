import requests
import schedule
import time
import hashlib

# --- Telegram Bot Bilgileri ---
BOT_TOKEN = "8073866792:AAFYIPIahzHjuOkVR0RxXeqDbfJBEHserLc"
CHAT_ID = "797882093"

# --- Kontrol edilecek siteler ---
URLS = [
    "https://docs.siberaltay.org/",
"https://siberaltay.org/",
"https://yavuzlar.org/",
"https://yildizcti.com/",
    "https://sibervatan.org/"
]

# İlk içeriklerin saklanacağı dict
stored_hashes = {}

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"[!] Telegram gönderim hatası: {e}")

def check_sites():
    global stored_hashes
    for site in URLS:
        try:
            r = requests.get(site, timeout=10)
            r.raise_for_status()
            content_hash = hashlib.sha256(r.text.encode()).hexdigest()

            if site not in stored_hashes:
                # İlk kez kaydet
                stored_hashes[site] = content_hash
                print(f"[+] {site} için başlangıç hash kaydedildi")
            else:
                if stored_hashes[site] != content_hash:
                    send_telegram(f"⚠️ {site} içeriği değişti!")
                    stored_hashes[site] = content_hash
                    print(f"[!] {site} değişti, Telegram’a bildirildi.")
                else:
                    print(f"[-] {site} değişmedi.")
        except Exception as e:
            print(f"[!] {site} kontrol hatası: {e}")

# --- 15 dakikada bir çalıştır ---
schedule.every(15).minutes.do(check_sites)

print("[*] Site kontrol sistemi başladı...")

while True:
    schedule.run_pending()
    time.sleep(5)
