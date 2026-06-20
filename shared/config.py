from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    nats_url: str = "nats://localhost:4222"

    # Transport: "nats" (default) or "kafka"
    transport: str = "nats"
    kafka_bootstrap_servers: str = "kafka:9092"

    # Postgres — optional persistence layer
    # Set DATABASE_URL to enable; leave empty to skip (in-memory only)
    database_url: str = ""

    # Detection model — leave empty to use StubBackend
    detection_model_path: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
