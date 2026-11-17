from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
import ngrok

from routes.whatsapp import send_router 
from routes.whatsapp import webhook_router 

from services.whatsapp import whatsapp_service
from livekit.agents import AgentSession
from livekit.plugins import langchain
from services.livekit_whatsapp import livekit_whatsapp
#langchain.LLMAdapter(graph=create_graph(), stream_mode=["messages", "custom"])




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

    await whatsapp_service.start()
    await livekit_whatsapp.initialize()


    try:
        yield

    finally:
        await livekit_whatsapp.close()
        await whatsapp_service.close()



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