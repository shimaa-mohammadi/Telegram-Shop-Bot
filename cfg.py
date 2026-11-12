"""خواندن تنظیمات از فایل config.json"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "BOT_TOKEN": "",
    "ADMINS": [],
    "BRAND_NAME": "فروشگاه",
    "SITE_URL": "",
    "SUPPORT_USERNAME": "",
    "PHONE": "",
    "CARD": {"bank": "", "number": "", "holder": ""},
    "CHANNELS": [],
    "LIMIT_TESTS": True,
    "SERVICES": [],
    "TEST_SERVICES": [],
    "TUTORIAL_TEXT": "آموزش استفاده به‌زودی تکمیل می‌شود.",
    "TUTORIAL_URL": "",
    "WELCOME_TEXT": "",
    "LOGO_PATH": "",
    "PROXY": "",
    "BUTTONS": {},
}


class Config:
    def __init__(self, path: str):
        data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        merged = dict(DEFAULTS)
        for k, v in data.items():
            if not k.startswith("_"):
                merged[k] = v
        self.__dict__.update(merged)
        self.BASE_DIR = BASE_DIR

        # نرمال‌سازی کانال‌ها: هر آیتم یا "@username" است یا {"id": ..., "url": ...}
        chans = []
        for ch in self.CHANNELS:
            if isinstance(ch, str):
                url = ch if ch.startswith("http") else "https://t.me/" + ch.lstrip("@")
                chans.append({"id": ch, "url": url})
            elif isinstance(ch, dict) and ch.get("id"):
                cid = str(ch["id"])
                url = ch.get("url") or (cid if cid.startswith("http") else "https://t.me/" + cid.lstrip("@"))
                chans.append({"id": cid, "url": url})
        self.CHANNELS = chans


cfg = Config(os.path.join(BASE_DIR, "config.json"))
