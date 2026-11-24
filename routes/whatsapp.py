import hashlib
import hmac
import json
import logging
import time
from collections import OrderedDict
from typing import Awaitable, TypeVar

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from config import settings
from services.livekit_calling import livekit_calling_service
from services.whatsapp import whatsapp_service
from services.livekit_whatsapp import livekit_whatsapp

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Two separate routers (the original code overwrote the first one).
send_router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
webhook_router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])

# E.164 without the leading "+" (WhatsApp Cloud API format), e.g. 212612345678
PHONE_PATTERN = r"^\+?[1-9]\d{6,14}$"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    to: str = Field(pattern=PHONE_PATTERN)
    message: str = Field(min_length=1, max_length=4096)


class SendTemplateRequest(BaseModel):
    to: str = Field(pattern=PHONE_PATTERN)
    template_name: str
    language: str = "en_US"
    components: list | None = None


class SendImageRequest(BaseModel):
    to: str = Field(pattern=PHONE_PATTERN)
    media_id: str
    caption: str | None = None


class SendDocumentRequest(BaseModel):
    to: str = Field(pattern=PHONE_PATTERN)
    media_id: str
    filename: str | None = None
    caption: str | None = None


class SendReactionRequest(BaseModel):
    to: str = Field(pattern=PHONE_PATTERN)
    message_id: str
    emoji: str


# ---------------------------------------------------------------------------
# Idempotency (Meta retries webhooks). In-memory; use Redis if you run
# more than one worker.
# ---------------------------------------------------------------------------

class SeenCache:
    def __init__(self, ttl: float = 3600, max_size: int = 10_000):
        self.ttl = ttl
        self.max_size = max_size
        self._items: OrderedDict[str, float] = OrderedDict()

    def seen(self, key: str) -> bool:
        """Return True if key was already seen; otherwise record it."""
        now = time.monotonic()

        while self._items:
            oldest_key, ts = next(iter(self._items.items()))
            if now - ts > self.ttl or len(self._items) > self.max_size:
                self._items.popitem(last=False)
            else:
                break

        if key in self._items:
            return True

        self._items[key] = now
        return False


seen_events = SeenCache()


# ---------------------------------------------------------------------------
# Send routes
# ---------------------------------------------------------------------------

async def _send(coro: Awaitable[T]) -> T:
    try:
        return await coro
    except Exception as exc:
        logger.exception("WhatsApp send failed")
        raise HTTPException(502, "WhatsApp API request failed") from exc


@send_router.post("/send")
async def send_message(request: SendMessageRequest):
    response = await _send(
        whatsapp_service.send_text_message(
            to=request.to,
            message=request.message,
        )
    )
    return {"status": "sent", "response": response}


@send_router.post("/send/template")
async def send_template(request: SendTemplateRequest):
    return await _send(
        whatsapp_service.send_template_message(
            to=request.to,
            template_name=request.template_name,
            language=request.language,
            components=request.components,
        )
    )


@send_router.post("/send/image")
async def send_image(request: SendImageRequest):
    return await _send(
        whatsapp_service.send_image(
            to=request.to,
            media_id=request.media_id,
            caption=request.caption,
        )
    )


@send_router.post("/send/document")
async def send_document(request: SendDocumentRequest):
    return await _send(
        whatsapp_service.send_document(
            to=request.to,
            media_id=request.media_id,
            filename=request.filename,
            caption=request.caption,
        )
    )


@send_router.post("/send/reaction")
async def send_reaction(request: SendReactionRequest):
    return await _send(
        whatsapp_service.send_reaction(
            to=request.to,
            message_id=request.message_id,
            emoji=request.emoji,
        )
    )


def get_phone_number_id(value: dict) -> str | None:
    metadata = value.get("metadata") or {}

    return (
        metadata.get("phone_number_id")
        or settings.whatsapp_phone_number_id
    )


# ---------------------------------------------------------------------------
# Webhook: verification
# ---------------------------------------------------------------------------

def verify_signature(payload: bytes, signature: str | None) -> bool:
    """Verify Meta's X-Hub-Signature-256 header (HMAC-SHA256 of raw body)."""

    secret = settings.meta_app_secret
    if not secret:
        logger.error("meta_app_secret is empty; rejecting webhook")
        return False

    if not signature or not signature.startswith("sha256="):
        return False

    received = signature.removeprefix("sha256=")
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(received, expected)


@webhook_router.get("", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    if (
        hub_mode == "subscribe"
        and settings.whatsapp_verify_token
        and hmac.compare_digest(
            hub_verify_token or "",
            settings.whatsapp_verify_token,
        )
    ):
        return hub_challenge

    raise HTTPException(403, "Webhook verification failed")


# ---------------------------------------------------------------------------
# Webhook: event processing
# ---------------------------------------------------------------------------


async def handle_call_event(call: dict, phone_number_id: str) -> None:
    event = call.get("event")
    direction = call.get("direction")
    call_id = call.get("id")

    if not call_id:
        logger.error("Call event missing call ID: %s", call)
        return

    if event == "connect":
        session = call.get("session") or {}
        sdp = session.get("sdp")

        if not sdp:
            logger.error("Call %s has no SDP", call_id)
            return

        if direction == "USER_INITIATED":
            logger.info("Accepting incoming WhatsApp call: %s", call_id)

            response = await livekit_whatsapp.accept_incoming_call(
                call_id=call_id,
                sdp=sdp,
            )

            logger.info(
                "Incoming call accepted: %s",
                call_id,
            )

        elif direction == "BUSINESS_INITIATED":
            logger.info("Connecting outgoing WhatsApp call: %s", call_id)

            response = await livekit_whatsapp.connect_outgoing_call(
                call_id=call_id,
                sdp=sdp,
            )

            logger.info(
                "Outgoing call connected: %s",
                call_id,
            )

        else:
            logger.warning(
                "Unknown call direction %s for call %s",
                direction,
                call_id,
            )

    elif event == "terminate":
        logger.info("WhatsApp call terminated by Meta: %s", call_id)

        await livekit_whatsapp.disconnect_call(
            call_id=call_id,
            user_initiated=True,
        )

        logger.info("LiveKit call cleanup completed: %s", call_id)

    else:
        logger.info(
            "Ignoring unsupported call event %s for %s",
            event,
            call_id,
        )


async def handle_calls_change(value: dict) -> None:
    phone_number_id = get_phone_number_id(value)

    if not phone_number_id:
        logger.error("Missing WhatsApp phone number ID")
        return

    for call in value.get("calls", []):
        await _safe(
            handle_call_event(call, phone_number_id),
            f"call event {call.get('id', 'unknown')}",
        )

    for status in value.get("statuses", []):
        if status.get("type") == "call":
            await _safe(
                whatsapp_service.handle_call_status(status),
                "call status",
            )

    for error in value.get("errors", []):
        logger.error("WhatsApp Calling error: %s", error)
async def handle_messages_change(
    value: dict,
    agent_app,
) -> None:

    # Handle incoming messages
    for message in value.get("messages", []):
        msg_id = message.get("id")

        if msg_id and seen_events.seen(f"msg:{msg_id}"):
            logger.info("Duplicate message ignored: %s", msg_id)
            continue

        await _safe(
            whatsapp_service.handle_received_message(
                message=message,
                agent_app=agent_app,
            ),
            "message",
        )

    # Handle delivery/read status updates
    for status in value.get("statuses", []):
        key = f"status:{status.get('id')}:{status.get('status')}"

        if seen_events.seen(key):
            continue

        await _safe(
            whatsapp_service.handle_message_status(status),
            "status",
        )

async def _safe(coro: Awaitable[object], what: str) -> None:
    """Isolate failures so one bad item doesn't drop the rest of the batch."""
    try:
        await coro
    except Exception:
        logger.exception("Failed to process %s", what)

async def process_webhook(
    payload: dict,
    agent_app,
) -> None:

    if payload.get("object") != "whatsapp_business_account":
        return

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})

            if field == "calls":
                await _safe(
                    handle_calls_change(value),
                    "calls change",
                )

            elif field == "messages":
                await _safe(
                    handle_messages_change(
                        value=value,
                        agent_app=agent_app,
                    ),
                    "messages change",
                )

            else:
                logger.debug(
                    "Ignoring webhook field: %s",
                    field,
                )
@webhook_router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receive webhook events from Meta and acknowledge immediately."""

    body = await request.body()

    if not verify_signature(
        body,
        request.headers.get("X-Hub-Signature-256"),
    ):
        raise HTTPException(401, "Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")

    # Retrieve the already initialized LangGraph application.
    agent_app = request.app.state.agent_app

    # Process webhook asynchronously after acknowledging Meta.
    background_tasks.add_task(
        process_webhook,
        payload,
        agent_app,
    )

    return {"status": "ok"}