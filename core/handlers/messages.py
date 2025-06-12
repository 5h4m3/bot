from pyrogram import filters
from core.bot import bot
from core.utils import (
    menu_utils,
    sessions,
    db,
    flood_control
)
from config import settings

@bot.on_message(filters.private & filters.text)
async def message_handler(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    try:
        # Обработка кода Telegram
        if user_id in user_sessions and user_sessions[user_id].get('status') == 'awaiting_telegram_code':
            await handle_telegram_code(client, user_id, text)
            return
        
        logging.info(f"📩 Received message from {user_id}: {text}")
        await asyncio.sleep(0.5)  # Небольшая задержка

        # Обработка кода доступа к боту
        if user_id in user_states and user_states[user_id].get('state') == 'awaiting_bot_access_code':
            if await validate_access_key(text, user_id):
                del user_states[user_id]
                await message.reply("✅ Ключ принят! Настройте бота в меню.")
                await show_main_menu(client, user_id)
            else:
                await message.reply("❌ Неверный ключ. Попробуйте еще раз:")
            return
    except Exception as e:
        logging.error(f"Ошибка в обработчике сообщений: {e}")
        await message.reply("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return

    # Обработка кода Telegram
    if user_id in user_sessions and user_sessions[user_id].get('status') == 'awaiting_telegram_code':
        await handle_telegram_code(client, user_id, text)
        return
    
    # Разрешаем обработку сообщений если пользователь в состоянии ожидания ключа
    if user_id in user_states and user_states[user_id].get('state') == 'awaiting_access_key':
        key = message.text.strip()
        if await validate_access_key(key, user_id):
            del user_states[user_id]
            phone, api_id, api_hash, _, _ = await get_user_settings(user_id)

            if phone and api_id and api_hash:
                await message.reply("✅ Ключ принят! Пытаемся подключиться...")
                await start_userbot(client, user_id)
            else:
                await message.reply(
                    "✅ Ключ принят! Введите номер телефона для начала настройки:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Ввести номер", callback_data="set_phone")]
                    ])
                )
        else:
            await message.reply(
                "❌ Неверный или уже использованный ключ. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_access")]
                ])
            )
        return
    
    # Для всех остальных сообщений проверяем доступ
    if not await is_admin(user_id) and not await check_user_access(user_id):
        await message.reply(
            "❌ Ваш ключ доступа истек!\n\n"
            "🔑 Пожалуйста, введите новый ключ доступа от администратора:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_access")]
            ])
        )
        user_states[user_id] = {'state': 'awaiting_access_key'}
        return
        
    if not await is_admin(user_id):
        if not await check_user_access(user_id):
            await message.reply(
                "❌ Ваш ключ доступа истек! Все настройки сброшены.\n\n"
                "Для продолжения работы вам необходимо получить новый ключ у администратора."
            )
            await revoke_expired_access()  # Запускаем очистку
            return
    
    # Проверяем, есть ли состояние у пользователя
    if user_id not in user_states:
        # Если нет состояния, просто игнорируем сообщение или показываем меню
        await show_main_menu(client, user_id)
        return
    
    # Обработка ввода длительности ключа
    if user_states[user_id].get('state') == 'awaiting_key_duration':
        duration = message.text.strip()
        prev_msg_id = user_states[user_id].get('prev_msg_id')
        
        key, error = await generate_access_key(client, user_id, duration)
        if error:
            await message.reply(f"❌ {error}")
            return
        
        del user_states[user_id]
        
        # Получаем срок действия ключа
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT expires_at FROM access_keys WHERE key=?', (key,))
        result = cursor.fetchone()
        conn.close()  # Важно закрывать соединение
        
        # Исправленное получение данных
        if result and result[0]:
            expires_at = result[0]
            # Удаляем миллисекунды если они есть
            if '.' in expires_at:
                expires_at = expires_at.split('.')[0]
            try:
                expires_str = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                duration_info = f"Срок действия до: {expires_str}"
            except ValueError:
                duration_info = f"Срок действия: {expires_at}"
        else:
            duration_info = "Постоянный ключ (без срока действия)"
        
        await client.send_message(
            user_id,
            f"🔑 Создан временный ключ:\n\n<code>{key}</code>\n\n{duration_info}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
            ])
        )
        
        try:
            await client.delete_messages(user_id, message.id)
            if prev_msg_id:
                await client.delete_messages(user_id, prev_msg_id)
        except:
            pass
        return
    
    # Обработка ввода ключа доступа
    if user_states[user_id].get('state') == 'awaiting_access_key':
        key = message.text.strip()
        if await validate_access_key(key, user_id):
            del user_states[user_id]
            phone, api_id, api_hash, _, _ = await get_user_settings(user_id)

            if phone and api_id and api_hash:
                # Всё есть — сразу запускаем userbot
                await message.reply("✅ Ключ принят! Пытаемся подключиться...")
                await start_userbot(client, user_id)
            else:
                # Нет данных — предлагаем настроить
                await message.reply(
                    "✅ Ключ принят! Введите номер телефона для начала настройки:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Ввести номер", callback_data="set_phone")]
                    ])
                )
        else:
            await message.reply(
                "❌ Неверный или уже использованный ключ. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_access")]
                ])
            )
        return
    
    # Обработка других состояний
    state = user_states[user_id].get('state')
    prev_msg_id = user_states[user_id].get('prev_msg_id')
    
    try:
        if state == 'awaiting_phone':
            phone = message.text.strip()
            if phone.startswith('+') and len(phone) > 5:
                await save_user_settings(user_id, phone=phone)
                await message.delete()
                await client.send_message(user_id, f"✅ Номер {phone} успешно сохранен!")
                await show_settings_menu(client, user_id, prev_msg_id)
            else:
                await message.reply("❌ Неверный формат номера! Попробуйте еще раз.")
        
        elif state == 'awaiting_api':
            try:
                parts = message.text.split()
                if len(parts) == 2:
                    api_id, api_hash = parts
                    api_id = int(api_id)  # Проверяем, что API ID - число
                    await save_user_settings(user_id, api_id=api_id, api_hash=api_hash)
                    await message.delete()
                    await client.send_message(user_id, "✅ API данные успешно сохранены!")
                    await show_settings_menu(client, user_id, prev_msg_id)
                else:
                    raise ValueError()
            except ValueError:
                await message.reply("❌ Неверный формат! Введите API ID (число) и API HASH через пробел")
            except Exception as e:
                await message.reply(f"❌ Ошибка: {str(e)}")
        
        # Удаляем состояние после обработки
        if user_id in user_states:
            del user_states[user_id]
            
    except Exception as e:
        logging.error(f"Ошибка в обработчике сообщений: {str(e)}")
        await message.reply("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        
    await show_main_menu(client, user_id)