from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str

    meta_app_secret: str

    whatsapp_api_version: str = "v25.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()