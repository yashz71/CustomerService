
import logging

import httpx
from typing import Any

from langchain_core.messages import HumanMessage
from config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:

    @staticmethod
    def fresh_turn_state(user_message: HumanMessage) -> dict:
        """
        Initialize the state expected by the existing Robin workflow.
        """
        return {
            "messages": [user_message],
            "plan": None,
            "parallel": True,
            "reasoning": None,
            "supervisor_instruction": None,
            "accounting_answer": None,
            "tax_answer": None,
            "general_answer": None,
            "download_url": None,
        }

    @staticmethod
    def extract_agent_response(result: dict) -> str:
        """
        Extract the final response from the LangGraph result.
        Supports both string and structured message content.
        """
        messages = result.get("messages", [])

        if not messages:
            return ""

        final_message = messages[-1]
        answer = getattr(final_message, "content", "")

        if isinstance(answer, str):
            return answer.strip()

        if isinstance(answer, list):
            text_parts = [
                block["text"]
                for block in answer
                if isinstance(block, dict)
                and block.get("type") == "text"
                and block.get("text")
            ]

            return "\n".join(text_parts).strip()

        return str(answer).strip() if answer else ""

    async def run_agent(
        self,
        agent_app: Any,
        sender_id: str,
        message_text: str,
    ) -> str:
        """
        Invoke the existing Robin LangGraph application.

        Each WhatsApp user gets a persistent LangGraph thread.
        """
        if agent_app is None:
            raise RuntimeError("LangGraph agent is not initialized.")

        thread_id = f"whatsapp:{sender_id}"

        user_message = HumanMessage(
            content=message_text.strip()
        )

        input_state = self.fresh_turn_state(user_message)

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        logger.info(
            "Invoking Robin agent: sender=%s thread=%s",
            sender_id,
            thread_id,
        )

        result = await agent_app.ainvoke(
            input_state,
            config=config,
        )

        answer = self.extract_agent_response(result)

        if not answer:
            logger.warning(
                "Robin agent returned an empty response: sender=%s",
                sender_id,
            )
            return (
                "I couldn't generate a response. "
                "Please try again."
            )

        logger.info(
            "Robin agent response generated: sender=%s length=%s",
            sender_id,
            len(answer),
        )

        return answer

    async def handle_received_message(
        self,
        message: dict,
        agent_app: Any,
    ) -> None:
        """
        Process an incoming WhatsApp text message,
        invoke Robin, and send the response back.
        """
        message_type = message.get("type")
        sender_id = message.get("from")
        message_id = message.get("id")

        if not sender_id:
            logger.warning(
                "Ignoring WhatsApp message without sender ID."
            )
            return

        if message_type != "text":
            logger.info(
                "Unsupported WhatsApp message type: "
                "sender=%s type=%s",
                sender_id,
                message_type,
            )

            await self.send_text_message(
                sender_id,
                "Currently, I can process text messages. "
                "Please send your request as text.",
            )
            return

        message_text = (
            message.get("text", {}).get("body", "")
        ).strip()

        if not message_text:
            logger.warning(
                "Ignoring empty WhatsApp message: sender=%s",
                sender_id,
            )
            return

        logger.info(
            "Processing WhatsApp message: "
            "sender=%s message_id=%s",
            sender_id,
            message_id,
        )

        # Mark the incoming message as read.
        if message_id:
            try:
                await self.mark_as_read(message_id)
            except Exception:
                logger.exception(
                    "Could not mark WhatsApp message as read: "
                    "message_id=%s",
                    message_id,
                )

        try:
            # 1. Invoke Robin.
            response = await self.run_agent(
                agent_app=agent_app,
                sender_id=sender_id,
                message_text=message_text,
            )

            # 2. Send the agent response to WhatsApp.
            await self.send_text_message(
                to=sender_id,
                message=response,
            )

            logger.info(
                "Agent response successfully submitted to WhatsApp: "
                "sender=%s",
                sender_id,
            )

        except Exception:
            logger.exception(
                "WhatsApp agent processing failed: sender=%s",
                sender_id,
            )

            try:
                await self.send_text_message(
                    sender_id,
                    "Sorry, I encountered an error while "
                    "processing your request. Please try again.",
                )
            except Exception:
                logger.exception(
                    "Failed to send WhatsApp error response: "
                    "sender=%s",
                    sender_id,
                )


    def __init__(self):
        self.client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return (
            f"https://graph.facebook.com/"
            f"v27.0"
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
    agent_app,
) -> None:

        message_type = message.get("type")
        sender_id = message.get("from")
        message_id = message.get("id")

        if message_type != "text":
            logger.info(
                "Received WhatsApp message: type=%s id=%s",
                message_type,
                message_id,
            )
            return

        text = message.get("text", {}).get("body", "").strip()

        logger.info(
            "Received text message: sender=%s message_id=%s",
            sender_id,
            message_id,
        )

        if not sender_id or not text:
            logger.warning("Ignoring invalid WhatsApp message.")
            return

        await self.mark_as_read(message_id)

        response = await self.run_agent(
            agent_app=agent_app,
            sender_id=sender_id,
            message_text=text,
        )

        await self.send_text_message(
            to=sender_id,
            message=response,
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
