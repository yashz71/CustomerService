import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from config import settings
from services.whatsapp import whatsapp_service


router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"],
)


def verify_signature(
    payload: bytes,
    signature: str | None,
) -> bool:
    """
    Verify Meta's X-Hub-Signature-256 header.

    Meta sends:

        X-Hub-Signature-256:
            sha256=<HMAC_SHA256_HASH>

    The HMAC is calculated using:
        - raw request body
        - Meta App Secret
    """

    if not signature:
        return False

    if not signature.startswith("sha256="):
        return False

    received_signature = signature.removeprefix("sha256=")

    expected_signature = hmac.new(
        settings.meta_app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        received_signature,
        expected_signature,
    )


@router.get(
    "",
    response_class=PlainTextResponse,
)
async def verify_webhook(
    hub_mode: str | None = None,
    hub_challenge: str | None = None,
    hub_verify_token: str | None = None,
):
    """
    Meta calls this endpoint when verifying the webhook.

    Expected:

        hub.mode=subscribe
        hub.challenge=<challenge>
        hub.verify_token=<your token>
    """

    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.whatsapp_verify_token
    ):
        return hub_challenge

    raise HTTPException(
        status_code=403,
        detail="Webhook verification failed",
    )


@router.post("")
async def receive_webhook(request: Request):
    """
    Receive webhook events from Meta.
    """

    # IMPORTANT:
    # Read the raw bytes BEFORE parsing JSON.
    body = await request.body()

    signature = request.headers.get(
        "X-Hub-Signature-256"
    )

    # Verify Meta's signature
    if not verify_signature(
        payload=body,
        signature=signature,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    payload = await request.json()

    await process_webhook(payload)

    return {
        "status": "ok",
    }


async def process_webhook(
    payload: dict,
) -> None:
    """
    Process a WhatsApp webhook payload.
    """

    if payload.get("object") != "whatsapp_business_account":
        return

    entries = payload.get("entry", [])

    for entry in entries:

        changes = entry.get("changes", [])

        for change in changes:

            value = change.get("value", {})

            # ---------------------------------
            # Incoming messages
            # ---------------------------------

            messages = value.get("messages", [])

            for message in messages:

                await whatsapp_service.handle_received_message(
                    message
                )

            # ---------------------------------
            # Message status updates
            # ---------------------------------

            statuses = value.get("statuses", [])

            for status in statuses:

                await whatsapp_service.handle_message_status(
                    status
                )