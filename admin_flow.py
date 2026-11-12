"""پنل مدیریت: تایید/رد سفارش‌ها، آمار، شارژ اعتبار، پیام همگانی، پاسخ پشتیبانی"""
import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
import ui
from cfg import cfg

router = Router(name="admin")
router.message.filter(F.chat.type == "private")


class AdminFSM(StatesGroup):
    broadcast = State()
    addcredit_uid = State()
    addcredit_amt = State()
    reply = State()
    send_info = State()      # ارسال اطلاعات سرویس به مشتری
    reject_reason = State()  # دلیل رد سفارش


def is_admin(user_id: int) -> bool:
    return user_id in cfg.ADMINS


async def _admin_or_alert(cb: CallbackQuery) -> bool:
    if is_admin(cb.from_user.id):
        return True
    await ui.safe_answer(cb, "⛔️ این بخش فقط برای مدیر است", show_alert=True)
    return False


def panel_text() -> str:
    p = db.pending_orders()
    return (
        f"🛠 <b>پنل مدیریت {ui.esc(cfg.BRAND_NAME)}</b>\n\n"
        f"⏳ سفارش‌های در انتظار تایید: <b>{ui.fa(len(p))}</b>\n\n"
        "👇 گزینه‌ای را انتخاب کنید:"
    )


def panel_kb():
    return ui.kb(
        [ui.b("📊 آمار ربات", "adm:stats"), ui.b("⏳ سفارش‌های در انتظار", "adm:pending")],
        [ui.b("➕ شارژ اعتبار کاربر", "adm:addcredit"), ui.b("📢 ارسال پیام همگانی", "adm:broadcast")],
    )


@router.message(Command("panel"))
async def panel(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.clear()
    await m.answer(panel_text(), reply_markup=panel_kb())


@router.callback_query(F.data == "adm:panel")
async def adm_panel(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    await state.clear()
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, panel_text(), panel_kb())


# ---------------- آمار ----------------

@router.callback_query(F.data == "adm:stats")
async def adm_stats(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    await ui.safe_answer(cb, )
    s = db.stats()
    text = (
        f"📊 <b>آمار ربات {ui.esc(cfg.BRAND_NAME)}</b>\n"
        f"{ui.SEP}\n"
        f"👥 کاربران: <b>{ui.fa(s['users'])}</b>\n"
        f"🧾 کل سفارش‌ها: <b>{ui.fa(s['orders'])}</b>\n"
        f"🟢 تایید شده: {ui.fa(s['approved'])}   🟡 در انتظار: {ui.fa(s['pending'])}   🔴 رد شده: {ui.fa(s['rejected'])}\n"
        f"{ui.SEP}\n"
        f"💰 درآمد تایید شده: <b>{ui.money(s['revenue'])}</b>\n"
        f"💳 شارژ کیف پول تایید شده: {ui.money(s['charges'])}"
    )
    await ui.safe_edit(cb.message, text, ui.kb([ui.b("◀️ بازگشت", "adm:panel")]))


# ---------------- سفارش‌های در انتظار ----------------

@router.callback_query(F.data == "adm:pending")
async def adm_pending(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    await ui.safe_answer(cb, )
    rows = db.pending_orders(limit=10)
    if not rows:
        await ui.safe_edit(cb.message, "🎉 <b>سفارش در انتظار تاییدی وجود ندارد.</b>",
                           ui.kb([ui.b("◀️ بازگشت", "adm:panel")]))
        return
    await ui.safe_edit(cb.message,
                       f"⏳ <b>{ui.fa(len(rows))} سفارش در انتظار تایید است</b>\nکارت هر سفارش جداگانه ارسال شد 👇",
                       ui.kb([ui.b("◀️ بازگشت", "adm:panel")]))
    for o in rows:
        u = db.get_user(o["user_id"])
        try:
            await cb.bot.send_message(cb.from_user.id, ui.order_card(o, u),
                                      reply_markup=ui.order_admin_kb(o["id"]))
        except Exception:
            pass


# ---------------- تایید سفارش ----------------

async def _edit_card(cb: CallbackQuery, order, user):
    try:
        await cb.message.edit_text(ui.order_card(order, user), reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            pass
    except Exception:
        pass


@router.callback_query(F.data.startswith("ok:"))
async def adm_approve(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    o = db.get_order(oid)
    if not o:
        await ui.safe_answer(cb, "سفارش یافت نشد", show_alert=True)
        return
    if o["status"] != "pending":
        await ui.safe_answer(cb, "این سفارش قبلاً بررسی شده است", show_alert=True)
        await _edit_card(cb, o, db.get_user(o["user_id"]))
        return

    uid = o["user_id"]
    db.set_order(oid, status="approved", admin_id=cb.from_user.id, decided_at=db.now())
    await ui.safe_answer(cb, "✅ تایید شد")

    if o["kind"] == "credit":
        db.add_balance(uid, o["price"])
        try:
            await cb.bot.send_message(uid,
                                      f"💰 کیف پول شما به مبلغ <b>{ui.money(o['price'])}</b> شارژ شد ✅\n"
                                      f"🧾 سفارش: {ui.fa(oid)}")
        except Exception:
            pass
        await _edit_card(cb, db.get_order(oid), db.get_user(uid))
        return

    try:
        await cb.bot.send_message(
            uid,
            f"🎉 <b>سفارش {ui.fa(oid)} شما تایید شد!</b>\n"
            "✅ اطلاعات سرویس به‌زودی برای شما ارسال می‌شود.\n\n"
            "📂 می‌توانید از بخش «سرویس‌های من» پیگیری کنید.")
    except Exception:
        pass
    await _edit_card(cb, db.get_order(oid), db.get_user(uid))
    try:
        await cb.bot.send_message(
            cb.from_user.id,
            f"📤 <b>اطلاعات سرویس سفارش {ui.fa(oid)} را برای مشتری بفرستید.</b>\n"
            "(متن، عکس یا فایل — همین‌جا بفرستید) یا بعداً از دکمه زیر استفاده کنید:",
            reply_markup=ui.kb([
                ui.b("📤 ارسال اطلاعات سرویس", f"info:{oid}"),
                ui.b("⏭ بعداً", "skipinfo"),
            ]))
    except Exception:
        pass


# ---------------- رد سفارش ----------------

@router.callback_query(F.data.startswith("no:"))
async def adm_reject(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, f"❌ رد سفارش {ui.fa(oid)}:", ui.kb([
        ui.b("✍️ رد با ذکر دلیل", f"rjy:{oid}"),
        ui.b("🚫 رد بدون دلیل", f"rjn:{oid}"),
        ui.b("◀️ انصراف", f"backorder:{oid}"),
    ]))


@router.callback_query(F.data.startswith("rjn:"))
async def adm_reject_noreason(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    await _finalize_reject(cb, oid, "")


@router.callback_query(F.data.startswith("rjy:"))
async def adm_reject_reason(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    await state.set_state(AdminFSM.reject_reason)
    await state.update_data(reject_oid=oid)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       f"✍️ <b>دلیل رد سفارش {ui.fa(oid)} را بنویسید</b>\n(این متن برای مشتری ارسال می‌شود):")


async def _finalize_reject(cb: CallbackQuery, oid: int, reason: str):
    o = db.get_order(oid)
    if not o or o["status"] != "pending":
        await ui.safe_answer(cb, "قبلاً بررسی شده است", show_alert=True)
        return
    uid = o["user_id"]
    db.set_order(oid, status="rejected", admin_id=cb.from_user.id,
                 note=reason or "", decided_at=db.now())
    refund = ""
    if o["paid_with"] == "credit":
        db.add_balance(uid, o["price"])
        refund = "\n💰 مبلغ پرداختی به اعتبار شما برگردانده شد."
    try:
        await cb.bot.send_message(
            uid,
            f"❌ <b>سفارش {ui.fa(oid)} رد شد.</b>\n"
            + (f"📝 دلیل: {ui.esc(reason)}\n" if reason else "")
            + "برای پیگیری با پشتیبانی در تماس باشید." + refund)
    except Exception:
        pass
    await ui.safe_answer(cb, "رد شد")
    await _edit_card(cb, db.get_order(oid), db.get_user(uid))


@router.message(AdminFSM.reject_reason, ~F.text.startswith("/"))
async def adm_reject_reason_send(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    data = await state.get_data()
    oid = data.get("reject_oid")
    await state.clear()
    if not oid:
        return
    reason = (m.text or "").strip()[:300]
    o = db.get_order(oid)
    if not o or o["status"] != "pending":
        await m.answer("⛔️ این سفارش قبلاً بررسی شده است.")
        return
    uid = o["user_id"]
    db.set_order(oid, status="rejected", admin_id=m.from_user.id,
                 note=reason, decided_at=db.now())
    refund = ""
    if o["paid_with"] == "credit":
        db.add_balance(uid, o["price"])
        refund = "\n💰 مبلغ پرداختی به اعتبار شما برگردانده شد."
    try:
        await m.bot.send_message(
            uid,
            f"❌ <b>سفارش {ui.fa(oid)} رد شد.</b>\n"
            + (f"📝 دلیل: {ui.esc(reason)}\n" if reason else "")
            + "برای پیگیری با پشتیبانی در تماس باشید." + refund)
    except Exception:
        pass
    await m.answer(ui.order_card(db.get_order(oid), db.get_user(uid)))


# ---------------- بازگشت به کارت سفارش ----------------

@router.callback_query(F.data.startswith("backorder:"))
async def adm_backorder(cb: CallbackQuery):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    o = db.get_order(oid)
    if not o:
        await ui.safe_answer(cb, "سفارش یافت نشد", show_alert=True)
        return
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, ui.order_card(o, db.get_user(o["user_id"])),
                       ui.order_admin_kb(oid))


# ---------------- ارسال اطلاعات سرویس ----------------

@router.callback_query(F.data.startswith("info:"))
async def adm_info(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    oid = int(cb.data.split(":", 1)[1])
    o = db.get_order(oid)
    if not o or o["status"] != "approved":
        await ui.safe_answer(cb, "سفارش معتبر نیست", show_alert=True)
        return
    await state.set_state(AdminFSM.send_info)
    await state.update_data(info_oid=oid)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       f"📤 <b>اطلاعات سرویس سفارش {ui.fa(oid)} را بفرستید</b>\n"
                       "(متن، عکس، فایل یا لینک — مستقیم برای مشتری ارسال می‌شود):")


@router.message(AdminFSM.send_info, ~F.text.startswith("/"))
async def adm_info_send(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    data = await state.get_data()
    oid = data.get("info_oid")
    await state.clear()
    if not oid:
        return
    o = db.get_order(oid)
    if not o:
        await m.answer("⛔️ سفارش یافت نشد.")
        return
    db.set_order(oid, info=ui.content_label(m))
    try:
        await m.bot.copy_message(o["user_id"], m.chat.id, m.message_id)
        await m.answer(f"✅ اطلاعات سفارش {ui.fa(oid)} برای مشتری ارسال و در پروفایلش ثبت شد.")
    except Exception:
        await m.answer("⚠️ ارسال به مشتری ناموفق بود (احتمالاً ربات را بلاک کرده)؛ ولی ثبت شد.")


@router.callback_query(F.data == "skipinfo")
async def adm_skipinfo(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await ui.safe_answer(cb, "باشه — بعداً می‌توانید اطلاعات را بفرستید.")


# ---------------- شارژ اعتبار کاربر ----------------

@router.callback_query(F.data == "adm:addcredit")
async def adm_addcredit(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    await state.set_state(AdminFSM.addcredit_uid)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       "🆔 <b>آیدی عددی کاربر را بفرستید</b>\n(کاربر با دستور /id می‌تواند بگیرید):")


@router.message(AdminFSM.addcredit_uid, F.text, ~F.text.startswith("/"))
async def adm_addcredit_uid(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    try:
        uid = int((m.text or "").strip())
    except ValueError:
        await m.answer("⚠️ عدد نامعتبر است؛ آیدی عددی بفرستید:")
        return
    u = db.get_user(uid)
    if not u:
        await m.answer("⚠️ چنین کاربری در ربات ثبت نشده است؛ آیدی دیگر بفرستید:")
        return
    await state.update_data(addc_uid=uid)
    await state.set_state(AdminFSM.addcredit_amt)
    await m.answer(
        f"👤 کاربر: {ui.mention(uid, u['first_name'] or 'کاربر')}\n"
        f"💰 اعتبار فعلی: {ui.money(u['balance'])}\n\n"
        "✍️ <b>مبلغ شارژ به تومان را بفرستید</b> (عدد منفی برای کسر):")


@router.message(AdminFSM.addcredit_amt, F.text, ~F.text.startswith("/"))
async def adm_addcredit_amt(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    amount = ui.parse_amount(m.text or "")
    if amount is None or amount == 0:
        await m.answer("⚠️ عدد نامعتبر است؛ مثال: 50000")
        return
    data = await state.get_data()
    uid = data["addc_uid"]
    u = db.get_user(uid)
    nb = db.add_balance(uid, amount)
    await state.clear()
    await m.answer(
        f"✅ انجام شد.\n"
        f"👤 {ui.mention(uid, u['first_name'] or 'کاربر')}\n"
        f"💰 اعتبار جدید: <b>{ui.money(nb)}</b>")
    try:
        if amount > 0:
            await m.bot.send_message(uid, f"💰 کیف پول شما به مبلغ <b>{ui.money(amount)}</b> شارژ شد ✅")
        else:
            await m.bot.send_message(uid, f"💰 مبلغ <b>{ui.money(-amount)}</b> از کیف پول شما کسر شد.")
    except Exception:
        pass


# ---------------- پیام همگانی ----------------

@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    await state.set_state(AdminFSM.broadcast)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message,
                       "📢 <b>محتوای پیام همگانی را بفرستید</b> (متن، عکس، ویدیو یا هر محتوایی).\n\n"
                       "⚠️ این پیام برای همه کاربران ارسال می‌شود.\n"
                       "برای انصراف، دوباره /panel را بزنید.")


@router.message(AdminFSM.broadcast, ~F.text.startswith("/"))
async def adm_broadcast_send(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.clear()
    ids = db.all_user_ids()
    ok = err = 0
    status = await m.answer(f"📤 در حال ارسال به {ui.fa(len(ids))} کاربر...")
    for uid in ids:
        try:
            await m.bot.copy_message(uid, m.chat.id, m.message_id)
            ok += 1
        except Exception:
            err += 1
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ <b>ارسال تمام شد.</b>\n📬 موفق: {ui.fa(ok)}   ⚠️ ناموفق: {ui.fa(err)}",
        reply_markup=panel_kb())


# ---------------- پاسخ به پیام پشتیبانی ----------------

@router.callback_query(F.data.startswith("reply:"))
async def adm_reply(cb: CallbackQuery, state: FSMContext):
    if not await _admin_or_alert(cb):
        return
    uid = int(cb.data.split(":", 1)[1])
    await state.set_state(AdminFSM.reply)
    await state.update_data(reply_uid=uid)
    await ui.safe_answer(cb, )
    await ui.safe_edit(cb.message, f"↩️ <b>پاسخ به کاربر {ui.fa(uid)} را بنویسید:</b>")


@router.message(AdminFSM.reply, ~F.text.startswith("/"))
async def adm_reply_send(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    data = await state.get_data()
    uid = data.get("reply_uid")
    await state.clear()
    if not uid:
        return
    try:
        await m.bot.copy_message(uid, m.chat.id, m.message_id)
        await m.answer("✅ پاسخ ارسال شد.")
    except Exception:
        await m.answer("⚠️ ارسال ناموفق بود (کاربر ربات را بلاک کرده است).")
