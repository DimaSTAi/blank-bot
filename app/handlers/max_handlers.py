"""Обработчики для MAX (max.ru). Логика повторяет Telegram-версию,
но на библиотеке maxo. Общие сервисы (каталог, оплата, PDF) — те же."""
import logging

from maxo import Router
from maxo.fsm.context import FSMContext
from maxo.routing.filters.base import BaseFilter
from maxo.fsm.state import State, StatesGroup
from maxo.routing.filters import Command, Payload, StateFilter
from maxo.types.callback_button import CallbackButton
from maxo.types.bot_started import BotStarted
from maxo.types.link_button import LinkButton
from maxo.utils.upload_media import FSInputFile

from app.catalog import DOCUMENTS
from app.config import LANDING_URL
from app.legal import CONSENT_TEXT, PRIVACY_TEXT, TERMS_TEXT, start_text
from app.services.cleanup_service import cleanup_old_pdfs
from app.services.payment_service import check_payment, create_payment
from app.services.pdf_service import generate_pdf

logger = logging.getLogger(__name__)

router = Router(name="max")


class StartButtonFilter(BaseFilter):
    """Кнопка «Начать» в MAX шлёт простое сообщение «Начать», а не команду /start."""

    async def __call__(self, update, ctx) -> bool:
        text = update.text
        return bool(text) and text.strip().lower() in ("начать", "старт")


class MaxForm(StatesGroup):
    filling = State()
    confirm = State()
    payment = State()


async def _ack(update):
    """MAX требует обязательный ответ на нажатие кнопки — шлём пустое уведомление."""
    try:
        await update.callback_answer(notification="")
    except Exception:
        logger.debug("Не удалось подтвердить нажатие кнопки")


async def _save_msg_id(update, state: FSMContext, msg):
    """Запоминаем id последнего сообщения бота (вопрос/сводка) — чтобы его можно было удалить."""
    try:
        await state.update_data(bot_msg_id=msg.body.mid)
    except Exception:
        logger.debug("Не удалось сохранить id сообщения-вопроса")


async def _delete_prev(update, state: FSMContext):
    """Удаляем предыдущее сообщение бота (старый вопрос) — без него чат чистый,
    переписка идёт естественно: ответ пользователя, ниже новый вопрос."""
    data = await state.get_data()
    mid = data.get("bot_msg_id")
    if not mid:
        return
    try:
        await update.bot.delete_message(message_id=mid)
    except Exception as e:
        logger.debug("Не удалось удалить сообщение %s: %s", mid, e)


# --- Клавиатуры (те же названия кнопок, что и в Telegram) ---

def _main_menu():
    rows = []
    for key, doc in DOCUMENTS.items():
        rows.append([CallbackButton(payload=f"doc:{key}", text=f"{doc['icon']} {doc['name']}")])
    rows.append([CallbackButton(payload="show_legal", text="📄 Оферта / Политика / Согласие")])
    rows.append([LinkButton(text="🌐 Наш сайт", url=LANDING_URL)])
    return rows


def _subtypes_keyboard(doc_key: str):
    doc = DOCUMENTS[doc_key]
    rows = [
        [CallbackButton(payload=f"subtype:{doc_key}:{sub_key}", text=sub["name"])]
        for sub_key, sub in doc["subtypes"].items()
    ]
    rows.append([CallbackButton(payload="menu", text="◀️ Назад")])
    return rows


def _legal_keyboard():
    return [
        [CallbackButton(payload="show_terms", text="📄 Публичная оферта")],
        [CallbackButton(payload="show_privacy", text="🔒 Политика конфиденциальности")],
        [CallbackButton(payload="show_consent", text="✅ Согласие на обработку данных")],
        [LinkButton(text="🌐 Наш сайт", url=LANDING_URL)],
        [CallbackButton(payload="menu", text="◀️ Назад")],
    ]


def _legal_menu_keyboard():
    return [
        [CallbackButton(payload="show_terms", text="📄 Публичная оферта")],
        [CallbackButton(payload="show_privacy", text="🔒 Политика конфиденциальности")],
        [CallbackButton(payload="show_consent", text="✅ Согласие на обработку данных")],
        [CallbackButton(payload="menu", text="◀️ Назад")],
    ]


def _restart_keyboard():
    return [[CallbackButton(payload="menu", text="📁 Другой документ")]]


def _back_keyboard():
    return [
        [CallbackButton(payload="back_step", text="◀️ Назад")],
        [CallbackButton(payload="menu", text="📁 В основное меню")],
    ]


# --- Нажатия на кнопки (Payload = разбивка «сообщение кнопки» на поля) ---

class DocPayload(Payload, prefix="doc"):
    key: str


class SubtypePayload(Payload, prefix="subtype"):
    doc_key: str
    subtype_key: str


class MenuPayload(Payload, prefix="menu"):
    pass


class PayPayload(Payload, prefix="pay"):
    pass


class CheckPaymentPayload(Payload, prefix="check_payment"):
    pass


class ShowLegalPayload(Payload, prefix="show_legal"):
    pass


class ShowTermsPayload(Payload, prefix="show_terms"):
    pass


class ShowPrivacyPayload(Payload, prefix="show_privacy"):
    pass


class ShowConsentPayload(Payload, prefix="show_consent"):
    pass


class BackStepPayload(Payload, prefix="back_step"):
    pass


class BackLastPayload(Payload, prefix="back_last"):
    pass


@router.message_created(Command("start"))
async def start_handler(update, state: FSMContext):
    await state.clear()
    cleanup_old_pdfs()
    await update.answer_text(start_text(restart_hint="набери «Начать» или /start"), keyboard=_main_menu())


@router.message_created(StartButtonFilter())
async def start_button_handler(update, state: FSMContext):
    await state.clear()
    await update.answer_text(start_text(restart_hint="набери «Начать» или /start"), keyboard=_main_menu())


@router.message_created(StateFilter(None))
async def fallback_handler(update, state: FSMContext):
    # В веб-версии MAX кнопка «Начать» шлёт служебное сообщение без текста.
    # Плюс на любой посторонний текст вне диалога отвечаем меню, чтобы бот не молчал.
    await state.clear()
    if update.text is None:
        await update.answer_text(start_text(restart_hint="набери «Начать» или /start"), keyboard=_main_menu())
    else:
        await update.answer_text(
            "Не понял. Чтобы начать заново, нажми «Начать» или выбери документ в меню.",
            keyboard=_main_menu(),
        )


@router.bot_started()
async def bot_started_handler(update: BotStarted, state: FSMContext):
    # Событие bot_started: нажатие «Начать» в веб-версии MAX приходит именно им.
    await state.clear()
    await update.send_message(text=start_text(restart_hint="набери «Начать» или /start"), keyboard=_main_menu())


@router.message_created(Command("terms"))
async def terms_handler(update):
    await update.answer_text(TERMS_TEXT, keyboard=_legal_keyboard())


@router.message_created(Command("privacy"))
async def privacy_handler(update):
    await update.answer_text(PRIVACY_TEXT, keyboard=_legal_keyboard())


@router.message_created(Command("consent"))
async def consent_handler(update):
    await update.answer_text(CONSENT_TEXT, keyboard=_legal_keyboard())


@router.message_callback(ShowTermsPayload.filter())
async def show_terms_handler(update):
    try:
        await update.edit_message(text=TERMS_TEXT, keyboard=_legal_keyboard())
    except Exception:
        await update.answer_text(TERMS_TEXT, keyboard=_legal_keyboard())
    await _ack(update)


@router.message_callback(ShowPrivacyPayload.filter())
async def show_privacy_handler(update):
    try:
        await update.edit_message(text=PRIVACY_TEXT, keyboard=_legal_keyboard())
    except Exception:
        await update.answer_text(PRIVACY_TEXT, keyboard=_legal_keyboard())
    await _ack(update)


@router.message_callback(ShowConsentPayload.filter())
async def show_consent_handler(update):
    try:
        await update.edit_message(text=CONSENT_TEXT, keyboard=_legal_keyboard())
    except Exception:
        await update.answer_text(CONSENT_TEXT, keyboard=_legal_keyboard())
    await _ack(update)


@router.message_callback(ShowLegalPayload.filter())
async def show_legal_handler(update):
    try:
        await update.edit_message(
            text="📄 Юридическая информация:\n\nВыбери документ:",
            keyboard=_legal_menu_keyboard(),
        )
    except Exception:
        await update.answer_text(
            text="📄 Юридическая информация:\n\nВыбери документ:",
            keyboard=_legal_menu_keyboard(),
        )
    await _ack(update)


@router.message_callback(MenuPayload.filter())
async def main_menu_handler(update, state: FSMContext):
    await _delete_prev(update, state)
    await state.clear()
    try:
        await update.edit_message("Выбери документ из каталога:", keyboard=_main_menu())
    except Exception:
        await update.answer_text("Выбери документ из каталога:", keyboard=_main_menu())
    await _ack(update)


@router.message_callback(DocPayload.filter())
async def doc_handler(update, payload: DocPayload, state: FSMContext):
    doc = DOCUMENTS[payload.key]
    await state.update_data(doc_key=payload.key)
    await update.edit_message(
        f"{doc['icon']} {doc['name']}\n\nВыбери подвид документа:",
        keyboard=_subtypes_keyboard(payload.key),
    )
    await _ack(update)


@router.message_callback(SubtypePayload.filter())
async def subtype_handler(update, payload: SubtypePayload, state: FSMContext):
    subtype = DOCUMENTS[payload.doc_key]["subtypes"][payload.subtype_key]
    fields = subtype["fields"]

    await state.update_data(
        doc_key=payload.doc_key,
        subtype_key=payload.subtype_key,
        fields=fields,
        answers={},
        current_field_index=0,
        price=subtype["price"],
    )

    intro = ""
    if payload.doc_key == "receipt" and payload.subtype_key == "receipt_debt":
        intro = (
            "Долговая расписка — это документ, который подтверждает: "
            "заёмщик получил деньги у кредитора и обязуется их вернуть. "
            "Используется как доказательство сделки займа.\n\n"
        )
    if payload.doc_key == "receipt" and payload.subtype_key == "receipt_return":
        intro = (
            "Расписка о возврате долга подтверждает: "
            "должник передал деньги кредитору, и долг считается погашенным. "
            "Служит доказательством при спорах.\n\n"
        )

    msg = await update.answer_text(
        f"📄 {subtype['name']}\n\nСтоимость: {subtype['price']} ₽\n\n"
        f"{intro}Ответь на вопросы. Первый вопрос:\n\n{fields[0]['label']}",
        keyboard=_back_keyboard(),
    )
    await _save_msg_id(update, state, msg)
    await state.set_state(MaxForm.filling)
    await _ack(update)


@router.message_created(StateFilter(MaxForm.filling))
async def filling_handler(update, state: FSMContext):
    if update.text is None:
        return

    data = await state.get_data()
    fields = data["fields"]
    answers = data["answers"]
    index = data["current_field_index"]

    field = fields[index]
    answers[field["key"]] = update.text
    index += 1

    if index < len(fields):
        await state.update_data(answers=answers, current_field_index=index)
        await _delete_prev(update, state)
        msg = await update.answer_text(fields[index]["label"], keyboard=_back_keyboard())
        await _save_msg_id(update, state, msg)
    else:
        await state.update_data(answers=answers, current_field_index=index)
        await _show_summary(update, state)


@router.message_callback(StateFilter(MaxForm.filling), BackStepPayload.filter())
async def back_step_handler(update, state: FSMContext):
    data = await state.get_data()
    fields = data.get("fields")
    index = data.get("current_field_index")

    if not fields or index is None:
        await update.answer_text("Диалог сброшен. Чтобы начать заново, нажми «Начать».", keyboard=_main_menu())
        await _ack(update)
        return
    if index == 0:
        await update.answer_text("◀️ Это первый вопрос — назад некуда. Ответь на него текстом.")
        await _ack(update)
        return

    index -= 1
    await state.update_data(current_field_index=index)
    await _delete_prev(update, state)
    msg = await update.answer_text(fields[index]["label"], keyboard=_back_keyboard())
    await _save_msg_id(update, state, msg)
    await _ack(update)


@router.message_callback(StateFilter(MaxForm.confirm), BackLastPayload.filter())
async def back_last_handler(update, state: FSMContext):
    data = await state.get_data()
    fields = data.get("fields")

    if not fields:
        await update.answer_text("Диалог сброшен. Чтобы начать заново, нажми «Начать».", keyboard=_main_menu())
        await _ack(update)
        return

    index = len(fields) - 1
    await state.update_data(current_field_index=index)
    await state.set_state(MaxForm.filling)
    await _delete_prev(update, state)
    msg = await update.answer_text(fields[index]["label"], keyboard=_back_keyboard())
    await _save_msg_id(update, state, msg)
    await _ack(update)


async def _show_summary(update, state: FSMContext):
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

    await _delete_prev(update, state)
    msg = await update.answer_text(
        summary,
        keyboard=[
            [CallbackButton(payload="pay", text="✅ Оплатить")],
            [CallbackButton(payload="back_last", text="◀️ Назад")],
            [CallbackButton(payload="menu", text="◀️ Назад к каталогу")],
        ],
    )
    await _save_msg_id(update, state, msg)
    await state.set_state(MaxForm.confirm)


@router.message_callback(PayPayload.filter())
async def pay_handler(update, payload: PayPayload, state: FSMContext):
    data = await state.get_data()
    doc_key = data["doc_key"]
    subtype_key = data["subtype_key"]
    price = data["price"]
    subtype_name = DOCUMENTS[doc_key]["subtypes"][subtype_key]["name"]

    try:
        payment_id, url = await create_payment(
            amount=price,
            description=f"Бланк-бот: {subtype_name}",
            metadata={
                "max_user_id": str(update.callback.user.user_id),
                "doc_key": doc_key,
                "subtype_key": subtype_key,
            },
        )
        await state.update_data(payment_id=payment_id)
        logger.info("Создан платёж %s для MAX-пользователя %s", payment_id, update.callback.user.user_id)
        await update.edit_message(
            f"💳 Для получения документа оплатите {price} ₽:\n\n{url}\n\n"
            f"После оплаты нажми кнопку «Проверить оплату».",
            keyboard=[
                [LinkButton(text="💳 Оплатить в браузере", url=url)],
                [CallbackButton(payload="check_payment", text="🔍 Проверить оплату")],
            ],
        )
        await state.set_state(MaxForm.payment)
    except Exception as e:
        logger.exception("Ошибка создания платежа (MAX): %s", e)
        await update.answer_text(f"Ошибка при создании платежа: {e}")
    await _ack(update)


@router.message_callback(CheckPaymentPayload.filter())
async def check_payment_handler(update, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    answers = data["answers"]
    doc_key = data["doc_key"]
    subtype_key = data["subtype_key"]

    try:
        status = await check_payment(payment_id)
        if status == "succeeded":
            cleanup_old_pdfs()
            pdf_path = generate_pdf(doc_key, subtype_key, answers)
            await update.edit_message("✅ Оплата прошла! Отправляю твой документ...")
            await update.send_media(
                media=[FSInputFile.file(pdf_path)],
                text=(
                    "Вот твой готовый документ. Распечатывай и подписывай. "
                    "Персональные данные удалятся через 3 дня."
                ),
                keyboard=_restart_keyboard(),
            )
            await state.clear()
        elif status in ("pending", "waiting_for_capture"):
            await update.callback_answer(text="Платёж ещё обрабатывается. Попробуй через несколько секунд.")
        else:
            await update.callback_answer(text=f"Платёж не прошёл. Статус: {status}")
    except Exception as e:
        logger.exception("Ошибка проверки платежа (MAX): %s", e)
        await update.callback_answer(text=f"Ошибка проверки: {e}")