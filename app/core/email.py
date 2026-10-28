
from typing import Optional, Dict, Any
import httpx
from app.core.config import settings
from fastapi import BackgroundTasks

import logging
logger = logging.getLogger(__name__)


BREVO_API_KEY = settings.BREVO_API_KEY
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

DEFAULT_SENDER_NAME = "CargoFlow Africa"
DEFAULT_SENDER_EMAIL = "noreply@cargoflowafrica.co.za"


class BrevoMailer:
    def __init__(self, background_tasks: Optional[BackgroundTasks] = None):
        self.background_tasks = background_tasks

    async def send(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        to_name: Optional[str] = None,
        sender_email: str = DEFAULT_SENDER_EMAIL,
        sender_name: str = DEFAULT_SENDER_NAME,
    ) -> dict:
        if not BREVO_API_KEY:
            raise ValueError("BREVO_API_KEY is missing from environment variables.")

        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        }

        payload: Dict[str, Any] = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_email, "name": to_name or to_email}],
            "subject": subject,
            "htmlContent": html_content,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    BREVO_API_URL, json=payload, headers=headers, timeout=10.0
                )
        except httpx.HTTPError:
            logger.exception("Brevo request failed for %s", to_email)
            raise

        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        if response.status_code not in (200, 201):
            logger.error("Brevo API error [%s] for %s: %s", response.status_code, to_email, data)
            raise Exception(f"Brevo API error [{response.status_code}]: {data}")

        return data

    def send_background(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        to_name: Optional[str] = None,
    ) -> None:
        if not self.background_tasks:
            raise RuntimeError("BackgroundTasks was not initialized in BrevoMailer.")
        
        self.background_tasks.add_task(
            self.send,
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            to_name=to_name,
        )


def get_mailer(background_tasks: BackgroundTasks) -> BrevoMailer:
    return BrevoMailer(background_tasks)