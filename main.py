import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import BOT_TOKEN, PROXY_URL
from app.handlers import main as handlers_main

logging.basicConfig(level=logging.INFO)


async def main():
    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else AiohttpSession()
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_main.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
