"""نقطه ورود ربات فروشگاه — اجرا با: python bot.py

ضدقطعی: اگر اینترنت/v2ray لحظه‌ای قطع شود، ربات کرش نمی‌کند؛
خودش بعد از چند ثانیه دوباره وصل می‌شود.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import admin_flow
import db
import user_flow
from cfg import cfg

RECONNECT_DELAY = 5  # ثانیه انتظار قبل از اتصال مجدد


async def _api_retry(fn, what: str, tries: int = 6, delay: float = 4.0):
    """اجرای یک درخواست API با چند بار تلاش مجدد"""
    for i in range(1, tries + 1):
        try:
            return await fn()
        except Exception as e:
            if i == tries:
                raise
            print(f"⚠️ {what}: تلاش {i} ناموفق ({type(e).__name__}) — {int(delay)} ثانیه بعد دوباره...")
            await asyncio.sleep(delay)


def _build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(admin_flow.router)   # پنل مدیر اول (اولویت دستور /panel)
    dp.include_router(user_flow.router)
    return dp


async def run_once(first_start: bool) -> None:
    """یک دور کامل: ساخت ربات، ورود، تنظیمات، شروع polling"""
    session = AiohttpSession(proxy=cfg.PROXY) if cfg.PROXY else None
    bot = Bot(cfg.BOT_TOKEN, session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        # ورود با retry — نتیجه کش می‌شود تا start_polling دیگر درخواست شبکه ندهد
        me = await _api_retry(bot.me, "ورود")
        print(f"🤖 ورود موفق: {me.first_name} (@{me.username})")

        await _api_retry(
            lambda: bot.delete_webhook(drop_pending_updates=first_start),
            "پاکسازی وب‌هوک")
        try:
            await _api_retry(lambda: bot.set_my_commands([
                BotCommand(command="start", description="شروع / منوی اصلی 🏠"),
                BotCommand(command="id", description="آیدی عددی من 🆔"),
                BotCommand(command="cancel", description="انصراف ✖️"),
                BotCommand(command="panel", description="پنل مدیریت 🛠"),
            ]), "تنظیم دستورها")
        except Exception:
            pass

        dp = _build_dispatcher()
        if first_start:
            admins = ", ".join(str(a) for a in cfg.ADMINS) or "—"
            print(f"✅ ربات «{cfg.BRAND_NAME}» با موفقیت راه‌اندازی شد.")
            print(f"🛠 مدیران: {admins}")
            print(f"📢 کانال‌های اجباری: {[c['id'] for c in cfg.CHANNELS] or '—'}")
            print("⏳ در حال دریافت پیام‌ها... (برای توقف Ctrl+C)")
        else:
            print("🔄 اتصال مجدد برقرار شد — ربات ادامه می‌دهد.")

        await dp.start_polling(bot)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


async def main():
    if (not cfg.BOT_TOKEN
            or "PUT-YOUR-TOKEN" in cfg.BOT_TOKEN
            or len(cfg.BOT_TOKEN) < 20):
        print("❌ توکن ربات تنظیم نشده است!")
        print("👉 فایل config.json را باز کنید و مقدار BOT_TOKEN را با توکن BotFather جایگزین کنید.")
        sys.exit(1)

    db.init_db()

    first_start = True
    while True:
        try:
            await run_once(first_start)
            break  # خروج تمیز (Ctrl+C)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            print(f"🔴 اتصال قطع شد ({type(e).__name__}) — "
                  f"{RECONNECT_DELAY} ثانیه دیگر دوباره تلاش می‌کنم...")
            await asyncio.sleep(RECONNECT_DELAY)
            first_start = False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 ربات متوقف شد.")
