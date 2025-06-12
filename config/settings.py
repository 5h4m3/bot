from decouple import config

class Settings:
    BOT_TOKEN = config('BOT_TOKEN')
    API_ID = config('API_ID', cast=int)
    API_HASH = config('API_HASH')
    ADMIN_USER_IDS = [int(x) for x in config('ADMIN_USER_IDS', '').split(',')]
    DB_FILE = 'userbot_db.sqlite'

settings = Settings()