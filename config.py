from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    CHILD_USER_ID: int = Field(0, description="Telegram ID ребёнка")
    PARENT_MOM_USER_ID: int = Field(0, description="Telegram ID мамы")
    PARENT_DAD_USER_ID: int = Field(0, description="Telegram ID папы")
    PARENT_CODE: str = Field("family2024", description="Код для регистрации родителя")
    DATABASE_URL: str = Field(
        "sqlite+aiosqlite:///solomiya_bot.db",
        description="URL базы данных"
    )
    MORNING_TIME: str = Field("07:30", description="Время утреннего уведомления")

    @property
    def parent_ids(self) -> list[int]:
        ids = []
        if self.PARENT_MOM_USER_ID:
            ids.append(self.PARENT_MOM_USER_ID)
        if self.PARENT_DAD_USER_ID:
            ids.append(self.PARENT_DAD_USER_ID)
        return ids


settings = Settings()
