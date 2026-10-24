from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from app.states import Form
from app.keyboards import main_menu_keyboard, subtypes_keyboard, confirm_keyboard, restart_keyboard, back_keyboard
from app.catalog import DOCUMENTS
from app.services.payment_service import create_payment, check_payment, new_idempotence_key
from app.services.pdf_service import generate_pdf
from app.services.cleanup_service import cleanup_old_pdfs
from app.legal import start_text, TERMS_TEXT, PRIVACY_TEXT, CONSENT_TEXT, legal_keyboard

router = Router()


@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    cleanup_old_pdfs()
    await message.answer(
        start_text(),
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(Form.choosing_doc)


@router.message(Command("terms"))
async def terms_handler(message: types.Message):
    await message.answer(TERMS_TEXT, reply_markup=legal_keyboard())


@router.message(Command("privacy"))
async def privacy_handler(message: types.Message):
    await message.answer(PRIVACY_TEXT, reply_markup=legal_keyboard())


@router.message(Command("consent"))
async def consent_handler(message: types.Message):
    await message.answer(CONSENT_TEXT, reply_markup=legal_keyboard())


@router.callback_query(F.data == "show_terms")
async def show_terms_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(TERMS_TEXT, reply_markup=legal_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_privacy")
async def show_privacy_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(PRIVACY_TEXT, reply_markup=legal_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_consent")
async def show_consent_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(CONSENT_TEXT, reply_markup=legal_keyboard())
    await callback.answer()


@router.callback_query(F.data == "show_legal")
async def show_legal_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📄 Юридическая информация:\n\n"
        "• /terms — публичная оферта\n"
        "• /privacy — политика конфиденциальности\n"
        "• /consent — согласие на обработку персональных данных",
        reply_markup=legal_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Выбери документ из каталога:",
        reply_markup=main_menu_keyboard(),
    )
    await state.set_state(Form.choosing_doc)
    await callback.answer()


@router.callback_query(F.data.startswith("doc:"))
async def doc_handler(callback: types.CallbackQuery, state: FSMContext):
    doc_key = callback.data.split(":")[1]
    doc = DOCUMENTS[doc_key]
    await callback.message.edit_text(
        f"{doc['icon']} {doc['name']}\n\nВыбери подвид документа:",
        reply_markup=subtypes_keyboard(doc_key),
    )
    await state.set_state(Form.choosing_subtype)
    await state.update_data(doc_key=doc_key)
    await callback.answer()


@router.callback_query(F.data.startswith("subtype:"))
async def subtype_handler(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    doc_key = parts[1]
    subtype_key = parts[2]
    subtype = DOCUMENTS[doc_key]["subtypes"][subtype_key]
    fields = subtype["fields"]

    await state.update_data(
        doc_key=doc_key,
        subtype_key=subtype_key,
        fields=fields,
        answers={},
        current_field_index=0,
        price=subtype["price"],
    )

    intro = ""
    if doc_key == "receipt" and subtype_key == "receipt_debt":
        intro = (
            "Долговая расписка — это документ, который подтверждает: "
            "заёмщик получил деньги у кредитора и обязуется их вернуть. "
            "Используется как доказательство сделки займа.\n\n"
        )
    if doc_key == "receipt" and subtype_key == "receipt_return":
        intro = (
            "Расписка о возврате долга подтверждает: "
            "должник передал деньги кредитору, и долг считается погашенным. "
            "Служит доказательством при спорах.\n\n"
        )

    await callback.message.edit_text(
        f"📄 {subtype['name']}\n\nСтоимость: {subtype['price']} ₽\n\n"
        f"{intro}Ответь на вопросы. Первый вопрос:\n\n{fields[0]['label']}",
        reply_markup=back_keyboard(),
    )
    await state.set_state(Form.filling)
    await callback.answer()


@router.message(Form.filling)
async def filling_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("fields"):
        await state.clear()
        await message.answer("Сессия сброшена. Начни заново: /start", reply_markup=main_menu_keyboard())
        return

    fields = data["fields"]
    answers = data["answers"]
    index = data["current_field_index"]

    field = fields[index]
    answers[field["key"]] = message.text
    index += 1

    if index < len(fields):
        next_field = fields[index]
        await state.update_data(answers=answers, current_field_index=index)
        await message.answer(f"{next_field['label']}", reply_markup=back_keyboard())
    else:
        await state.update_data(answers=answers, current_field_index=index)
        await _show_summary(message, state)


@router.callback_query(F.data == "back_step")
async def back_step_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fields = data.get("fields")
    index = data.get("current_field_index")

    if not fields or index is None:
        await callback.answer("Диалог сброшен. Начни заново: /start", show_alert=True)
        return
    if index == 0:
        await callback.answer("Это первый вопрос, назад некуда", show_alert=True)
        return

    index -= 1
    await state.update_data(current_field_index=index)
    await callback.message.answer(
        f"{fields[index]['label']}",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "back_last")
async def back_last_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fields = data.get("fields")

    if not fields:
        await callback.answer("Диалог сброшен. Начни заново: /start", show_alert=True)
        return

    index = len(fields) - 1
    await state.update_data(current_field_index=index)
    await state.set_state(Form.filling)
    await callback.message.answer(
        f"{fields[index]['label']}",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


async def _show_summary(message: types.Message, state: FSMContext):
    data = await state.get_data()
    answers = data["answers"]
    doc_key = data["doc_key"]
    subtype_key = data["subtype_key"]
    price = data["price"]
    subtype_name = DOCUMENTS[doc_key]["subtypes"][subtype_key]["name"]

    summary = f"📄 {DOCUMENTS[doc_key]['name']} — {subtype_name}\n\n"
    for field in DOCUMENTS[doc_key]["subtypes"][subtype_key]["fields"]:
        summary += f"• {field['label']}: {answers.get(field['key'], '-')}\n"
    summary += f"\n💰 Стоимость: {price} ₽\n\nВсё верно?"

    await message.answer(summary, reply_markup=confirm_keyboard())
    await state.set_state(Form.confirm)


@router.callback_query(F.data == "pay")
async def pay_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # мгновенная реакция кнопки, пока создаётся платёж
    data = await state.get_data()
    if not data.get("doc_key"):
        await callback.answer("Сессия сброшена. Начни заново: /start", show_alert=True)
        return
    doc_key = data["doc_key"]
    subtype_key = data["subtype_key"]
    price = data["price"]
    subtype_name = DOCUMENTS[doc_key]["subtypes"][subtype_key]["name"]

    try:
        idem_key = data.get("idem_key")
        if not idem_key:
            # Сохраняем ДО запроса: если ответ потерялся по таймауту,
            # повторный клик «Оплатить» вернёт тот же платёж по ключу
            idem_key = new_idempotence_key()
            await state.update_data(idem_key=idem_key)
        payment_id, url = await create_payment(
            amount=price,
            description=f"Бланк-бот: {subtype_name}",
            metadata={
                "telegram_user_id": str(callback.from_user.id),
                "doc_key": doc_key,
                "subtype_key": subtype_key,
            },
        )
        await state.update_data(payment_id=payment_id)
        await callback.message.edit_text(
            f"💳 Для получения документа оплатите {price} ₽ по ссылке:\n\n{url}\n\n"
            f"⚠️ Если оплата не открывается — выключи VPN и попробуй снова.\n\n"
            f"После оплаты нажми кнопку «Проверить оплату» и получи готовый документ.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔍 Проверить оплату", callback_data="check_payment")],
            ]),
        )
        await state.set_state(Form.payment)
    except Exception as e:
        await callback.message.edit_text(f"Ошибка при создании платежа: {e}")


@router.callback_query(F.data == "check_payment")
async def check_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    answers = data.get("answers")
    doc_key = data.get("doc_key")
    subtype_key = data.get("subtype_key")

    if not payment_id or not answers:
        # Платёж мог создаться, а ответ потеряться по таймауту — восстанавливаем
        # его по ключу идемпотентности
        if not payment_id and answers and doc_key and subtype_key and data.get("idem_key"):
            try:
                subtype = DOCUMENTS[doc_key]["subtypes"][subtype_key]
                payment_id, url = await create_payment(
                    amount=data["price"],
                    description=f"Бланк-бот: {subtype['name']}",
                    metadata={
                        "telegram_user_id": str(callback.from_user.id),
                        "doc_key": doc_key,
                        "subtype_key": subtype_key,
                    },
                    idempotence_key=data["idem_key"],
                )
                await state.update_data(payment_id=payment_id)
            except Exception:
                pass
        if not payment_id:
            await callback.answer("Сессия сброшена. Начни заново: /start", show_alert=True)
            return

    try:
        status = await check_payment(payment_id)
        if status == "succeeded":
            cleanup_old_pdfs()
            pdf_path = generate_pdf(doc_key, subtype_key, answers)
            await callback.message.edit_text("✅ Оплата прошла! Отправляю твой документ...")
            await callback.message.answer_document(
                document=types.FSInputFile(pdf_path),
                caption="Вот твой готовый документ. Распечатывай и подписывай. "
                        "Персональные данные удалятся через 3 дня.",
                reply_markup=restart_keyboard(),
            )
            await state.clear()
        elif status in ("pending", "waiting_for_capture"):
            await callback.answer("Платёж ещё обрабатывается. Попробуй через несколько секунд.", show_alert=True)
        else:
            # Платёж отменён/не прошёл — освобождаем, чтобы «Оплатить» создал новый.
            # Ключ тоже сбрасываем: он навсегда указывает на отменённый платёж
            await state.update_data(payment_id=None, idem_key=None)
            await callback.answer(f"Платёж не прошёл. Статус: {status}", show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка проверки: {e}", show_alert=True)
    await callback.answer()
