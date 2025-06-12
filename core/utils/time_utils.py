import ntplib
from datetime import datetime
from config.constants import constants
import sqlite3
sqlite3.register_adapter(datetime, adapt_datetime)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def get_current_time():
    return datetime.now(constants.MOSCOW_TZ)
   
def sync_ntp_time():
    try:
        c = ntplib.NTPClient()
        response = c.request('pool.ntp.org')
        return datetime.utcfromtimestamp(response.tx_time)
    except:
        return None

def adapt_datetime(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")
    
def format_wait_time(seconds):
    """Форматирует время ожидания в читаемый вид (минуты/часы)"""
    if seconds < 60:
        return f"{seconds} секунд"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} минут"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours} часов {minutes} минут"
        return f"{hours} часов"
        
