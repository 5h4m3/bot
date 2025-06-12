import asyncio
from core.bot import bot, tasks
from core.utils import db

async def main():
    # Инициализация
    db.init_db()
    
    # Запуск фоновых задач
    asyncio.create_task(tasks.check_expired_codes())
    asyncio.create_task(tasks.periodic_access_check())
    
    # Запуск бота
    await bot.start()
    print("⚡ Бот запущен")
    
    # Бесконечный цикл
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")