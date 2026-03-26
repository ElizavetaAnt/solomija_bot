import asyncio
import logging
import sys
from datetime import date

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db, get_session
from init_data import populate_initial_data
from scheduler import scheduler, set_bot, setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

bot_instance: Bot = None


async def on_startup(bot: Bot) -> None:
    global bot_instance
    bot_instance = bot

    logger.info("Initializing database...")
    await init_db()

    logger.info("Populating initial data...")
    async with get_session() as session:
        await populate_initial_data(session)

    logger.info("Creating today's task completions...")
    from scheduler import create_day_completions
    async with get_session() as session:
        today = date.today()
        count = await create_day_completions(session, today)
        logger.info(f"Created {count} completions for today ({today})")

    logger.info("Starting scheduler...")
    try:
        morning_parts = settings.MORNING_TIME.split(":")
        morning_hour = int(morning_parts[0])
        morning_minute = int(morning_parts[1]) if len(morning_parts) > 1 else 0
    except (ValueError, IndexError):
        morning_hour, morning_minute = 7, 30

    set_bot(bot)
    setup_scheduler(morning_hour, morning_minute)
    scheduler.start()
    logger.info("Scheduler started.")

    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username}")


async def on_shutdown(bot: Bot) -> None:
    logger.info("Shutting down...")
    if scheduler.running:
        scheduler.shutdown()
    logger.info("Scheduler stopped.")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    from handlers.common import router as common_router
    from handlers.child import router as child_router
    from handlers.parent import router as parent_router

    dp.include_router(common_router)
    dp.include_router(child_router)
    dp.include_router(parent_router)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
