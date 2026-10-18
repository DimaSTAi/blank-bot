"""Запуск бота для MAX (max.ru) на библиотеке maxo."""
import asyncio
import logging

from maxo import Bot, Dispatcher

from app.config import MAX_BOT_TOKEN
from app.handlers.max_handlers import router as max_router

logger = logging.getLogger(__name__)


async def run_max_bot_if_configured() -> None:
    """Стартует MAX-бота, если задан MAX_BOT_TOKEN. Иначе молча пропускает."""
    if not MAX_BOT_TOKEN:
        logger.info("MAX_BOT_TOKEN не задан — бот для MAX не запускается (работает только Telegram)")
        return

    dp = Dispatcher()
    dp.include_router(max_router)

    while True:
        bot = Bot(MAX_BOT_TOKEN)
        try:
            await dp.start_polling(bot)
            return
        except Exception:
            logger.exception("MAX-бот упал, перезапуск через 5 секунд")
            await asyncio.sleep(5)