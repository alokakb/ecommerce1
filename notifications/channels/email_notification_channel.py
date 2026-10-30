from django.conf import settings
from notifications.channels.notification_channel import NotificationChannel
from notifications.providers.email_provider_factory import ProviderFactory

class EmailNotificationChannel(NotificationChannel):
    def send_notification(self, notification):
        message_data = notification.message

        subject = message_data['subject']
        body = message_data['body']

        provider = settings.NOTIFICATION_CHANNELS.get("email", {}).get("provider")
        if not provider:
            raise ValueError("Email notification provider is not configured")

        email_provider = ProviderFactory.get_provider(provider)

        return email_provider.send_mail(
            recipient=notification.recipient,
            subject=subject,
            body=body
        )

