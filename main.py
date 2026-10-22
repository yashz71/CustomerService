from fastapi import FastAPI

from routes.whatsapp import router as whatsapp_router
import ngrok


app = FastAPI(
    title="WhatsApp Cloud API",
    version="1.0.0",
)


app.include_router(
    whatsapp_router
)

def connect_ngrok():
    forwarder = ngrok.forward("localhost:8085", authtoken_from_env=True, domain="among-aged-mammogram.ngrok-free.dev")
    print(f"Available at: {forwarder.url()}")


connect_ngrok()
@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "WhatsApp Cloud API",
    }