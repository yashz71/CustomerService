from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str

    meta_app_secret: str
    BASE_URL: str
    MCP_SERVER_URL_ROBIN: str
    API_KEY: str
    whatsapp_api_version: str = "26.0"
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    livekit_agent_name: str = "robin"
    NEON_DATABASE_URL: str
    LANGSMITH_TRACING: str 
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str
    LANGSMITH_AGENT_ID: str
    LANGSMITH_AGENT_ENVIRONMENT: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_TRANSCRIPTION_MODEL: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()