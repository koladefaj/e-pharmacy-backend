from app.services.notification.base import NotificationChannel


class WhatsAppNotification(NotificationChannel):
    async def send(self, recipient: str, message: str, **kwargs):
        # integrate Twilio / Meta WhatsApp later
        print(f"[WHATSAPP] To: {recipient} | Message: {message}")
