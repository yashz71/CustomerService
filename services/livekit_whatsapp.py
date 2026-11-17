
import logging

from dotenv import load_dotenv

# Load environment variables before importing settings.
load_dotenv(override=True)

from livekit import api
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.rtc import SessionDescription

from config import settings

logger = logging.getLogger(__name__)


class LiveKitWhatsAppService:

    def __init__(self):
        self.client: api.LiveKitAPI | None = None

    async def initialize(self):
        if self.client is None:
            self.client = api.LiveKitAPI()
            logger.info("LiveKit Cloud API client initialized")

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None
            logger.info("LiveKit Cloud API client closed")

    def _agent_dispatch(self):
        return [
            RoomAgentDispatch(
                agent_name=settings.livekit_agent_name
            )
        ]

    async def accept_incoming_call(
        self,
        call_id: str,
        sdp: str,
    ):
        request = api.AcceptWhatsAppCallRequest(
            whatsapp_phone_number_id=settings.whatsapp_phone_number_id,
            whatsapp_api_key=settings.whatsapp_access_token,
            whatsapp_cloud_api_version=settings.whatsapp_api_version,
            whatsapp_call_id=call_id,
            sdp=SessionDescription(
                type="offer",
                sdp=sdp,
            ),
            agents=self._agent_dispatch(),
            wait_until_answered=True,
        )

        response = await self.client.connector.accept_whatsapp_call(
            request
        )

        logger.info(
            "Accepted incoming WhatsApp call %s, room=%s",
            call_id,
            response.room_name,
        )

        return response

    async def initiate_outgoing_call(
        self,
        phone_number: str,
    ):
        request = api.DialWhatsAppCallRequest(
            whatsapp_phone_number_id=settings.whatsapp_phone_number_id,
            whatsapp_to_phone_number=phone_number,
            whatsapp_api_key=settings.whatsapp_access_token,
            whatsapp_cloud_api_version=settings.whatsapp_api_version,
            agents=self._agent_dispatch(),
        )

        response = await self.client.connector.dial_whatsapp_call(
            request
        )

        logger.info(
            "Initiated outgoing call %s, room=%s",
            response.whatsapp_call_id,
            response.room_name,
        )

        return response

    async def connect_outgoing_call(
        self,
        call_id: str,
        sdp: str,
    ):
        request = api.ConnectWhatsAppCallRequest(
            whatsapp_call_id=call_id,
            sdp=SessionDescription(
                type="answer",
                sdp=sdp,
            ),
        )

        response = await self.client.connector.connect_whatsapp_call(
            request
        )

        logger.info(
            "Connected outgoing WhatsApp call: %s",
            call_id,
        )

        return response

    async def disconnect_call(
        self,
        call_id: str,
        user_initiated: bool = True,
    ):
        reason = (
            api.DisconnectWhatsAppCallRequest.USER_INITIATED
            if user_initiated
            else api.DisconnectWhatsAppCallRequest.BUSINESS_INITIATED
        )

        request_args = {
            "whatsapp_call_id": call_id,
            "disconnect_reason": reason,
        }

        if not user_initiated:
            request_args["whatsapp_api_key"] = (
                settings.whatsapp_access_token
            )

        request = api.DisconnectWhatsAppCallRequest(
            **request_args
        )

        response = await self.client.connector.disconnect_whatsapp_call(
            request
        )

        logger.info(
            "Disconnected WhatsApp call: %s",
            call_id,
        )

        return response


livekit_whatsapp = LiveKitWhatsAppService()
