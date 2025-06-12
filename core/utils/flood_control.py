import time
from config.settings import settings

FLOOD_CONTROL = {}  # {user_id: {attempts: int, first_attempt: float}}

async def check_flood(user_id):
    """Проверяет, не слишком ли частые попытки входа"""
    now = time.time()
    if user_id not in FLOOD_CONTROL:
        FLOOD_CONTROL[user_id] = {'attempts': 1, 'first_attempt': now}
        return False
    
    if now - FLOOD_CONTROL[user_id]['first_attempt'] > settings.ATTEMPT_WINDOW:
        FLOOD_CONTROL[user_id] = {'attempts': 1, 'first_attempt': now}
        return False
    
    FLOOD_CONTROL[user_id]['attempts'] += 1
    
    if FLOOD_CONTROL[user_id]['attempts'] > settings.MAX_ATTEMPTS:
        wait_time = int(settings.ATTEMPT_WINDOW - (now - FLOOD_CONTROL[user_id]['first_attempt']))
        return wait_time
    return False