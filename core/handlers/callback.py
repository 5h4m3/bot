from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core.bot import bot
from core.utils import menu_utils, sessions

@bot.on_callback_query()
async def handle_callback_actions(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if not await is_admin(user_id):
        if not await check_user_access(user_id):
            await callback_query.answer(
                "❌ Ваш ключ доступа истек! Настройки сброшены.",
                show_alert=True
            )
            await revoke_expired_access()  # Запускаем очистку
            return
    
    if data == "generate_key":
        if await is_admin(user_id):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Постоянный ключ", callback_data="generate_permanent_key")],
                [InlineKeyboardButton("⏳ Временный ключ", callback_data="ask_duration")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
            ])
            await callback_query.edit_message_text(
                "Выберите тип ключа:",
                reply_markup=keyboard
            )
    
    elif data == "generate_permanent_key":
        key, error = await generate_access_key(client, user_id)
        if key:
            await callback_query.edit_message_text(
                f"🔑 Создан постоянный ключ:\n\n<code>{key}</code>\n\n"
                "Ключ не имеет срока действия.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
                ])
            )
    elif data == "list_keys":
        if await is_admin(user_id):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT key, used_by, created_at, expires_at 
                FROM access_keys 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            keys = cursor.fetchall()
            conn.close()
            
            now = datetime.now()
            text = "🗝 Последние 10 ключей:\n\n"
            
            for key in keys:
                key_str, used_by, created_at, expires_at = key
                
                # Определяем статус ключа
                status = "✅ Использован" if used_by else "🆓 Активен"
                
                # Форматируем время создания
                created_str = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                
                # Обрабатываем срок действия
                expire_info = ""
                if expires_at:
                    # Удаляем миллисекунды если они есть
                    if '.' in expires_at:
                        expires_at = expires_at.split('.')[0]
                    
                    expire_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                    expire_str = expire_dt.strftime("%d.%m.%Y %H:%M")
                    
                    # Проверяем истек ли срок
                    if expire_dt < now:
                        expire_info = f"❌ Истек {expire_str}"
                    else:
                        expire_info = f"⏳ Действителен до: {expire_str}"
                else:
                    expire_info = "♾️ Бессрочный"
                
                text += (
                    f"🔑 <code>{key_str}</code>\n"
                    f"🕒 Создан: {created_str}\n"
                    f"📌 Статус: {status}\n"
                    f"⌛ {expire_info}\n\n"
                )
            
            await callback_query.answer()
            await callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
                ])
            )
    
    elif data == "ask_duration":
        user_states[user_id] = {
            'state': 'awaiting_key_duration',
            'prev_msg_id': callback_query.message.id
        }
        await callback_query.edit_message_text(
            "⏳ Введите продолжительность действия ключа:\n\n"
            "Примеры:\n"
            "• 30m - 30 минут\n"
            "• 2h - 2 часа\n"
            "• 7d - 7 дней\n"
            "• 1M - 1 месяц\n\n"
            "Введите значение:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")]
            ])
        )
    
    elif data == "admin_menu":
        if await is_admin(user_id):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Сгенерировать ключ доступа", callback_data="generate_key")],
                [InlineKeyboardButton("📋 Список ключей", callback_data="list_keys")],
                [InlineKeyboardButton("⚙️ Основное меню", callback_data="main_menu")]
            ])
            await callback_query.edit_message_text(
                "Меню администратора:",
                reply_markup=keyboard
            )
    
    elif data == "list_keys":
        if await is_admin(user_id):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT key, used_by, created_at FROM access_keys ORDER BY created_at DESC LIMIT 10')
            keys = cursor.fetchall()
            conn.close()
            
            text = "🗝 Последние 10 ключей:\n\n"
            for key in keys:
                status = "✅ Использован" if key[1] else "🆓 Активен"
                text += f"<code>{key[0]}</code> - {status}\n"
            
            await callback_query.answer()
            await callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
                ])
            )
    elif data == "cancel_access":
        if user_id in sessions.user_states and sessions.user_states[user_id].get('state') == 'awaiting_access_key':
            del sessions.user_states[user_id]
        await menu_utils.show_main_menu(client, user_id)
            
    message_id = callback_query.message.id
    
    try:
        await callback_query.answer()
    except Exception as e:
        print(f"Не удалось ответить на callback: {e}")

    if data == "main_menu":
        await show_main_menu(client, user_id, message_id)
    
    elif data == "settings":
        await show_settings_menu(client, user_id, message_id)
    
    elif data == "set_phone":
        # Устанавливаем состояние ожидания номера телефона
        user_states[user_id] = {
            'state': 'awaiting_phone',
            'prev_msg_id': message_id
        }
        await client.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="📱 Введите новый номер телефона (в формате +79123456789):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]
            ])
        )
    
    elif data == "set_api":
        # Устанавливаем состояние ожидания API данных
        user_states[user_id] = {
            'state': 'awaiting_api',
            'prev_msg_id': message_id
        }
        await client.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="🔑 Введите API ID и API HASH через пробел (например: 123456 abcdef123456):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]
            ])
        )
    
    elif data == "cancel_input":
        if user_id in user_states:
            prev_msg_id = user_states[user_id].get('prev_msg_id')
            del user_states[user_id]
            await show_settings_menu(client, user_id, prev_msg_id)
    
    elif data == "status":
        phone, api_id, api_hash, is_active, _ = await get_user_settings(user_id)
        
        status_text = (
            f"📊 Текущие настройки:\n"
            f"📱 Номер: {phone or 'не установлен'}\n"
            f"🔑 API ID: {api_id or 'не установлен'}\n"
            f"🔑 API HASH: {api_hash or 'не установлен'}\n"
            f"🔄 Статус: {'активен ✅' if is_active else 'неактивен ⛔'}"
        )
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
        
        try:
            msg = await client.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=status_text,
                reply_markup=keyboard
            )
            await cleanup_menus(client, user_id, msg.id)
        except Exception as e:
            print(f"Не удалось отредактировать сообщение: {e}")
            msg = await client.send_message(
                user_id,
                text=status_text,
                reply_markup=keyboard
            )
            await cleanup_menus(client, user_id, msg.id)
    
        # Обновляем ID последнего сообщения
        if user_id not in user_states:
            user_states[user_id] = {}
        user_states[user_id]['last_message_id'] = msg.id
    
    elif data == "toggle_bot":
        _, _, _, is_active, _ = await get_user_settings(user_id)
        if is_active:
            if await stop_userbot(user_id):
                await client.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text="🛑 Бот остановлен!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")]
                    ])
                )
            else:
                await client.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text="ℹ️ Бот не был запущен",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")]
                    ])
                )
        else:
            if not await start_userbot(client, user_id, message_id):
                # Сообщение об ошибке уже отправлено в start_userbot
                pass
    
    elif data == "resend_code":
        if user_id in user_sessions:
            last_request = user_sessions[user_id].get('code_request_time', 0)
            if time.time() - last_request < 120:
                await callback_query.answer("⚠️ Подождите 2 минуты перед повторной отправкой", show_alert=True)
                return
    
        await callback_query.answer("⌛ Отправляем новый код...")
        success = await start_userbot(client, user_id, callback_query.message.id)
        if not success:
            # Сообщение об ошибке уже отправлено в start_userbot
            pass
    
    elif data == "cancel_code":
        if user_id in user_sessions:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
            del user_sessions[user_id]
        await show_main_menu(client, user_id)