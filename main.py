from contextlib import AsyncExitStack, asynccontextmanager
import logging
from fastapi import FastAPI
import ngrok
from services.trasnscription import create_transcription_client
from routes.whatsapp import send_router 
from routes.whatsapp import webhook_router 

from services.whatsapp import whatsapp_service
from livekit.agents import AgentSession
from livekit.plugins import langchain
from services.livekit_whatsapp import livekit_whatsapp
#langchain.LLMAdapter(graph=create_graph(), stream_mode=["messages", "custom"])

from agent.utils.robin.workflow import build_robin
from agent.startup.mcp_robin import initialize_mcp_robin
from agent.utils.config import NEON_DATABASE_URL

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver



logging.basicConfig(
level=logging.INFO,
format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def connect_ngrok():
     forwarder = ngrok.forward(
         "localhost:8085",
        authtoken_from_env=True,
        domain="among-aged-mammogram.ngrok-free.dev",
     )

     public_url = forwarder.url()
     logger.info("Ngrok tunnel available at: %s", public_url)

     return public_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:

        try:
            # 1. Initialize transcription client
            logger.info("Initializing transcription client...")

            app.state.transcription_client = create_transcription_client()

            # Register cleanup immediately, including if later startup steps fail.
            stack.push_async_callback(app.state.transcription_client.close)

            logger.info("Transcription client initialized.")

            # 2. Initialize MCP
            logger.info("Initializing MCP Robin...")
            mcp_robin = await initialize_mcp_robin()

            logger.info("MCP Robin initialized.")

            # 3. Initialize PostgreSQL checkpointer
            if not NEON_DATABASE_URL:
                raise RuntimeError("NEON_DATABASE_URL is missing.")

            langgraph_db_url = NEON_DATABASE_URL.replace(
                "postgresql+psycopg://",
                "postgresql://",
            )

            logger.info("Connecting to PostgreSQL...")

            saver = await stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(langgraph_db_url)
            )

            await saver.setup()

            logger.info("PostgreSQL checkpointer initialized.")

            # 4. Build LangGraph workflow
            logger.info("Building Robin workflow...")

            workflow = build_robin(mcp_robin["tool_node"])

            app.state.agent_app = workflow.compile(
                checkpointer=saver
            )

            logger.info("LangGraph agent initialized.")

            # 5. Connect to Telegram
            logger.info("Connecting to Telegram...")
            await whatsapp_service.start()
            await livekit_whatsapp.initialize()
            
        
            yield
        except Exception:
                    logger.exception("MaintiDoc startup or runtime failed.")
                    raise
        
        finally:
            await livekit_whatsapp.close()
            await whatsapp_service.close()
            logger.info("MaintiDoc is shutting down.")


    

    



app = FastAPI(
    title="WhatsApp Cloud API",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(send_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "WhatsApp Cloud API",
    }
if __name__ == "__main__":
    import uvicorn

# Start the tunnel before the FastAPI server.
    connect_ngrok()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8085,
    )