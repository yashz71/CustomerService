
import logging

from livekit import api
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.rtc import SessionDescription

from config import settings

logger = logging.getLogger(__name__)


class LiveKitCallingService:

    def __init__(self):
        self.client: api.LiveKitAPI | None = None

    async def start(self):
        if self.client is None:
            self.client = api.LiveKitAPI(
                url=settings.livekit_url,
                api_key=settings.livekit_api_key,
                api_secret=settings.livekit_api_secret,
            )

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _get_client(self) -> api.LiveKitAPI:
        if self.client is None:
            raise RuntimeError(
                "LiveKit client has not been initialized"
            )
        return self.client

    async def accept_incoming_call(
        self,
        call: dict,
    ) -> dict:

        client = self._get_client()

        call_id = call.get("id")
        session = call.get("session") or {}

        sdp_type = session.get("sdp_type")
        sdp_offer = session.get("sdp")

        if not call_id or not sdp_offer:
            raise ValueError(
                "Incoming call is missing call ID or SDP offer"
            )

        if sdp_type != "offer":
            raise ValueError(
                f"Expected SDP offer, received {sdp_type}"
            )

        room_name = f"whatsapp-{call_id.replace('.', '-')}"

        logger.info(
            "Accepting WhatsApp call: call_id=%s room=%s",
            call_id,
            room_name,
        )

        response = await client.connector.accept_whatsapp_call(
            api.AcceptWhatsAppCallRequest(
                whatsapp_phone_number_id=(
                    settings.whatsapp_phone_number_id
                ),
                whatsapp_api_key=(
                    settings.whatsapp_access_token
                ),
                whatsapp_cloud_api_version=(
                    settings.whatsapp_api_version
                ),
                whatsapp_call_id=call_id,
                sdp=SessionDescription(
                    type="offer",
                    sdp=sdp_offer,
                ),
                room_name=room_name,
                agents=[
                    RoomAgentDispatch(
                        agent_name="whatsapp-agent"
                    )
                ],
                wait_until_answered=True,
            )
        )

        logger.info(
            "WhatsApp call accepted: call_id=%s room=%s",
            call_id,
            response.room_name,
        )

        return {
            "call_id": call_id,
            "room_name": response.room_name,
        }

    async def disconnect_user_call(
        self,
        call_id: str,
    ) -> None:

        client = self._get_client()

        await client.connector.disconnect_whatsapp_call(
            api.DisconnectWhatsAppCallRequest(
                whatsapp_call_id=call_id,
                disconnect_reason=(
                    api.DisconnectWhatsAppCallRequest.USER_INITIATED
                ),
            )
        )

        logger.info(
            "LiveKit WhatsApp session disconnected: %s",
            call_id,
        )


livekit_calling_service = LiveKitCallingService()
