import asyncio
import logging
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
# С сервера Amvera ЮKassa отвечает нестабильно (то 1с, то дольше 20с) —
# поэтому таймаут + повторные попытки. Ключ идемпотентности один на все
# попытки, так что повтор не создаст второй платёж.
# Скаляр, а не кортеж (5,20): в проде на Amvera кортеж отработал как
# read=5 (локально тот же код — read=20, причина неясна), из-за этого
# медленные ответы ЮKassa отваливались. Скаляр однозначен на любой версии.
TIMEOUT = 25
ATTEMPTS = 2
PAUSE = 2  # секунды между попытками

logger = logging.getLogger(__name__)

# Один постоянный сеанс на все запросы — соединение с ЮKassa не рвётся,
# каждый следующий платёж идёт по уже прогретому каналу (без нового TLS-рукопожатия)
_session = requests.Session()


def _warm_up_sync() -> None:
    """Прогрев: первое соединение с ЮKassa устанавливаем при старте бота,
    чтобы первый клиентский клик «Оплатить» не ждал рукопожатия."""
    try:
        import urllib3
        logger.info(
            "Версии HTTP-библиотек: requests %s / urllib3 %s",
            requests.__version__, urllib3.__version__,
        )
        r = _session.get(API_URL + "payments", auth=_auth(), timeout=TIMEOUT, params={"limit": "1"})
        logger.info("Прогрев ЮKassa выполнен (статус %s)", r.status_code)
    except Exception as e:
        logger.warning("Прогрев ЮKassa не удался (не критично): %s", e)


async def warm_up() -> None:
    await asyncio.to_thread(_warm_up_sync)
    # не даём сеансу простаивать — обновляем соединение раз в ~7 минут
    while True:
        await asyncio.sleep(420)
        _warm_up_sync()


def _auth() -> tuple[str, str]:
    return YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY


def _request_with_retry(method: str, path: str, **kwargs) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            r = _session.request(method, API_URL + path, auth=_auth(), timeout=TIMEOUT, **kwargs)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            logger.warning("ЮKassa: попытка %d/%d не удалась (%s): %s", attempt, ATTEMPTS, type(e).__name__, e)
            if attempt < ATTEMPTS:
                time.sleep(PAUSE)
    raise last_exc


def new_idempotence_key() -> str:
    """Ключ идемпотентности: создаём ДО запроса платежа и сохраняем в память
    диалога. Если ответ ЮKassa потерялся по таймауту, повторный POST с тем
    же ключом вернёт тот же платёж — двойной оплаты не будет."""
    return str(uuid.uuid4())


def _create_payment_sync(
    amount: int,
    description: str,
    return_url: str,
    metadata: dict,
    idempotence_key: str,
) -> tuple[str, str]:
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
        headers={"Idempotence-Key": idempotence_key},
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
    idempotence_key: str = None,
) -> tuple[str, str]:
    """Создаёт платёж в ЮKassa. Возвращает (payment_id, ссылка_на_оплату).
    Если передать тот же idempotence_key с теми же данными — вернётся тот же платёж."""
    if return_url is None:
        return_url = YOOKASSA_RETURN_URL
    if idempotence_key is None:
        idempotence_key = new_idempotence_key()

    payment_id, url = await asyncio.to_thread(
        _create_payment_sync,
        amount,
        description,
        return_url,
        metadata or {},
        idempotence_key,
    )
    return payment_id, url


async def check_payment(payment_id: str) -> str:
    """Проверяет статус платежа: 'succeeded', 'pending', 'canceled' и т.д."""
    return await asyncio.to_thread(_find_payment_sync, payment_id)