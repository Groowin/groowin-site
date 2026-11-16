"""hr.nobd.edu.kz жаңа вакансияларын тексеріп, Telegram-ға хабарлайды.
Тек стандартты кітапхана керек (pip install қажет емес)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://hr.nobd.edu.kz/portal/jobs/api/jobs/all/filter/sign"
SITE = "https://hr.nobd.edu.kz/"
SEEN_FILE = Path("seen.json")
OPEN_FILE = Path("open.json")   # қазір ашық вакансиялар (жабылуды анықтау үшін)
REMIND_DAYS = 2                 # мерзім аяқталуына неше күн қалғанда ескерту
MISS_LIMIT = 2                  # неше рет қатарынан жоғалса «жабылды» деп санау
TZ = timezone(timedelta(hours=5))
PAGES = 2         # неше бет тексеру (әр бет PAGE_SIZE вакансия)
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


def map_links(address):
    """Мекенжайдан 2ГИС және Google Maps іздеу сілтемелерін жасайды."""
    if not address:
        return ""
    q = urllib.parse.quote(address)
    return (f"🗺 2ГИС: https://2gis.kz/search/{q}\n"
            f"🗺 Google: https://www.google.com/maps/search/?api=1&query={q}\n")


def fmt(job):
    org = job.get("organization") or {}
    s, e = job.get("salaryStart"), job.get("salaryEnd")
    salary = f"{int(s):,}".replace(",", " ") if s else "көрсетілмеген"
    if e:
        salary += f" – {int(e):,}".replace(",", " ")
    address = org.get("ruAddress") or org.get("address")
    return (f"🆕 {job.get('title')}\n"
            f"🏫 {org.get('kkName') or org.get('name')}\n"
            f"📍 {address}\n"
            f"{map_links(address)}"
            f"💰 {salary} ₸\n"
            f"📅 дейін: {(job.get('vacancyEndDate') or '')[:10]}\n"
            f"📞 {org.get('contactNumber') or ''}\n"
            f"🔗 {SITE}")


def track_open(current):
    """Ашық вакансиялар тізімін жүргізеді: жабылғанын және мерзім ескертуін жібереді."""
    now = datetime.now(TZ).date()
    notify = bool(BOT_TOKEN and CHAT_ID)
    first = not OPEN_FILE.exists()
    state = {} if first else json.loads(OPEN_FILE.read_text())
    cur = {str(j["id"]): j for j in current}

    # 1) Жабылған вакансиялар
    if not first:
        for jid in list(state):
            if jid in cur:
                state[jid]["miss"] = 0
                continue
            state[jid]["miss"] = state[jid].get("miss", 0) + 1
            if state[jid]["miss"] >= MISS_LIMIT:
                info = state.pop(jid)
                print("Жабылды:", jid, info["title"])
                if notify:
                    send(f"❌ Вакансия жабылды: {info['title']}\n🏫 {info['org']}\n"
                         f"Қазір ашық: {len(cur)}")

    # 2) Жаңа вакансияларды тізімге қосу және мерзім ескертуі
    for jid, j in cur.items():
        org = j.get("organization") or {}
        st = state.setdefault(jid, {"reminded": False, "miss": 0})
        st.update(title=j.get("title"), org=org.get("kkName") or org.get("name"),
                  end=(j.get("vacancyEndDate") or "")[:10])
        try:
            days_left = (datetime.strptime(st["end"], "%Y-%m-%d").date() - now).days
        except ValueError:
            continue
        if 0 <= days_left <= REMIND_DAYS and not st["reminded"]:
            st["reminded"] = True
            if notify:
                send(f"⏰ Мерзімі аяқталады ({days_left} күн қалды): {st['title']}\n"
                     f"🏫 {st['org']}\n📅 дейін: {st['end']}\n"
                     f"📞 {org.get('contactNumber') or ''}")

    OPEN_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1))


USE_WORKER = True   # True: батырмаға Cloudflare Worker жауап береді (getUpdates өшеді)
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
    if USE_WORKER:
        return
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

    current = [j for j in jobs if matches(j)]
    track_open(current)

    if BOT_TOKEN and CHAT_ID:
        handle_buttons(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
