import streamlit as st
import extra_streamlit_components as stx
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Page Configuration ---
st.set_page_config(page_title="User Portal", page_icon="🔑")

# --- Cookie Manager Initialization ---
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# --- SMTP Email Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"      # Replace with your SMTP email
SENDER_PASSWORD = "your_app_password"       # Replace with your SMTP App Password

def send_welcome_email(recipient_email: str, username: str) -> bool:
    """Dispatches a personalized welcome email via SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = f"Welcome, {username}!"

        body = (
            f"Hello {username},\n\n"
            f"Welcome to our platform! You have successfully logged in.\n\n"
            f"Best regards,\nThe System Team"
        )
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send welcome email: {e}")
        return False

# --- Persistent Session Check ---
auth_cookie = cookie_manager.get(cookie="auth_user")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# Auto-login from persistent cookie if present
if auth_cookie and not st.session_state.logged_in:
    try:
        user_data = json.loads(auth_cookie)
        st.session_state.logged_in = True
        st.session_state.username = user_data.get("username", "")
        st.session_state.user_email = user_data.get("email", "")
    except Exception:
        pass

# --- Interface & Logic ---
if not st.session_state.logged_in:
    st.title("🔐 Login")

    with st.form("login_form"):
        username_input = st.text_input("Username", placeholder="Enter your username")
        email_input = st.text_input("Email Address", placeholder="name@example.com")
        submit_button = st.form_submit_button("Submit & Login")

    if submit_button:
        if username_input.strip() and email_input.strip() and "@" in email_input:
            st.session_state.logged_in = True
            st.session_state.username = username_input.strip()
            st.session_state.user_email = email_input.strip()

            # Save login state to browser cookie (Expires in 30 days)
            cookie_data = json.dumps({
                "username": st.session_state.username,
                "email": st.session_state.user_email
            })
            cookie_manager.set("auth_user", cookie_data, max_age=30*24*3600)

            with st.spinner("Sending welcome email..."):
                send_welcome_email(st.session_state.user_email, st.session_state.username)

            st.rerun()
        else:
            st.error("Please provide both a valid username and email address.")

else:
    # --- Welcome Dashboard ---
    st.title(f"Welcome! {st.session_state.username}")
    st.success(f"Logged in as **{st.session_state.username}** ({st.session_state.user_email})")
    
    st.info("You will remain automatically logged in every time you open this website until you explicitly log out.")

    st.divider()

    if st.button("Log Out", type="primary"):
        # Clear cookies and reset state
        cookie_manager.delete("auth_user")
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""
        st.rerun()
    
