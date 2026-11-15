"""hr.nobd.edu.kz жаңа вакансияларын тексеріп, Telegram-ға хабарлайды.
Тек стандартты кітапхана керек (pip install қажет емес)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://hr.nobd.edu.kz/portal/jobs/api/jobs/all/filter/sign"
SITE = "https://hr.nobd.edu.kz/"
SEEN_FILE = Path("seen.json")
PAGES = 2          # неше бет тексеру (әр бет PAGE_SIZE вакансия)
PAGE_SIZE = 50

# --- СҮЗГІ (өзгертуге болады) ---
# Аймақ коды: 27 = Батыс Қазақстан облысы, 2710 = Орал қаласы,
# 79 = Шымкент, 71 = Астана. Бос тізім [] = барлық аймақ.
KATO = "271010000"          # Орал қаласы (сайттың өз коды)
SEARCH_TEXT = "Учитель физики"
REGION_PREFIXES = []        # аймақты сервер өзі сүзеді
# Лауазым атауындағы сөздер (кіші әріппен). Бос [] = барлық вакансия.
KEYWORDS = ["физик"]  # Учитель физики / физика пәні мұғалімі

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def fetch_page(page):
    body = json.dumps({
        "filter": {"kato": KATO, "specializationText": SEARCH_TEXT, "ln": "ru",
                   "educationLanguage": [], "educationType": [],
                   "experienceType": [], "onlyNew": False},
        "pagination": {"page": page, "size": PAGE_SIZE},
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://hr.nobd.edu.kz",
        "Referer": "https://hr.nobd.edu.kz/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/157.0.0.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("data") or []


def matches(job):
    org = job.get("organization") or {}
    if REGION_PREFIXES:
        codes = [str(org.get(k) or "") for k in ("regionCode", "locationCode", "areaCode")]
        if not any(c.startswith(p) for c in codes for p in REGION_PREFIXES):
            return False
    if KEYWORDS:
        text = ((job.get("title") or "") + " " +
                ((job.get("specialization") or {}).get("name") or "")).lower()
        if not any(k in text for k in KEYWORDS):
            return False
    return True


def fmt(job):
    org = job.get("organization") or {}
    s, e = job.get("salaryStart"), job.get("salaryEnd")
    salary = f"{int(s):,}".replace(",", " ") if s else "көрсетілмеген"
    if e:
        salary += f" – {int(e):,}".replace(",", " ")
    return (f"🆕 {job.get('title')}\n"
            f"🏫 {org.get('kkName') or org.get('name')}\n"
            f"📍 {org.get('ruAddress') or org.get('address')}\n"
            f"💰 {salary} ₸\n"
            f"📅 дейін: {(job.get('vacancyEndDate') or '')[:10]}\n"
            f"📞 {org.get('contactNumber') or ''}\n"
            f"🔗 {SITE}")


BUTTON = "🔍 Жұмыс бар ма?"
KEYBOARD = json.dumps({"keyboard": [[{"text": BUTTON}]], "resize_keyboard": True})


def send(text, keyboard=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/sendMessage"
    fields = {"chat_id": CHAT_ID.strip(), "text": text}
    if keyboard:
        fields["reply_markup"] = KEYBOARD
    data = urllib.parse.urlencode(fields).encode()
    for attempt in range(1, 4):
        try:
            urllib.request.urlopen(url, data=data, timeout=30).read()
            return True
        except Exception as exc:
            print(f"Telegram қатесі ({attempt}/3): {exc}")
            time.sleep(5 * attempt)
    return False


def handle_buttons(current):
    """Батырма басылған/жазылған хабарламаларды оқып, жауап береді.
    current = қазір ашық вакансиялар тізімі, не None (сайт қолжетімсіз)."""
    base = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/getUpdates"
    try:
        updates = json.load(urllib.request.urlopen(base, timeout=30)).get("result", [])
    except Exception as exc:
        print("getUpdates қатесі:", exc)
        return
    if not updates:
        return
    asked = False
    for u in updates:
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != CHAT_ID.strip():
            continue  # басқа адамдарға жауап бермейміз
        if (msg.get("text") or "").strip() in (BUTTON, "/start", "/jobs"):
            asked = True
    if asked:
        if current is None:
            send("⚠️ Сайт қазір қолжетімсіз (техжұмыс болуы мүмкін), кейінірек қайта сұра.",
                 keyboard=True)
        elif not current:
            send("😕 Қазір Оралда физика мұғалімі вакансиясы жоқ. "
                 "Жаңасы шықса, өзім хабарлаймын.", keyboard=True)
        else:
            send(f"📋 Қазір ашық: {len(current)} вакансия", keyboard=True)
            for j in current[:10]:
                send(fmt(j).replace("🆕", "📌", 1))
    # Өңделген хабарламаларды Telegram-да «оқылды» деп белгілейміз
    last = max(u["update_id"] for u in updates)
    try:
        urllib.request.urlopen(f"{base}?offset={last + 1}", timeout=30).read()
    except Exception as exc:
        print("offset қатесі:", exc)


def main():
    jobs = []
    try:
        for p in range(PAGES):
            page = fetch_page(p)
            if not page:
                break
            jobs += page
    except Exception as exc:  # техжұмыс, желі қатесі — келесі жолы қайталаймыз
        print("Сұраныс қатесі:", exc)
        if BOT_TOKEN and CHAT_ID:
            handle_buttons(None)
        return 0

    first_run = not SEEN_FILE.exists()
    seen = set(json.loads(SEEN_FILE.read_text())) if not first_run else set()
    new = [j for j in jobs if j["id"] not in seen and matches(j)]

    if first_run:
        print(f"Бірінші іске қосу: {len(new)} вакансия белгіленді, хабарламасыз.")
        if BOT_TOKEN and CHAT_ID:
            send(f"✅ Бақылау қосылды. Қазір сүзгіге сай {len(new)} вакансия бар, "
                 f"жаңалары шыққанда хабарлаймын.\n"
                 f"Төмендегі «{BUTTON}» батырмасын бассаң, ашық вакансияларды көрсетемін "
                 f"(жауап 15 минутқа дейін кешігуі мүмкін).", keyboard=True)
            for j in new[:10]:
                send(fmt(j))
    else:
        for j in reversed(new):
            print("Жаңа:", j["id"], j["title"])
            if BOT_TOKEN and CHAT_ID:
                send(fmt(j))

    seen |= {j["id"] for j in jobs}
    SEEN_FILE.write_text(json.dumps(sorted(seen)))

    if BOT_TOKEN and CHAT_ID:
        handle_buttons([j for j in jobs if matches(j)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
