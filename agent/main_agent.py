import logging
import textwrap

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, inference
from livekit.plugins import langchain

from utils.robin.workflow import build_robin
from startup.mcp_robin import initialize_mcp_robin

logger = logging.getLogger("robin-voice")

server = AgentServer()


class RobinAssistant(Agent):
    def __init__(self, graph):
        super().__init__(
            instructions=(
                "You are Robin, a helpful AI voice assistant. "
                "Answer the user's questions clearly and naturally. "
                "Use the available tools when necessary."
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

    try:
        workflow = build_robin(mcp_robin["tool_node"])
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

        await session.start(
            agent=RobinAssistant(graph),
            room=ctx.room,
        )

        await ctx.connect()

        await session.generate_reply(
            instructions="Greet the caller and ask how you can help."
        )

    finally:
        # Close MCP resources using the cleanup method exposed
        # by your initialize_mcp_robin() implementation.
        pass


if __name__ == "__main__":
    agents.cli.run_app(server)