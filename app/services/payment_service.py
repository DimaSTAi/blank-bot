import asyncio
import os
import uuid

import requests

# Если на компьютере включён системный прокси/VPN, запросы попытается
# идти через него и упадёт, когда прокси выключен. ЮKassa — российский сервис,
# ходим к ней напрямую всегда.
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

from app.config import (
    YOOKASSA_SHOP_ID,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_RETURN_URL,
)

API_URL = "https://api.yookassa.ru/v3/"
TIMEOUT = 15  # секунды; без лимита запрос к ЮKassa может висеть вечно


def _auth() -> tuple[str, str]:
    return YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY


def _create_payment_sync(amount: int, description: str, return_url: str, metadata: dict) -> tuple[str, str]:
    body = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    r = requests.post(
        API_URL + "payments",
        auth=_auth(),
        headers={"Idempotence-Key": str(uuid.uuid4())},
        json=body,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    payment = r.json()
    return payment["id"], payment["confirmation"]["confirmation_url"]


def _find_payment_sync(payment_id: str) -> str:
    r = requests.get(
        API_URL + f"payments/{payment_id}",
        auth=_auth(),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["status"]


async def create_payment(
    amount: int,
    description: str,
    return_url: str = None,
    metadata: dict = None,
) -> tuple[str, str]:
    """Создаёт платёж в ЮKassa. Возвращает (payment_id, ссылка_на_оплату)."""
    if return_url is None:
        return_url = YOOKASSA_RETURN_URL

    payment_id, url = await asyncio.to_thread(
        _create_payment_sync,
        amount,
        description,
        return_url,
        metadata or {},
    )
    return payment_id, url


async def check_payment(payment_id: str) -> str:
    """Проверяет статус платежа: 'succeeded', 'pending', 'canceled' и т.д."""
    return await asyncio.to_thread(_find_payment_sync, payment_id)