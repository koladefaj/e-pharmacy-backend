# test_sendgrid_windows.py
import ssl
import warnings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings

# --- Config ---
SENDGRID_API_KEY = settings.sendgrid_api_key
FROM_EMAIL = settings.email_from
TO_EMAIL = "your_email_here@gmail.com"  # Change to your email

if not SENDGRID_API_KEY or not FROM_EMAIL or not TO_EMAIL:
    print("Please set SENDGRID_API_KEY, EMAIL_FROM, and TO_EMAIL properly.")
    exit(1)

# --- Bypass SSL verification (Windows / local dev only!) ---
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Create email ---
message = Mail(
    from_email=FROM_EMAIL,
    to_emails=TO_EMAIL,
    subject="SendGrid Test Email (Windows SSL Bypass)",
    plain_text_content="This is a test email from SendGrid on Windows ignoring SSL.",
)

# --- Send email ---
try:
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    print(f"✅ Email sent! Status code: {response.status_code}")
except Exception as e:
    print(f"❌ SendGrid failed: {e}")
