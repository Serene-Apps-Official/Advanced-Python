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
# Dark, minimal, brass-accented theme. The CSS lives in a separate plain
# text file (style.css) rather than a giant string inside this file, on
# purpose: a plain CSS file can be partially truncated by a bad copy/paste
# and the app will just look a bit plain — it can never cause a Python
# SyntaxError and crash the whole app the way a broken triple-quoted
# string can. Keep style.css in the same folder as app.py.
# =========================================================================

import os

def load_css():
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""  # if the file is missing/broken, app still runs — just unstyled

st.markdown(f"<style>{load_css()}</style>", unsafe_allow_html=True)

# =========================================================================
# Helpers
# =========================================================================

def render_header(eyebrow, title, sub):
    st.markdown(f"""
    <div class="desk-header">
        <div class="desk-eyebrow">{eyebrow}</div>
        <div class="desk-title">{title}</div>
        <div class="desk-sub">{sub}</div>
        <div class="desk-header-rule"></div>
    </div>
    """, unsafe_allow_html=True)


def days_until(date_str):
    try:
        target = datetime.date.fromisoformat(date_str)
        return (target - datetime.date.today()).days
    except Exception:
        return None


def render_queue_badge_html(count):
    if count == 0:
        return '<span class="queue-badge empty">available</span>'
    elif count >= 2:
        return f'<span class="queue-badge busy">{count} waiting</span>'
    else:
        return f'<span class="queue-badge">{count} waiting</span>'


def render_footer():
    st.markdown("""
    <div class="desk-footer">
        Built for Shaikh Zulqarnain &nbsp;·&nbsp; developed by <span class="name">Serene</span>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# SESSION / LOGIN
# Device stays logged in via a token stored in the URL query params.
# =========================================================================

if "account" not in st.session_state:
    st.session_state.account = None
if "pending_login" not in st.session_state:
    st.session_state.pending_login = None

if st.session_state.account is None:
    token_from_url = st.query_params.get("t", None)
    if token_from_url:
        acct = get_account_by_device_token(token_from_url)
        if acct and acct["verified"]:
            st.session_state.account = acct


def do_logout():
    st.session_state.account = None
    st.session_state.pending_login = None
    st.query_params.clear()


# =========================================================================
# LOGIN SCREEN
# =========================================================================

if st.session_state.account is None:
    render_header("Shaikh Zulqarnain · 10th A", "The Book Desk", "Log in to reserve books or manage the desk.")

    if st.session_state.pending_login is None:
        st.markdown('<span class="section-label">Select your name</span>', unsafe_allow_html=True)
        chosen_name = st.selectbox("Name", NAME_OPTIONS, label_visibility="collapsed")

        st.markdown('<span class="section-label">Your email address</span>', unsafe_allow_html=True)
        email_input = st.text_input("Email", label_visibility="collapsed", placeholder="you@example.com")

        if st.button("Continue", use_container_width=True):
            email_clean = email_input.strip().lower()
            if not email_clean or "@" not in email_clean:
                st.error("Please enter a valid email address.")
            elif chosen_name == "admin":
                if email_clean != ADMIN_EMAIL.lower():
                    st.error("This email isn't authorized for the admin account.")
                else:
                    st.session_state.pending_login = {"name": "admin", "email": email_clean, "mode": "admin_password"}
                    st.rerun()
            else:
                existing = get_account_by_email(email_clean)
                if existing and existing["name"] != chosen_name:
                    st.error("This email is already registered under a different name.")
                else:
                    code = generate_code()
                    ok, err = send_verification_email(email_clean, code)
                    if not ok:
                        st.error(err)
                    else:
                        set_login_code(email_clean, chosen_name, code)
                        st.session_state.pending_login = {"name": chosen_name, "email": email_clean, "mode": "email_code"}
                        st.success(f"Code sent to {email_clean}. Check your inbox.")
                        st.rerun()

    elif st.session_state.pending_login["mode"] == "admin_password":
        st.markdown('<span class="section-label">Admin login — enter the admin password</span>', unsafe_allow_html=True)
        pw = st.text_input("Password", type="password", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Unlock admin", use_container_width=True):
                admin_pw = st.secrets.get("ADMIN_PASSWORD", None)
                if not admin_pw:
                    st.error(
                        "No admin password is configured. Set ADMIN_PASSWORD in your app's Secrets "
                        "(Streamlit Cloud → Settings → Secrets)."
                    )
                elif pw == admin_pw:
                    acct = create_or_get_account("admin", ADMIN_EMAIL, is_admin=True)
                    token = generate_device_token()
                    mark_verified_with_token(ADMIN_EMAIL, token)
                    st.session_state.account = get_account_by_email(ADMIN_EMAIL)
                    st.session_state.pending_login = None
                    st.query_params["t"] = token
                    log_admin_action("login")
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        with c2:
            if st.button("Back", use_container_width=True, type="secondary"):
                st.session_state.pending_login = None
                st.rerun()

    elif st.session_state.pending_login["mode"] == "email_code":
        pending = st.session_state.pending_login
        st.markdown(
            f'<span class="section-label">Enter the 6-digit code sent to {pending["email"]}</span>',
            unsafe_allow_html=True
        )
        code_input = st.text_input("Code", label_visibility="collapsed", placeholder="123456", max_chars=6)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Verify", use_container_width=True):
                if check_login_code(pending["email"], code_input.strip()):
                    create_or_get_account(pending["name"], pending["email"])
                    token = generate_device_token()
                    mark_verified_with_token(pending["email"], token)
                    clear_login_code(pending["email"])
                    st.session_state.account = get_account_by_email(pending["email"])
                    st.session_state.pending_login = None
                    st.query_params["t"] = token
                    st.rerun()
                else:
                    st.error("Incorrect or expired code.")
        with c2:
            if st.button("Resend code", use_container_width=True, type="secondary"):
                code = generate_code()
                ok, err = send_verification_email(pending["email"], code)
                if ok:
                    set_login_code(pending["email"], pending["name"], code)
                    st.success("New code sent.")
                else:
                    st.error(err)
        if st.button("Use a different name or email", type="secondary"):
            st.session_state.pending_login = None
            st.rerun()

    render_footer()
    st.stop()


# ========================================
