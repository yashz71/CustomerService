from fastapi import FastAPI

from routes.whatsapp import router as whatsapp_router


app = FastAPI(
    title="WhatsApp Cloud API",
    version="1.0.0",
)


app.include_router(
    whatsapp_router
)


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "WhatsApp Cloud API",
    }