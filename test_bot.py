import asyncio
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers import main as handlers_main
from app.services.pdf_service import generate_pdf


def make_dp():
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_main.router)
    return dp


class FakeSession:
    def __init__(self):
        self.responses = []

    async def close(self):
        pass

    def get_responses(self):
        return self.responses


class FakeBot:
    def __init__(self):
        self.session = FakeSession()
        self.id = 1
        self._me = None

    async def me(self):
        return types.User(id=1, is_bot=True, first_name="TestBot", username="testbot")

    async def send_message(self, chat_id, text, **kwargs):
        self.session.responses.append({"method": "send_message", "chat_id": chat_id, "text": text, "kwargs": kwargs})

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kwargs):
        self.session.responses.append({"method": "edit_message_text", "text": text, "kwargs": kwargs})

    async def answer_callback_query(self, callback_query_id, **kwargs):
        self.session.responses.append({"method": "answer_callback_query", "callback_query_id": callback_query_id, "kwargs": kwargs})

    async def send_document(self, chat_id, document, **kwargs):
        self.session.responses.append({"method": "send_document", "chat_id": chat_id, "document": document, "kwargs": kwargs})

    async def __call__(self, method, **kwargs):
        # aiogram вызывает бота как функцию для методов API
        method_name = method.__api_method__
        params = method.model_dump(exclude_unset=True)
        if method_name == "sendMessage":
            return await self.send_message(**params)
        if method_name == "editMessageText":
            return await self.edit_message_text(**params)
        if method_name == "answerCallbackQuery":
            return await self.answer_callback_query(**params)
        if method_name == "sendDocument":
            return await self.send_document(**params)
        self.session.responses.append({"method": method_name, "params": params})


def make_user(user_id=123):
    return types.User(id=user_id, is_bot=False, first_name="Test")


def make_chat(chat_id=123):
    return types.Chat(id=chat_id, type="private")


def make_message(text, user_id=123, chat_id=123, message_id=1):
    return types.Message(
        message_id=message_id,
        from_user=make_user(user_id),
        chat=make_chat(chat_id),
        date=0,
        text=text,
    )


def make_callback(data, user_id=123, message_id=1):
    return types.CallbackQuery(
        id="cb",
        from_user=make_user(user_id),
        chat_instance="ci",
        data=data,
        message=make_message("placeholder", user_id=user_id, chat_id=123, message_id=message_id),
    )


async def test_dkp_thing(dp, bot):
    # 1. Старт
    await dp.feed_update(bot, types.Update(message=make_message("/start"), update_id=1))
    print("=== После /start ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 2. Выбор документа ДКП
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("doc:dkp"), update_id=2))
    print("\n=== После doc:dkp ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 3. Выбор подвида dkp_thing
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("subtype:dkp:dkp_thing"), update_id=3))
    print("\n=== После subtype:dkp:dkp_thing ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 4. Заполняем поля
    answers = [
        "г. Москва",
        "05.07.2026",
        "Петров Пётр Петрович",
        "4515",
        "123456",
        "ОВД Москвы, 10.05.2010",
        "770-064",
        "ул. Ленина, 1",
        "ООО \"Покупатель\"",
        "",
        "",
        "",
        "",
        "ул. Пушкина, 5",
        "Ноутбук Apple MacBook Air",
        "13.3 дюйма, M1, 8 GB RAM, 256 GB SSD, в коробке, зарядное устройство",
        "1 шт.",
        "120000",
        "Сто двадцать тысяч",
    ]
    for i, value in enumerate(answers, start=4):
        bot.session.responses.clear()
        await dp.feed_update(bot, types.Update(message=make_message(value, message_id=i), update_id=i))
        print(f"\n=== После ответа {i-3} ===")
        for r in bot.session.get_responses():
            print(r["method"], repr(r.get("text", ""))[:200])

    # 5. Проверим генерацию PDF напрямую
    print("\n=== Проверка генерации PDF ===")
    data = {
        "place": "г. Москва",
        "date": "05.07.2026",
        "seller_name": "Петров Пётр Петрович",
        "seller_passport_series": "4515",
        "seller_passport_number": "123456",
        "seller_passport_issued": "ОВД Москвы, 10.05.2010",
        "seller_passport_code": "770-064",
        "seller_address": "ул. Ленина, 1",
        "buyer_name": "ООО \"Покупатель\"",
        "buyer_passport_series": "",
        "buyer_passport_number": "",
        "buyer_passport_issued": "",
        "buyer_passport_code": "",
        "buyer_address": "ул. Пушкина, 5",
        "product_name": "Ноутбук Apple MacBook Air",
        "product_description": "13.3 дюйма, M1, 8 GB RAM, 256 GB SSD, в коробке, зарядное устройство",
        "product_quantity": "1 шт.",
        "price": "120000",
        "price_words": "Сто двадцать тысяч",
    }
    pdf_path = generate_pdf("dkp", "dkp_thing", data)
    print(f"PDF создан: {pdf_path}")
    print(f"Размер файла: {os.path.getsize(pdf_path)} байт")


async def test_act_goods_transfer(dp, bot):
    # 1. Старт
    await dp.feed_update(bot, types.Update(message=make_message("/start"), update_id=100))
    print("\n=== АКТ: После /start ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 2. Выбор категории Акты
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("doc:act"), update_id=101))
    print("\n=== АКТ: После doc:act ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 3. Выбор подвида act_goods_transfer
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("subtype:act:act_goods_transfer"), update_id=102))
    print("\n=== АКТ: После subtype:act:act_goods_transfer ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 4. Заполняем поля
    answers = [
        "г. Москва",
        "05.07.2026",
        "123",
        "01.07.2026",
        "Петров Пётр Петрович",
        "4515",
        "123456",
        "ОВД Москвы, 10.05.2010",
        "770-064",
        "ул. Ленина, 1",
        "ООО \"Покупатель\"",
        "",
        "",
        "",
        "",
        "ул. Пушкина, 5",
        "Ноутбук Apple MacBook Air",
        "шт.",
        "1",
        "Модель M1, 13.3 дюйма, серебристый",
        "120000",
        "не облагается",
        "120000",
        "претензий не имеется",
    ]
    for i, value in enumerate(answers, start=103):
        bot.session.responses.clear()
        await dp.feed_update(bot, types.Update(message=make_message(value, message_id=i), update_id=i))
        print(f"\n=== АКТ: После ответа {i-102} ===")
        for r in bot.session.get_responses():
            print(r["method"], repr(r.get("text", ""))[:200])

    # 5. Проверим генерацию PDF напрямую
    print("\n=== АКТ: Проверка генерации PDF ===")
    data = {
        "place": "г. Москва",
        "date": "05.07.2026",
        "contract_number": "123",
        "contract_date": "01.07.2026",
        "seller_name": "Петров Пётр Петрович",
        "seller_passport_series": "4515",
        "seller_passport_number": "123456",
        "seller_passport_issued": "ОВД Москвы, 10.05.2010",
        "seller_passport_code": "770-064",
        "seller_address": "ул. Ленина, 1",
        "buyer_name": "ООО \"Покупатель\"",
        "buyer_passport_series": "",
        "buyer_passport_number": "",
        "buyer_passport_issued": "",
        "buyer_passport_code": "",
        "buyer_address": "ул. Пушкина, 5",
        "product_name": "Ноутбук Apple MacBook Air",
        "product_unit": "шт.",
        "product_quantity": "1",
        "product_assortment": "Модель M1, 13.3 дюйма, серебристый",
        "product_price": "120000",
        "product_vat": "не облагается",
        "product_total": "120000",
        "transfer_notes": "претензий не имеется",
    }
    pdf_path = generate_pdf("act", "act_goods_transfer", data)
    print(f"PDF создан: {pdf_path}")
    print(f"Размер файла: {os.path.getsize(pdf_path)} байт")


async def test_rent_flat(dp, bot):
    # 1. Старт
    await dp.feed_update(bot, types.Update(message=make_message("/start"), update_id=200))
    print("\n=== АРЕНДА: После /start ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 2. Выбор категории Аренда
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("doc:rent"), update_id=201))
    print("\n=== АРЕНДА: После doc:rent ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 3. Выбор подвида rent_flat
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("subtype:rent:rent_flat"), update_id=202))
    print("\n=== АРЕНДА: После subtype:rent:rent_flat ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 4. Заполняем поля
    answers = [
        "г. Москва",
        "06.07.2026",
        "Иванов Иван Иванович",
        "4515",
        "123456",
        "ОВД Москвы, 10.05.2010",
        "770-064",
        "ул. Арбат, 1",
        "Петров Пётр Петрович",
        "4516",
        "654321",
        "ОВД Москвы, 15.06.2015",
        "770-065",
        "ул. Пушкина, 5",
        "квартира",
        "г. Москва, ул. Ленина, д. 10, корп. 2, кв. 50",
        "2",
        "прочерк",
        "прочерк",
        "5",
        "45",
        "12 месяцев",
        "75000",
        "75000",
    ]
    for i, value in enumerate(answers, start=203):
        bot.session.responses.clear()
        await dp.feed_update(bot, types.Update(message=make_message(value, message_id=i), update_id=i))
        print(f"\n=== АРЕНДА: После ответа {i-202} ===")
        for r in bot.session.get_responses():
            print(r["method"], repr(r.get("text", ""))[:200])

    # 5. Проверим генерацию PDF напрямую
    print("\n=== АРЕНДА: Проверка генерации PDF ===")
    data = {
        "place": "г. Москва",
        "date": "06.07.2026",
        "landlord_name": "Иванов Иван Иванович",
        "landlord_passport_series": "4515",
        "landlord_passport_number": "123456",
        "landlord_passport_issued": "ОВД Москвы, 10.05.2010",
        "landlord_passport_code": "770-064",
        "landlord_registration_address": "ул. Арбат, 1",
        "tenant_name": "Петров Пётр Петрович",
        "tenant_passport_series": "4516",
        "tenant_passport_number": "654321",
        "tenant_passport_issued": "ОВД Москвы, 15.06.2015",
        "tenant_passport_code": "770-065",
        "tenant_registration_address": "ул. Пушкина, 5",
        "rent_object": "квартира",
        "address": "г. Москва, ул. Ленина, д. 10, корп. 2, кв. 50",
        "rooms": "2",
        "room_type": "",
        "room_number": "",
        "floor": "5",
        "area": "45",
        "term": "12 месяцев",
        "rent_amount": "75000",
        "deposit": "75000",
    }
    pdf_path = generate_pdf("rent", "rent_flat", data)
    print(f"PDF создан: {pdf_path}")
    print(f"Размер файла: {os.path.getsize(pdf_path)} байт")


async def test_rent_transport(dp, bot):
    # 1. Старт
    await dp.feed_update(bot, types.Update(message=make_message("/start", message_id=300), update_id=300))
    print("\n=== АРЕНДА ТС: После /start ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 2. Выбор категории Аренда
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("doc:rent", message_id=300), update_id=301))
    print("\n=== АРЕНДА ТС: После doc:rent ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 3. Выбор подвида rent_transport
    bot.session.responses.clear()
    await dp.feed_update(bot, types.Update(callback_query=make_callback("subtype:rent:rent_transport", message_id=300), update_id=302))
    print("\n=== АРЕНДА ТС: После subtype:rent:rent_transport ===")
    for r in bot.session.get_responses():
        print(r["method"], repr(r.get("text", ""))[:200])

    # 4. Заполняем поля
    answers = [
        "г. Москва",
        "06.07.2026",
        "Иванов Иван Иванович",
        "01.01.1980",
        "4515",
        "123456",
        "ОВД Москвы, 10.05.2010",
        "770-064",
        "ул. Арбат, 1",
        "Петров Пётр Петрович",
        "05.05.1985",
        "4516",
        "654321",
        "ОВД Москвы, 15.06.2015",
        "770-065",
        "ул. Пушкина, 5",
        "Toyota Camry",
        "B",
        "Легковой автомобиль",
        "А123ВС77",
        "JTDBU4EE3B9123456",
        "2015",
        "2.5L 2AR-FE",
        "NMTBU4EE3B9123456",
        "SEDAN123",
        "Чёрный",
        "77ТС",
        "123456",
        "ГИБДД г. Москвы, 15.03.2015",
        "01.07.2026",
        "31.07.2026",
        "50000",
        "30000",
        "1",
        "1",
    ]
    for i, value in enumerate(answers, start=303):
        bot.session.responses.clear()
        await dp.feed_update(bot, types.Update(message=make_message(value, message_id=i), update_id=i))
        print(f"\n=== АРЕНДА ТС: После ответа {i-302} ===")
        for r in bot.session.get_responses():
            print(r["method"], repr(r.get("text", ""))[:200])

    # 5. Проверим генерацию PDF напрямую
    print("\n=== АРЕНДА ТС: Проверка генерации PDF ===")
    data = {
        "place": "г. Москва",
        "date": "06.07.2026",
        "landlord_name": "Иванов Иван Иванович",
        "landlord_birth_date": "01.01.1980",
        "landlord_passport_series": "4515",
        "landlord_passport_number": "123456",
        "landlord_passport_issued": "ОВД Москвы, 10.05.2010",
        "landlord_passport_code": "770-064",
        "landlord_registration_address": "ул. Арбат, 1",
        "tenant_name": "Петров Пётр Петрович",
        "tenant_birth_date": "05.05.1985",
        "tenant_passport_series": "4516",
        "tenant_passport_number": "654321",
        "tenant_passport_issued": "ОВД Москвы, 15.06.2015",
        "tenant_passport_code": "770-065",
        "tenant_registration_address": "ул. Пушкина, 5",
        "vehicle_model": "Toyota Camry",
        "vehicle_category": "B",
        "vehicle_pts_type": "Легковой автомобиль",
        "vehicle_reg_number": "А123ВС77",
        "vehicle_vin": "JTDBU4EE3B9123456",
        "vehicle_year": "2015",
        "vehicle_engine": "2.5L 2AR-FE",
        "vehicle_chassis": "NMTBU4EE3B9123456",
        "vehicle_body": "SEDAN123",
        "vehicle_color": "Чёрный",
        "vehicle_pts_series": "77ТС",
        "vehicle_pts_number": "123456",
        "vehicle_pts_issued": "ГИБДД г. Москвы, 15.03.2015",
        "contract_start_date": "01.07.2026",
        "contract_end_date": "31.07.2026",
        "rent_amount": "50000",
        "deposit": "30000",
        "late_payment_penalty": "1",
        "late_return_penalty": "1",
    }
    pdf_path = generate_pdf("rent", "rent_transport", data)
    print(f"PDF создан: {pdf_path}")
    print(f"Размер файла: {os.path.getsize(pdf_path)} байт")


async def main():
    dp = make_dp()
    bot = FakeBot()
    await test_dkp_thing(dp, bot)
    await test_act_goods_transfer(dp, bot)
    await test_rent_flat(dp, bot)
    await test_rent_transport(dp, bot)


if __name__ == "__main__":
    asyncio.run(main())
