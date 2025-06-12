import asyncio
from config import settings, constants
from pyrogram import Client
from pyrogram.errors import (
    PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, FloodWait
)
import time
import logging
from core.utils import db

user_sessions = {}  # Глобальное состояние сессий
user_states = {}    # Глобальное состояние пользователей

async def handle_telegram_code(client, user_id, code):
    # Проверяем существование сессии в самом начале
    if user_id not in user_sessions:
        await client.send_message(user_id, "❌ Сессия не найдена. Начните заново через /start.")
        return False

    session = user_sessions[user_id]
    
    # Проверяем время жизни кода (5 минут)
    current_time = time.time()
    if current_time - session.get('code_time', 0) > 300:
        await client.send_message(user_id, "⌛ Время действия кода истекло. Используйте /start для нового.")
        try:
            await session['client'].disconnect()
        except:
            pass
        del user_sessions[user_id]
        return False

    # Очистка кода от лишних символов
    code_clean = ''.join([c for c in str(code) if c.isdigit()])
    if len(code_clean) != 5:
        await client.send_message(user_id, "❌ Код должен содержать ровно 5 цифр")
        return False
    
    try:
        logging.info(f"🔹 Sign in attempt - Phone: {session['phone']}, Code hash: {session['phone_code_hash']}, Code: {code_clean} (timestamp: {session.get('code_time')}, current: {time.time()})")
        logging.info(f"🔹 Time difference: {time.time() - session.get('code_time', 0)}")
        await asyncio.sleep(1)  # Задержка перед входом
            
        # Проверяем подключение
        if not session['client'].is_connected:
            await session['client'].connect()

        # Пытаемся войти
        try:
            await session['client'].sign_in(
                phone_number=session['phone'],
                phone_code_hash=session['phone_code_hash'],
                phone_code=code_clean
            )
        except SessionPasswordNeeded:
            user_sessions[user_id]['status'] = 'awaiting_password'
            await client.send_message(
                user_id,
                "🔐 Введите пароль двухфакторной аутентификации:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_code")]
                ])
            )
            return False

        # Успешная авторизация
        await save_user_settings(
            user_id,
            is_active=1,
            session_file=session['session_name']
        )

        # Сохраняем сессию
        await session['client'].stop()

        # Запускаем userbot
        user_client = Client(
            session['session_name'],
            api_id=session['client'].api_id,
            api_hash=session['client'].api_hash
        )
        await user_client.start()
        asyncio.create_task(main_loop(user_id, user_client))
        
        await client.send_message(user_id, "✅ Успешная авторизация! Бот запущен.")
        return True

    except PhoneCodeInvalid:
        await client.send_message(user_id, "❌ Неверный код подтверждения")
        return False
        
    except PhoneCodeExpired:
        await client.send_message(user_id, "⌛ Код истек. Используйте /start для нового.")
        try:
            await session['client'].disconnect()
        except:
            pass
        del user_sessions[user_id]
        return False
        
    except Exception as e:
        logging.error(f"Ошибка авторизации: {str(e)}", exc_info=True)
        await client.send_message(
            user_id,
            f"❌ Ошибка авторизации: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data="resend_code")],
                [InlineKeyboardButton("🔙 В меню", callback_data="main_menu")]
            ])
        )
        return False
        
async def handle_2fa(client, user_id):
    user_sessions[user_id]['status'] = 'awaiting_password'
    await client.send_message(
        user_id,
        "🔐 Введите пароль двухфакторной аутентификации:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_code")]
        ])
    )
        
async def revoke_expired_access():
    """Отзывает доступ для всех пользователей с истекшими ключами"""
    conn = sqlite3.connect(settings.DB_FILE)
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''SELECT used_by FROM access_keys 
                    WHERE expires_at IS NOT NULL AND expires_at <= ? AND used_by IS NOT NULL''', 
                    (now,))
    
    for user_id in [row[0] for row in cursor.fetchall()]:
        await stop_userbot(user_id)
        cursor.execute('UPDATE access_keys SET used_by=NULL WHERE used_by=?', (user_id,))
        user_states[user_id] = {'state': 'awaiting_access_key'}
        
        try:
            await bot.send_message(
                user_id,
                "⏳ Срок действия вашего ключа доступа истек!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_access")]])
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id}: {e}")

    conn.commit()
    conn.close()
    
async def check_telegram_ban(phone):
    from config.settings import settings
    try:
        temp_client = Client("temp_session", api_id=settings.API_ID, api_hash=settings.API_HASH)
        await temp_client.connect()
        await temp_client.send_code(phone)
        await temp_client.disconnect()
        return False
    except FloodWait as e:
        return e.value
    except Exception:
        return True
    finally:
        if 'temp_client' in locals():
            await temp_client.disconnect()

async def check_authorization(client):
    try:
        me = await client.get_me()
        return me is not None
    except:
        return False
        
async def start_userbot(client, user_id, edit_message_id=None):
    try:
        logging.info(f"🔹 Starting userbot for user_id: {user_id}")
        await asyncio.sleep(1)

        # Проверка флуд-контроля
        if user_id in FLOOD_CONTROL:
            last_request = FLOOD_CONTROL[user_id].get('last_request', 0)
            if time.time() - last_request < 30:
                logging.warning("⚠️ Flood control active, waiting 30 sec")
                await asyncio.sleep(30)

        phone, api_id, api_hash, is_active, _ = await get_user_settings(user_id)
        
        if not all([phone, api_id, api_hash]):
            await client.send_message(user_id, "❌ Необходимо настроить номер и API данные")
            return False

        session_name = f'sessions/session_{user_id}'
        user_client = Client(
            session_name,
            api_id=int(api_id),
            api_hash=api_hash,
            phone_number=phone
        )

        # Проверяем и отключаем старую сессию (если есть)
        if user_id in user_sessions:
            try:
                if hasattr(user_sessions[user_id]['client'], 'is_connected'):
                    if user_sessions[user_id]['client'].is_connected:
                        await user_sessions[user_id]['client'].disconnect()
            except Exception as e:
                logging.error(f"⚠️ Ошибка при отключении старого клиента: {e}")

        # Подключаем новый клиент
        try:
            await user_client.connect()
        except Exception as e:
            logging.error(f"❌ Ошибка подключения: {e}")
            await client.send_message(user_id, "❌ Не удалось подключиться. Попробуйте позже.")
            return False

        # Отправляем код
        try:
            sent_code = await user_client.send_code(phone)
            logging.info(f"✅ Код отправлен на {phone}, хэш: {sent_code.phone_code_hash}")
            
            user_sessions[user_id] = {
                'client': user_client,
                'phone_code_hash': sent_code.phone_code_hash,
                'phone': phone,
                'session_name': session_name,
                'code_time': time.time(),
                'status': 'awaiting_telegram_code'
            }

            await client.send_message(
                user_id,
                f"🔑 Код отправлен на {phone}\nВведите 5-значный код (действителен 5 минут):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый код", callback_data="resend_code")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_code")]
                ])
            )
            return True

        except FloodWait as e:
            wait_time = format_wait_time(e.value)
            await client.send_message(
                user_id,
                f"⏳ Telegram временно блокирует отправку кодов на этот номер.\n\n"
                f"⚠️ Пожалуйста, подождите **{wait_time}** прежде чем повторить попытку.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Попробовать позже", callback_data="main_menu")],
                    [InlineKeyboardButton("🆘 Поддержка", url="https://t.me/btw_idm")]
                ])
            )
            return False

        except Exception as e:
            logging.error(f"❌ Ошибка при отправке кода: {e}")
            await client.send_message(user_id, f"❌ Ошибка: {str(e)}")
            return False

    except Exception as e:
        logging.error(f"❌ Критическая ошибка в start_userbot: {e}")
        await client.send_message(user_id, "❌ Произошла ошибка. Попробуйте позже.")
        return False

        # Отправляем код
        sent_code = await user_client.send_code(phone)
        logging.info(f"✅ Код отправлен на {phone}, хэш: {sent_code.phone_code_hash}")
    except FloodWait as e:
        wait_time = format_wait_time(e.value)
        await client.send_message(
            user_id,
            f"⏳ Telegram блокирует запросы. Попробуйте через {wait_time}.",
        )
        return False
    except Exception as e:
        logging.error(f"Ошибка отправки кода: {e}")
        await client.send_message(user_id, f"❌ Ошибка: {e}")
        return False
        
        # Проверяем, не заблокирован ли номер
        ban_time = await check_telegram_ban(phone)
        if ban_time:
            if isinstance(ban_time, int):  # Если это FloodWait
                wait_time = format_wait_time(ban_time)
                await client.send_message(
                    user_id,
                    f"⏳ Telegram временно блокирует отправку кодов. Ждите {wait_time}.",
                )
            else:  # Другая ошибка (например, номер забанен)
                await client.send_message(
                    user_id,
                    "❌ Невозможно отправить код. Возможно, номер заблокирован.",
                )
            return False

        # Отправляем код
        sent_code = await user_client.send_code(phone)
        logging.info(f"✅ Код отправлен. Номер: {phone}, хэш: {sent_code.phone_code_hash}")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки кода: {type(e)}: {e}")
    
    except FloodWait as e:
        wait_time = format_wait_time(e.value)
        await client.send_message(
            user_id,
            f"⏳ Лимит запросов исчерпан. Ждите {wait_time}.",
        )
        return False
    except Exception as e:
        logging.error(f"Ошибка при отправке кода: {e}")
        await client.send_message(user_id, f"❌ Ошибка: {e}")
        return False

async def stop_userbot(user_id):
    if user_id in user_sessions:
        try:
            if hasattr(user_sessions[user_id]['client'], 'is_connected'):
                if user_sessions[user_id]['client'].is_connected:
                    await user_sessions[user_id]['client'].disconnect()
            await save_user_settings(user_id, is_active=0)
            return True
        except Exception as e:
            logging.error(f"⚠️ Ошибка при остановке бота: {e}")
            return False
    return True
    
async def handle_telegram_code(client, user_id, code):
    try:
        # Проверяем существование сессии в самом начале
        if user_id not in user_sessions:
            await client.send_message(user_id, "❌ Сессия не найдена. Начните заново через /start.")
            return False

        session = user_sessions.get(user_id)
        if not session:
            await client.send_message(user_id, "❌ Ошибка сессии. Начните заново.")
            return False

        # Проверяем время жизни кода (5 минут)
        current_time = time.time()
        code_time = session.get('code_time', 0)
        
        if current_time - code_time > 300:  # 5 минут
            await client.send_message(user_id, "⌛ Время действия кода истекло. Используйте /start для нового.")
            try:
                if 'client' in session:
                    await session['client'].disconnect()
            except:
                pass
            if user_id in user_sessions:
                del user_sessions[user_id]
            return False

        # Очистка кода от лишних символов
        code_clean = ''.join([c for c in str(code) if c.isdigit()])
        if len(code_clean) != 5:
            await client.send_message(user_id, "❌ Код должен содержать ровно 5 цифр")
            return False

        # Проверяем подключение
        if not session.get('client') or not session['client'].is_connected:
            try:
                await session['client'].connect()
            except Exception as e:
                await client.send_message(user_id, f"❌ Ошибка подключения: {str(e)}")
                return False

        # Пытаемся войти
        try:
            await session['client'].sign_in(
                phone_number=session['phone'],
                phone_code_hash=session['phone_code_hash'],
                phone_code=code_clean
            )
        except SessionPasswordNeeded:
            user_sessions[user_id]['status'] = 'awaiting_password'
            await client.send_message(
                user_id,
                "🔐 Введите пароль двухфакторной аутентификации:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_code")]
                ])
            )
            return False
        except PhoneCodeInvalid:
            await client.send_message(user_id, "❌ Неверный код подтверждения")
            return False
        except PhoneCodeExpired:
            await client.send_message(user_id, "⌛ Код истек. Используйте /start для нового.")
            try:
                await session['client'].disconnect()
            except:
                pass
            if user_id in user_sessions:
                del user_sessions[user_id]
            return False

        # Успешная авторизация
        await save_user_settings(
            user_id,
            is_active=1,
            session_file=session['session_name']
        )

        # Сохраняем сессию
        try:
            await session['client'].stop()
        except:
            pass

        # Запускаем userbot
        try:
            user_client = Client(
                session['session_name'],
                api_id=session['client'].api_id,
                api_hash=session['client'].api_hash
            )
            await user_client.start()
            asyncio.create_task(main_loop(user_id, user_client))
            await client.send_message(user_id, "✅ Успешная авторизация! Бот запущен.")
            return True
        except Exception as e:
            await client.send_message(user_id, f"❌ Ошибка запуска бота: {str(e)}")
            return False

    except Exception as e:
        logging.error(f"Критическая ошибка в handle_telegram_code: {str(e)}", exc_info=True)
        await client.send_message(
            user_id,
            "❌ Произошла критическая ошибка. Пожалуйста, начните процесс заново."
        )
        if user_id in user_sessions:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
            del user_sessions[user_id]
        return False
        
@bot.on_message(filters.private & filters.text)
async def handle_2fa_password(client, message):
    user_id = message.from_user.id
    if user_id in user_sessions and user_sessions[user_id].get('status') == 'awaiting_password':
        password = message.text.strip()
        try:
            await user_sessions[user_id]['client'].check_password(password)
            # Продолжаем процесс авторизации
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")