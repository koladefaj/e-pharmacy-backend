import logging
from app.services.notification.base import NotificationChannel
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailNotification(NotificationChannel):
    async def send(self, recipient: str, message: str) -> bool:
        mail = Mail(
            from_email=settings.email_from,
            to_emails=recipient,
            subject="E-Pharmacy Notification",
            plain_text_content=message,
        )

        try:
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            sg.send(mail)
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
