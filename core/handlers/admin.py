from pyrogram import filters
from core.bot import bot
from config.settings import settings
from core.utils.db import generate_access_key
        
async def is_admin(user_id):
    from config.settings import settings
    return user_id in settings.ADMIN_USER_IDS

async def send_logs_to_admin():
    from config.settings import settings
    with open("bot.log", "rb") as f:
        await bot.send_document(
            chat_id=settings.ADMIN_USER_ID,
            document=f
        )
        
@bot.on_message(filters.command("generate_key") & filters.user(settings.ADMIN_USER_IDS))
async def generate_key_handler(client, message):
    """Генерирует новый ключ доступа с возможностью указания срока действия"""
    if not await is_admin(user_id):
        return None, "Только администратор может генерировать ключи"
    
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    expires_at = None
    
    if duration:
        try:
            # Проверяем отрицательные значения
            if duration.startswith('-'):
                return None, "Время не может быть отрицательным"
            
            amount = int(duration[:-1])
            unit = duration[-1].lower()
            
            now = datetime.now()
            if unit == 'm':  # минуты
                expires_at = now + timedelta(minutes=amount)
            elif unit == 'h':  # часы
                expires_at = now + timedelta(hours=amount)
            elif unit == 'd':  # дни
                expires_at = now + timedelta(days=amount)
            elif unit == 'w':  # недели
                expires_at = now + timedelta(weeks=amount)
            elif unit == 'M':  # месяцы (30 дней)
                expires_at = now + timedelta(days=amount*30)
            else:
                return None, "Неверный формат времени. Используйте m(инуты), h(асы), d(ни), w(если) или M(есяцы)"
        except ValueError:
            return None, "Неверный формат. Пример: 30m, 2h, 1M"
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO access_keys 
            (key, created_by, expires_at) 
            VALUES (?, ?, ?)
        ''', (key, user_id, expires_at.strftime("%Y-%m-%d %H:%M:%S") if expires_at else None))
        conn.commit()
        conn.close()
        return key, None
    except Exception as e:
        return None, f"Ошибка базы данных: {str(e)}"