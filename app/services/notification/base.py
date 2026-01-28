from abc import ABC, abstractmethod

class NotificationChannel(ABC):
    @abstractmethod
    async def send(self, recipient: str, message: str, **kwargs):
        """
        Base send method. 
        Use **kwargs to handle channel-specific data like attachments or titles.
        """
        pass