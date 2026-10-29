from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    PROJECT_NAME: str = 'Cargo Flow API'
    SECRET_KEY: str = 'change-me'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = 'postgresql+psycopg://user:password@localhost:5432/cargo_flow'

    STAFF_EMAIL_DOMAINS: set[str] = {'cargoflowafrica.co.za'}

    BREVO_API_KEY: str = ''

    UPLOAD_DIR: str = '/data/uploads'
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    ALLOWED_UPLOAD_TYPES: dict[str, list[str]] = {
        'application/pdf': ['.pdf'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
    }

    ENVIRONMENT: str = 'production'
    SKIP_OTP: bool = False

    # Comma-separated browser origins allowed to call the API
    CORS_ORIGINS: str = 'http://localhost:3000'


settings = Settings()

