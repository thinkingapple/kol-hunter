from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    success: bool
    message_id: str = ""
    error: str = ""


class EmailProvider(ABC):
    @abstractmethod
    async def send_email(
        self, to: str, subject: str, body_html: str,
        from_addr: str, from_name: str = "", reply_to: str = None
    ) -> SendResult:
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        ...
