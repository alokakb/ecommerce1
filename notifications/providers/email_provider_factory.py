from notifications.providers.gmail_smtp_provider import GmailSmtpProvider

class ProviderFactory:
    @staticmethod
    def get_provider(provider:str):
        if provider == "gmail":
            return GmailSmtpProvider()
        else:
            raise ValueError(f"Unsupported provider {provider}")
