import streamlit as st
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Page Configuration ---
st.set_page_config(page_title="User Portal", page_icon="🔑")

# --- SMTP Credentials Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # SSL port for increased connection stability
SENDER_EMAIL = "your_email@gmail.com"       # Replace with your Gmail address
SENDER_PASSWORD = "your_16_char_app_pass"   # Replace with your 16-character Google App Password

def send_welcome_email(recipient_email: str, username: str) -> bool:
    """Dispatches a personalized welcome email via secure SSL SMTP connection."""
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email
    msg["Subject"] = f"Welcome to the Portal, {username}!"

    text_content = f"Hello {username},\n\nWelcome! You have successfully logged in.\n\nBest regards,\nThe Team"
    html_content = f"""
    <html>
      <body>
        <h2>Welcome, {username}!</h2>
        <p>You have successfully logged in to the application.</p>
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
    except smtplib.SMTPAuthenticationError:
        st.error("SMTP Authentication Failed: Ensure you are using an App Password instead of your regular account password.")
        return False
    except smtplib.SMTPConnectError:
        st.error("SMTP Connection Failed: Unable to reach the mail server. Check network or firewall settings.")
        return False
    except Exception as e:
        st.error(f"Email Dispatch Error: {str(e)}")
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

            with st.spinner("Dispatching welcome email..."):
                email_sent = send_welcome_email(clean_email, clean_username)

            if email_sent:
                st.session_state.logged_in = True
                st.session_state.username = clean_username
                st.session_state.user_email = clean_email

                # Persist authentication in URL parameters
                st.query_params["username"] = clean_username
                st.query_params["email"] = clean_email

                st.rerun()
        else:
            st.error("Please enter a valid username and email address.")

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
        st.rerun()
        
