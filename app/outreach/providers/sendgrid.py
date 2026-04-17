import httpx

import config
from app.outreach.providers.base import EmailProvider, SendResult


class SendGridProvider(EmailProvider):
    API_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self):
        self.api_key = config.SENDGRID_API_KEY

    async def send_email(
        self, to: str, subject: str, body_html: str,
        from_addr: str = "", from_name: str = "", reply_to: str = None
    ) -> SendResult:
        if not self.api_key:
            return SendResult(success=False, error="SendGrid API key not configured")

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {
                "email": from_addr or config.SENDER_EMAIL,
                "name": from_name or config.SENDER_NAME,
            },
            "subject": subject,
            "content": [{"type": "text/html", "value": body_html}],
        }
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )
                if resp.status_code in (200, 201, 202):
                    return SendResult(success=True, message_id=resp.headers.get("X-Message-Id", ""))
                return SendResult(success=False, error=f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def check_health(self) -> bool:
        return bool(self.api_key)
