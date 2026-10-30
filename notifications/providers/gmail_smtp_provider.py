from django.conf import settings
from django.core.mail import send_mail

from notifications.providers.email_provider import EmailProvider

class GmailSmtpProvider(EmailProvider):
    def send_mail(self, *, recipient, subject, body):
        return send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )