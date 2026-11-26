import asyncio
import base64
import logging
import time
from io import BytesIO

from livekit import rtc
from PIL import Image


logger = logging.getLogger(__name__)


class RobinVision:
    def __init__(self):
        self.latest_frame_url: str | None = None
        self.latest_frame_timestamp: float | None = None

        self._stream: rtc.VideoStream | None = None
        self._task: asyncio.Task | None = None

        self.frame_count = 0

    async def attach(self, track: rtc.Track):
        """Attach to the participant's video track."""

        if self._task and not self._task.done():
            await self.stop()

        self._stream = rtc.VideoStream(
            track,
            format=rtc.VideoBufferType.RGB24,
        )

        self._task = asyncio.create_task(self._read_frames())

        logger.info("RobinVision attached to video track")

    async def _read_frames(self):
        """Read frames and encode them as JPEG data URLs."""

        try:
            async for event in self._stream:
                frame = event.frame

                self.frame_count += 1

                # Read RGB24 frame data directly using Pillow.
                image = Image.frombytes(
                    "RGB",
                    (frame.width, frame.height),
                    bytes(frame.data),
                )

                # Resize while preserving aspect ratio.
                image.thumbnail((768, 768))

                # Encode as JPEG.
                buffer = BytesIO()
                image.save(
                    buffer,
                    format="JPEG",
                    quality=75,
                    optimize=True,
                )

                image_base64 = base64.b64encode(
                    buffer.getvalue()
                ).decode("utf-8")

                self.latest_frame_url = (
                    f"data:image/jpeg;base64,{image_base64}"
                )

                self.latest_frame_timestamp = time.time()

                if self.frame_count == 1:
                    logger.info(
                        "First frame processed: %sx%s",
                        frame.width,
                        frame.height,
                    )

        except asyncio.CancelledError:
            logger.info("RobinVision frame reader cancelled")
            raise

        except Exception:
            logger.exception("Error while processing video frames")

    async def stop(self):
        """Stop reading frames and release the video stream."""

        if self._task:
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
        self.latest_frame_timestamp = None

        logger.info("RobinVision stopped")