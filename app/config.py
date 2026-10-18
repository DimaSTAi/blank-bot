import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "RUB")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "")
YOOKASSA_WEBHOOK_URL = os.getenv("YOOKASSA_WEBHOOK_URL", "")
YOOKASSA_WEBHOOK_SECRET = os.getenv("YOOKASSA_WEBHOOK_SECRET", "")
PROXY_URL = os.getenv("PROXY_URL", "")

YOOKASSA_TEST_MODE = os.getenv("YOOKASSA_TEST_MODE", "true").lower() in ("true", "1", "yes")

# Цены по категориям документов (используются в catalog.py)
DKP_PRICE = 180
RENT_PRICE = 180
RECEIPT_PRICE = 180
CLAIM_PRICE = 180
ACT_PRICE = 180
GIFT_PRICE = 180
