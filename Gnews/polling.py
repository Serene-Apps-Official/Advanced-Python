import streamlit as st
import smtplib
import ssl
import random
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape

# --- Page Configuration ---
st.set_page_config(page_title="User Portal", page_icon="🔑")

# --- Constants ---
OTP_LENGTH = 4
OTP_VALID_SECONDS = 5 * 60   # code expires 5 minutes after being sent
OTP_MAX_ATTEMPTS = 5         # lock out after this many wrong guesses
RESEND_COOLDOWN_SECONDS = 30 # minimum gap between resend requests

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
    """Generates a random 4-digit numeric code as a zero-padded string."""
    return "".join(random.choices("0123456789", k=OTP_LENGTH))


def send_otp_email(recipient_email: str, username: str, code: str) -> bool:
    """Sends the verification code to the user's email via secure SSL SMTP."""
    if not SMTP_CONFIGURED:
        st.error(
            "Email is not configured. Add SMTP credentials to .streamlit/secrets.toml "
            "(see comment at top of app.py)."
        )
        return False

    safe_username = escape(username)

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email
    msg["Subject"] = f"Your verification code: {code}"

    text_content = (
        f"Hello {username},\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in {OTP_VALID_SECONDS // 60} minutes.\n\n"
        f"If you did not request this, you can ignore this email.\n\n"
        f"Best regards,\nThe Team"
    )
    html_content = f"""
    <html>
      <body>
        <h2>Verify your email, {safe_username}</h2>
        <p>Your verification code is:</p>
        <h1 style="letter-spacing: 6px;">{code}</h1>
        <p>This code expires in {OTP_VALID_SECONDS // 60} minutes.</p>
        <hr>
        <p><small>If you did not request this, you can ignore this email.</small></p>
      </body>
    </html>
    """

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


def send_welcome_email(recipient_email: str, username: str) -> bool:
    """Dispatches a personalized welcome email once verification succeeds."""
    if not SMTP_CONFIGURED:
        return False

    safe_username = escape(username)

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email
    msg["Subject"] = f"Welcome to the Portal, {username}!"

    text_content = f"Hello {username},\n\nWelcome! Your email has been verified and you are now logged in.\n\nBest regards,\nThe Team"
    html_content = f"""
    <html>
      <body>
        <h2>Welcome, {safe_username}!</h2>
        <p>Your email has been verified and you are now logged in.</p>
        <hr>
        <p><small>This is an automated notification.</small></p>
      </body>
    </html>
    """

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        return True
    except Exception:
        # Welcome email is a nice-to-have; don't block login if it fails.
        return False


# --- Session State Setup ---
# NOTE ON SECURITY: once verified via the emailed code, this app treats
# "logged_in" as true for the session and persists it via URL query params so
# the tab survives a refresh. That part is still just session continuity, not
# a durable account system — there's no password, no database of users, and
# a new browser/device requires re-verifying. For anything beyond low-stakes
# use, pair this with a real auth backend (Auth0, Firebase Auth, etc.) and use
# this OTP flow purely as the email-ownership check.
query_params = st.query_params

if "logged_in" not in st.session_state:
    if "username" in query_params and "email" in query_params:
        st.session_state.logged_in = True
        st.session_state.username = query_params["username"]
        st.session_state.user_email = query_params["email"]
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""

for key, default in {
    "otp_pending": False,       # True once a code has been sent, until verified
    "otp_code": None,           # the current correct code
    "otp_sent_at": None,        # timestamp the code was sent
    "otp_attempts": 0,          # wrong guesses so far
    "pending_username": "",
    "pending_email": "",
    "welcome_email_sent": False,
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


# --- Interface Logic ---
if not st.session_state.logged_in:
    st.title("🔐 Login")

    if not st.session_state.otp_pending:
        # --- Step 1: collect details, send code ---
        st.caption("Enter your details and we'll email you a verification code.")

        with st.form("login_form"):
            username_input = st.text_input("Username", placeholder="Enter your username")
            email_input = st.text_input("Email Address", placeholder="name@example.com")
            submit_button = st.form_submit_button("Send Verification Code")

        if submit_button:
            if username_input.strip() and email_input.strip() and "@" in email_input:
                clean_username = username_input.strip()
                clean_email = email_input.strip()
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
                    st.rerun()
            else:
                st.error("Please enter a valid username and email address.")

    else:
        # --- Step 2: enter code to verify ---
        st.caption(f"We sent a {OTP_LENGTH}-digit code to **{st.session_state.pending_email}**.")

        elapsed = time.time() - st.session_state.otp_sent_at
        remaining = max(0, OTP_VALID_SECONDS - elapsed)

        if remaining == 0:
            st.warning("That code has expired. Please request a new one.")
        else:
            mins, secs = divmod(int(remaining), 60)
            st.caption(f"Code expires in {mins:02d}:{secs:02d}")

        with st.form("otp_form"):
            code_input = st.text_input(
                "Verification code",
                placeholder="1234",
                max_chars=OTP_LENGTH,
            )
            verify_button = st.form_submit_button("Verify & Log In")

        if verify_button:
            if remaining == 0:
                st.error("Code expired. Please request a new one below.")
            elif st.session_state.otp_attempts >= OTP_MAX_ATTEMPTS:
                st.error("Too many incorrect attempts. Please request a new code.")
            elif code_input.strip() == st.session_state.otp_code:
                clean_username = st.session_state.pending_username
                clean_email = st.session_state.pending_email

                st.session_state.logged_in = True
                st.session_state.username = clean_username
                st.session_state.user_email = clean_email

                st.query_params["username"] = clean_username
                st.query_params["email"] = clean_email

                if not st.session_state.welcome_email_sent:
                    send_welcome_email(clean_email, clean_username)
                    st.session_state.welcome_email_sent = True

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
            if st.button("Use a different email"):
                reset_otp_state()
                st.rerun()

else:
    # --- Dashboard View ---
    st.title(f"Welcome! {st.session_state.username}")
    st.success(f"Logged in as **{st.session_state.username}** ({st.session_state.user_email})")

    st.info("Your session will remain active upon reopening this site until you log out.")

    st.divider()

    if st.button("Log Out", type="primary"):
        st.query_params.clear()
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""
        st.session_state.welcome_email_sent = False
        reset_otp_state()
        st.rerun()
                        
