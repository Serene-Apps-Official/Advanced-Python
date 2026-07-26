import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Page Configuration ---
st.set_page_config(page_title="User Portal", page_icon="🔑")

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

# --- Initialize Session State from URL Query Parameters ---
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

# --- Interface Logic ---
if not st.session_state.logged_in:
    st.title("🔐 Login")

    with st.form("login_form"):
        username_input = st.text_input("Username", placeholder="Enter your username")
        email_input = st.text_input("Email Address", placeholder="name@example.com")
        submit_button = st.form_submit_button("Submit & Login")

    if submit_button:
        if username_input.strip() and email_input.strip() and "@" in email_input:
            clean_username = username_input.strip()
            clean_email = email_input.strip()

            # Update session state
            st.session_state.logged_in = True
            st.session_state.username = clean_username
            st.session_state.user_email = clean_email

            # Save state into native query parameters for session persistence
            st.query_params["username"] = clean_username
            st.query_params["email"] = clean_email

            with st.spinner("Sending welcome email..."):
                send_welcome_email(clean_email, clean_username)

            st.rerun()
        else:
            st.error("Please provide both a valid username and email address.")

else:
    # --- Welcome Dashboard ---
    st.title(f"Welcome! {st.session_state.username}")
    st.success(f"Logged in as **{st.session_state.username}** ({st.session_state.user_email})")

    st.info("Your login status is saved in the URL parameters and will persist upon revisiting.")

    st.divider()

    if st.button("Log Out", type="primary"):
        # Clear URL parameters and reset session state
        st.query_params.clear()
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_email = ""
        st.rerun()
        
