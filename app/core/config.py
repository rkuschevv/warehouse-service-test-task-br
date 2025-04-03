from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Сервис мониторинга состояния складов"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC: str = "ru.retail.warehouses"
    DATABASE_URL: str = "sqlite:///./warehouse.db"
    
    class Config:
        env_file = ".env"

settings = Settings() 