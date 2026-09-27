import httpx

from config import settings


class WhatsAppService:

    @property
    def messages_url(self) -> str:
        return (
            f"https://graph.facebook.com/"
            f"{settings.whatsapp_api_version}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": (
                f"Bearer {settings.whatsapp_access_token}"
            ),
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self,
        to: str,
        message: str,
    ) -> dict:
        """
        Send a text message through the WhatsApp Cloud API.

        You can later expand this service with:
        - images
        - documents
        - audio
        - video
        - templates
        - interactive messages
        - reactions
        """

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.messages_url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()

        return response.json()

    async def handle_received_message(
        self,
        message: dict,
    ) -> None:
        """
        Business logic for an incoming WhatsApp message.

        TODO:
            - Extract the sender
            - Extract message type
            - Extract message content
            - Pass message to your agent
            - Generate a response
            - Call send_text_message()
        """

        pass

    async def handle_message_status(
        self,
        status: dict,
    ) -> None:
        """
        Handle WhatsApp message status updates.

        Examples:
            sent
            delivered
            read
            failed

        TODO:
            - Store status
            - Update database
            - Trigger application logic
        """

        pass


whatsapp_service = WhatsAppService()