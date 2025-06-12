import asyncio
import logging
from core.utils import sessions

async def main_loop(user_id, client):
    from config import constants
    from core.utils import db
    
    logging.info(f"▶️ Starting main loop for user_id: {user_id}")
    await asyncio.sleep(2)  # Начальная задержка
    
    # Проверяем доступ перед запуском
    if not await check_user_access(user_id):
        await stop_userbot(user_id)
        await save_user_settings(user_id, is_active=0)
        try:
            await bot.send_message(
                user_id,
                "⏳ Срок действия вашего ключа доступа истек!\n\n"
                "❌ Бот был автоматически остановлен. Для продолжения работы "
                "вам необходимо получить новый ключ у администратора."
            )
        except:
            pass
        return
    
    messages = [
        ("я", 10), ("бизнес", 10), ("снять деньги", 5), ("склад", 5),
        ("заказать сырьё", 5), ("закупить на все деньги", 5),
        ("да", 5), ("я", 5)
    ]
    
    special_messages = [
        ("я", 10), ("семьи", 15), ("🔫 война за притон", 0)
    ]
    
    while True:
        try:
            _, _, _, is_active, _ = await get_user_settings(user_id)
            if not is_active:
                break
                
            now = get_current_time()
            if now.hour == 19 and now.minute == 1:
                for msg, delay in special_messages:
                    await client.send_message(TARGET_CHAT, msg)
                    if delay > 0:
                        await asyncio.sleep(delay)
                
            for msg, delay in messages:
                _, _, _, is_active, _ = await get_user_settings(user_id)
                if not is_active:
                    break
                
                try:
                    await client.send_message(TARGET_CHAT, msg)
                    await asyncio.sleep(delay)
                except Exception:
                    await asyncio.sleep(5)
            
            
            
    while True:
        try:
            # Проверка активности
            if not await check_user_active(user_id):
                break
                
            # Обработка специальных сообщений
            if is_special_time():
                await process_special_messages(client)
                await asyncio.sleep(6 * 3600)
                continue
                
            # Основной цикл сообщений
            await process_regular_messages(client)
            
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)
            
async def check_expired_codes():
    while True:
        logging.debug("🔹 Checking expired codes...")
        await asyncio.sleep(60)
        
        now = time.time()
        for user_id, session in list(sessions.user_sessions.items()):
            if session.get('status') == 'awaiting_telegram_code':
                time_diff = now - session.get('code_time', 0)
                logging.debug(f"⏳ User {user_id} code age: {time_diff} sec")
                
                if time_diff > 240:
                    logging.warning(f"⚠️ Code expiring soon for {user_id}")
                    await sessions.bot.send_message(
                        user_id,
                        "⚠️ Код скоро истечет. Введите его в течение 1 минуты или запросите новый."
                    )

async def periodic_access_check():
    """Периодическая проверка и отзыв истекших доступов"""
    while True:
        try:
            await sessions.revoke_expired_access()
            await asyncio.sleep(3600)
        except Exception as e:
            print(f"Ошибка при проверке доступа: {e}")
            await asyncio.sleep(600)