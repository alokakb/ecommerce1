from notifications.channels.email_notification_channel import EmailNotificationChannel
from notifications.channels.whatsapp_notification_channel import WhatsAppNotificationChannel
from notifications.channels.notification_channel import NotificationChannel

class ChannelFactory:
    @staticmethod
    def create_channel(channel:str) -> NotificationChannel:
        if channel == "whatsapp":
            return WhatsAppNotificationChannel()
        elif channel == "email":
            return EmailNotificationChannel()
        else:
            raise ValueError(f"Unsupported notification channel: {channel}")