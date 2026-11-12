"""پایگاه داده SQLite ربات (users + orders)"""
import os
import sqlite3
import threading
from datetime import datetime

from cfg import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "shop.db")

_lock = threading.Lock()
_conn = None


def _get() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def _exec(sql: str, params=()):
    with _lock:
        c = _get()
        cur = c.execute(sql, params)
        c.commit()
        return cur


def _one(sql: str, params=()):
    with _lock:
        return _get().execute(sql, params).fetchone()


def _all(sql: str, params=()):
    with _lock:
        return _get().execute(sql, params).fetchall()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def init_db():
    _exec("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        balance INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        last_seen TEXT
    )""")
    _exec("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,             -- buy | test | renew | credit
        service_id TEXT DEFAULT '',
        service_title TEXT DEFAULT '',
        volume TEXT DEFAULT '',
        duration TEXT DEFAULT '',
        price INTEGER NOT NULL DEFAULT 0,
        custom_name TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
        paid_with TEXT DEFAULT '',      -- card | credit | free
        receipt TEXT DEFAULT '',
        info TEXT DEFAULT '',
        parent_id INTEGER,
        note TEXT DEFAULT '',
        admin_id INTEGER,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        decided_at TEXT
    )""")


# ---------------- users ----------------

def upsert_user(user_id: int, username: str, first_name: str):
    _exec("""INSERT INTO users(user_id, username, first_name, last_seen)
             VALUES(?,?,?,?)
             ON CONFLICT(user_id) DO UPDATE SET
               username=excluded.username,
               first_name=excluded.first_name,
               last_seen=excluded.last_seen""",
          (user_id, username or "", first_name or "", now()))


def get_user(user_id: int):
    return _one("SELECT * FROM users WHERE user_id=?", (user_id,))


def all_user_ids():
    return [r["user_id"] for r in _all("SELECT user_id FROM users")]


def add_balance(user_id: int, delta: int) -> int:
    _exec("UPDATE users SET balance = balance + ? WHERE user_id=?", (int(delta), user_id))
    return get_user(user_id)["balance"]


# ---------------- orders ----------------

def count_kind(user_id: int, kind: str, status: str) -> int:
    r = _one("SELECT COUNT(*) c FROM orders WHERE user_id=? AND kind=? AND status=?",
             (user_id, kind, status))
    return r["c"]


def create_order(user_id: int, kind: str, service_id="", service_title="", price=0,
                 custom_name="", volume="", duration="",
                 paid_with="", receipt="", parent_id=None) -> int:
    _exec("""INSERT INTO orders(user_id, kind, service_id, service_title, volume, duration,
                                 price, custom_name, paid_with, receipt, parent_id)
             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (user_id, kind, service_id, service_title, volume, duration,
           int(price), custom_name, paid_with, receipt, parent_id))
    return _one("SELECT last_insert_rowid() AS id")["id"]


def get_order(oid: int):
    return _one("SELECT * FROM orders WHERE id=?", (oid,))


def set_order(oid: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    _exec(f"UPDATE orders SET {cols} WHERE id=?", (*fields.values(), oid))


def user_orders(user_id: int, statuses=("approved",)):
    ph = ",".join("?" * len(statuses))
    return _all(f"SELECT * FROM orders WHERE user_id=? AND status IN ({ph}) ORDER BY id DESC",
                (user_id, *statuses))


def pending_orders(limit=None):
    sql = "SELECT * FROM orders WHERE status='pending' ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _all(sql)


def stats() -> dict:
    users = _one("SELECT COUNT(*) c FROM users")["c"]
    orders = _one("SELECT COUNT(*) c FROM orders")["c"]
    approved = _one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders "
                    "WHERE status='approved' AND kind IN ('buy','test','renew')")
    charges = _one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM orders "
                   "WHERE status='approved' AND kind='credit'")
    pending = _one("SELECT COUNT(*) c FROM orders WHERE status='pending'")["c"]
    rejected = _one("SELECT COUNT(*) c FROM orders WHERE status='rejected'")["c"]
    return {
        "users": users,
        "orders": orders,
        "approved": approved["c"],
        "revenue": approved["s"],
        "charges": charges["s"],
        "pending": pending,
        "rejected": rejected,
    }
