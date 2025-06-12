from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.utils.db import get_user_settings, save_user_settings

ACTIVE_MENUS = {}  # {user_id: [message_ids]}

async def show_admin_menu(client, user_id):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Сгенерировать ключ", callback_data="generate_key")],
        [InlineKeyboardButton("📋 Список ключей", callback_data="list_keys")],
        [InlineKeyboardButton("⚙️ Основное меню", callback_data="main_menu")]
    ])
    await client.send_message(user_id, "👑 Админ-панель:", reply_markup=keyboard)

async def request_phone_number(client, user_id, prev_message_id=None):
    user_states[user_id] = {'state': 'awaiting_phone', 'prev_msg_id': prev_message_id}
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]]
    
    try:
        if prev_message_id:
            await client.edit_message_text(
                chat_id=user_id,
                message_id=prev_message_id,
                text="📱 Введите новый номер телефона (в формате +79123456789):",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return prev_message_id
    except:
        pass
    
    msg = await client.send_message(
        chat_id=user_id,
        text="📱 Введите новый номер телефона (в формате +79123456789):",
        reply_markup=InlineKeyboardMarkup(keyboard))
    return msg.id
    
async def cleanup_menus(client, user_id, keep_message_id=None):
    """Удаляет все предыдущие меню, кроме указанного"""
    if user_id in ACTIVE_MENUS:
        for msg_id in ACTIVE_MENUS[user_id]:
            if msg_id != keep_message_id:
                try:
                    await client.delete_messages(user_id, msg_id)
                except:
                    pass
        ACTIVE_MENUS[user_id] = [keep_message_id] if keep_message_id else []
    elif keep_message_id:
        ACTIVE_MENUS[user_id] = [keep_message_id]

async def show_main_menu(client, user_id, prev_message_id=None):
    await cleanup_menus(client, user_id)
    
    phone, api_id, api_hash, is_active, _ = await get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("✅ Включить" if not is_active else "⛔ Выключить", callback_data="toggle_bot")],
        [InlineKeyboardButton("🔄 Статус", callback_data="status")],
        [InlineKeyboardButton("🆘 Поддержка", url="https://t.me/btw_idm")]
    ]
    
    text = (
        "🔹 Главное меню управления ботом:\n\n"
        "Если вы столкнулись с какой-то проблемой или ошибкой, "
        "обратитесь в поддержку, нажав на кнопку 🆘 Поддержка"
    )
    
    try:
        if prev_message_id:
            msg = await client.edit_message_text(
                chat_id=user_id,
                message_id=prev_message_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard))
            await cleanup_menus(client, user_id, msg.id)
            return msg.id
    except:
        pass
    
    msg = await client.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard))
    
    await cleanup_menus(client, user_id, msg.id)
    return msg.id

async def show_settings_menu(client, user_id, prev_message_id=None):
    await cleanup_menus(client, user_id)
    
    keyboard = [
        [InlineKeyboardButton("📱 Изменить номер", callback_data="set_phone")],
        [InlineKeyboardButton("🔑 Изменить API", callback_data="set_api")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    
    try:
        if prev_message_id:
            msg = await client.edit_message_text(
                chat_id=user_id,
                message_id=prev_message_id,
                text="⚙️ Меню настроек:",
                reply_markup=InlineKeyboardMarkup(keyboard))
            await cleanup_menus(client, user_id, msg.id)
            return msg.id
    except:
        pass
    
    msg = await client.send_message(
        chat_id=user_id,
        text="⚙️ Меню настроек:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    
    await cleanup_menus(client, user_id, msg.id)
    return msg.id