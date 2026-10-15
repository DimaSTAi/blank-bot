import asyncio
from yookassa import Configuration, Payment
from app.config import (
    YOOKASSA_SHOP_ID,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_RETURN_URL,
)


Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def _create_payment_sync(amount: int, description: str, return_url: str, metadata: dict) -> Payment:
    return Payment.create(
        {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "capture": True,
            "description": description,
            "metadata": metadata,
        }
    )


def _find_payment_sync(payment_id: str) -> Payment:
    return Payment.find_one(payment_id)


async def create_payment(
    amount: int,
    description: str,
    return_url: str = None,
    metadata: dict = None,
) -> tuple[str, str]:
    """Создаёт платёж в ЮKassa. Возвращает (payment_id, confirmation_url)."""
    if return_url is None:
        return_url = YOOKASSA_RETURN_URL

    payment = await asyncio.to_thread(
        _create_payment_sync,
        amount,
        description,
        return_url,
        metadata or {},
    )
    return payment.id, payment.confirmation.confirmation_url


async def check_payment(payment_id: str) -> str:
    """Проверяет статус платежа. Возвращает 'succeeded', 'pending', 'canceled' и т.д."""
    payment = await asyncio.to_thread(_find_payment_sync, payment_id)
    return payment.status
