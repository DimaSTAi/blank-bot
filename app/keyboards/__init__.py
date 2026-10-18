from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.catalog import DOCUMENTS
from app.config import LANDING_URL


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, doc in DOCUMENTS.items():
        buttons.append([InlineKeyboardButton(
            text=f"{doc['icon']} {doc['name']}",
            callback_data=f"doc:{key}"
        )])
    buttons.append([InlineKeyboardButton(
        text="📄 Оферта / Политика / Согласие",
        callback_data="show_legal"
    )])
    buttons.append([InlineKeyboardButton(
        text="🌐 Наш сайт",
        url=LANDING_URL
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subtypes_keyboard(doc_key: str) -> InlineKeyboardMarkup:
    doc = DOCUMENTS[doc_key]
    buttons = []
    for sub_key, sub in doc["subtypes"].items():
        buttons.append([InlineKeyboardButton(
            text=sub["name"],
            callback_data=f"subtype:{doc_key}:{sub_key}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", callback_data="pay")],
        [InlineKeyboardButton(text="◀️ Назад к каталогу", callback_data="main_menu")],
    ])


def restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Другой документ", callback_data="main_menu")],
    ])
