
import asyncio
import logging

from livekit import agents, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    inference,
)
from livekit.plugins import langchain

from utils.robin.workflow import build_robin
from utils.robin.vision import RobinVision
from startup.mcp_robin import initialize_mcp_robin
from utils.nami.workflow import build_nami
from utils.workflow import build_workflow

logger = logging.getLogger("robin-voice")

server = AgentServer()


class RobinAssistant(Agent):
    def __init__(self, graph):
        super().__init__(
            instructions=(
                "You are Robin, a helpful AI voice assistant. "
                "You can also see the user's live camera when a frame "
                "is available. Use visual information when relevant. "
                "Never claim to see something that is not visible "
                "in the provided frame. "
                "Answer clearly and naturally."
            ),
            llm=langchain.LLMAdapter(
                graph=graph,
                stream_mode="messages",
            ),
        )

@server.rtc_session(agent_name="robin")
async def robin_voice_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    mcp_robin = await initialize_mcp_robin()
    vision = RobinVision()

    # Stop vision only when the LiveKit job is shutting down
    ctx.add_shutdown_callback(vision.stop)
    nami = build_nami(vision)

    robin = build_robin(mcp_robin["tool_node"], vision)
    
    workflow = build_workflow(
        robin=robin,
        nami=nami,
        vision=vision,
    )

    graph = workflow.compile()

    session = AgentSession(
        stt=inference.STT(
            model="assemblyai/universal-3-6-pro",
            language="en",
        ),
        tts=inference.TTS(
            model="inworld/inworld-tts-2",
            voice="Olivia",
            language="en",
        ),
    )

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            logger.info(
                "Camera track subscribed: participant=%s",
                participant.identity,
            )
            asyncio.create_task(vision.attach(track))

    await session.start(
        agent=RobinAssistant(graph),
        room=ctx.room,
    )

    await ctx.connect()

    await session.generate_reply(
        instructions="Greet the caller and ask how you can help."
    )

    

if __name__ == "__main__":
    agents.cli.run_app(server)
