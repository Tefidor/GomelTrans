import asyncio
from aiogram import executor
from create_bot import dp
from data_base.mysql_db import init_db
from handlers import client
from config.config import get_config_value
from aiogram.types import ParseMode
import logging


client.register_handlers_client(dp)


async def send_message_to_admin(text: str):
    await dp.bot.send_message(chat_id=get_config_value('bot', 'admin_id'), text=text, parse_mode=ParseMode.HTML)


async def on_startup(dp):
    try:
        await init_db()
        await send_message_to_admin("Бот запущен!")
        print("Бот запущен!")
    except Exception as e:
        logging.exception("Ошибка при запуске бота:")
        await send_message_to_admin(f"Ошибка при запуске бота: <pre>{e}</pre>")


async def on_shutdown(dp):
    try:
        await send_message_to_admin("Бот выключен!")
        print("Бот выключен!")
    except Exception as e:
        logging.exception("Ошибка при остановке бота:")
        await send_message_to_admin(f"Ошибка при остановке бота: <pre>{e}</pre>")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    executor.start_polling(
        dispatcher=dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
