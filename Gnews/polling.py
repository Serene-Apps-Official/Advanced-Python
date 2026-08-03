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
                suspended INTEGER NOT NULL DEFAULT 0,
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
        existing_acct_cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()]
        if "suspended" not in existing_acct_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0")


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


def student_already_in_queue(book_id, student_name):
    """True if this student already has a 'waiting' reservation for this book."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM reservations WHERE book_id = ? AND student_name = ? AND status = 'waiting' LIMIT 1",
            (book_id, student_name)
        ).fetchone()
        return row is not None


def set_suspended(email, suspended):
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET suspended = ? WHERE email = ?",
            (1 if suspended else 0, email.strip().lower())
        )


def get_all_accounts():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


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
# Dark, minimal, brass-accented theme. Kept as a single plain (non-f) triple
# quoted string with no Python interpolation, so CSS braces/quotes can't be
# misread as Python syntax. Wrapped in try/except so a rendering issue here
# can never take down the rest of the app — worst case it just runs unstyled.
# =========================================================================

BOOK_DESK_CSS = """
/* =========================================================================
   THE BOOK DESK — "The Library Ledger"
   Dark, minimal, brass-accented theme for Streamlit.
   ========================================================================= */

@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ink: #eae4d6;
    --ink-dim: #a89f8c;
    --ink-faint: #6f6857;
    --paper: #14120f;
    --paper-raised: #1c1912;
    --paper-card: #201c15;
    --brass: #c9a15a;
    --brass-bright: #e3bd76;
    --brass-dim: #7a6236;
    --line: #35301f;
    --danger: #c86a5a;
    --good: #7fa876;
}

html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at top, #1a170f 0%, var(--paper) 55%) !important;
    color: var(--ink) !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}

[data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer { visibility: hidden; }

.block-container {
    max-width: 780px !important;
    padding-top: 2.5rem !important;
    padding-bottom: 4rem !important;
}

/* ---- Header ---- */

.desk-header { margin-bottom: 1.75rem; }

.desk-eyebrow {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--brass);
    font-weight: 600;
    margin-bottom: 0.4rem;
}

.desk-title {
    font-family: 'Fraunces', serif;
    font-size: 2.4rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1.1;
    margin-bottom: 0.4rem;
}

.desk-sub {
    font-size: 0.95rem;
    color: var(--ink-dim);
    margin-bottom: 1rem;
}

.desk-header-rule {
    height: 1px;
    background: linear-gradient(90deg, var(--brass-dim), transparent 70%);
    margin-top: 0.5rem;
}

/* ---- Section labels ---- */

.section-label {
    display: block;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--brass);
    font-weight: 600;
    margin: 1.1rem 0 0.4rem 0;
}

/* ---- Inputs ---- */

[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: var(--paper-raised) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    color: var(--ink) !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: var(--brass) !important;
    box-shadow: 0 0 0 1px var(--brass) !important;
}

[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stRadio"] label {
    color: var(--ink-dim) !important;
}

[data-baseweb="select"] svg { fill: var(--ink-dim) !important; }

/* ---- Buttons ---- */

.stButton button, .stFormSubmitButton button, .stDownloadButton button {
    background: var(--paper-raised) !important;
    color: var(--brass-bright) !important;
    border: 1px solid var(--brass-dim) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
    transition: all 0.15s ease !important;
}

.stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {
    background: var(--brass) !important;
    color: #14120f !important;
    border-color: var(--brass) !important;
}

.stButton button[kind="primary"] {
    background: var(--brass) !important;
    color: #14120f !important;
}

/* ---- Book rows ---- */

.book-row {
    background: var(--paper-card);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-top: 0.6rem;
}

.book-row-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.book-row-title {
    font-family: 'Fraunces', serif;
    font-size: 1.05rem;
    font-weight: 500;
    color: var(--ink);
}

.row-spacer { height: 0.6rem; }

/* ---- Queue badges ---- */

.queue-badge {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    background: rgba(201, 161, 90, 0.12);
    color: var(--brass);
    border: 1px solid var(--brass-dim);
}

.queue-badge.empty {
    background: rgba(127, 168, 118, 0.12);
    color: var(--good);
    border-color: rgba(127, 168, 118, 0.4);
}

.queue-badge.busy {
    background: rgba(200, 106, 90, 0.12);
    color: var(--danger);
    border-color: rgba(200, 106, 90, 0.4);
}

/* ---- Reservation / result cards ---- */

.res-card {
    background: var(--paper-card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--brass);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-top: 0.7rem;
    margin-bottom: 0.3rem;
}

.res-card-title {
    font-family: 'Fraunces', serif;
    font-size: 1rem;
    font-weight: 500;
    color: var(--ink);
    margin-bottom: 0.15rem;
}

.res-card-meta {
    font-size: 0.8rem;
    color: var(--ink-dim);
}

.empty-state {
    color: var(--ink-faint);
    font-style: italic;
    padding: 1.5rem 0;
    text-align: center;
    border: 1px dashed var(--line);
    border-radius: 10px;
    margin-top: 0.5rem;
}

/* ---- Log rows ---- */

.log-row {
    font-size: 0.78rem;
    color: var(--ink-dim);
    padding: 0.35rem 0;
    border-bottom: 1px solid var(--line);
}

/* ---- Sidebar ---- */

[data-testid="stSidebar"] {
    background: var(--paper-raised) !important;
    border-right: 1px solid var(--line) !important;
}

.side-name {
    font-family: 'Fraunces', serif;
    font-size: 1.15rem;
    color: var(--brass-bright);
    font-weight: 600;
    margin-top: 0.5rem;
}

.side-email {
    font-size: 0.78rem;
    color: var(--ink-faint);
    margin-bottom: 0.5rem;
}

[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color: var(--ink) !important;
    font-size: 0.92rem;
}

/* ---- Tabs ---- */

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.3rem;
    border-bottom: 1px solid var(--line);
}

[data-testid="stTabs"] button[role="tab"] {
    color: var(--ink-faint) !important;
    font-weight: 600;
    font-size: 0.85rem;
}

[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--brass-bright) !important;
    border-bottom-color: var(--brass) !important;
}

/* ---- Alerts ---- */

[data-testid="stAlert"] {
    border-radius: 8px !important;
    background: var(--paper-card) !important;
    border: 1px solid var(--line) !important;
}

/* ---- Footer ---- */

.desk-footer {
    margin-top: 3rem;
    padding-top: 1.2rem;
    border-top: 1px solid var(--line);
    text-align: center;
    font-size: 0.75rem;
    color: var(--ink-faint);
    letter-spacing: 0.02em;
}

.desk-footer .name {
    color: var(--brass);
    font-weight: 600;
}
"""
