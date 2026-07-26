import streamlit as st
import smtplib
import ssl
import random
import time
import sqlite3
import hashlib
import hmac
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape

# --- Page Configuration ---
st.set_page_config(page_title="User Portal", page_icon="🔑")

# --- Constants ---
OTP_LENGTH = 4
OTP_VALID_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30
DB_PATH = os.path.join(os.path.dirname(__file__), "portal.db")

# --- NOTE ON STORAGE (read this before deploying) ---
# This app stores accounts in a local SQLite file (portal.db) sitting next to
# app.py. On Streamlit Community Cloud, the filesystem persists while the app
# is running, but a redeploy (new commit, reboot, or the app going to sleep
# and waking back up on a new container) can wipe it. That means accounts and
# saved notes can occasionally disappear without warning.
#
# This is fine for testing/demoing. For real production use with accounts you
# expect to keep, swap this for a hosted database (e.g. Supabase, Postgres,
# Turso) that lives outside the app's own container. The functions below
# (get_user, create_user, verify_password, save_user_note) are the only ones
# that touch storage — replacing the DB just means rewriting those.


# --- Database Setup ---
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


# --- Password Hashing (PBKDF2, no plaintext passwords ever stored) ---
def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return pw_hash.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    salt = bytes.fromhex(stored_salt)
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, stored_hash)


def get_user(email: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def create_user(email: str, username: str, password: str):
    pw_hash, salt = hash_password(password)
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (email, username, password_hash, password_salt, note) VALUES (?, ?, ?, ?, '')",
        (email, username, pw_hash, salt),
    )
    conn.commit()
    conn.close()


def save_user_note(email: str, note: str):
    conn = get_connection()
    conn.execute("UPDATE users SET note = ? WHERE email = ?", (note, email))
    conn.commit()
    conn.close()


# --- SMTP Credentials Configuration ---
# NEVER hardcode credentials in source. Put these in .streamlit/secrets.toml (local)
# or in your deployment's Secrets manager (Streamlit Community Cloud, etc):
#
#   [smtp]
#   server = "smtp.gmail.com"
#   port = 465
#   sender_email = "your_email@gmail.com"
#   sender_password = "your_16_char_app_pass"
#
# .streamlit/secrets.toml should be in .gitignore and never committed.
try:
    SMTP_SERVER = st.secrets["smtp"]["server"]
    SMTP_PORT = int(st.secrets["smtp"]["port"])
    SENDER_EMAIL = st.secrets["smtp"]["sender_email"]
    SENDER_PASSWORD = st.secrets["smtp"]["sender_password"]
    SMTP_CONFIGURED = True
except Exception:
    SMTP_CONFIGURED = False


def generate_otp() -> str:
    return "".join(random.choices("0123456789", k=OTP_LENGTH))


def _send_email(recipient_email: str, subject: str, text_content: str, html_content: str) -> bool:
    if not SMTP_CONFIGURED:
        st.error(
            "Email is not configured. Add SMTP credentials to .streamlit/secrets.toml "
            "(see comment near the top of app.py)."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        st.error("SMTP Authentication Failed: Ensure you are using an App Password instead of your regular account password.")
        return False
    except smtplib.SMTPConnectError:
        st.error("SMTP Connection Failed: Unable to reach the mail server. Check network or firewall settings.")
        return False
    except Exception as e:
        st.error(f"Email Dispatch Error: {str(e)}")
        return False


def send_otp_email(recipient_email: str, username: str, code: str) -> bool:
    safe_username = escape(username)
    text_content = (
        f"Hello {username},\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in {OTP_VALID_SECONDS // 60} minutes.\n\n"
        f"If you did not request this, you can ignore this email.\n\n"
        f"Best regards,\nThe Team"
    )
    html_content = f"""
    <html><body>
        <h2>Verify your email, {safe_username}</h2>
        <p>Your verification code is:</p>
        <h1 style="letter-spacing: 6px;">{code}</h1>
        <p>This code expires in {OTP_VALID_SECONDS // 60} minutes.</p>
        <hr><p><small>If you did not request this, you can ignore this email.</small></p>
    </body></html>
    """
    return _send_email(recipient_email, f"Your verification code: {code}", text_content, html_content)


def send_welcome_email(recipient_email: str, username: str) -> bool:
    safe_username = escape(username)
    text_content = f"Hello {username},\n\nYour account has been created and verified. Welcome!\n\nBest regards,\nThe Team"
    html_content = f"""
    <html><body>
        <h2>Welcome, {safe_username}!</h2>
        <p>Your account has been created and verified.</p>
        <hr><p><small>This is an automated notification.</small></p>
    </body></html>
    """
    return _send_email(recipient_email, f"Welcome to the Portal, {username}!", text_content, html_content)


# --- Session State Setup ---
# NOTE ON SECURITY: login persists via URL query params (?email=...) purely so
# a refreshed tab stays logged in. The query param itself is not treated as
# proof of identity for anything sensitive — the password check only happens
# at actual login time, and the note-saving action just uses whatever email
# is currently in session. Don't extend this pattern to gate highly sensitive
# actions without a proper server-side session/token system.
query_params = st.query_params

if "logged_in" not in st.session_state:
    if "email" in query_params and get_user(query_params["email"]):
        user = get_user(query_params["email"])
        st.session_state.logged_in = True
        st.session_state.username = user["username"]
        st.session_state.user_email = user["email"]
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""

for key, default in {
    "mode": "login",            # "login" or "signup"
    "otp_pending": False,
    "otp_code": None,
    "otp_sent_at": None,
    "otp_attempts": 0,
    "pending_username": "",
    "pending_email": "",
    "pending_password": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def reset_otp_state():
    st.session_state.otp_pending = False
    st.session_state.otp_code = None
    st.session_state.otp_sent_at = None
    st.session_state.otp_attempts = 0
    st.session_state.pending_username = ""
    st.session_state.pending_email = ""
    st.session_state.pending_password = ""


# --- Interface Logic ---
if not st.session_state.logged_in:

    if not st.session_state.otp_pending:
        st.title("🔐 " + ("Sign Up" if st.session_state.mode == "signup" else "Log In"))

        tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

        # --- LOG IN TAB ---
        with tab_login:
            st.caption("Already have an account? Enter your email and password.")
            with st.form("login_form"):
                login_email = st.text_input("Email Address", placeholder="name@example.com", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                login_submit = st.form_submit_button("Log In")

            if login_submit:
                clean_email = login_email.strip()
                user = get_user(clean_email) if clean_email else None

                if not clean_email or not login_password:
                    st.error("Please enter both email and password.")
                elif user is None:
                    st.error("No account found with that email. Try signing up instead.")
                elif not verify_password(login_password, user["password_hash"], user["password_salt"]):
                    st.error("Incorrect password.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = user["username"]
                    st.session_state.user_email = user["email"]
                    st.query_params["email"] = user["email"]
                    st.rerun()

        # --- SIGN UP TAB ---
        with tab_signup:
            st.caption("New here? Create an account — we'll verify your email with a code first.")
            with st.form("signup_form"):
                signup_username = st.text_input("Username", placeholder="Enter your username", key="signup_username")
                signup_email = st.text_input("Email Address", placeholder="name@example.com", key="signup_email")
                signup_password = st.text_input("Choose a Password", type="password", key="signup_password")
                signup_password_confirm = st.text_input("Confirm Password", type="password", key="signup_password_confirm")
                signup_submit = st.form_submit_button("Send Verification Code")

            if signup_submit:
                clean_username = signup_username.strip()
                clean_email = signup_email.strip()

                if not (clean_username and clean_email and "@" in clean_email and signup_password):
                    st.error("Please fill in all fields with a valid email.")
                elif len(signup_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif signup_password != signup_password_confirm:
                    st.error("Passwords do not match.")
                elif get_user(clean_email) is not None:
                    st.error("An account with that email already exists. Try logging in instead.")
                else:
                    code = generate_otp()
                    with st.spinner("Sending verification code..."):
                        sent = send_otp_email(clean_email, clean_username, code)
                    if sent:
                        st.session_state.otp_pending = True
                        st.session_state.otp_code = code
                        st.session_state.otp_sent_at = time.time()
                        st.session_state.otp_attempts = 0
                        st.session_state.pending_username = clean_username
                        st.session_state.pending_email = clean_email
                        st.session_state.pending_password = signup_password
                        st.rerun()

    else:
        # --- OTP VERIFICATION STEP (sign-up only) ---
        st.title("🔐 Verify Your Email")
        st.caption(f"We sent a {OTP_LENGTH}-digit code to **{st.session_state.pending_email}**.")

        elapsed = time.time() - st.session_state.otp_sent_at
        remaining = max(0, OTP_VALID_SECONDS - elapsed)

        if remaining == 0:
            st.warning("That code has expired. Please request a new one.")
        else:
            mins, secs = divmod(int(remaining), 60)
            st.caption(f"Code expires in {mins:02d}:{secs:02d}")

        with st.form("otp_form"):
            code_input = st.text_input("Verification code", placeholder="1234", max_chars=OTP_LENGTH)
            verify_button = st.form_submit_button("Verify & Create Account")

        if verify_button:
            if remaining == 0:
                st.error("Code expired. Please request a new one below.")
            elif st.session_state.otp_attempts >= OTP_MAX_ATTEMPTS:
                st.error("Too many incorrect attempts. Please request a new code.")
            elif code_input.strip() == st.session_state.otp_code:
                clean_username = st.session_state.pending_username
                clean_email = st.session_state.pending_email
                clean_password = st.session_state.pending_password

                if get_user(clean_email) is not None:
                    st.error("An account with that email already exists. Try logging in instead.")
                    reset_otp_state()
                    st.session_state.mode = "login"
                    st.rerun()
                else:
                    create_user(clean_email, clean_username, clean_password)
                    send_welcome_email(clean_email, clean_username)

                    st.session_state.logged_in = True
                    st.session_state.username = clean_username
                    st.session_state.user_email = clean_email
                    st.query_params["email"] = clean_email

                    reset_otp_state()
                    st.rerun()
            else:
                st.session_state.otp_attempts += 1
                left = OTP_MAX_ATTEMPTS - st.session_state.otp_attempts
                if left > 0:
                    st.error(f"Incorrect code. {left} attempt(s) remaining.")
                else:
                    st.error("Too many incorrect attempts. Please request a new code.")

        col1, col2 = st.columns(2)
        with col1:
            can_resend = elapsed >= RESEND_COOLDOWN_SECONDS
            if st.button(
                "Resend Code" if can_resend else f"Resend available in {int(RESEND_COOLDOWN_SECONDS - elapsed)}s",
                disabled=not can_resend,
            ):
                new_code = generate_otp()
                with st.spinner("Resending verification code..."):
                    sent = send_otp_email(
                        st.session_state.pending_email,
                        st.session_state.pending_username,
                        new_code,
                    )
                if sent:
                    st.session_state.otp_code = new_code
                    st.session_state.otp_sent_at = time.time()
                    st.session_state.otp_attempts = 0
                    st.rerun()
        with col2:
            if st.button("Start Over"):
                reset_otp_state()
                st.rerun()

else:
    # --- Dashboard View ---
    st.title(f"Welcome! {st.session_state.username}")
    st.success(f"Logged in as **{st.session_state.username}** ({st.session_state.user_email})")

    st.divider()

    st.subheader("📝 Your Notes")
    user = get_user(st.session_state.user_email)
    existing_note = user["note"] if user else ""

    note_input = st.text_area("Write something and save it:", value=existing_note, height=150)

    if st.button("Save", type="primary"):
        save_user_note(st.session_state.user_email, note_input)
        st.success("Saved!")
        st.rerun()

    st.divider()

    if st.button("Log Out"):
        st.query_params.clear()
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""
        reset_otp_state()
        st.rerun()
    
