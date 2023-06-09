from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config.config import get_config_value

# Initialize bot and dispatcher
bot = Bot(get_config_value('bot', 'token'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
