import httpx

import config
from app.outreach.providers.base import EmailProvider, SendResult


class MailgunProvider(EmailProvider):
    def __init__(self):
        self.api_key = config.MAILGUN_API_KEY
        self.domain = config.MAILGUN_DOMAIN

    async def send_email(
        self, to: str, subject: str, body_html: str,
        from_addr: str = "", from_name: str = "", reply_to: str = None
    ) -> SendResult:
        if not self.api_key or not self.domain:
            return SendResult(success=False, error="Mailgun credentials not configured")

        sender = f"{from_name or config.SENDER_NAME} <{from_addr or config.SENDER_EMAIL}>"
        data = {
            "from": sender,
            "to": to,
            "subject": subject,
            "html": body_html,
        }
        if reply_to:
            data["h:Reply-To"] = reply_to

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.mailgun.net/v3/{self.domain}/messages",
                    auth=("api", self.api_key),
                    data=data,
                    timeout=15,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return SendResult(success=True, message_id=result.get("id", ""))
                return SendResult(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def check_health(self) -> bool:
        return bool(self.api_key and self.domain)
