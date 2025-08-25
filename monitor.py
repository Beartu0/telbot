import os, time, json, hashlib, requests, schedule
from urllib.parse import urlparse

# === Telegram ayarları (Railway'de ENV olarak ver) ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHAT_ID   = os.getenv("CHAT_ID",   "PUT_CHAT_ID_HERE")

# === Kalıcı durum dosyası ===
STATE_FILE = "state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"urls": [], "hashes": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(STATE, f, ensure_ascii=False, indent=2)

STATE = load_state()

# === Telegram yardımcıları ===
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_msg(text):
    try:
        requests.post(f"{TG_API}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print(f"[!] Telegram gönderim hatası: {e}")

def fetch_updates(offset=None, timeout=25):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=timeout+5)
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:
        print(f"[!] getUpdates hatası: {e}")
        return []

# === Site kontrol ===
def normalize_url(u: str) -> str:
    u = u.strip()
    if not u:
        return u
    if not urlparse(u).scheme:
        u = "http://" + u  # şema yoksa http varsay
    return u

def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

def check_site_once(url: str) -> tuple[bool, str]:
    """True->değişti, False->değişmedi | mesaj"""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        h = hash_content(r.text)
        prev = STATE["hashes"].get(url)
        if prev is None:
            STATE["hashes"][url] = h
            save_state()
            return (False, f"➕ İlk kez kaydedildi: {url}")
        if prev != h:
            STATE["hashes"][url] = h
            save_state()
            return (True,  f"⚠️ İçerik değişti: {url}")
        return (False, f"✓ Değişiklik yok: {url}")
    except Exception as e:
        return (False, f"❌ Erişim hatası ({url}) → {e}")

def check_all_sites():
    if not STATE["urls"]:
        print("[i] İzlenen URL yok.")
        return
    for u in list(STATE["urls"]):
        changed, msg = check_site_once(u)
        print(msg)
        if changed:
            send_msg(msg)

# === Komut işleme ===
def cmd_urls():
    if not STATE["urls"]:
        send_msg("📭 İzlenen URL yok. `/add <url>` ile ekleyebilirsin.")
        return
    lines = [f"{i+1}. {u}" for i, u in enumerate(STATE["urls"])]
    send_msg("📄 İzlenen URL'ler:\n" + "\n".join(lines))

def cmd_status():
    total = len(STATE["urls"])
    send_msg(f"ℹ️ İzlenen site sayısı: {total}\n"
             f"`/urls` ile listeyi görebilir, `/check` ile anlık kontrol yapabilirsin.")

def cmd_check():
    if not STATE["urls"]:
        send_msg("📭 İzlenen URL yok. Önce `/add <url>` ekle.")
        return
    send_msg("🔎 Anlık kontrol başlıyor...")
    for u in list(STATE["urls"]):
        changed, msg = check_site_once(u)
        send_msg(msg)

def cmd_add(arg: str):
    u = normalize_url(arg)
    if not u:
        send_msg("⚠️ Kullanım: `/add <url>`")
        return
    if u in STATE["urls"]:
        send_msg(f"ℹ️ Zaten listede: {u}")
        return
    STATE["urls"].append(u)
    save_state()
    # İlk hash'i al
    _, msg = check_site_once(u)
    send_msg(f"✅ Eklendi: {u}\n{msg}")

def cmd_remove(arg: str):
    if not STATE["urls"]:
        send_msg("📭 Liste boş.")
        return
    target = arg.strip()
    removed = None
    # index ile silme (/remove 2)
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(STATE["urls"]):
            removed = STATE["urls"].pop(idx)
    else:
        # URL ile silme
        target = normalize_url(target)
        if target in STATE["urls"]:
            STATE["urls"].remove(target)
            removed = target
    if removed:
        STATE["hashes"].pop(removed, None)
        save_state()
        send_msg(f"🗑️ Silindi: {removed}")
    else:
        send_msg("⚠️ Bulunamadı. Kullanım: `/remove <url|index>`")

def handle_command(text: str):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) == 2 else ""

    if cmd == "/urls":
        cmd_urls()
    elif cmd == "/status":
        cmd_status()
    elif cmd == "/check":
        cmd_check()
    elif cmd == "/add":
        cmd_add(arg)
    elif cmd == "/remove":
        cmd_remove(arg)
    elif cmd in ("/start", "/help"):
        send_msg(
            "👋 Komutlar:\n"
            "/urls – izlenen URL'leri göster\n"
            "/status – özet durum\n"
            "/check – anlık kontrol yap\n"
            "/add <url> – listeye ekle\n"
            "/remove <url|index> – listeden sil"
        )
    else:
        send_msg("❔ Bilinmeyen komut. /help yaz.")

# === Zamanlayıcı ===
schedule.every(15).minutes.do(check_all_sites)

def main():
    send_msg("🟢 Bot başladı. /help ile komutları görebilirsin.")
    last_update_id = None
    while True:
        # schedule işlerini çalıştır
        schedule.run_pending()

        # telegram update'lerini çek (long polling)
        updates = fetch_updates(offset=last_update_id + 1 if last_update_id else None)
        for up in updates:
            last_update_id = up["update_id"]
            msg = up.get("message") or up.get("edited_message")
            if not msg: 
                continue
            chat_id = str(msg.get("chat", {}).get("id"))
            if chat_id != str(CHAT_ID):
                # sadece izin verdiğin chat'e cevap ver
                continue
            text = msg.get("text", "")
            if text.startswith("/"):
                handle_command(text)

        time.sleep(2)

if __name__ == "__main__":
    main()
