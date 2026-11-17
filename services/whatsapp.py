
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:

    def __init__(self):
        self.client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return (
            f"https://graph.facebook.com/"
            f"{settings.whatsapp_api_version}"
        )

    @property
    def messages_url(self) -> str:
        return (
            f"{self.base_url}/"
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

    async def start(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=20,
                ),
            )

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _post(
        self,
        url: str,
        payload: dict,
    ) -> dict:

        if self.client is None:
            raise RuntimeError("WhatsApp client is not initialized")

        try:
            response = await self.client.post(
                url,
                headers=self.headers,
                json=payload,
            )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API error: status=%s response=%s",
                exc.response.status_code,
                exc.response.text,
            )
            raise

        except httpx.RequestError:
            logger.exception("WhatsApp API connection failed")
            raise

    async def send_message(
        self,
        to: str,
        message_type: str,
        content: dict,
    ) -> dict:

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": message_type,
            message_type: content,
        }

        return await self._post(
            self.messages_url,
            payload,
        )



    @property
    def calls_url(self) -> str:
        return (
            f"{self.base_url}/"
            f"{settings.whatsapp_phone_number_id}/calls"
        )

    async def call_action(
        self,
        action: str,
        call_id: str | None = None,
        to: str | None = None,
        session: dict | None = None,
        callback_data: str | None = None,
    ) -> dict:

        allowed_actions = {
            "connect",
            "pre_accept",
            "accept",
            "reject",
            "terminate",
        }

        if action not in allowed_actions:
            raise ValueError("Invalid WhatsApp call action")

        payload = {
            "messaging_product": "whatsapp",
            "action": action,
        }

        if to:
            payload["to"] = to

        if call_id:
            payload["call_id"] = call_id

        if session:
            payload["session"] = session

        if callback_data:
            payload["biz_opaque_callback_data"] = callback_data

        return await self._post(
            self.calls_url,
            payload,
        )

    async def accept_call(
        self,
        call_id: str,
        sdp_answer: str,
    ) -> dict:

        return await self.call_action(
            action="accept",
            call_id=call_id,
            session={
                "sdp_type": "answer",
                "sdp": sdp_answer,
            },
        )

    async def reject_call(
        self,
        call_id: str,
    ) -> dict:

        return await self.call_action(
            action="reject",
            call_id=call_id,
        )

    async def terminate_call(
        self,
        call_id: str,
    ) -> dict:

        return await self.call_action(
            action="terminate",
            call_id=call_id,
        )

    async def handle_call_event(
        self,
        call: dict,
    ) -> None:

        event = call.get("event")
        call_id = call.get("id")
        direction = call.get("direction")

        logger.info(
            "WhatsApp call event: id=%s event=%s direction=%s",
            call_id,
            event,
            direction,
        )

        if event == "connect":

            session = call.get("session", {})

            sdp = session.get("sdp")
            sdp_type = session.get("sdp_type")

            logger.info(
                "Call connection request: id=%s sdp_type=%s",
                call_id,
                sdp_type,
            )

            # Pass the SDP offer to your WebRTC/SIP layer.
            # Do not simply echo the offer as an answer.

        elif event == "terminate":

            logger.info(
                "WhatsApp call terminated: id=%s",
                call_id,
            )

    async def handle_call_status(
        self,
        status: dict,
    ) -> None:

        logger.info(
            "WhatsApp call status: id=%s status=%s",
            status.get("id"),
            status.get("status"),
        )

        if status.get("status") == "REJECTED":
            logger.info("Customer rejected the call")

        elif status.get("status") == "ACCEPTED":
            logger.info("Customer accepted the call")

        elif status.get("status") == "RINGING":
            logger.info("Customer's device is ringing")




    # ---------------------------
    # Text
    # ---------------------------

    async def send_text_message(
        self,
        to: str,
        message: str,
    ) -> dict:

        return await self.send_message(
            to=to,
            message_type="text",
            content={
                "preview_url": False,
                "body": message,
            },
        )

    # ---------------------------
    # Template
    # ---------------------------

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language: str = "en_US",
        components: list | None = None,
    ) -> dict:

        template = {
            "name": template_name,
            "language": {"code": language},
        }

        if components:
            template["components"] = components

        return await self.send_message(
            to=to,
            message_type="template",
            content=template,
        )

    # ---------------------------
    # Image
    # ---------------------------

    async def send_image(
        self,
        to: str,
        media_id: str,
        caption: str | None = None,
    ) -> dict:

        content = {"id": media_id}

        if caption:
            content["caption"] = caption

        return await self.send_message(
            to=to,
            message_type="image",
            content=content,
        )

    # ---------------------------
    # Document
    # ---------------------------

    async def send_document(
        self,
        to: str,
        media_id: str,
        filename: str | None = None,
        caption: str | None = None,
    ) -> dict:

        content = {"id": media_id}

        if filename:
            content["filename"] = filename

        if caption:
            content["caption"] = caption

        return await self.send_message(
            to=to,
            message_type="document",
            content=content,
        )

    # ---------------------------
    # Interactive messages
    # ---------------------------

    async def send_interactive(
        self,
        to: str,
        interactive: dict,
    ) -> dict:

        return await self.send_message(
            to=to,
            message_type="interactive",
            content=interactive,
        )

    # ---------------------------
    # Reactions
    # ---------------------------

    async def send_reaction(
        self,
        to: str,
        message_id: str,
        emoji: str,
    ) -> dict:

        return await self.send_message(
            to=to,
            message_type="reaction",
            content={
                "message_id": message_id,
                "emoji": emoji,
            },
        )

    # ---------------------------
    # Mark as read
    # ---------------------------

    async def mark_as_read(
        self,
        message_id: str,
    ) -> dict:

        return await self._post(
            self.messages_url,
            {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
        )

    # ---------------------------
    # Incoming message handling
    # ---------------------------

    async def handle_received_message(
        self,
        message: dict,
    ) -> None:

        message_type = message.get("type")

        if message_type == "text":
            text = message.get("text", {}).get("body")

            logger.info(
                "Received text message: sender=%s message_id=%s",
                message.get("from"),
                message.get("id"),
            )

            logger.debug("Message body: %s", text)

        else:
            logger.info(
                "Received WhatsApp message: type=%s id=%s",
                message_type,
                message.get("id"),
            )

    async def handle_message_status(
        self,
        status: dict,
    ) -> None:

        logger.info(
            "WhatsApp status update: id=%s status=%s recipient=%s",
            status.get("id"),
            status.get("status"),
            status.get("recipient_id"),
        )

        if status.get("status") == "failed":
            logger.error(
                "WhatsApp message delivery failed: %s",
                status.get("errors"),
            )


whatsapp_service = WhatsAppService()
