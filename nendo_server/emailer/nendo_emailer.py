# -*- encoding: utf-8 -*-
"""Basic emailer using Mailgun."""
import logging

import requests
from config import Settings


class NendoEmailer:
    """Simple Nendo emailer based on Mailgun."""

    def __init__(self, logger: logging.Logger, settings: Settings):
        """Init."""
        self.client = None
        self.logger = logger
        self.logger.info("Initializing the emailer")
        self.settings = settings

    def send_email(self, to_email: str, subject: str, body: str):
        """Send email."""
        return requests.post(
            "https://api.mailgun.net/v3/mg.nendo.ai/messages",
            auth=("api", self.settings.mailgun_api_key),
            data={
                "from": f"Nendo support <{self.settings.email_from_address}>",
                "to": to_email,
                "subject": subject,
                "text": body,
            },
            timeout=120,
        )
