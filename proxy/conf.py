from typing import List, NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROXY_")
    OBJECT_STORE_HOST: str = "minio"
    OBJECT_STORE_PORT: int = 9000
    OBJECT_STORE_SSL_ENABLED: bool = True
    SECRET: str
    LOG_LEVEL: str = "info"
    ENVIRONMENT: str = "development"
    DEBUG_SESSION: bool = False
    ALLOWED_METHODS: List[str] = [
        "GET",
        "PUT",
        "DELETE",
        "POST",
        "OPTIONS",
        "HEAD",
        "PATCH",
    ]

    @property
    def request_methods(self):
        return NamedTuple(
            "RequestMethods",
            **{m.lower(): str for m in set(self.ALLOWED_METHODS)},
        )(*[m.lower() for m in set(self.ALLOWED_METHODS)])


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
