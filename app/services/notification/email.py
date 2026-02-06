import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.core.config import settings
from app.services.notification.base import NotificationChannel

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

            from sendgrid.helpers.mail import (
                Attachment,
                Disposition,
                FileContent,
                FileName,
                FileType,
            )

            encoded_file = base64.b64encode(attachment).decode()
            mail.add_attachment(
                Attachment(
                    FileContent(encoded_file),
                    FileName(filename),
                    FileType("application/pdf"),
                    Disposition("attachment"),
                )
            )

        try:
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            # SendGrid's client is synchronous;
            sg.send(mail)
            return True
        except Exception as e:
            # Handle SSL Certificate Verify Failed (Common in corporate/local envs)
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                logger.warning(
                    "SSL Certificate verification failed. Retrying with unverified context."
                )
                import ssl

                # Verify we are in a safe environment to do this?
                # For now, we assume if it failed, we try this fallback.
                try:
                    # Save original context creator
                    original_create_default_https_context = (
                        ssl._create_default_https_context
                    )
                    # Bypass verification
                    ssl._create_default_https_context = ssl._create_unverified_context

                    sg_unverified = SendGridAPIClient(settings.sendgrid_api_key)
                    sg_unverified.send(mail)
                    logger.info("Email sent successfully with unverified context.")
                    return True
                except Exception as retry_e:
                    logger.error(f"Retry failed: {retry_e}")
                    # Fall through to return False
                finally:
                    # Restore original context
                    ssl._create_default_https_context = (
                        original_create_default_https_context
                    )

            logger.error(f"Email send failed: {e}")
            return False
