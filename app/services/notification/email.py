import logging
import base64  # Necessary for attachments
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition
)
from app.services.notification.base import NotificationChannel
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailNotification(NotificationChannel):
    async def send(self, recipient: str, message: str, **kwargs) -> bool:
        # Pull extra data out of kwargs safely
        attachment = kwargs.get("attachment")
        filename = kwargs.get("filename", "invoice.pdf")

        mail = Mail(
            from_email=settings.email_from,
            to_emails=recipient,
            subject="Order Invoice - E-Pharmacy",
            plain_text_content=message,
        )

        if attachment:
            import base64
            from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
            
            encoded_file = base64.b64encode(attachment).decode()
            mail.add_attachment(Attachment(
                FileContent(encoded_file),
                FileName(filename),
                FileType("application/pdf"),
                Disposition("attachment")
            ))

        try:
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            # SendGrid's client is synchronous; 
            sg.send(mail)
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False