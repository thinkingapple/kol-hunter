import config
from app.outreach.providers.base import EmailProvider


def get_email_provider() -> EmailProvider:
    """Get the configured email provider."""
    provider_name = config.EMAIL_PROVIDER.lower()
    if provider_name == "gmail":
        from app.outreach.providers.gmail_smtp import GmailSMTPProvider
        return GmailSMTPProvider()
    elif provider_name == "sendgrid":
        from app.outreach.providers.sendgrid import SendGridProvider
        return SendGridProvider()
    elif provider_name == "mailgun":
        from app.outreach.providers.mailgun import MailgunProvider
        return MailgunProvider()
    else:
        from app.outreach.providers.gmail_smtp import GmailSMTPProvider
        return GmailSMTPProvider()


async def send_single_email(to: str, subject: str, body_html: str) -> bool:
    """Send a single email using the configured provider."""
    provider = get_email_provider()
    result = await provider.send_email(
        to=to,
        subject=subject,
        body_html=body_html,
        from_addr=config.SENDER_EMAIL,
        from_name=config.SENDER_NAME,
    )
    return result.success
