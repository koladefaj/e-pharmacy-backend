from typing import List
from app.services.notification.email import EmailNotification
from app.services.notification.whatsapp import WhatsAppNotification

class NotificationService:
    def __init__(self):
        self.channels = {
            "email": EmailNotification(),
            "whatsapp": WhatsAppNotification(),
        }

    async def notify(
        self,
        *,
        email: str | None,
        phone: str | None,
        message: str,
        channels: List[str],
    ):
        for channel in channels:
            if channel == "email" and email:
                await self.channels["email"].send(email, message)

            if channel == "whatsapp" and phone:
                await self.channels["whatsapp"].send(phone, message)
