from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    #Databse URl ex: """sqlite:///./support.db""", """postgresql://postgres:[EMAIL_ADDRESS]/supportops"""
    database_url: SecretStr

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 20


settings = Settings()
