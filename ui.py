"""متن‌ها، کیبوردها و ابزارهای نمایش ربات (UI مدرن فارسی)"""
from html import escape as esc

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from cfg import cfg

FA = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹،")

KIND_LABELS = {
    "buy": "🛒 خرید سرویس",
    "test": "🧪 اکانت تست",
    "renew": "🔄 تمدید سرویس",
    "credit": "💰 شارژ کیف پول",
}
PAID_LABELS = {
    "card": "💳 کارت به کارت",
    "credit": "💰 پرداخت از اعتبار",
    "free": "🎁 رایگان",
}
STATUS_LABELS = {
    "pending": "🟡 در انتظار تایید",
    "approved": "🟢 تایید شده ✅",
    "rejected": "🔴 رد شده ❌",
}

SEP = "━━━━━━━━━━━━━━━━━━"


# ---------------- کمکی‌ها ----------------

def fa(x) -> str:
    try:
        return f"{int(x):,}".translate(FA)
    except (TypeError, ValueError):
        return str(x).translate(FA)


def money(p) -> str:
    try:
        p = int(p)
    except (TypeError, ValueError):
        return "—"
    return "رایگان 🎁" if p == 0 else f"{fa(p)} تومان"


def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{esc(name or str(uid))}</a>'


def rowdict(u):
    return dict(u) if u is not None else {}


def sanitize_name(raw: str):
    t = " ".join((raw or "").split())
    if not t:
        return None
    t = t.replace(" ", "_")
    if "<" in t or ">" in t or len(t) < 2 or len(t) > 32:
        return None
    return t


def parse_amount(raw: str):
    t = (raw or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    t = t.replace("،", "").replace(",", "").replace(" ", "").replace("تومان", "")
    neg = t.startswith("-")
    t = t.lstrip("+-")
    if not t.isdigit():
        return None
    v = int(t)
    return -v if neg else v


def extract_receipt(m: Message):
    """بررسی پیام رسید پرداخت → (برچسب، file_id در صورت عکس)"""
    if m.photo:
        return "🖼 عکس رسید ارسال شد ✅", m.photo[-1].file_id
    if m.document and (m.document.mime_type or "").startswith("image/"):
        return "🖼 عکس رسید (فایل) ارسال شد ✅", m.document.file_id
    if m.text and len(m.text.strip()) >= 3:
        return esc(m.text.strip()[:300]), None
    return None, None


def content_label(m: Message) -> str:
    """برچسب محتوا برای ذخیره در «اطلاعات سرویس»"""
    if m.photo:
        return f"photo:{m.photo[-1].file_id}"
    if m.document:
        return f"file:{m.document.file_id}"
    if m.video:
        return f"video:{m.video.file_id}"
    if m.text:
        return esc(m.text.strip()[:1000])
    return "🔔 محتوا از طریق پشتیبانی ارسال شده است"


async def safe_answer(cb, text: str = None, show_alert: bool = False):
    """پاسخ امن به دکمه — اگر تلگرام کوئری را منقضی کرده باشد، نادیده گرفته می‌شود
    تا فلوی اصلی (نمایش صفحات) در هر حالتی انجام شود."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass


async def safe_edit(msg, text: str, kb=None) -> bool:
    """ویرایش امن پیام؛ در صورت خطا پیام جدید می‌فرستد"""
    try:
        await msg.edit_text(text, reply_markup=kb)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return True
    except Exception:
        pass
    try:
        await msg.answer(text, reply_markup=kb)
        return True
    except Exception:
        return False


# ---------------- کیبورد ----------------

def b(text, data=None, url=None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url) if url else InlineKeyboardButton(text=text, callback_data=data)


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


_BTN_DEFAULTS = {
    "test": "🧪 اکانت تست",
    "buy": "🛒 خرید سرویس",
    "renew": "🔄 تمدید سرویس",
    "mine": "📂 سرویس‌های من",
    "credit": "💰 اعتبار من",
    "tariff": "🏷 تعرفه‌ها",
    "tutorial": "📚 آموزش استفاده",
    "support": "☎️ پشتیبانی",
}


def btn_label(key: str) -> str:
    """برچسب دکمه از config.json (بخش BUTTONS) یا پیش‌فرض"""
    custom = getattr(cfg, "BUTTONS", None) or {}
    return str(custom.get(key) or _BTN_DEFAULTS[key])


def main_menu_kb() -> InlineKeyboardMarkup:
    return kb(
        [b(btn_label("test"), "menu:test"), b(btn_label("buy"), "menu:buy")],
        [b(btn_label("renew"), "menu:renew"), b(btn_label("mine"), "menu:mine")],
        [b(btn_label("credit"), "menu:credit"), b(btn_label("tariff"), "menu:tariff")],
        [b(btn_label("tutorial"), "menu:tut"), b(btn_label("support"), "menu:support")],
    )


def back_kb() -> InlineKeyboardMarkup:
    return kb([b("◀️ بازگشت به منوی اصلی", "back_main")])


def cancel_kb() -> InlineKeyboardMarkup:
    return kb([b("◀️ انصراف و بازگشت", "cancel_flow")])


def join_kb(channels) -> InlineKeyboardMarkup:
    rows = [[b("📢 عضویت در کانال", url=ch["url"])] for ch in channels]
    rows.append([b("✅ بررسی عضویت", "check_join")])
    return kb(*rows)


def services_kb(services, prefix: str) -> InlineKeyboardMarkup:
    rows = [[b(f"🛍 {esc(str(s.get('title', 'سرویس')))} — {money(s.get('price', 0))}", f"{prefix}:{s.get('id')}")]
            for s in services]
    rows.append([b("◀️ انصراف و بازگشت", "cancel_flow")])
    return kb(*rows)


def pay_kb(price: int, balance: int) -> InlineKeyboardMarkup:
    rows = [[b("💳 پرداخت کارت به کارت", "pay:card")]]
    if balance >= price:
        rows.append([b(f"💰 پرداخت از اعتبار (موجودی: {fa(balance)})", "pay:credit")])
    rows.append([b("◀️ انصراف", "cancel_flow")])
    return kb(*rows)


def credit_pay_kb() -> InlineKeyboardMarkup:
    return kb([b("✅ تایید و پرداخت", "pay:credit_ok")], [b("◀️ انصراف", "cancel_flow")])


def credit_amount_kb() -> InlineKeyboardMarkup:
    return kb(
        [b(f"💵 {fa(50000)}", "camt:50000"), b(f"💵 {fa(100000)}", "camt:100000")],
        [b(f"💵 {fa(200000)}", "camt:200000"), b(f"💵 {fa(500000)}", "camt:500000")],
        [b("✍️ مبلغ دلخواه", "camt:custom")],
        [b("◀️ بازگشت", "back_main")],
    )


def credit_charge_kb() -> InlineKeyboardMarkup:
    return kb([b("✅ تایید و ادامه", "credit:proceed")], [b("◀️ بازگشت", "back_main")])


def renew_list_kb(orders) -> InlineKeyboardMarkup:
    rows = [[b(f"🔄 {esc(o['custom_name'] or o['service_title'])} — {esc(o['service_title'])}", f"renew:{o['id']}")]
            for o in orders]
    rows.append([b("◀️ بازگشت", "back_main")])
    return kb(*rows)


def my_orders_kb(orders) -> InlineKeyboardMarkup:
    rows = [[b(f"🧾 #{fa(o['id'])} • {esc(o['custom_name'] or o['service_title'])}", f"svc:{o['id']}")]
            for o in orders]
    rows.append([b("◀️ بازگشت", "back_main")])
    return kb(*rows)


def svc_detail_kb(oid: int) -> InlineKeyboardMarkup:
    return kb([b("🔄 تمدید این سرویس", f"renew:{oid}")], [b("◀️ بازگشت", "menu:mine")])


def no_service_kb() -> InlineKeyboardMarkup:
    return kb([b("🛒 خرید سرویس", "menu:buy")], [b("◀️ بازگشت", "back_main")])


def test_limit_kb() -> InlineKeyboardMarkup:
    return kb([b("🛒 خرید سرویس", "menu:buy")], [b("☎️ پشتیبانی", "menu:support")], [b("◀️ بازگشت", "back_main")])


def wallet_kb() -> InlineKeyboardMarkup:
    return kb([b("➕ شارژ کیف پول", "credit:add")], [b("◀️ بازگشت به منوی اصلی", "back_main")])


def tariff_kb() -> InlineKeyboardMarkup:
    rows = [[b("🛒 خرید سرویس", "menu:buy")]]
    if cfg.SITE_URL:
        rows.append([b("🌐 مشاهده سایت", url=cfg.SITE_URL)])
    rows.append([b("◀️ بازگشت", "back_main")])
    return kb(*rows)


def tutorial_kb() -> InlineKeyboardMarkup:
    rows = []
    if cfg.TUTORIAL_URL:
        rows.append([b("🌐 مشاهده آموزش در سایت", url=cfg.TUTORIAL_URL)])
    rows.append([b("☎️ پشتیبانی", "menu:support")])
    rows.append([b("◀️ بازگشت", "back_main")])
    return kb(*rows)


def support_kb() -> InlineKeyboardMarkup:
    rows = []
    if cfg.SUPPORT_USERNAME:
        rows.append([b("💬 چت با پشتیبانی", url=f"https://t.me/{cfg.SUPPORT_USERNAME}")])
    if cfg.PHONE:
        rows.append([b("📞 تماس تلفنی", url=f"tel:{cfg.PHONE}")])
    rows.append([b("✉️ ارسال پیام به پشتیبانی", "support:msg")])
    rows.append([b("◀️ بازگشت", "back_main")])
    return kb(*rows)


def reply_kb(uid: int) -> InlineKeyboardMarkup:
    return kb([b("↩️ پاسخ به این پیام", f"reply:{uid}")])


def order_admin_kb(oid: int) -> InlineKeyboardMarkup:
    return kb([b("✅ تایید", f"ok:{oid}"), b("❌ رد", f"no:{oid}")])


# ---------------- متن‌ها ----------------

def join_text() -> str:
    return (
        "🔒 <b>دسترسی به ربات فقط برای اعضای کانال امکان‌پذیر است.</b>\n\n"
        "1️⃣ ابتدا در کانال زیر عضو شوید\n"
        "2️⃣ سپس دکمه «✅ بررسی عضویت» را بزنید\n\n"
        "🙏 از همراهی شما سپاسگزاریم 💙"
    )


ASK_NAME = (
    "📛 <b>اسم دلخواه سرویس خود را بنویسید</b>\n\n"
    "✍️ مثال: <code>ali_store</code>\n"
    "ℹ️ این نام روی سرویس شما ثبت می‌شود (۲ تا ۳۲ کاراکتر)."
)
BAD_NAME = (
    "⚠️ <b>اسم وارد شده معتبر نیست.</b>\n"
    "لطفاً یک نام ۲ تا ۳۲ کاراکتری (بدون علائم &lt; و &gt;) بفرستید:"
)
ORDER_SUBMITTED = (
    "✅ <b>سفارش شما ثبت شد و در انتظار تایید مدیر است.</b>\n"
    "🔔 نتیجه به‌زودی از همین ربات اعلام می‌شود.\n\n"
    "📂 پس از تایید، اطلاعات سرویس در بخش «سرویس‌های من» هم قابل مشاهده است."
)
CREDIT_SUBMITTED = "✅ <b>درخواست شارژ کیف پول ثبت شد و در انتظار تایید مدیر است.</b>"
NO_SERVICE_TEXT = "📂 <b>هنوز سرویسی ثبت نشده است.</b>\nبرای شروع، سرویس مورد نظر خود را خریداری کنید 👇"
TEST_LIMIT_TEXT = (
    "🧪 <b>شما قبلاً اکانت تست دریافت کرده‌اید.</b>\n"
    "برای ادامه، سرویس اصلی را خریداری کنید 🛒"
)


def summary_text(data: dict) -> str:
    kind = data.get("kind", "buy")
    svc = data.get("service", {}) or {}
    name = data.get("custom_name", "")
    price = data.get("price", 0)
    lines = [
        f"🧾 <b>{KIND_LABELS.get(kind, 'سفارش')}</b>",
        SEP,
        f"🛍 سرویس: <b>{esc(str(svc.get('title', '—')))}</b>",
    ]
    if svc.get("volume"):
        lines.append(f"📦 حجم: {esc(str(svc['volume']))}")
    if svc.get("duration"):
        lines.append(f"⏳ مدت اعتبار: {esc(str(svc['duration']))}")
    if name:
        lines.append(f"📛 اسم دلخواه: <code>{esc(str(name))}</code>")
    if kind == "renew":
        lines.append("♻️ این سفارش برای تمدید سرویس قبلی شماست")
    lines += [
        f"💳 مبلغ قابل پرداخت: <b>{money(price)}</b>",
        SEP,
        "👇 <b>روش پرداخت را انتخاب کنید:</b>",
    ]
    return "\n".join(lines)


def card_pay_text(price) -> str:
    card = cfg.CARD or {}
    lines = ["💳 <b>پرداخت کارت به کارت</b>", SEP]
    if card.get("bank"):
        lines.append(f"🏦 بانک: {esc(str(card['bank']))}")
    if card.get("number"):
        lines.append(f"🔢 شماره کارت:\n<code>{esc(str(card['number']))}</code>\n(برای کپی، روی شماره بزنید ✂️)")
    if card.get("holder"):
        lines.append(f"👤 به نام: {esc(str(card['holder']))}")
    lines += [
        f"💵 مبلغ: <b>{money(price)}</b>",
        SEP,
        "📩 پس از واریز، <b>عکس رسید</b> یا <b>کد پیگیری تراکنش</b> را ارسال کنید 👇",
    ]
    return "\n".join(lines)


def credit_pay_confirm(price: int, balance: int) -> str:
    return (
        "💰 <b>پرداخت از اعتبار</b>\n\n"
        f"💳 مبلغ سفارش: <b>{money(price)}</b>\n"
        f"📦 موجودی فعلی: {fa(balance)}\n"
        f"📦 موجودی پس از پرداخت: {fa(max(balance - price, 0))}\n\n"
        "آیا ادامه می‌دهید؟"
    )


def credit_charge_confirm(amount: int) -> str:
    return f"💳 <b>شارژ کیف پول</b>\n\n💵 مبلغ: <b>{money(amount)}</b>\n\nادامه می‌دهید؟"


def wallet_text(u) -> str:
    u = rowdict(u)
    return (
        "💰 <b>کیف پول شما</b>\n"
        f"{SEP}\n"
        f"💵 اعتبار فعلی: <b>{money(u.get('balance', 0))}</b>\n"
        "ℹ️ اعتبار برای پرداخت سریع‌تر سفارش‌ها استفاده می‌شود.\n"
        f"{SEP}\n"
        "👇 برای افزایش اعتبار، دکمه زیر را بزنید:"
    )


def svc_text(o) -> str:
    info = o["info"] or ""
    lines = [
        f"🧾 <b>سرویس {esc(o['custom_name'] or '')}</b> — سفارش {fa(o['id'])}",
        SEP,
        f"🛍 سرویس: {esc(o['service_title'] or '—')}",
    ]
    if o["volume"]:
        lines.append(f"📦 حجم: {esc(o['volume'])}")
    if o["duration"]:
        lines.append(f"⏳ مدت اعتبار: {esc(o['duration'])}")
    lines.append(f"🗓 ثبت: {o['created_at']}")
    lines.append(SEP)
    if info.startswith(("photo:", "file:", "video:")):
        lines.append("📤 اطلاعات سرویس در پیام بالا/زیر ارسال شده است ⬆️⬇️")
    elif info:
        lines.append(f"📤 <b>اطلاعات سرویس شما:</b>\n{info}")
    else:
        lines.append("⏳ اطلاعات سرویس پس از بررسی مدیر برای شما ارسال می‌شود.")
    return "\n".join(lines)


def order_card(o, u) -> str:
    """کارت سفارش برای نمایش به مدیر"""
    ud = rowdict(u)
    uid = o["user_id"]
    name = ud.get("first_name") or "کاربر"
    lines = [
        f"🆕 <b>{KIND_LABELS.get(o['kind'], 'سفارش')} — سفارش {fa(o['id'])}</b>",
        SEP,
        f"👤 مشتری: {mention(uid, name)}" + (f" (@{ud['username']})" if ud.get("username") else ""),
        f"🆔 شناسه: <code>{uid}</code>",
    ]
    if o["kind"] != "credit":
        lines.append(f"📛 اسم دلخواه: <code>{esc(o['custom_name'] or '—')}</code>")
    lines.append(f"🛍 سرویس: {esc(o['service_title'] or '—')}")
    if o["volume"]:
        lines.append(f"📦 حجم: {esc(o['volume'])}")
    if o["duration"]:
        lines.append(f"⏳ مدت: {esc(o['duration'])}")
    lines += [
        f"💳 مبلغ: <b>{money(o['price'])}</b>",
        f"🧾 روش پرداخت: {PAID_LABELS.get(o['paid_with'], '—')}",
        f"🎫 رسید: {o['receipt'] or '—'}",
        f"🗓 ثبت: {o['created_at']}",
        f"📊 وضعیت: {STATUS_LABELS.get(o['status'], o['status'])}",
    ]
    if o["note"]:
        lines.append(f"📝 یادداشت: {esc(o['note'])}")
    return "\n".join(lines)


def tariff_text() -> str:
    lines = [f"🏷 <b>تعرفه‌های {esc(cfg.BRAND_NAME)}</b>", ""]
    for s in cfg.SERVICES:
        lines.append(SEP)
        lines.append(f"🛍 <b>{esc(str(s.get('title', 'سرویس')))}</b>")
        if s.get("volume"):
            lines.append(f"📦 حجم: {esc(str(s['volume']))}")
        if s.get("duration"):
            lines.append(f"⏳ مدت اعتبار: {esc(str(s['duration']))}")
        lines.append(f"💵 قیمت: <b>{money(s.get('price', 0))}</b>")
    if cfg.TEST_SERVICES:
        t = cfg.TEST_SERVICES[0]
        lines.append(SEP)
        lines.append(f"🧪 اکانت تست: {esc(str(t.get('title', '')))} — {money(t.get('price', 0))}")
    lines.append(SEP)
    return "\n".join(lines)


def tutorial_text() -> str:
    txt = cfg.TUTORIAL_TEXT or "📚 آموزش استفاده به‌زودی تکمیل می‌شود."
    return f"📚 <b>آموزش استفاده</b>\n{SEP}\n{txt}"


def support_text() -> str:
    lines = ["☎️ <b>تماس با پشتیبانی</b>", SEP]
    if cfg.SUPPORT_USERNAME:
        lines.append(f"👤 آیدی پشتیبانی: @{cfg.SUPPORT_USERNAME}")
    if cfg.PHONE:
        lines.append(f"📱 شماره تماس: {cfg.PHONE}")
    lines += [
        "🕐 پاسخگویی: هر روز ۹ صبح تا ۱۲ شب",
        "",
        "👇 یکی از روش‌های زیر را انتخاب کنید:",
    ]
    return "\n".join(lines)
