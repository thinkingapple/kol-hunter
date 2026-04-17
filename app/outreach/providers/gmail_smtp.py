import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
from app.outreach.providers.base import EmailProvider, SendResult


class GmailSMTPProvider(EmailProvider):
    def __init__(self):
        self.address = config.GMAIL_ADDRESS
        self.password = config.GMAIL_APP_PASSWORD

    async def send_email(
        self, to: str, subject: str, body_html: str,
        from_addr: str = "", from_name: str = "", reply_to: str = None
    ) -> SendResult:
        if not self.address or not self.password:
            return SendResult(success=False, error="Gmail credentials not configured")

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{from_name or config.SENDER_NAME} <{from_addr or self.address}>"
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname="smtp.gmail.com",
                port=587,
                start_tls=True,
                username=self.address,
                password=self.password,
            )
            return SendResult(success=True, message_id=msg.get("Message-ID", ""))
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def check_health(self) -> bool:
        if not self.address or not self.password:
            return False
        try:
            smtp = aiosmtplib.SMTP(hostname="smtp.gmail.com", port=587, start_tls=True)
            await smtp.connect()
            await smtp.login(self.address, self.password)
            await smtp.quit()
            return True
        except Exception:
            return False
