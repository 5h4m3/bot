import logging
from logging.handlers import RotatingFileHandler

class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        record.msg = record.msg.replace("+7912", "***")
        return True

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler("debug.log", maxBytes=1_000_000, backupCount=3, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger().addFilter(SensitiveDataFilter())
    logging.getLogger("pyrogram").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)