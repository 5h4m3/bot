from pytz import timezone

class Constants:
    MOSCOW_TZ = timezone('Europe/Moscow')
    MESSAGES = [
        ("я", 10), ("бизнес", 10), ("снять деньги", 5), 
        ("склад", 5), ("заказать сырьё", 5), 
        ("закупить на все деньги", 5), ("да", 5), ("я", 5)
    ]

    SPECIAL_MESSAGES = [
        ("я", 10), ("семьи", 15), ("🔫 война за притон", 0)
    ]

constants = Constants()