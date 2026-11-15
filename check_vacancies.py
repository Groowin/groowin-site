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


def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID.strip(), "text": text}).encode()
    for attempt in range(1, 4):
        try:
            urllib.request.urlopen(url, data=data, timeout=30).read()
            return True
        except Exception as exc:
            print(f"Telegram қатесі ({attempt}/3): {exc}")
            time.sleep(5 * attempt)
    return False


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
        return 0

    first_run = not SEEN_FILE.exists()
    seen = set(json.loads(SEEN_FILE.read_text())) if not first_run else set()
    new = [j for j in jobs if j["id"] not in seen and matches(j)]

    if first_run:
        print(f"Бірінші іске қосу: {len(new)} вакансия белгіленді, хабарламасыз.")
        if BOT_TOKEN and CHAT_ID:
            send(f"✅ Бақылау қосылды. Қазір сүзгіге сай {len(new)} вакансия бар, "
                 f"жаңалары шыққанда хабарлаймын.")
            for j in new[:10]:
                send(fmt(j))
    else:
        for j in reversed(new):
            print("Жаңа:", j["id"], j["title"])
            if BOT_TOKEN and CHAT_ID:
                send(fmt(j))

    seen |= {j["id"] for j in jobs}
    SEEN_FILE.write_text(json.dumps(sorted(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
