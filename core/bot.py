from pyrogram import Client
from config.settings import settings

bot = Client(
    "bot",
    bot_token=settings.BOT_TOKEN,
    api_id=settings.API_ID,
    api_hash=settings.API_HASH
)