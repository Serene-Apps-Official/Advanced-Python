import streamlit as st
import datetime
import base64
import sqlite3
from contextlib import contextmanager

st.set_page_config(
    page_title="The Book Desk — Shaikh Zulqarnain",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================================
# DATABASE LAYER
# All persistence for the Book Reservation Desk, merged into this single
# file so the whole app deploys as one app.py. Uses SQLite - no external
# database needed.
# =========================================================================

DB_PATH = "reservations.db"

# ---- Fixed catalog ---------------------------------------------------------
# Subjects and which item types each one actually has.
# Textbooks are intentionally excluded everywhere (students cannot borrow them).
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


def all_book_items():
    """Flat list of (subject, item_type, display_label, book_id)."""
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
                expires_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_status (
                book_id TEXT PRIMARY KEY,
                currently_out INTEGER NOT NULL DEFAULT 0
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


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


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
                "SELECT * FROM reservations WHERE book_id = ? ORDER BY id ASC",
                (book_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reservations WHERE book_id = ? AND status = 'waiting' ORDER BY id ASC",
                (book_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_all_active_reservations():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE status = 'waiting' ORDER BY book_id, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_reservations():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reservations ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_reservations_for_student(student_name):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE student_name = ? AND status = 'waiting' ORDER BY id ASC",
            (student_name,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_queue_position(reservation_id):
    """1-indexed position of this reservation within its book's waiting queue.
    Uses the row id (insertion order) rather than the timestamp, since two
    reservations can share the same second-resolution timestamp."""
    with get_conn() as conn:
        row = conn.execute("SELECT book_id, id FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        if not row:
            return None
        count = conn.execute(
            """SELECT COUNT(*) as c FROM reservations
               WHERE book_id = ? AND status = 'waiting' AND id <= ?""",
            (row["book_id"], row["id"])
        ).fetchone()
        return count["c"]


def mark_fulfilled(reservation_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET status = 'fulfilled', fulfilled_at = ? WHERE id = ?",
            (now_iso(), reservation_id)
        )


def cancel_reservation(reservation_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE id = ?",
            (reservation_id,)
        )


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
            """SELECT book_id, COUNT(*) as waiting_count
               FROM reservations WHERE status = 'waiting' GROUP BY book_id"""
        ).fetchall()
        return {r["book_id"]: r["waiting_count"] for r in rows}

init_db()

# =========================================================================
# DESIGN SYSTEM — "Library Hold Desk"
# Deep library green, parchment, brass ticket accents. Serif catalog
# headers over clean sans body. Reservations render as numbered hold tickets.
# =========================================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,600;0,700;1,500&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');

:root {
    --ink: #22303C;
    --parchment: #F7F3E9;
    --parchment-deep: #EFE8D8;
    --green: #1B4332;
    --green-deep: #12291F;
    --sage: #84A98C;
    --brass: #B8860B;
    --brass-light: #D4A62A;
    --red: #B23A2E;
    --line: rgba(34,48,60,0.14);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--ink); }
.stApp { background: var(--parchment); }

h1, h2, h3 { font-family: 'Lora', serif !important; color: var(--green-deep); letter-spacing: -0.01em; }

/* Header block */
.desk-header {
    border-bottom: 2px solid var(--green-deep);
    padding-bottom: 18px;
    margin-bottom: 28px;
}
.desk-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--brass);
    font-weight: 500;
}
.desk-title {
    font-family: 'Lora', serif;
    font-weight: 700;
    font-size: 2.1rem;
    color: var(--green-deep);
    margin: 4px 0 2px 0;
}
.desk-sub {
    font-size: 0.92rem;
    color: rgba(34,48,60,0.65);
}

/* Ticket card — the signature element */
.ticket {
    background: #fff;
    border: 1px solid var(--line);
    border-left: 5px solid var(--green);
    border-radius: 6px;
    padding: 16px 18px;
    margin-bottom: 12px;
    position: relative;
    box-shadow: 0 1px 3px rgba(34,48,60,0.06);
}
.ticket.mine { border-left-color: var(--brass); background: #FFFDF6; }
.ticket-pos {
    font-family: 'Lora', serif;
    font-weight: 700;
    font-size: 1.6rem;
    color: var(--green-deep);
    float: right;
    line-height: 1;
    opacity: 0.85;
}
.ticket-pos.first { color: var(--brass); }
.ticket-name { font-weight: 600; font-size: 1.02rem; }
.ticket-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    color: rgba(34,48,60,0.6);
    margin-top: 4px;
}

/* Book card in catalog */
.book-card {
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.book-card .subject { font-family: 'Lora', serif; font-weight: 600; font-size: 1.05rem; color: var(--green-deep); }
.book-card .item-type { font-size: 0.85rem; color: rgba(34,48,60,0.6); }
.queue-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 3px 9px;
    border-radius: 20px;
    background: var(--parchment-deep);
    color: var(--green-deep);
    float: right;
}
.queue-badge.empty { background: rgba(132,169,140,0.18); color: var(--sage); }
.queue-badge.busy { background: rgba(178,58,46,0.1); color: var(--red); }

/* Buttons */
.stButton>button {
    background: var(--green) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    transition: background 0.15s ease;
}
.stButton>button:hover { background: var(--green-deep) !important; }

/* Divider */
.thin-rule { border: none; border-top: 1px solid var(--line); margin: 22px 0; }

/* Empty state */
.empty-note {
    font-style: italic;
    color: rgba(34,48,60,0.5);
    font-size: 0.9rem;
    padding: 10px 0;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =========================================================================
# Helpers
# =========================================================================

def render_header(eyebrow, title, sub):
    st.markdown(f"""
    <div class="desk-header">
        <div class="desk-eyebrow">{eyebrow}</div>
        <div class="desk-title">{title}</div>
        <div class="desk-sub">{sub}</div>
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


# =========================================================================
# Navigation
# =========================================================================

if "view" not in st.session_state:
    st.session_state.view = "reserve"

top_l, top_r = st.columns([3, 1])
with top_r:
    nav_choice = st.selectbox(
        "Go to",
        ["Reserve a book", "My reservations", "Admin"],
        label_visibility="collapsed",
        index=["Reserve a book", "My reservations", "Admin"].index(
            {"reserve": "Reserve a book", "mine": "My reservations", "admin": "Admin"}[st.session_state.view]
        ),
    )
    st.session_state.view = {"Reserve a book": "reserve", "My reservations": "mine", "Admin": "admin"}[nav_choice]


# =========================================================================
# VIEW: Reserve a book
# =========================================================================

if st.session_state.view == "reserve":
    render_header(
        "Shaikh Zulqarnain · 10th A",
        "The Book Desk",
        "Reserve a notebook or digest ahead of time — first to reserve gets it first."
    )

    counts = reservation_counts_by_book()
    items = all_book_items()

    with st.form("reservation_form", clear_on_submit=False):
        st.markdown("**Who are you?**")
        student_name = st.selectbox("Student name", STUDENTS, label_visibility="collapsed")

        st.markdown("**Which book do you need?**")
        item_labels = [it["label"] for it in items]
        chosen_label = st.selectbox("Book needed", item_labels, label_visibility="collapsed")
        chosen_item = next(it for it in items if it["label"] == chosen_label)

        # Live queue context for the chosen book
        current_count = counts.get(chosen_item["book_id"], 0)
        if current_count == 0:
            st.caption("🟢 No one else is waiting for this right now.")
        else:
            st.caption(f"🟠 {current_count} student(s) already waiting — you'll be #{current_count + 1} in line.")

        st.markdown("**When do you need it by?**")
        needed_by = st.date_input(
            "Needed by",
            min_value=datetime.date.today(),
            value=datetime.date.today(),
            label_visibility="collapsed"
        )

        st.markdown("**Signature**")
        sig_tab1, sig_tab2 = st.tabs(["Draw signature", "Upload image"])
        signature_data = None
        signature_type = None

        with sig_tab1:
            st.caption("Draw with your mouse or finger below.")
            try:
                from streamlit_drawable_canvas import st_canvas
                canvas_result = st_canvas(
                    stroke_width=2,
                    stroke_color="#22303C",
                    background_color="#FFFFFF",
                    height=150,
                    width=400,
                    drawing_mode="freedraw",
                    key="sig_canvas",
                )
                if canvas_result.image_data is not None:
                    import numpy as np
                    from PIL import Image
                    import io
                    arr = canvas_result.image_data
                    if arr.sum() > 0:
                        img = Image.fromarray(arr.astype("uint8"), "RGBA")
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        signature_data = base64.b64encode(buf.getvalue()).decode()
                        signature_type = "drawn"
            except ImportError:
                st.info(
                    "Drawing requires the `streamlit-drawable-canvas` package. "
                    "Add it to requirements.txt, or use the **Upload image** tab instead."
                )

        with sig_tab2:
            uploaded_sig = st.file_uploader("Upload a photo of your signature", type=["png", "jpg", "jpeg"])
            if uploaded_sig is not None:
                signature_data = base64.b64encode(uploaded_sig.read()).decode()
                signature_type = "uploaded"

        submitted = st.form_submit_button("Reserve this book", use_container_width=True)

        if submitted:
            if signature_data is None:
                st.error("Please draw or upload your signature before submitting.")
            else:
                create_reservation(
                    book_id=chosen_item["book_id"],
                    student_name=student_name,
                    needed_by_date=needed_by.isoformat(),
                    signature_data=signature_data,
                    signature_type=signature_type,
                )
                st.success(f"Reserved! You're in line for **{chosen_label}**.")
                st.rerun()

    st.markdown('<hr class="thin-rule">', unsafe_allow_html=True)
    st.markdown("### Current queue status")
    st.caption("A quick look at what's in demand right now.")

    for subject, item_types in SUBJECTS.items():
        with st.expander(subject, expanded=False):
            for item_type in item_types:
                book_id = f"{subject}::{item_type}"
                count = counts.get(book_id, 0)
                badge = render_queue_badge_html(count)
                st.markdown(
                    f'<div class="book-card">{badge}<div class="item-type">{item_type}</div></div>',
                    unsafe_allow_html=True
                )


# =========================================================================
# VIEW: My reservations
# =========================================================================

elif st.session_state.view == "mine":
    render_header(
        "Personal status",
        "My Reservations",
        "Check your place in line and when your reservation is for."
    )

    who = st.selectbox("I am:", STUDENTS)
    my_reservations = get_reservations_for_student(who)

    if not my_reservations:
        st.markdown('<div class="empty-note">No active reservations. Head to "Reserve a book" to join a queue.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"**{len(my_reservations)}** active reservation(s):")
        for res in my_reservations:
            pos = get_queue_position(res["id"])
            book_label = res["book_id"].replace("::", " — ")
            d_until = days_until(res["needed_by_date"])

            if d_until is not None and d_until < 0:
                due_text = f"needed by {res['needed_by_date']} (overdue)"
            elif d_until == 0:
                due_text = "needed today"
            else:
                due_text = f"needed by {res['needed_by_date']} ({d_until} day{'s' if d_until != 1 else ''} left)"

            pos_class = "first" if pos == 1 else ""
            st.markdown(f"""
            <div class="ticket mine">
                <span class="ticket-pos {pos_class}">#{pos}</span>
                <div class="ticket-name">{book_label}</div>
                <div class="ticket-meta">{due_text.upper()}</div>
            </div>
            """, unsafe_allow_html=True)

        st.caption("Position #1 means you're next to receive the book from Shaikh Zulqarnain.")


# =========================================================================
# VIEW: Admin
# =========================================================================

elif st.session_state.view == "admin":
    render_header("Owner access only", "Admin Panel", "Full control over queues, reservations, and fulfillment.")

    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

    if not st.session_state.admin_authed:
        st.markdown("Enter your passcode to continue.")
        code_input = st.text_input("Passcode", type="password", label_visibility="collapsed")
        if st.button("Unlock"):
            admin_code = st.secrets.get("ADMIN_PASSCODE", None) if hasattr(st, "secrets") else None
            if admin_code is None:
                st.error(
                    "No admin passcode is configured. Set ADMIN_PASSCODE in your app's Secrets "
                    "(Streamlit Cloud → Settings → Secrets) before using the admin panel."
                )
            elif code_input == admin_code:
                st.session_state.admin_authed = True
                log_admin_action("login")
                st.rerun()
            else:
                st.error("Incorrect passcode.")
        st.stop()

    top_bar
