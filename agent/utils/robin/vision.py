
import asyncio
import base64
import logging
from io import BytesIO

from livekit import rtc
from livekit.agents.utils.images import (
    encode,
    EncodeOptions,
    ResizeOptions,
)

logger = logging.getLogger("robin-vision")


class RobinVision:
    def __init__(self):
        self.latest_frame_url = None
        self._stream = None
        self._task = None
        self.frame_count = 0

    async def attach(self, track: rtc.Track):
        await self.stop()

        logger.info(
            "Creating VideoStream: track_id=%s kind=%s",
            track.sid,
            track.kind,
        )

        self._stream = rtc.VideoStream(
            track,
            format=rtc.VideoBufferType.RGB24,
        )

        self._task = asyncio.create_task(
            self._read_frames()
        )

        logger.info("Video reader task started")

    async def _read_frames(self):
        logger.info("VIDEO READER ENTERED")

        try:
            async for event in self._stream:
                self.frame_count += 1
                frame = event.frame

                if self.frame_count % 30 == 0:
                    logger.info(
                        "VIDEO FRAME | count=%s | size=%sx%s",
                        self.frame_count,
                        frame.width,
                        frame.height,
                    )

                try:
                    image_bytes = encode(
                        frame,
                        EncodeOptions(
                            format="JPEG",
                            quality=75,
                            resize_options=ResizeOptions(
                                width=768,
                                height=768,
                                strategy="scale_aspect_fit",
                            ),
                        ),
                    )

                    encoded = base64.b64encode(image_bytes).decode("utf-8")

                    self.latest_frame_url = (
                        f"data:image/jpeg;base64,{encoded}"
                    )

                except Exception:
                    logger.exception("Frame conversion failed")

            logger.warning(
                "VIDEO STREAM ENDED NORMALLY | frames=%s",
                self.frame_count,
            )

        except asyncio.CancelledError:
            logger.warning(
                "VIDEO READER CANCELLED | frames=%s",
                self.frame_count,
            )
            raise

        except Exception:
            logger.exception(
                "VIDEO READER EXCEPTION | frames=%s",
                self.frame_count,
            )

        finally:
            logger.warning(
                "VIDEO READER EXITED | frames=%s",
                self.frame_count,
            )
    async def stop(self):
        logger.warning(
            "VISION STOP CALLED | frames=%s",
            self.frame_count,
        )

        if self._task:
            logger.warning("Cancelling video reader task")

            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

            self._task = None

        if self._stream:
            await self._stream.aclose()
            self._stream = None

        self.latest_frame_url = None
        self.frame_count = 0

        logger.warning("VISION STOP COMPLETED")