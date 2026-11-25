import os
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = os.environ["TARGET_URL"]
SELECTOR = os.environ.get("SELECTOR", "")   # اختیاری: مثلاً "li.news-item"
TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]
STATE_FILE = "seen.json"


def normalize(text):
    return " ".join(text.split())



def fetch_html():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)   # چند ثانیه صبر تا محتوا کامل بیاد
        html = page.content()
        browser.close()
    return html

def get_items():
    soup = BeautifulSoup(fetch_html(), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    items = set()
    if SELECTOR:
        for el in soup.select(SELECTOR):
            t = normalize(el.get_text(" "))
            if t:
                items.add(t)
    else:
        for line in soup.get_text("\n").splitlines():
            t = normalize(line)
            if len(t) > 3:
                items.add(t)
    return items


def send_telegram(text):
    # تلگرام حداکثر ۴۰۹۶ کاراکتر در هر پیام قبول می‌کنه
    for i in range(0, len(text), 4000):
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[i:i + 4000]},
            timeout=20,
        )
        resp.raise_for_status()


def main():
    current = get_items()

    if not os.path.exists(STATE_FILE):
        # اجرای اول: فقط وضعیت فعلی رو ذخیره می‌کنیم، الارم نمی‌دیم
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(current), f, ensure_ascii=False, indent=1)
        print("baseline saved:", len(current), "items")
        return

    with open(STATE_FILE, encoding="utf-8") as f:
        seen = set(json.load(f))

    new_items = current - seen
    if new_items:
        msg = f"🔔 {len(new_items)} مورد جدید در صفحه:\n\n"
        msg += "\n\n".join(f"➕ {x}" for x in sorted(new_items))
        msg += f"\n\n{URL}"
        send_telegram(msg)   # اگه ارسال fail بشه، state ذخیره نمی‌شه و دفعه‌ی بعد دوباره تلاش می‌شه

        # آیتم‌های قدیمی رو هم نگه می‌داریم تا آیتمِ حذف‌شده و دوباره‌برگشته، الارم نده
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen | current), f, ensure_ascii=False, indent=1)
    else:
        print("no new items")


if __name__ == "__main__":
    main()
