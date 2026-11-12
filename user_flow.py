"""هندلرهای بخش مشتری: عضویت اجباری، منو، خرید، اکانت تست، تمدید، کیف پول، پشتیبانی"""
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

import db
import ui
from cfg import cfg

router = Router(name="user")
router.message.filter(F.chat.type == "private")


class BuyFSM(StatesGroup):
    name = State()      # گرفتن اسم دلخواه
    receipt = State()   # گرفتن رسید پرداخت


class CreditFSM(StatesGroup):
    amount = State()
    receipt = State()


class SupportFSM(StatesGroup):
    message = State()


# ---------------- عضویت اجباری در کانال ----------------

async def missing_channels(bot, user_id: int):
    """کانال‌هایی که کاربر عضو آن‌ها نیست را برمی‌گرداند"""
    out = []
    for ch in cfg.CHANNELS:
        try:
            m = await bot.get_chat_member(ch["id"], user_id)
            if m.status in ("left", "kicked"):
                out.append(ch)
            elif m.status == "restricted" and not getattr(m, "is_member", True):
                out.append(ch)
        except Exception:
            # اگر ربات ادمین کانال نباشد یا کانال اشتباه باشد، بررسی نادیده گرفته می‌شود
            pass
    return out


async def membership_guard(cb: CallbackQuery) -> bool:
    miss = await missing_channels(cb.bot, cb.from_user.id)
    if not miss:
        return True
    await ui.safe_answer(cb, "🔒 ابتدا در کانال عضو شوید", show_alert=True)
    await ui.safe_edit(cb.message, ui.join_text(), ui.join_kb(miss))
    return False


# ---------------- منوی اصلی ----------------

def menu_text() -> str:
    if cfg.WELCOME_TEXT:
        return cfg.WELCOME_TEXT
    lines = [
        f"✨ <b>به فروشگاه {ui.esc(cfg.BRAND_NAME)} خوش آمدید!</b>",
        "",
        "🛍 برای خرید، تمدید و مدیریت سرویس‌ها از دکمه‌های زیر استفاده کنید.",
    ]
    if cfg.SUPPORT_USERNAME:
        lines.append(f"📞 پشتیبانی: @{cfg.SUPPORT_USERNAME}")
    if cfg.SITE_URL:
        lines.append(f"🌐 سایت: {cfg.SITE_URL}")
    lines.append("")
    lines.append("👇 <b>یکی از گزینه‌های زیر را انتخاب کنید:</b>")
    return "\n".join(lines)


async def show_menu(bot, chat_id: int):
    logo = cfg.LOGO_PATH
    if logo:
        path = logo if os.path.isabs(logo) else os.path.join(cfg.BASE_DIR, logo)
        if os.path.exists(path):
            try:
                await bot.send_photo(chat_id, FSInputFile(path), caption=menu_text(),
                                     reply_markup=ui.main_menu_kb())
                return
            except Exception:
                pass
    await bot.send_message(chat_id, menu_text(), reply_markup=ui.main_menu_kb())


# ---------------- دستورها ----------------

@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    db.upsert_user(m.from_user.id, m.from_user.username or "", m.from_user.first_name or "")
    miss = await missing_channels(m.bot, m.from_user.id)
    if miss:
        await m.answer(ui.join_text(), reply_markup=ui.join_kb(miss))
    else:
        await show_menu(m.bot, m.chat.id)


@router.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"🆔 آیدی عددی شما: <code>{m.from_user.id}</code>")


@router.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(menu_text(), reply_markup=ui.main_menu_kb())


# ---------------- بررسی عضویت ----------------

@router.callback_query(F.data == "check_join")
async def check_join(cb: CallbackQuery):
    db.upsert_user(cb.from_user.id, cb.from_user.username or "", cb.from_user.first_name or "")
    miss = await missing_channels(cb.bot, cb.from_user.id)
    if miss:
        await ui.safe_answer(cb, "❌ شما هنوز عضو کانال نشده‌اید!", show_alert=True)
    else:
        await ui.safe_answer(cb, "✅ عضویت شما تایید شد! خوش آمدید 🎉")
        await ui.safe_edit(cb.message, menu_text(), ui.main_menu_kb())


# ---------------- منو ----------------

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, menu_text(), ui.main_menu_kb())


@router.callback_query(F.data == "cancel_flow")
async def cancel_flow(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await ui.safe_answer(cb, "انصراف ✖️")
    await ui.safe_edit(cb.message, menu_text(), ui.main_menu_kb())


@router.callback_query(F.data.startswith("menu:"))
async def menu_dispatch(cb: CallbackQuery, state: FSMContext):
    await ui.safe_answer(cb, )
    act = cb.data.split(":", 1)[1]
    uid = cb.from_user.id

    # همه بخش‌ها فقط برای اعضای کانال
    if not await membership_guard(cb):
        return

    if act == "buy":
        await state.clear()
        await state.update_data(kind="buy")
        await state.set_state(BuyFSM.name)
        await ui.safe_edit(cb.message, ui.ASK_NAME, ui.cancel_kb())

    elif act == "test":
        if cfg.LIMIT_TESTS and db.count_kind(uid, "test", "approved") >= 1:
            await ui.safe_edit(cb.message, ui.TEST_LIMIT_TEXT, ui.test_limit_kb())
            return
        await state.clear()
        await state.update_data(kind="test")
        await state.set_state(BuyFSM.name)
        await ui.safe_edit(cb.message, ui.ASK_NAME, ui.cancel_kb())

    elif act == "renew":
        orders = db.user_orders(uid, ("approved",))
        if not orders:
            await ui.safe_edit(cb.message, ui.NO_SERVICE_TEXT, ui.no_service_kb())
            return
        await state.clear()
        await ui.safe_edit(cb.message, "🔄 <b>کدام سرویس را تمدید می‌کنید؟</b>", ui.renew_list_kb(orders))

    elif act == "mine":
        orders = db.user_orders(uid, ("approved",))
        if not orders:
            await ui.safe_edit(cb.message, ui.NO_SERVICE_TEXT, ui.no_service_kb())
            return
        await ui.safe_edit(cb.message, "📂 <b>سرویس‌های شما</b>\nبرای مشاهده جزئیات انتخاب کنید:", ui.my_orders_kb(orders))

    elif act == "credit":
        u = db.get_user(uid)
        await ui.safe_edit(cb.message, ui.wallet_text(u), ui.wallet_kb())

    elif act == "tariff":
        await ui.safe_edit(cb.message, ui.tariff_text(), ui.tariff_kb())

    elif act == "tut":
        await ui.safe_edit(cb.message, ui.tutorial_text(), ui.tutorial_kb())

    elif act == "support":
        await ui.safe_edit(cb.message, ui.support_text(), ui.support_kb())


# ---------------- مرحله ۱: اسم دلخواه ----------------

@router.message(BuyFSM.name, F.text)
async def buy_name(m: Message, state: FSMContext):
    name = ui.sanitize_name(m.text or "")
    if not name:
        await m.answer(ui.BAD_NAME, reply_markup=ui.cancel_kb())
        return
    data = await state.update_data(custom_name=name)
    kind = data.get("kind", "buy")
    services = cfg.TEST_SERVICES if kind == "test" else cfg.SERVICES
    if not services:
        await state.clear()
        await m.answer("⚠️ فعلاً سرویسی برای انتخاب وجود ندارد؛ با پشتیبانی در تماس باشید.",
                       reply_markup=ui.back_kb())
        return
    await m.answer("🛍 <b>سرویس مورد نظر خود را انتخاب کنید:</b>",
                   reply_markup=ui.services_kb(services, "pick" if kind == "buy" else "picktest"))


@router.message(BuyFSM.name)
async def buy_name_bad(m: Message):
    await m.answer("⚠️ لطفاً فقط متن بفرستید.", reply_markup=ui.cancel_kb())


# ---------------- مرحله ۲: انتخاب سرویس ----------------

@router.callback_query(F.data.startswith("pick:"))
async def pick_service(cb: CallbackQuery, state: FSMContext):
    sid = cb.data.split(":", 1)[1]
    svc = next((s for s in cfg.SERVICES if str(s.get("id")) == sid), None)
    await _picked(cb, state, svc)


@router.callback_query(F.data.startswith("picktest:"))
async def pick_test(cb: CallbackQuery, state: FSMContext):
    sid = cb.data.split(":", 1)[1]
    svc = next((s for s in cfg.TEST_SERVICES if str(s.get("id")) == sid), None)
    await _picked(cb, state, svc)


async def _picked(cb: CallbackQuery, state: FSMContext, svc):
    data = await state.get_data()
    if not svc or not data.get("custom_name"):
        await ui.safe_answer(cb, "⛔️ این درخواست منقضی شده است؛ دوباره از منو شروع کنید.", show_alert=True)
        return
    await state.update_data(service=svc, price=int(svc.get("price", 0)))
    await ui.safe_answer(cb, )

    kind = data.get("kind", "buy")
    if kind == "test" and int(svc.get("price", 0)) == 0:
        # اکانت تست رایگان: بدون مرحله پرداخت، مستقیم برای تایید مدیر
        await _submit_order(cb.message, state, paid_with="free", receipt="")
        return
    await show_pay_screen(cb, state)


# ---------------- مرحله ۳: پرداخت ----------------

async def show_pay_screen(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    u = db.get_user(cb.from_user.id)
    balance = u["balance"] if u else 0
    await ui.safe_edit(cb.message, ui.summary_text(data), ui.pay_kb(int(data["price"]), balance))


@router.callback_query(F.data == "pay:card")
async def pay_card(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "price" not in data:
        await ui.safe_answer(cb, "⛔️ سفارش منقضی شده است؛ دوباره از منو شروع کنید.", show_alert=True)
        return
    await ui.safe_answer(cb, )
    await state.set_state(BuyFSM.receipt)
    await ui.safe_edit(cb.message, ui.card_pay_text(int(data["price"])), ui.cancel_kb())


@router.message(BuyFSM.receipt)
async def buy_receipt(m: Message, state: FSMContext):
    data = await state.get_data()
    if "price" not in data:
        await state.clear()
        await m.answer("⛔️ این سفارش منقضی شده است؛ از منو دوباره شروع کنید.",
                       reply_markup=ui.main_menu_kb())
        return
    ref, fid = ui.extract_receipt(m)
    if not ref:
        await m.answer("📩 لطفاً <b>عکس رسید</b> یا <b>کد پیگیری تراکنش</b> را ارسال کنید:",
                       reply_markup=ui.cancel_kb())
        return
    await _submit_order(m, state, paid_with="card", receipt=ref, receipt_file_id=fid)


@router.callback_query(F.data == "pay:credit")
async def pay_credit(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "price" not in data:
        await ui.safe_answer(cb, "⛔️ سفارش منقضی شده است.", show_alert=True)
        return
    price = int(data["price"])
    u = db.get_user(cb.from_user.id)
    balance = u["balance"] if u else 0
    if balance < price:
        await ui.safe_answer(cb, "💰 اعتبار شما کافی نیست؛ می‌توانید از بخش «اعتبار من» شارژ کنید.", show_alert=True)
        return
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, ui.credit_pay_confirm(price, balance), ui.credit_pay_kb())


@router.callback_query(F.data == "pay:credit_ok")
async def pay_credit_ok(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "price" not in data:
        await ui.safe_answer(cb, "⛔️ سفارش منقضی شده است.", show_alert=True)
        return
    price = int(data["price"])
    uid = cb.from_user.id
    u = db.get_user(uid)
    if not u or u["balance"] < price:
        await ui.safe_answer(cb, "💰 اعتبار شما کافی نیست.", show_alert=True)
        return
    db.add_balance(uid, -price)
    await ui.safe_answer(cb, )
    await _submit_order(cb.message, state, paid_with="credit")


# ---------------- ثبت نهایی سفارش + اطلاع به مدیر ----------------

async def _submit_order(target: Message, state: FSMContext, paid_with: str,
                        receipt: str = "", receipt_file_id=None):
    data = await state.get_data()
    uid = target.from_user.id
    kind = data["kind"]
    svc = data["service"]
    name = data["custom_name"]
    price = int(data["price"])

    oid = db.create_order(uid, kind,
                          service_id=str(svc.get("id", "")),
                          service_title=str(svc.get("title", "")),
                          price=price,
                          custom_name=name,
                          volume=str(svc.get("volume", "")),
                          duration=str(svc.get("duration", "")),
                          paid_with=paid_with,
                          receipt=receipt,
                          parent_id=data.get("parent_id"))
    await state.clear()
    order = db.get_order(oid)
    user = db.get_user(uid)

    # تایید به کاربر
    await target.answer(ui.ORDER_SUBMITTED, reply_markup=ui.main_menu_kb())

    # کارت سفارش برای مدیران
    for admin_id in cfg.ADMINS:
        try:
            await target.bot.send_message(admin_id, ui.order_card(order, user),
                                          reply_markup=ui.order_admin_kb(oid))
            if receipt_file_id:
                await target.bot.copy_message(admin_id, target.chat.id, target.message_id)
        except Exception:
            pass


# ---------------- تمدید سرویس ----------------

@router.callback_query(F.data.startswith("renew:"))
async def renew_pick(cb: CallbackQuery, state: FSMContext):
    if not await membership_guard(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    o = db.get_order(oid)
    if not o or o["user_id"] != cb.from_user.id or o["status"] != "approved":
        await ui.safe_answer(cb, "⛔️ سرویس یافت نشد.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        kind="renew",
        custom_name=o["custom_name"],
        service={"id": o["service_id"], "title": o["service_title"],
                 "volume": o["volume"], "duration": o["duration"], "price": o["price"]},
        price=o["price"],
        parent_id=o["id"],
    )
    await ui.safe_answer(cb, )
    await show_pay_screen(cb, state)


# ---------------- سرویس‌های من ----------------

@router.callback_query(F.data.startswith("svc:"))
async def svc_detail(cb: CallbackQuery):
    if not await membership_guard(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    o = db.get_order(oid)
    if not o or o["user_id"] != cb.from_user.id:
        await ui.safe_answer(cb, "⛔️ دسترسی ندارید.", show_alert=True)
        return
    await ui.safe_answer(cb, )
    info = o["info"] or ""
    if info.startswith("photo:"):
        try:
            await cb.message.answer_photo(info[6:], caption=ui.svc_text(o),
                                          reply_markup=ui.svc_detail_kb(oid))
            return
        except Exception:
            pass
    elif info.startswith("file:"):
        try:
            await cb.message.answer_document(info[5:], caption=ui.svc_text(o),
                                             reply_markup=ui.svc_detail_kb(oid))
            return
        except Exception:
            pass
    await ui.safe_edit(cb.message, ui.svc_text(o), ui.svc_detail_kb(oid))


# ---------------- اعتبار من / شارژ کیف پول ----------------

@router.callback_query(F.data == "credit:add")
async def credit_add(cb: CallbackQuery, state: FSMContext):
    if not await membership_guard(cb):
        return
    await state.clear()
    await state.set_state(CreditFSM.amount)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       "💰 <b>مبلغ شارژ کیف پول را انتخاب یا بنویسید (تومان):</b>",
                       ui.credit_amount_kb())


@router.callback_query(F.data.startswith("camt:"))
async def credit_amount_cb(cb: CallbackQuery, state: FSMContext):
    v = cb.data.split(":", 1)[1]
    if v == "custom":
        await ui.safe_answer(cb, )
        await ui.safe_edit(cb.message, "✍️ <b>مبلغ دلخواه به تومان بفرستید</b> (حداقل ۱۰,۰۰۰):",
                           ui.cancel_kb())
        return
    amount = int(v)
    await state.update_data(credit_amount=amount)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, ui.credit_charge_confirm(amount), ui.credit_charge_kb())


@router.message(CreditFSM.amount, F.text)
async def credit_amount_msg(m: Message, state: FSMContext):
    n = ui.parse_amount(m.text or "")
    if not n or n < 10000:
        await m.answer("⚠️ مبلغ نامعتبر است؛ عددی بزرگ‌تر یا مساوی ۱۰,۰۰۰ تومان بفرستید:",
                       reply_markup=ui.cancel_kb())
        return
    await state.update_data(credit_amount=n)
    await m.answer(ui.credit_charge_confirm(n), reply_markup=ui.credit_charge_kb())


@router.callback_query(F.data == "credit:proceed")
async def credit_proceed(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("credit_amount")
    if not amount:
        await ui.safe_answer(cb, "⛔️ منقضی شده؛ دوباره تلاش کنید.", show_alert=True)
        return
    await ui.safe_answer(cb, )
    await state.set_state(CreditFSM.receipt)
    await ui.safe_edit(cb.message, ui.card_pay_text(int(amount)), ui.cancel_kb())


@router.message(CreditFSM.receipt)
async def credit_receipt(m: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("credit_amount")
    if not amount:
        await state.clear()
        await m.answer("⛔️ منقضی شد؛ از منو شروع کنید.", reply_markup=ui.main_menu_kb())
        return
    ref, fid = ui.extract_receipt(m)
    if not ref:
        await m.answer("📩 لطفاً عکس رسید یا کد پیگیری را ارسال کنید:", reply_markup=ui.cancel_kb())
        return
    uid = m.from_user.id
    oid = db.create_order(uid, "credit", service_title="شارژ کیف پول",
                          price=int(amount), paid_with="card", receipt=ref)
    await state.clear()
    order = db.get_order(oid)
    user = db.get_user(uid)
    await m.answer(ui.CREDIT_SUBMITTED, reply_markup=ui.main_menu_kb())
    for admin_id in cfg.ADMINS:
        try:
            await m.bot.send_message(admin_id, ui.order_card(order, user),
                                     reply_markup=ui.order_admin_kb(oid))
            if fid:
                await m.bot.copy_message(admin_id, m.chat.id, m.message_id)
        except Exception:
            pass


# ---------------- پشتیبانی ----------------

@router.callback_query(F.data == "support:msg")
async def support_msg(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportFSM.message)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       "✉️ <b>پیام خود را بنویسید</b> (متن، عکس یا فایل).\n"
                       "پاسخ پشتیبانی در همین چت ارسال می‌شود 📨",
                       ui.cancel_kb())


@router.message(SupportFSM.message)
async def support_send(m: Message, state: FSMContext):
    await state.clear()
    n = 0
    for admin_id in cfg.ADMINS:
        try:
            await m.bot.copy_message(admin_id, m.chat.id, m.message_id,
                                     reply_markup=ui.reply_kb(m.from_user.id))
            n += 1
        except Exception:
            pass
    if n:
        await m.answer("✅ پیام شما به پشتیبانی ارسال شد؛ به‌زودی پاسخ می‌گیرید.",
                       reply_markup=ui.main_menu_kb())
    else:
        await m.answer("⚠️ موقتاً امکان ارسال وجود ندارد؛ کمی بعد دوباره تلاش کنید.",
                       reply_markup=ui.main_menu_kb())
