from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.bot import bot
from core.utils import sessions, menu_utils

async def request_api_credentials(client, user_id, prev_message_id=None):
    from core.utils import sessions
    sessions.user_states[user_id] = {
        'state': 'awaiting_api',
        'prev_msg_id': prev_message_id
    }
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]]
    
    try:
        if prev_message_id:
            await menu_utils.edit_or_send(
                client, user_id, prev_message_id,
                "🔑 Введите API ID и HASH через пробел:",
                keyboard
            )
        else:
            await menu_utils.edit_or_send(
                client, user_id, None,
                "🔑 Введите API ID и HASH через пробел:",
                keyboard
            )
    except Exception as e:
        logging.error(f"Error requesting API: {e}")

@bot.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    await menu_utils.show_main_menu(client, message.from_user.id)
    user_id = message.from_user.id
    
    if await sessions.is_admin(user_id):
        # Показать админ-меню
        await menu_utils.show_admin_menu(client, user_id)
    elif await sessions.check_user_access(user_id):
        # Показать основное меню
        await menu_utils.show_main_menu(client, user_id)
    else:
        sessions.user_states[user_id] = {'state': 'awaiting_access_key'}
        await message.reply(
            "🔐 Для доступа введите ключ:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_access")]])
        )