import asyncio
import os
import time
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
# С сервера Amvera ЮKassa отвечает нестабильно (то 1с, то дольше 30с) —
# поэтому таймаут + повторные попытки. Ключ идемпотентности один на все
# попытки, так что повтор не создаст второй платёж.
TIMEOUT = (5, 30)
ATTEMPTS = 3
PAUSE = 2  # секунды между попытками


def _auth() -> tuple[str, str]:
    return YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY


def _request_with_retry(method: str, path: str, **kwargs) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            r = requests.request(method, API_URL + path, auth=_auth(), timeout=TIMEOUT, **kwargs)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt < ATTEMPTS:
                time.sleep(PAUSE)
    raise last_exc


def _create_payment_sync(amount: int, description: str, return_url: str, metadata: dict) -> tuple[str, str]:
    body = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    payment = _request_with_retry(
        "post",
        "payments",
        headers={"Idempotence-Key": str(uuid.uuid4())},
        json=body,
    )
    return payment["id"], payment["confirmation"]["confirmation_url"]


def _find_payment_sync(payment_id: str) -> str:
    payment = _request_with_retry("get", f"payments/{payment_id}")
    return payment["status"]


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