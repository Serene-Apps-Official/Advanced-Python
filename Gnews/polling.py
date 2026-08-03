import streamlit as st
import datetime
import base64
import sqlite3
import smtplib
import ssl
import random
import string
import secrets as pysecrets
from email.mime.text import MIMEText
from contextlib import contextmanager

st.set_page_config(
    page_title="The Book Desk — Shaikh Zulqarnain",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================================
# CONFIG
# =========================================================================

DB_PATH = "reservations.db"

# The one email address allowed to log in as admin. Selecting "admin" as the
# name with any other email will be rejected.
ADMIN_EMAIL = "zohebpass1231@gmail.com"

SUBJECTS = {
    "Hindi":            ["Workbook", "Grammar Notebook", "Digest"],
    "Marathi":          ["Workbook", "Grammar Notebook", "Digest"],
    "History/Civics":   ["Notebook", "Digest"],
    "Geography":        ["Notebook", "Digest"],
    "Maths-1 (Algebra)":  ["Notebook", "Digest"],
    "Maths-2 (Geometry)": ["Notebook", "Digest"],
    "Science-1 (Physics + Chemistry)": ["Notebook", "Digest"],
    "Science-2 (Biology)":            ["Notebook", "Digest"],
    "English":          ["Workbook", "Grammar Notebook", "Digest"],
}

STUDENTS = ["Maaz", "Ziyan", "Ismail", "Mutahhir", "Talha", "Shaikh Affan"]
NAME_OPTIONS = STUDENTS + ["admin"]


def all_book_items():
    items = []
    for subject, item_types in SUBJECTS.items():
        for item_type in item_types:
            book_id = f"{subject}::{item_type}"
            items.append({
                "book_id": book_id,
                "subject": subject,
                "item_type": item_type,
                "label": f"{subject} — {item_type}",
            })
    return items


# =========================================================================
# DATABASE LAYER
# =========================================================================

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                is_admin INTEGER NOT NULL DEFAULT 0,
                verified INTEGER NOT NULL DEFAULT 0,
                device_token TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_codes (
                email TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                needed_by_date TEXT NOT NULL,
                signature_data TEXT,
                signature_type TEXT,
                status TEXT NOT NULL DEFAULT 'waiting',
                created_at TEXT NOT NULL,
                fulfilled_at TEXT,
                returned INTEGER NOT NULL DEFAULT 0,
                returned_on TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                detail TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        # Migration safety: add columns if an older DB file is reused
        existing_cols = [r["name"] for r in conn.execute("PRAGMA table_info(reservations)").fetchall()]
        if "returned" not in existing_cols:
            conn.execute("ALTER TABLE reservations ADD COLUMN returned INTEGER NOT NULL DEFAULT 0")
        if "returned_on" not in existing_cols:
            conn.execute("ALTER TABLE reservations ADD COLUMN returned_on TEXT")


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---- Accounts / auth --------------------------------------------------------

def get_account_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def get_account_by_device_token(token):
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE device_token = ?", (token,)).fetchone()
        return dict(row) if row else None


def create_or_get_account(name, email, is_admin=False):
    email = email.strip().lower()
    existing = get_account_by_email(email)
    if existing:
        return existing
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (name, email, is_admin, verified, created_at) VALUES (?, ?, ?, 0, ?)",
            (name, email, 1 if is_admin else 0, now_iso())
        )
    return get_account_by_email(email)


def mark_verified_with_token(email, device_token):
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET verified = 1, device_token = ? WHERE email = ?",
            (device_token, email.strip().lower())
        )


def set_login_code(email, name, code):
    expires = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_codes (email, code, name, expires_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(email) DO UPDATE SET code=excluded.code, name=excluded.name, expires_at=excluded.expires_at",
            (email.strip().lower(), code, name, expires)
        )


def check_login_code(email, code):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM login_codes WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not row:
            return False
        if row["code"] != code:
            return False
        if datetime.datetime.now() > datetime.datetime.fromisoformat(row["expires_at"]):
            return False
        return True


def clear_login_code(email):
    with get_conn() as conn:
        conn.execute("DELETE FROM login_codes WHERE email = ?", (email.strip().lower(),))


# ---- Reservation operations -------------------------------------------------

def create_reservation(book_id, student_name, needed_by_date, signature_data, signature_type):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reservations
               (book_id, student_name, needed_by_date, signature_data, signature_type, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'waiting', ?)""",
            (book_id, student_name, needed_by_date, signature_data, signature_type, now_iso())
        )


def get_queue_for_book(book_id, include_fulfilled=False):
    with get_conn() as conn:
        if include_fulfilled:
            rows = conn.execute(
                "SELECT * FROM reservations WHERE book_id = ? ORDER BY id ASC", (book_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reservations WHERE book_id = ? AND status = 'waiting' ORDER BY id ASC",
                (book_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_all_reservations():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reservations ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_reservations_for_student(student_name):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE student_name = ? AND status = 'waiting' ORDER BY id ASC",
            (student_name,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_queue_position(reservation_id):
    with get_conn() as conn:
        row = conn.execute("SELECT book_id, id FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        if not row:
            return None
        count = conn.execute(
            "SELECT COUNT(*) as c FROM reservations WHERE book_id = ? AND status = 'waiting' AND id <= ?",
            (row["book_id"], row["id"])
        ).fetchone()
        return count["c"]


def mark_fulfilled(reservation_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET status = 'fulfilled', fulfilled_at = ? WHERE id = ?",
            (now_iso(), reservation_id)
        )


def mark_returned(reservation_id, returned_on_date):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET returned = 1, returned_on = ? WHERE id = ?",
            (returned_on_date, reservation_id)
        )


def unmark_returned(reservation_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET returned = 0, returned_on = NULL WHERE id = ?",
            (reservation_id,)
        )


def cancel_reservation(reservation_id):
    with get_conn() as conn:
        conn.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))


def delete_reservation(reservation_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))


def log_admin_action(action, detail=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_log (action, detail, timestamp) VALUES (?, ?, ?)",
            (action, detail, now_iso())
        )


def reservation_counts_by_book():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT book_id, COUNT(*) as waiting_count FROM reservations WHERE status = 'waiting' GROUP BY book_id"
        ).fetchall()
        return {r["book_id"]: r["waiting_count"] for r in rows}


init_db()


# =========================================================================
# EMAIL SENDING
# Uses Gmail SMTP with an App Password stored in Streamlit Secrets.
# Required secrets: SENDER_EMAIL, SENDER_APP_PASSWORD
# =========================================================================

def send_verification_email(to_email, code):
    sender_email = st.secrets.get("SENDER_EMAIL", None)
    sender_password = st.secrets.get("SENDER_APP_PASSWORD", None)

    if not sender_email or not sender_password:
        return False, (
            "Email sending isn't configured yet. Set SENDER_EMAIL and SENDER_APP_PASSWORD "
            "in your app's Secrets (Streamlit Cloud → Settings → Secrets)."
        )

    subject = "Your Book Desk verification code"
    body = (
        f"Your verification code is: {code}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"— The Book Desk (Shaikh Zulqarnain's book sharing log)"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, f"Couldn't send the email: {e}"


def generate_code():
    return "".join(random.choices(string.digits, k=6))


def generate_device_token():
    return pysecrets.token_urlsafe(24)


# =========================================================================
# DESIGN SYSTEM — "The Library Ledger"
# A dark, minimal, professional theme inspired by premium editorial sites:
# near-black ink base, warm brass/amber glow accent (library-stamp, reading-
# lamp feel), serif display type over clean sans body, monospace for ticket
# data. Every native Streamlit control is restyled to disappear into this
# language — no default Streamlit look should be visible anywhere.
#
# Signature element: the "ticket stub" — a perforated hold-slip card with a
# torn edge and punched notch, echoing a physical library due-date card.
# =========================================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,opsz,wght@0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;1,14..32,500&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --ink: #0A0E0C;
    --ink-1: #0F1512;
    --ink-2: #151C18;
    --ink-3: #1E2621;
    --brass: #C9A227;
    --brass-bright: #F0C94A;
    --brass-dim: #8A6D1F;
    --text: #EDEAE0;
    --text-dim: #9C9A8E;
    --text-faint: #6B6A61;
    --hairline: rgba(201,162,39,0.16);
    --hairline-bright: rgba(201,162,39,0.34);
    --danger: #C9573B;
    --success: #6B9B6E;
    --radius-s: 6px;
    --radius-m: 12px;
    --radius-l: 20px;
    --ease: cubic-bezier(.22,.61,.36,1);
    --serif: 'Lora', 'Georgia', serif;
    --sans: 'Inter', system-ui, sans-serif;
    --mono: 'JetBrains Mono', monospace;
}

/* ---- Nuke Streamlit chrome ------------------------------------------- */
#MainMenu, header[data-testid="stHeader"], footer, .stDeployButton,
div[data-testid="stToolbar"], div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {
    display: none !important;
}
.stApp {
    background:
        radial-gradient(circle at 15% 0%, rgba(201,162,39,.07), transparent 45%),
        radial-gradient(circle at 85% 100%, rgba(201,162,39,.05), transparent 50%),
        var(--ink) !important;
}
.stApp, .stApp * {
    font-family: var(--sans);
}
body, .stApp, [data-testid="stAppViewContainer"] {
    color: var(--text) !important;
}
.block-container {
    max-width: 760px !important;
    padding-top: 2.5rem !important;
    padding-bottom: 5rem !important;
}
h1, h2, h3, h4 {
    font-family: var(--serif) !important;
    color: var(--text) !important;
    letter-spacing: -0.01em;
    font-weight: 500 !important;
}

/* ---- Grain texture overlay -------------------------------------------- */
.grain-overlay {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    opacity: .025; mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* ---- Header block ------------------------------------------------------ */
.desk-header { margin-bottom: 36px; position: relative; z-index: 1; }
.desk-eyebrow {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--brass-bright);
}
.desk-eyebrow::before {
    content: ''; width: 6px; height: 6px; transform: rotate(45deg);
    background: var(--brass); display: inline-block;
    box-shadow: 0 0 8px rgba(201,162,39,.7);
}
.desk-title {
    font-family: var(--serif);
    font-weight: 500;
    font-size: 2.4rem;
    color: var(--text);
    margin: 10px 0 6px 0;
    letter-spacing: -0.015em;
}
.desk-sub {
    font-size: 0.96rem;
    color: var(--text-dim);
    font-weight: 300;
    max-width: 46ch;
}
.desk-header-rule {
    margin-top: 24px;
    height: 1px;
    background: linear-gradient(to right, var(--hairline-bright), transparent 70%);
}

/* ---- Session badge ------------------------------------------------------ */
.session-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 0 18px 0;
    position: relative; z-index: 1;
}
.session-badge {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: var(--mono);
    font-size: 0.74rem;
    letter-spacing: 0.04em;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid var(--hairline);
    background: var(--ink-2);
    color: var(--text-dim);
}
.session-badge .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--brass); box-shadow: 0 0 6px rgba(201,162,39,.8);
}
.session-badge.admin { border-color: var(--hairline-bright); color: var(--brass-bright); }

/* ---- Ticket stub — the signature element ------------------------------- */
.ticket {
    position: relative;
    background: var(--ink-2);
    border: 1px solid var(--hairline);
    border-radius: var(--radius-m);
    padding: 18px 22px;
    margin-bottom: 16px;
    overflow: visible;
    transition: border-color .3s var(--ease), transform .3s var(--ease), box-shadow .3s var(--ease);
}
.ticket:hover {
    border-color: var(--hairline-bright);
    box-shadow: 0 8px 28px -14px rgba(201,162,39,.35);
}
.ticket.mine { border-color: var(--hairline-bright); background: linear-gradient(150deg, var(--ink-2), var(--ink-3)); }
/* Perforated notch on the left edge, like a torn ticket stub */
.ticket::before {
    content: '';
    position: absolute; left: -8px; top: 50%; transform: translateY(-50%);
    width: 16px; height: 16px; border-radius: 50%;
    background: var(--ink);
    border: 1px solid var(--hairline);
}
.ticket-pos {
    font-family: var(--mono);
    font-weight: 600;
    font-size: 1.7rem;
    color: var(--text-dim);
    float: right;
    line-height: 1;
    opacity: 0.85;
}
.ticket-pos.first { color: var(--brass-bright); text-shadow: 0 0 14px rgba(240,201,74,.4); }
.ticket-name {
    font-family: var(--serif);
    font-weight: 500;
    font-size: 1.08rem;
    color: var(--text);
}
.ticket-meta {
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.03em;
    color: var(--text-faint);
    margin-top: 6px;
}

/* ---- Book / catalog cards ----------------------------------------------- */
.book-card {
    background: var(--ink-2);
    border: 1px solid var(--hairline);
    border-radius: var(--radius-s);
    padding: 12px 16px;
    margin-bottom: 8px;
    transition: border-color .25s var(--ease);
}
.book-card:hover { border-color: var(--hairline-bright); }
.book-card .item-type { font-size: 0.88rem; color: var(--text-dim); }
.queue-badge {
    display: inline-block;
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 20px;
    background: var(--ink-3);
    color: var(--text-dim);
    float: right;
    border: 1px solid var(--hairline);
}
.queue-badge.empty { background: rgba(107,155,110,0.1); color: var(--success); border-color: rgba(107,155,110,0.25); }
.queue-badge.busy { background: rgba(201,87,59,0.1); color: var(--danger); border-color: rgba(201,87,59,0.25); }

/* ---- Divider ------------------------------------------------------------ */
.thin-rule { border: none; border-top: 1px solid var(--hairline); margin: 30px 0; }

.empty-note {
    font-style: italic;
    color: var(--text-faint);
    font-size: 0.9rem;
    padding: 14px 0;
}

/* ---- Section labels ------------------------------------------------------ */
.section-label {
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--brass);
    margin-bottom: 10px;
    display: block;
}

/* =========================================================================
   STREAMLIT WIDGET OVERRIDES
   ========================================================================= */

/* Buttons */
.stButton>button, .stFormSubmitButton>button {
    background: var(--brass) !important;
    color: var(--ink) !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 600 !important;
    font-family: var(--sans) !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 1.6rem !important;
    transition: transform .3s var(--ea
