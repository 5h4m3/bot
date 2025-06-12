import sqlite3
from datetime import datetime
from config.settings import settings

def log_to_db(user_id, action, status):
    conn = sqlite3.connect(settings.DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (user_id, action, timestamp, status) VALUES (?, ?, ?, ?)",
        (user_id, action, datetime.now(), status)
    )
    conn.commit()
    conn.close()
    
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Таблица для ключей доступа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_keys (
                key TEXT PRIMARY KEY,
                created_by INTEGER,
                used_by INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT NULL
            )
        ''')
        
        # Таблица для пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                api_id INTEGER,
                api_hash TEXT,
                is_active INTEGER DEFAULT 0,
                session_file TEXT
            )
        ''')
        
        # Создаем таблицу для логов, если её нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        ''')
        
        conn.commit()
    except Exception as e:
        logging.critical(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        conn.close()
        
async def get_user_settings(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT phone, api_id, api_hash, is_active, session_file FROM users WHERE user_id=?', (user_id,))
        result = cursor.fetchone()
        return result if result else (None, None, None, 0, None)
    except Exception as e:
        logging.error(f"Ошибка получения настроек: {e}")
        return (None, None, None, 0, None)
    finally:
        conn.close()
        
async def save_user_settings(user_id, **kwargs):
    current = await get_user_settings(user_id)
    updates = {
        'phone': kwargs.get('phone', current[0]),
        'api_id': kwargs.get('api_id', current[1]),
        'api_hash': kwargs.get('api_hash', current[2]),
        'is_active': kwargs.get('is_active', current[3]),
        'session_file': kwargs.get('session_file', current[4])
    }
    
    conn = sqlite3.connect(settings.DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO users 
                    (user_id, phone, api_id, api_hash, is_active, session_file)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, *updates.values()))
    conn.commit()
    conn.close()
    
async def check_user_access(user_id):
    """Проверяет, действителен ли ключ пользователя"""
    conn = sqlite3.connect(settings.DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        SELECT expires_at FROM access_keys 
        WHERE used_by = ? AND (expires_at IS NULL OR expires_at > ?)
    ''', (user_id, now))
    result = cursor.fetchone()
    conn.close()
    return result is not None

async def validate_access_key(key, user_id):
    """Проверяет и активирует ключ доступа"""
    conn = sqlite3.connect(settings.DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        SELECT * FROM access_keys 
        WHERE key=? AND used_by IS NULL AND (expires_at IS NULL OR expires_at > ?)
    ''', (key, now))
    result = cursor.fetchone()
    
    if result:
        cursor.execute('UPDATE access_keys SET used_by=? WHERE key=?', (user_id, key))
        conn.commit()
    conn.close()
    return bool(result)
        
def update_db_structure():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Проверяем существование колонки expires_at в access_keys
    cursor.execute("PRAGMA table_info(access_keys)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'expires_at' not in columns:
        try:
            cursor.execute('ALTER TABLE access_keys ADD COLUMN expires_at TIMESTAMP DEFAULT NULL')
            conn.commit()
            print("✅ База данных успешно обновлена (добавлен expires_at)")
        except Exception as e:
            print(f"❌ Ошибка обновления базы: {e}")
    
    # Можно добавить аналогичные проверки для таблицы users
    cursor.execute("PRAGMA table_info(users)")
    users_columns = [column[1] for column in cursor.fetchall()]
    
    # Пример проверки для возможного нового поля в users
    if 'new_field' not in users_columns:
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN new_field TEXT DEFAULT NULL')
            conn.commit()
            print("✅ Добавлено новое поле в таблицу users")
        except Exception as e:
            print(f"❌ Ошибка обновления таблицы users: {e}")
    
    conn.close()

async def generate_access_key(client, user_id, duration=None):
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