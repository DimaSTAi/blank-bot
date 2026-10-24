import os
import html
import shutil
from datetime import datetime
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader, PdfWriter

from app.config import DEFAULT_CURRENCY

FONTS_DIR = "app/static/fonts"

_MONTHS = {
    "01": "января", "02": "февраля", "03": "марта", "04": "апреля",
    "05": "мая", "06": "июня", "07": "июля", "08": "августа",
    "09": "сентября", "10": "октября", "11": "ноября", "12": "декабря",
}


def _format_date(date_str: str) -> tuple[str, str, str]:
    """Разбивает строку даты DD.MM.YYYY на (день, месяц_прописью, год)."""
    try:
        day, month, year = date_str.split(".")
        return day, _MONTHS.get(month, month), year
    except Exception:
        return "", "", ""


def _ensure_fonts():
    if not os.path.isdir(FONTS_DIR):
        os.makedirs(FONTS_DIR, exist_ok=True)

    # Если шрифты уже лежат в проекте (например, в Docker), ничего не копируем.
    existing = {
        "arial.ttf": os.path.join(FONTS_DIR, "arial.ttf"),
        "arialbd.ttf": os.path.join(FONTS_DIR, "arialbd.ttf"),
    }
    if all(os.path.exists(p) for p in existing.values()):
        return

    # Fallback: пытаемся скопировать из Windows на машине разработчика.
    sources = [
        ("C:\\Windows\\Fonts\\arial.ttf", existing["arial.ttf"]),
        ("C:\\Windows\\Fonts\\arialbd.ttf", existing["arialbd.ttf"]),
    ]
    for src, dst in sources:
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy(src, dst)
            except Exception:
                pass


def _register_fonts():
    _ensure_fonts()
    fonts = {
        "Arial": os.path.join(FONTS_DIR, "arial.ttf"),
        "ArialBold": os.path.join(FONTS_DIR, "arialbd.ttf"),
    }
    for name, path in fonts.items():
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass


def _pdf_path(doc_key: str, subtype_key: str, data: dict) -> str:
    date = data.get("date", datetime.now().strftime("%d.%m.%Y"))
    return f"app/data/{doc_key}_{subtype_key}_{date}.pdf"


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Arial", fontName="Arial", fontSize=11, leading=15, alignment=0))
    styles.add(ParagraphStyle(name="ArialCenter", fontName="Arial", fontSize=11, leading=15, alignment=1))
    styles.add(ParagraphStyle(name="ArialBoldCenter", fontName="ArialBold", fontSize=14, leading=18, alignment=1))
    styles.add(ParagraphStyle(name="ArialBold", fontName="ArialBold", fontSize=11, leading=15, alignment=0))
    styles.add(ParagraphStyle(name="ArialSmall", fontName="Arial", fontSize=9, leading=12, alignment=0, textColor=colors.grey))
    styles.add(ParagraphStyle(name="ArialSmallCenter", fontName="Arial", fontSize=9, leading=12, alignment=1, textColor=colors.grey))
    return styles


def _safe_data(data: dict) -> dict:
    return {k: html.escape(str(v)) for k, v in data.items()}


def _sign_table(data: dict, left_label: str, left_key: str, right_label: str, right_key: str, styles, left_phone_key: str = None, right_phone_key: str = None):
    left_phone = f"<br/>тел.: {data.get(left_phone_key, '')}" if left_phone_key and data.get(left_phone_key) else ""
    right_phone = f"<br/>тел.: {data.get(right_phone_key, '')}" if right_phone_key and data.get(right_phone_key) else ""
    sign_data = [
        [
            Paragraph(f"<b>{left_label}</b><br/>________________ / {data.get(left_key, '')}{left_phone}", styles["Arial"]),
            Paragraph(f"<b>{right_label}</b><br/>________________ / {data.get(right_key, '')}{right_phone}", styles["Arial"]),
        ],
    ]
    table = Table(sign_data, colWidths=[8 * cm, 8 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _header(story, title, city, date, styles):
    story.append(Paragraph(title, styles["ArialBoldCenter"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"г. {city} «{date}»", styles["ArialCenter"]))
    story.append(Spacer(1, 16))


def _paragraph(story, text, styles, bold_prefix: str = None):
    if bold_prefix:
        text = f"<b>{bold_prefix}</b> {text}"
    story.append(Paragraph(text, styles["Arial"]))


def _section_title(story, text, styles):
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>{text}</b>", styles["ArialBold"]))


def generate_pdf(doc_key: str, subtype_key: str, data: dict) -> str:
    _register_fonts()
    output_path = _pdf_path(doc_key, subtype_key, data)
    styles = _styles()
    safe = _safe_data(data)
    city = safe.get("city", "")
    date = safe.get("date", "")

    if doc_key == "dkp":
        if subtype_key == "dkp_vehicle":
            return _dkp_vehicle_pdf(output_path, safe, styles)
        if subtype_key == "dkp_spec":
            return _dkp_spec_pdf(output_path, safe, styles)
        if subtype_key == "dkp_thing":
            return _dkp_thing_pdf(output_path, safe, styles)
        return _fallback_pdf(doc_key, subtype_key, data)
    if doc_key == "rent":
        return _rent_pdf(output_path, subtype_key, city, date, safe, styles)
    if doc_key == "receipt":
        return _receipt_pdf(output_path, subtype_key, city, date, safe, styles)
    if doc_key == "claim" and subtype_key == "claim_product":
        return _claim_product_pdf(output_path, city, date, safe, styles)
    if doc_key == "act":
        if subtype_key == "act_goods_transfer":
            return _act_goods_transfer_pdf(output_path, safe, styles)
        return _act_default_pdf(output_path, safe, styles)
    if doc_key == "gift" and subtype_key == "gift_default":
        return _gift_default_pdf(output_path, city, date, safe, styles)

    return _fallback_pdf(doc_key, subtype_key, data)


def _dkp_vehicle_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialDoc", fontName="Arial", fontSize=10, leading=12, alignment=0)
    bold = ParagraphStyle(name="ArialDocBold", fontName="ArialBold", fontSize=10, leading=12, alignment=0)
    center_bold = ParagraphStyle(name="ArialDocBoldCenter", fontName="ArialBold", fontSize=11, leading=14, alignment=1)
    small_center = ParagraphStyle(name="ArialSmallCenterDoc", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")

    story = []

    # Шапка: дата слева, место справа
    header_data = [
        [
            Paragraph(f"«{day}» {month} {year} года", normal),
            Paragraph(f"г. {place}", normal),
        ],
        [
            Paragraph("(дата)", small_center),
            Paragraph("(город)", small_center),
        ],
    ]
    header_table = Table(header_data, colWidths=[7 * cm, 9.7 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("ДОГОВОР КУПЛИ-ПРОДАЖИ ТРАНСПОРТНОГО СРЕДСТВА", center_bold))
    story.append(Spacer(1, 12))

    def _party_lines(prefix):
        name = data.get(prefix + "_name", "")
        birth = data.get(prefix + "_birth_date", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        residence = data.get(prefix + "_residence_address", "")
        reg = data.get(prefix + "_registration_address", "")
        return [
            f"гр. {name}, проживающий(ая) по адресу {residence}, зарегистрированный(ая) по адресу {reg},",
            f"дата рождения: {birth},",
            f"паспорт: серия {ps} № {pn}, выдан {pi}, код подразделения {pc},",
        ]

    seller_lines = _party_lines("seller")
    buyer_lines = _party_lines("buyer")
    for line in seller_lines:
        story.append(Paragraph(line, normal))
    story.append(Paragraph("именуемый(ая) в дальнейшем \"Продавец\",", normal))
    story.append(Spacer(1, 4))
    for line in buyer_lines:
        story.append(Paragraph(line, normal))
    story.append(Paragraph("именуемый(ая) в дальнейшем \"Покупатель\", заключили настоящий договор о нижеследующем:", normal))
    story.append(Spacer(1, 8))

    # 1. Предмет договора
    story.append(Paragraph(
        "1. Продавец передаёт в собственность покупателя (продаёт), а Покупатель принимает (покупает) и оплачивает транспортное средство:",
        normal
    ))

    ts_rows = [
        [Paragraph("Марка, модель ТС:", normal), Paragraph(data.get("vehicle_model", ""), normal)],
        [Paragraph("Идентификационный номер (VIN):", normal), Paragraph(data.get("vehicle_vin", ""), normal)],
        [Paragraph("Год выпуска:", normal), Paragraph(data.get("vehicle_year", ""), normal)],
        [Paragraph("№ двигателя:", normal), Paragraph(data.get("vehicle_engine_number", ""), normal)],
        [Paragraph("№ рамы:", normal), Paragraph(data.get("vehicle_frame_number", ""), normal)],
        [Paragraph("Цвет:", normal), Paragraph(data.get("vehicle_color", ""), normal)],
        [Paragraph("Пробег:", normal), Paragraph(data.get("vehicle_mileage", ""), normal)],
        [Paragraph("Государственный регистрационный знак:", normal), Paragraph(data.get("vehicle_reg_number", ""), normal)],
        [Paragraph("Свидетельство о регистрации ТС (СТС):", normal), Paragraph(data.get("vehicle_sts", ""), normal)],
        [Paragraph("Выдано:", normal), Paragraph(data.get("vehicle_sts_issued", ""), normal)],
    ]
    ts_table = Table(ts_rows, colWidths=[7.5 * cm, 9.2 * cm])
    ts_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(ts_table)
    story.append(Spacer(1, 6))

    pts_day, pts_month, pts_year = _format_date(data.get("vehicle_pts_issued_date", ""))
    story.append(Paragraph(
        f"2. Указанное в п. 1 транспортное средство принадлежит Продавцу на праве собственности, что подтверждает паспорт транспортного средства, "
        f"серии {data.get('vehicle_pts_series', '')} № {data.get('vehicle_pts_number', '')}, выданный «{pts_day}» {pts_month} {pts_year} года, "
        f"{data.get('vehicle_pts_issued', '')}.",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "3. Со слов Продавца отчуждаемое транспортное средство никому не продано, не заложено, в споре и под запрещением (арестом) не состоит.",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "3.1. Продавец гарантирует, что на дату заключения настоящего договора указанное в п. 1 транспортное средство принадлежит ему на законном основании, свободно от права третьих лиц, никому не продано, не заложено, в споре и под арестом (запрещением) не состоит, ограничения в пользовании отсутствуют.",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "3.2. Настоящий договор вступает в силу с момента подписания и составлен в трёх экземплярах, имеющих равную юридическую силу. Настоящий договор действует до полного исполнения сторонами принятых на себя обязательств.",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"4. Стоимость указанного в п. 1 транспортного средства составляет: {data.get('price', '')} руб. ({data.get('price_words', '')}).",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"5. Покупатель в оплату за транспортное средство передал Продавцу {data.get('price', '')} руб. ({data.get('price_words', '')}).",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "6. Право собственности на транспортное средство, указанное в п. 1 договора, переходит к Покупателю с момента подписания настоящего договора.",
        normal
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "7. Покупатель подтверждает, что ознакомлен с техническим состоянием транспортного средства, осмотрел его и претензий не имеет.",
        normal
    ))
    story.append(Spacer(1, 8))

    # Подписи
    sign_data = [
        [Paragraph("Продавец", bold), Paragraph("Покупатель", bold)],
        [Paragraph("Деньги получил, транспортное средство передал.", normal), Paragraph("Деньги передал, транспортное средство получил.", normal)],
        [Paragraph(f"________________ / {data.get('seller_name', '')}", normal), Paragraph(f"________________ / {data.get('buyer_name', '')}", normal)],
        [Paragraph(f"(подпись / Ф.И.О.)<br/>Тел. {data.get('seller_phone', '')}", small_center), Paragraph(f"(подпись / Ф.И.О.)<br/>Тел. {data.get('buyer_phone', '')}", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _gift_default_pdf(output_path: str, city: str, date: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)

    normal = ParagraphStyle(name="ArialGift", fontName="Arial", fontSize=11, leading=15, alignment=0)
    bold = ParagraphStyle(name="ArialGiftBold", fontName="ArialBold", fontSize=11, leading=15, alignment=0)
    center_bold = ParagraphStyle(name="ArialGiftBoldCenter", fontName="ArialBold", fontSize=14, leading=18, alignment=1)
    small_center = ParagraphStyle(name="ArialGiftSmallCenter", fontName="Arial", fontSize=9, leading=11, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(date)

    def _person_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        return f"{name}, паспорт: серия {ps} № {pn}, выдан {pi}"

    story = []

    story.append(Paragraph("ДОГОВОР ДАРЕНИЯ", center_bold))
    story.append(Spacer(1, 12))

    header_data = [
        [
            Paragraph(f"г. {city}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        f"Я, {_person_text('donor')}, именуемый(ая) в дальнейшем «Даритель», с одной стороны, и {_person_text('donee')}, именуемый(ая) в дальнейшем «Одаряемый», с другой стороны, заключили настоящий договор о нижеследующем:",
        normal
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. Предмет договора", bold))
    story.append(Paragraph(
        f"1.1. Даритель настоящим Договором передаёт в дар Одаряемому принадлежащее ему на праве собственности имущество: {data.get('gift_name', '')}.",
        normal
    ))
    story.append(Paragraph(
        "1.2. Одаряемый принимает указанное имущество в качестве дара от Дарителя.",
        normal
    ))

    story.append(Paragraph("2. Возмещение расходов", bold))
    story.append(Paragraph(
        "2.1. Расходы, понесённые в связи с заключением настоящего Договора, оплачиваются следующим образом: каждая Сторона несёт собственные расходы.",
        normal
    ))

    story.append(Paragraph("3. Порядок вступления договора в силу", bold))
    story.append(Paragraph(
        "3.1. Настоящий Договор считается заключённым и вступает в силу со дня его подписания сторонами.",
        normal
    ))

    story.append(Paragraph("4. Прочие условия договора", bold))
    story.append(Paragraph(
        "4.1. Настоящий Договор составлен в 2-х подлинных экземплярах, по одному для каждой из Сторон.",
        normal
    ))
    story.append(Paragraph(
        "4.2. В случаях, не предусмотренных настоящим Договором, стороны руководствуются действующим законодательством Российской Федерации.",
        normal
    ))
    story.append(Paragraph(
        "4.3. После подписания настоящего Договора все предварительные переговоры по нему, переписка, предварительные соглашения и протоколы о намерениях по вопросам, так или иначе касающимся настоящего Договора, теряют юридическую силу.",
        normal
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. Адреса и реквизиты сторон", bold))
    sign_data = [
        [Paragraph("Даритель:", bold), Paragraph("Одаряемый:", bold)],
        [Paragraph(f"{data.get('donor_name', '')} ________________", normal), Paragraph(f"{data.get('donee_name', '')} ________________", normal)],
        [Paragraph("(подпись / Ф.И.О.)", small_center), Paragraph("(подпись / Ф.И.О.)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _dkp_spec_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialSpec", fontName="Arial", fontSize=10, leading=13, alignment=0)
    bold = ParagraphStyle(name="ArialSpecBold", fontName="ArialBold", fontSize=10, leading=13, alignment=0)
    center_bold = ParagraphStyle(name="ArialSpecBoldCenter", fontName="ArialBold", fontSize=13, leading=16, alignment=1)
    small_center = ParagraphStyle(name="ArialSpecSmallCenter", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")
    pts_day, pts_month, pts_year = _format_date(data.get("tech_pts_issued_date", ""))

    story = []

    # Шапка: населённый пункт слева, дата справа
    header_data = [
        [
            Paragraph(f"{place}", normal),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
        [
            Paragraph("(населённый пункт)", small_center),
            Paragraph("(число и месяц прописью)", small_center),
        ],
    ]
    header_table = Table(header_data, colWidths=[7 * cm, 9.7 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("ДОГОВОР КУПЛИ-ПРОДАЖИ СПЕЦТЕХНИКИ", center_bold))
    story.append(Spacer(1, 12))

    # Стороны
    def _party_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        address = data.get(prefix + "_address", "")
        if ps and pn:
            return f"{name}, паспорт серии {ps} № {pn}, выдан {pi}, код {pc}, адрес: {address}"
        return f"{name}, адрес: {address}"

    story.append(Paragraph(f"Продавец: {_party_text('seller')}", normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Покупатель: {_party_text('buyer')}", normal))
    story.append(Spacer(1, 8))
    story.append(Paragraph("заключили настоящий договор о нижеследующем:", normal))
    story.append(Spacer(1, 8))

    # 1. Предмет договора
    story.append(Paragraph(
        "1. Продавец продаёт, а Покупатель покупает принадлежащую Продавцу на праве собственности спецтехнику:",
        normal
    ))
    story.append(Spacer(1, 4))

    tech_rows = [
        [Paragraph("спецтехнику", normal), Paragraph(data.get("tech_name", ""), normal)],
        [Paragraph("идентификационный номер", normal), Paragraph(data.get("tech_id_number", ""), normal)],
        [Paragraph("регистрационный номер", normal), Paragraph(data.get("tech_reg_number", ""), normal)],
        [Paragraph("год выпуска", normal), Paragraph(data.get("tech_year", ""), normal)],
        [Paragraph("пробег / моточасы", normal), Paragraph(data.get("tech_mileage", ""), normal)],
        [Paragraph("№ двигателя", normal), Paragraph(data.get("tech_engine_number", ""), normal)],
        [Paragraph("№ шасси", normal), Paragraph(data.get("tech_chassis_number", ""), normal)],
        [Paragraph("№ кузова (рамы)", normal), Paragraph(data.get("tech_body_number", ""), normal)],
        [Paragraph("цвет", normal), Paragraph(data.get("tech_color", ""), normal)],
        [Paragraph("тип ТС", normal), Paragraph(data.get("tech_type", ""), normal)],
    ]
    tech_table = Table(tech_rows, colWidths=[6.5 * cm, 10.2 * cm])
    tech_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 6))

    # ПТС
    story.append(Paragraph(
        f"ПТС серия {data.get('tech_pts_series', '')} № {data.get('tech_pts_number', '')}, "
        f"дата выдачи «{pts_day}» {pts_month} {pts_year} года, выдан {data.get('tech_pts_issued', '')}, "
        f"гражданину (Ф.И.О.) / наименованию организации {data.get('tech_pts_owner', '')}.",
        normal
    ))
    story.append(Spacer(1, 8))

    # 2. Цена
    story.append(Paragraph(
        f"2. Стоимость указанной в п. 1 спецтехники составляет {data.get('price', '')} руб. ({data.get('price_words', '')}).",
        normal
    ))
    story.append(Spacer(1, 4))

    # 3. Оплата
    story.append(Paragraph(
        f"3. Покупатель уплачивает Продавцу стоимость спецтехники в размере {data.get('price', '')} руб. ({data.get('price_words', '')}) в момент подписания настоящего договора.",
        normal
    ))
    story.append(Spacer(1, 4))

    # 4. Передача
    story.append(Paragraph(
        "4. Спецтехника передаётся Продавцом и принимается Покупателем в момент подписания настоящего договора. Покупатель проверил техническое состояние спецтехники и претензий не имеет.",
        normal
    ))
    story.append(Spacer(1, 4))

    # 5. Право собственности
    story.append(Paragraph(
        "5. Право собственности на спецтехнику переходит к Покупателю с момента подписания настоящего договора и оплаты его стоимости.",
        normal
    ))
    story.append(Spacer(1, 4))

    # 6. Гарантии
    story.append(Paragraph(
        "6. Продавец гарантирует, что спецтехника принадлежит ему на законном основании, свободна от прав третьих лиц, не находится в залоге, аресте, споре и под запрещением не состоит.",
        normal
    ))
    story.append(Spacer(1, 4))

    # 7. Подписи
    story.append(Paragraph("7. Подписи сторон:", normal))
    story.append(Spacer(1, 8))

    sign_data = [
        [Paragraph("Продавец", bold), Paragraph("Покупатель", bold)],
        [Paragraph("Деньги получил,<br/>спецтехнику передал.", normal), Paragraph("Деньги передал,<br/>спецтехнику получил.", normal)],
        [Paragraph(f"________________ / {data.get('seller_name', '')}", normal), Paragraph(f"________________ / {data.get('buyer_name', '')}", normal)],
        [Paragraph("(подпись и Ф.И.О. полностью)", small_center), Paragraph("(подпись и Ф.И.О. полностью)", small_center)],
        [Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center), Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _dkp_thing_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialThing", fontName="Arial", fontSize=10, leading=13, alignment=0)
    bold = ParagraphStyle(name="ArialThingBold", fontName="ArialBold", fontSize=10, leading=13, alignment=0)
    center_bold = ParagraphStyle(name="ArialThingBoldCenter", fontName="ArialBold", fontSize=13, leading=16, alignment=1)
    small = ParagraphStyle(name="ArialThingSmall", fontName="Arial", fontSize=8, leading=10, alignment=0)
    small_center = ParagraphStyle(name="ArialThingSmallCenter", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")

    story = []

    # Заголовок и дата
    story.append(Paragraph("ДОГОВОР КУПЛИ-ПРОДАЖИ ТОВАРА", center_bold))
    story.append(Spacer(1, 8))

    # Шапка
    header_data = [
        [
            Paragraph(f"{place}", normal),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
        [
            Paragraph("(населённый пункт)", small_center),
            Paragraph("(дата)", small_center),
        ],
    ]
    header_table = Table(header_data, colWidths=[7 * cm, 9.7 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    # Реквизиты сторон
    def _party_lines(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        address = data.get(prefix + "_address", "")
        if ps and pn:
            return [
                f"{name}",
                f"паспорт серии {ps} № {pn}, выдан {pi}, код {pc}",
                f"адрес: {address}",
            ]
        return [name, f"адрес: {address}"]

    seller_lines = "<br/>".join(_party_lines("seller"))
    buyer_lines = "<br/>".join(_party_lines("buyer"))

    party_data = [
        [Paragraph("Продавец:", bold), Paragraph("Покупатель:", bold)],
        [Paragraph(seller_lines, small), Paragraph(buyer_lines, small)],
    ]
    party_table = Table(party_data, colWidths=[8.35 * cm, 8.35 * cm])
    party_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(party_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Стороны заключили настоящий договор о нижеследующем:", normal))
    story.append(Spacer(1, 8))

    # 1. Предмет договора
    story.append(Paragraph("1. Предмет договора", bold))
    story.append(Paragraph(
        f"1.1. Продавец обязуется передать в собственность Покупателя, а Покупатель обязуется принять и оплатить товар: {data.get('product_name', '')}.",
        normal
    ))
    story.append(Paragraph(
        f"1.2. Вид, основные характеристики, комплектность и состояние товара: {data.get('product_description', '')}.",
        normal
    ))
    story.append(Paragraph(
        f"1.3. Количество товара: {data.get('product_quantity', '')}.",
        normal
    ))
    story.append(Spacer(1, 6))

    # 2. Цена
    story.append(Paragraph("2. Цена договора и порядок расчётов", bold))
    story.append(Paragraph(
        f"2.1. Стоимость товара, передаваемого по настоящему договору, составляет {data.get('price', '')} руб. ({data.get('price_words', '')}).",
        normal
    ))
    story.append(Paragraph(
        "2.2. Оплата товара производится Покупателем путём передачи наличных денежных средств Продавцу в момент подписания настоящего договора.",
        normal
    ))
    story.append(Spacer(1, 6))

    # 3. Передача
    story.append(Paragraph("3. Порядок передачи и принятия товара", bold))
    story.append(Paragraph(
        "3.1. Продавец передаёт товар Покупателю в момент подписания настоящего договора.",
        normal
    ))
    story.append(Paragraph(
        "3.2. Покупатель осмотрел товар, проверил его качество, комплектность и количество. Претензий к Продавцу не имеет.",
        normal
    ))
    story.append(Paragraph(
        "3.3. Право собственности на товар, а также риск случайной гибели или повреждения товара, переходят к Покупателю с момента подписания настоящего договора.",
        normal
    ))
    story.append(Spacer(1, 6))

    # 4. Гарантии
    story.append(Paragraph("4. Гарантии сторон", bold))
    story.append(Paragraph(
        "4.1. Продавец гарантирует, что товар принадлежит ему на законном основании, свободен от прав третьих лиц, не находится в залоге, аресте, споре и под запрещением не состоит.",
        normal
    ))
    story.append(Paragraph(
        "4.2. Стороны руководствуются действующим законодательством Российской Федерации.",
        normal
    ))
    story.append(Spacer(1, 6))

    # 5. Заключительные положения
    story.append(Paragraph("5. Заключительные положения", bold))
    story.append(Paragraph(
        "5.1. Настоящий договор составлен в двух экземплярах, имеющих равную юридическую силу, по одному для каждой из сторон.",
        normal
    ))
    story.append(Spacer(1, 12))

    # Подписи
    sign_data = [
        [Paragraph("Продавец", bold), Paragraph("Покупатель", bold)],
        [Paragraph(f"________________ / {data.get('seller_name', '')}", normal), Paragraph(f"________________ / {data.get('buyer_name', '')}", normal)],
        [Paragraph("(подпись и Ф.И.О. полностью)", small_center), Paragraph("(подпись и Ф.И.О. полностью)", small_center)],
        [Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center), Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _simple_contract_pdf(output_path, title, city, date, data, left_label, left_key, right_label, right_key, sections, styles):
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, title, city, date, styles)

    _paragraph(story, f"{data.get(left_key, '')}", styles, f"{left_label}:")
    _paragraph(story, f"{data.get(right_key, '')}", styles, f"{right_label}:")
    story.append(Spacer(1, 12))

    for section_title, parts in sections:
        _section_title(story, section_title, styles)
        for p in parts:
            try:
                text = p.format(**data)
            except KeyError:
                text = p
            story.append(Paragraph(text, styles["Arial"]))

    story.append(Spacer(1, 24))
    story.append(_sign_table(data, left_label, left_key, right_label, right_key, styles))

    story.append(Spacer(1, 24))
    story.append(Paragraph("Сформировано автоматически ботом «Бланк-бот».", styles["ArialSmallCenter"]))

    doc.build(story)
    return output_path


def _rent_pdf(output_path: str, subtype_key: str, city: str, date: str, data: dict, styles) -> str:
    if subtype_key == "rent_flat":
        return _rent_flat_pdf(output_path, data, styles, daily=False)
    if subtype_key == "rent_flat_daily":
        return _rent_flat_pdf(output_path, data, styles, daily=True)
    if subtype_key == "rent_garage":
        return _rent_garage_pdf(output_path, data, styles)
    if subtype_key == "rent_transport":
        return _rent_transport_pdf(output_path, data, styles)

    config = {
        "rent_commercial": ("ДОГОВОР АРЕНДЫ КОММЕРЧЕСКОГО ПОМЕЩЕНИЯ", [
            ("1. Предмет договора", [
                "Арендодатель предоставляет Арендатору во временное пользование помещение по адресу: {address}.",
                "Площадь: {area} кв. м."
            ]),
            ("2. Срок аренды", ["Срок договора: {term}."]),
            ("3. Арендная плата и залог", [
                "Арендная плата: {rent_amount} руб.",
                "Залог: {deposit} руб."
            ]),
            ("4. Права и обязанности", [
                "Стороны обязуются соблюдать условия договора. Арендатор не вправе передавать помещение третьим лицам без согласия Арендодателя."
            ]),
        ]),
        "rent_transport": ("ДОГОВОР АРЕНДЫ ТРАНСПОРТНОГО СРЕДСТВА", [
            ("1. Предмет договора", [
                "Арендодатель предоставляет Арендатору во временное пользование ТС {vehicle_model}, гос. номер {vehicle_reg_number}."
            ]),
            ("2. Срок аренды", ["Срок аренды: {term}."]),
            ("3. Оплата и залог", [
                "Стоимость аренды: {rent_amount} руб.",
                "Залог: {deposit} руб."
            ]),
            ("4. Ответственность", [
                "Арендатор обязуется вернуть ТС в исправном состоянии. Арендодатель подтверждает отсутствие ограничений."
            ]),
        ]),
        "rent_thing": ("ДОГОВОР АРЕНДЫ ВЕЩИ", [
            ("1. Предмет договора", [
                "Арендодатель предоставляет Арендатору во временное пользование вещь: {thing_name}.",
                "Описание: {thing_description}."
            ]),
            ("2. Срок аренды", ["Срок аренды: {term}."]),
            ("3. Оплата и залог", [
                "Стоимость аренды: {rent_amount} руб.",
                "Залог: {deposit} руб."
            ]),
            ("4. Ответственность", [
                "Арендатор обязуется сохранить вещь и вернуть в том же состоянии."
            ]),
        ]),
        "rent_tool": ("ДОГОВОР АРЕНДЫ ИНСТРУМЕНТА", [
            ("1. Предмет договора", [
                "Арендодатель предоставляет Арендатору во временное пользование инструмент: {tool_name}.",
                "Описание и комплектация: {tool_description}."
            ]),
            ("2. Срок аренды", ["Срок аренды: {term}."]),
            ("3. Оплата и залог", [
                "Стоимость аренды: {rent_amount} руб.",
                "Залог: {deposit} руб."
            ]),
            ("4. Ответственность", [
                "Арендатор обязуется вернуть инструмент в срок и в исправном состоянии."
            ]),
        ]),
        "rent_equipment": ("ДОГОВОР АРЕНДЫ ОБОРУДОВАНИЯ", [
            ("1. Предмет договора", [
                "Арендодатель предоставляет Арендатору во временное пользование оборудование: {equipment_name}.",
                "Серийный/инвентарный номер: {equipment_serial}. Описание: {equipment_description}."
            ]),
            ("2. Срок аренды", ["Срок аренды: {term}."]),
            ("3. Оплата и залог", [
                "Стоимость аренды: {rent_amount} руб.",
                "Залог: {deposit} руб."
            ]),
            ("4. Ответственность", [
                "Арендатор обязуется эксплуатировать оборудование по назначению."
            ]),
        ]),
    }
    cfg = config.get(subtype_key)
    if not cfg:
        return _fallback_pdf("rent", subtype_key, data)
    title, sections = cfg
    return _simple_contract_pdf(output_path, title, city, date, data, "Арендодатель", "landlord_name", "Арендатор", "tenant_name", sections, styles)


def _rent_transport_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialRentTransport", fontName="Arial", fontSize=8.5, leading=11, alignment=0)
    bold = ParagraphStyle(name="ArialRentTransportBold", fontName="ArialBold", fontSize=8.5, leading=11, alignment=0)
    center_bold = ParagraphStyle(name="ArialRentTransportBoldCenter", fontName="ArialBold", fontSize=12, leading=14, alignment=1)
    small_center = ParagraphStyle(name="ArialRentTransportSmallCenter", fontName="Arial", fontSize=6.5, leading=8, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")
    start_day, start_month, start_year = _format_date(data.get("contract_start_date", ""))
    end_day, end_month, end_year = _format_date(data.get("contract_end_date", ""))

    story = []

    story.append(Paragraph("ДОГОВОР АРЕНДЫ ТРАНСПОРТНОГО СРЕДСТВА", center_bold))
    story.append(Spacer(1, 4))

    header_data = [
        [
            Paragraph(f"{place}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    def _party_text(prefix):
        name = data.get(prefix + "_name", "")
        birth = data.get(prefix + "_birth_date", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        reg = data.get(prefix + "_registration_address", "")
        return f"{name}, {birth} года рождения, паспорт серии {ps} № {pn}, выдан {pi}, код {pc}, зарегистрирован(а) по адресу: {reg}"

    story.append(Paragraph(
        f"Мы, нижеподписавшиеся, {_party_text('landlord')}, именуемый(ая) в дальнейшем «Арендодатель», с одной стороны, и {_party_text('tenant')}, именуемый(ая) в дальнейшем «Арендатор», с другой стороны, заключили настоящий договор о нижеследующем:",
        normal
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("1. Предмет договора", bold))
    story.append(Paragraph(
        "1.1. Предметом настоящего договора является транспортное средство, далее ТС:",
        normal
    ))

    ts_rows = [
        [Paragraph("Марка, модель:", normal), Paragraph(data.get("vehicle_model", ""), normal)],
        [Paragraph("Категория ТС:", normal), Paragraph(data.get("vehicle_category", ""), normal)],
        [Paragraph("Тип ТС по ПТС:", normal), Paragraph(data.get("vehicle_pts_type", ""), normal)],
        [Paragraph("Регистрационный знак:", normal), Paragraph(data.get("vehicle_reg_number", ""), normal)],
        [Paragraph("Идентификационный номер (VIN):", normal), Paragraph(data.get("vehicle_vin", ""), normal)],
        [Paragraph("Год выпуска:", normal), Paragraph(data.get("vehicle_year", ""), normal)],
        [Paragraph("Двигатель:", normal), Paragraph(data.get("vehicle_engine", ""), normal)],
        [Paragraph("Шасси:", normal), Paragraph(data.get("vehicle_chassis", ""), normal)],
        [Paragraph("Кузов:", normal), Paragraph(data.get("vehicle_body", ""), normal)],
        [Paragraph("Цвет:", normal), Paragraph(data.get("vehicle_color", ""), normal)],
    ]
    ts_table = Table(ts_rows, colWidths=[5.5 * cm, 11.2 * cm])
    ts_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(ts_table)

    story.append(Paragraph(
        f"1.2. Указанное ТС принадлежит Арендодателю на основании паспорта транспортного средства: серия {data.get('vehicle_pts_series', '')} № {data.get('vehicle_pts_number', '')}, выданного {data.get('vehicle_pts_issued', '')}.",
        normal
    ))

    story.append(Paragraph("2. Права и обязанности Арендодателя", bold))
    story.append(Paragraph(
        "2.1. Арендодатель обязуется:",
        normal
    ))
    story.append(Paragraph(
        "2.1.1. передать ТС Арендатору не позднее дня, следующего за днём подписания настоящего договора;",
        normal
    ))
    story.append(Paragraph(
        "2.1.2. предоставить Арендатору транспортное средство в исправном техническом состоянии, без дефектов;",
        normal
    ))
    story.append(Paragraph(
        "2.1.3. передать Арендатору свидетельство о регистрации транспортного средства и ключи от данного транспортного средства;",
        normal
    ))
    story.append(Paragraph(
        "2.1.4. производить страхование транспортного средства за свой счёт.",
        normal
    ))
    story.append(Paragraph(
        "2.2. Арендодатель вправе:",
        normal
    ))
    story.append(Paragraph(
        "2.2.1. требовать от Арендатора своевременного внесения арендной платы;",
        normal
    ))
    story.append(Paragraph(
        "2.2.2. требовать возврата арендованного транспортного средства в срок, установленный настоящим договором.",
        normal
    ))

    story.append(Paragraph("3. Права и обязанности Арендатора", bold))
    story.append(Paragraph(
        "3.1. Арендатор обязуется:",
        normal
    ))
    story.append(Paragraph(
        "3.1.1. своевременно вносить арендную плату и использовать транспортное средство по назначению;",
        normal
    ))
    story.append(Paragraph(
        "3.1.2. поддерживать транспортное средство в надлежащем состоянии и нести расходы на его содержание, а также расходы, связанные с его эксплуатацией в течение всего срока аренды;",
        normal
    ))
    story.append(Paragraph(
        "3.1.3. осуществлять за свой счёт капитальный и текущий ремонт переданного в аренду транспортного средства только после согласования с Арендодателем;",
        normal
    ))
    story.append(Paragraph(
        "3.1.4. осуществлять управление транспортным средством, его техническую и коммерческую эксплуатацию своими силами;",
        normal
    ))
    story.append(Paragraph(
        "3.1.5. производить за свой счёт страхование ответственности за вред, причинённый третьим лицам в связи с использованием транспортного средства;",
        normal
    ))
    story.append(Paragraph(
        "3.1.6. по истечении срока договора возвратить транспортное средство Арендодателю в исправном техническом состоянии с учётом нормального износа и без косметических дефектов не позднее даты, указанной в п. 4.1, до 12:00.",
        normal
    ))
    story.append(Paragraph(
        "3.2. Арендатор вправе:",
        normal
    ))
    story.append(Paragraph(
        "3.2.1. сдавать транспортное средство в субаренду только с письменного согласия Арендодателя;",
        normal
    ))
    story.append(Paragraph(
        "3.2.2. заключать от своего имени с третьими лицами договоры перевозки и иные договоры, не противоречащие назначению транспортного средства.",
        normal
    ))

    story.append(Paragraph("4. Срок действия договора", bold))
    story.append(Paragraph(
        f"4.1. Настоящий договор действует с «{start_day}» {start_month} {start_year} г. по «{end_day}» {end_month} {end_year} г. со дня его подписания.",
        normal
    ))
    story.append(Paragraph(
        "4.2. Арендатор не имеет преимущественного права заключения договора аренды на новый срок.",
        normal
    ))

    story.append(Paragraph("5. Арендная плата", bold))
    story.append(Paragraph(
        f"5.1. Арендная плата составляет {data.get('rent_amount', '')} руб. в сутки.",
        normal
    ))
    story.append(Paragraph(
        "5.2. Арендатор осуществляет платёж, предусмотренный пунктом 5.1 настоящего договора, не позднее последнего дня аренды транспортного средства.",
        normal
    ))

    story.append(Paragraph("6. Ответственность сторон", bold))
    story.append(Paragraph(
        "6.1. Арендодатель несёт ответственность за недостатки транспортного средства, переданного в аренду по настоящему договору, полностью или частично препятствующие его использованию.",
        normal
    ))
    story.append(Paragraph(
        f"6.2. В случае просрочки внесения арендной платы Арендатор выплачивает Арендодателю неустойку в размере {data.get('late_payment_penalty', '')}% от суммы долга за каждый день просрочки.",
        normal
    ))
    story.append(Paragraph(
        f"6.3. В случае просрочки возврата транспортного средства Арендатор выплачивает Арендодателю неустойку в размере {data.get('late_return_penalty', '')}% от суммы ежедневного арендного платежа за каждый день просрочки.",
        normal
    ))
    story.append(Spacer(1, 4))

    sign_data = [
        [Paragraph("Арендодатель", bold), Paragraph("Арендатор", bold)],
        [Paragraph(f"{data.get('landlord_name', '')} ________________", normal), Paragraph(f"{data.get('tenant_name', '')} ________________", normal)],
        [Paragraph("(Ф.И.О.)                               (подпись)", small_center), Paragraph("(Ф.И.О.)                               (подпись)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)

    # Добавляем акт осмотра и страницу подписей
    return _append_inspection_and_signatures(output_path, data)


def _append_inspection_and_signatures(contract_path: str, data: dict) -> str:
    inspection_path = "C:/Users/Пользователь/Downloads/akt-osmotra-avtomobilya.pdf"
    output_path = contract_path

    writer = PdfWriter()

    # 1. Договор
    contract_reader = PdfReader(contract_path)
    for page in contract_reader.pages:
        writer.add_page(page)

    # 2. Первая страница акта осмотра + подписи снизу
    if os.path.exists(inspection_path):
        inspection_reader = PdfReader(inspection_path)
        inspection_page = inspection_reader.pages[0]

        # Создаём overlay с подписями внизу страницы
        overlay_path = contract_path.replace(".pdf", "_overlay.pdf")
        overlay_doc = SimpleDocTemplate(
            overlay_path,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm,
        )
        normal = ParagraphStyle(name="ArialOverlay", fontName="Arial", fontSize=9, leading=11, alignment=0)
        bold = ParagraphStyle(name="ArialOverlayBold", fontName="ArialBold", fontSize=9, leading=11, alignment=0)
        small_center = ParagraphStyle(name="ArialOverlaySmallCenter", fontName="Arial", fontSize=6.5, leading=8, alignment=1, textColor=colors.grey)
        story = []
        story.append(Spacer(1, 24 * cm))
        story.append(Paragraph("Подписи сторон", bold))
        story.append(Spacer(1, 8))
        sign_data = [
            [Paragraph("Арендодатель", bold), Paragraph("Арендатор", bold)],
            [Paragraph(f"{data.get('landlord_name', '')} ________________", normal), Paragraph(f"{data.get('tenant_name', '')} ________________", normal)],
            [Paragraph("(Ф.И.О.)                               (подпись)", small_center), Paragraph("(Ф.И.О.)                               (подпись)", small_center)],
            [Paragraph("", normal), Paragraph("", normal)],
            [Paragraph("Дата: «___» __________ 20__ г.", normal), Paragraph("Дата: «___» __________ 20__ г.", normal)],
        ]
        sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
        sign_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        story.append(sign_table)
        overlay_doc.build(story)

        overlay_reader = PdfReader(overlay_path)
        inspection_page.merge_page(overlay_reader.pages[0])
        writer.add_page(inspection_page)

        try:
            os.remove(overlay_path)
        except Exception:
            pass

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path


def _rent_flat_pdf(output_path: str, data: dict, styles, daily: bool = False) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialRent", fontName="Arial", fontSize=9.5, leading=12, alignment=0)
    bold = ParagraphStyle(name="ArialRentBold", fontName="ArialBold", fontSize=9.5, leading=12, alignment=0)
    bold_italic = ParagraphStyle(name="ArialRentBoldItalic", fontName="ArialBold", fontSize=9.5, leading=12, alignment=0)
    # Note: reportlab TTF does not support italic style flags for custom fonts; emulate with <i> tags in Paragraph text.
    center_bold = ParagraphStyle(name="ArialRentBoldCenter", fontName="ArialBold", fontSize=13, leading=16, alignment=1)
    small_center = ParagraphStyle(name="ArialRentSmallCenter", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")

    story = []

    title = "ДОГОВОР АРЕНДЫ КВАРТИРЫ / КОМНАТЫ (ПОСУТОЧНО)" if daily else "ДОГОВОР АРЕНДЫ КВАРТИРЫ"
    period_label = "сутки" if daily else "месяц"

    # Шапка
    story.append(Paragraph(title, center_bold))
    story.append(Spacer(1, 4))
    header_data = [
        [
            Paragraph(f"{place}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Стороны
    def _party_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        reg = data.get(prefix + "_registration_address", "")
        if ps and pn:
            return f"{name}, паспорт серии {ps} № {pn}, выдан {pi}, код {pc}, зарегистрирован(а) по адресу: {reg}"
        return f"{name}, зарегистрирован(а) по адресу: {reg}"

    story.append(Paragraph(
        f"Мы, нижеподписавшиеся, гр. {_party_text('landlord')}, именуемый(ая) в дальнейшем «Арендодатель», с одной стороны, и гр. {_party_text('tenant')}, именуемый(ая) в дальнейшем «Наниматель», с другой стороны, заключили настоящий договор о нижеследующем:",
        normal
    ))
    story.append(Spacer(1, 4))

    # 1. Предмет договора
    story.append(Paragraph("1. Предмет договора", bold))
    rooms = data.get('rooms', '')
    rooms_text = f"{rooms}-комнатную" if rooms else "___-комнатную"
    rent_object = data.get('rent_object', '').lower().strip()
    room_type = data.get('room_type', '').lower().strip()
    room_number = data.get('room_number', '')
    if rent_object in ('комната', 'комнату'):
        if room_type in ('общежитие', 'в общежитии'):
            object_desc = f"комнату № {room_number} в общежитии"
        else:
            object_desc = f"комнату № {room_number} в {rooms_text} квартире"
        story.append(Paragraph(
            f"1.1. Арендодатель предоставляет, а Наниматель получает во временное пользование (аренду) {object_desc}, расположенную по адресу: {data.get('address', '')}. Этаж: {data.get('floor', '')}, общая площадь: {data.get('area', '')} кв. м.",
            normal
        ))
        story.append(Paragraph(
            "1.2. Арендодатель предоставляет, а Наниматель получает во временное пользование находящиеся в сдаваемой комнате предметы мебели и бытовую технику в состоянии, пригодном для использования.",
            normal
        ))
    else:
        story.append(Paragraph(
            f"1.1. Арендодатель предоставляет, а Наниматель получает во временное пользование (аренду) {rooms_text} квартиру, расположенную по адресу: {data.get('address', '')}. Этаж: {data.get('floor', '')}, общая площадь: {data.get('area', '')} кв. м.",
            normal
        ))
        story.append(Paragraph(
            "1.2. Арендодатель предоставляет, а Наниматель получает во временное пользование находящиеся в квартире предметы мебели и бытовую технику в состоянии, пригодном для использования.",
            normal
        ))
    story.append(Paragraph(
        f"1.3. Срок аренды составляет {data.get('term', '')}.",
        normal
    ))
    story.append(Paragraph(
        "1.4. Передаваемая в аренду квартира используется Нанимателем только для проживания, без права сдачи её в субаренду.",
        normal
    ))

    story.append(Paragraph("2. Права и обязанности Арендодателя", bold))
    story.append(Paragraph(
        "2.1. Арендодатель подтверждает, что он получил согласие всех совершеннолетних лиц, зарегистрированных по данному адресу, или владеющих совместно с ним данной жилплощадью, на сдачу данной квартиры в аренду.",
        normal
    ))
    story.append(Paragraph(
        "2.2. Арендодатель подтверждает, что на момент подписания настоящего договора аренды данная квартира не продана, не подарена, не является предметом судебного спора, не находится под залогом, арестом, не сдана внаём. Дом на период аренды квартиры не подлежит сносу или капитальному ремонту с отселением.",
        normal
    ))
    story.append(Paragraph(
        "2.3. Арендодатель имеет право посещать Нанимателя только с предварительным уведомлением.",
        normal
    ))
    story.append(Paragraph(
        "2.4. Арендодатель устраняет последствия аварий и повреждений, произошедших не по вине Нанимателя, своими силами.",
        normal
    ))
    story.append(Paragraph(
        "2.5. Арендодатель оплачивает: эксплуатационные расходы, центральное отопление, коммунальные услуги, телефон (абонентская ежемесячная плата).",
        normal
    ))

    story.append(Paragraph("3. Права и обязанности Нанимателя", bold))
    story.append(Paragraph(
        "3.1. Содержать арендуемую квартиру в порядке, предусмотренном санитарными, противопожарными и иными установленными действующими законодательством РФ нормами.",
        normal
    ))
    story.append(Paragraph(
        "3.2. О предстоящем освобождении снимаемой в аренду квартиры известить Арендодателя не менее чем за 30 дней.",
        normal
    ))
    story.append(Paragraph(
        "3.3. В случае нанесения ущерба арендуемой квартире и имуществу, находящемуся в ней, Наниматель обязуется возместить Арендодателю причинённый ущерб.",
        normal
    ))
    story.append(Paragraph(
        "3.4. Наниматель обязуется оплачивать расходы по электроэнергии в полном объёме, ежемесячно.",
        normal
    ))
    story.append(Paragraph(
        "3.5. Нанимателю запрещается сдавать квартиру в субаренду.",
        normal
    ))
    story.append(Paragraph(
        "3.6. В квартире запрещается курение (в противном случае это является основанием для расторжения настоящего договора).",
        normal
    ))

    story.append(Paragraph("4. Порядок расчётов", bold))
    if daily:
        story.append(Paragraph(
            f"4.1. За арендуемое жилое помещение Наниматель уплачивает арендную плату в размере {data.get('rent_amount', '')} руб. за одни {period_label}.",
            normal
        ))
        story.append(Paragraph(
            "4.2. Арендная плата вносится Нанимателем при заключении настоящего договора.",
            normal
        ))
    else:
        story.append(Paragraph(
            f"4.1. За арендуемую квартиру Наниматель уплачивает месячную плату в размере {data.get('rent_amount', '')} руб.",
            normal
        ))
        story.append(Paragraph(
            "4.2. Ежемесячная арендная плата вносится Нанимателем за месяц вперёд не позднее 5 числа каждого месяца.",
            normal
        ))
        story.append(Paragraph(
            f"4.3. При подписании договора Нанимателем вносится Арендодателю оплата за месяц вперёд в размере {data.get('rent_amount', '')} руб., а также залоговая сумма {data.get('deposit', '')} руб., которая возвращается Нанимателю при выезде его из квартиры.",
            normal
        ))
    story.append(Paragraph(
        "4.4. Размер арендной платы остаётся неизменным в течение всего срока действия договора.",
        normal
    ))

    story.append(Paragraph("5. Срок действия договора аренды квартиры, порядок изменения, расторжения договора", bold))
    story.append(Paragraph(
        f"5.1. Настоящий договор вступает в силу с момента его подписания и действует в течение {data.get('term', '')}.",
        normal
    ))
    story.append(Paragraph(
        "5.2. Изменения и дополнения к настоящему договору могут вноситься только по соглашению сторон путём подписания дополнительного соглашения, являющегося неотъемлемой частью настоящего договора аренды квартиры.",
        normal
    ))
    story.append(Paragraph(
        "5.3. Досрочное расторжение договора аренды Арендодателем возможно в случаях, если Наниматель нарушил свои обязанности по настоящему договору аренды квартиры.",
        normal
    ))

    story.append(Paragraph("6. Порядок рассмотрения споров", bold))
    story.append(Paragraph(
        "6.1. Все споры между сторонами, связанные с настоящим договором аренды, решаются путём взаимных переговоров.",
        normal
    ))
    story.append(Paragraph(
        "6.2. В случае невозможности их разрешения переговорным путём, они будут рассмотрены в соответствии с Законодательством РФ.",
        normal
    ))
    story.append(Paragraph(
        "6.3. Дополнительные права и обязанности сторон могут быть прописаны в дополнительном соглашении.",
        normal
    ))
    story.append(Spacer(1, 6))

    sign_data = [
        [Paragraph("Арендодатель:", bold), Paragraph("Наниматель:", bold)],
        [Paragraph(f"{data.get('landlord_name', '')} ________________", normal), Paragraph(f"{data.get('tenant_name', '')} ________________", normal)],
        [Paragraph("(Ф.И.О.)                               (подпись)", small_center), Paragraph("(Ф.И.О.)                               (подпись)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _rent_garage_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialRentGarage", fontName="Arial", fontSize=9, leading=12, alignment=0)
    bold = ParagraphStyle(name="ArialRentGarageBold", fontName="ArialBold", fontSize=9, leading=12, alignment=0)
    center_bold = ParagraphStyle(name="ArialRentGarageBoldCenter", fontName="ArialBold", fontSize=13, leading=16, alignment=1)
    small_center = ParagraphStyle(name="ArialRentGarageSmallCenter", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")

    rent_type = data.get("rent_type", "").lower().strip()
    is_daily = "сут" in rent_type or "ден" in rent_type or "посуточ" in rent_type
    period_label = "сутки" if is_daily else "месяц"
    period_label_plural = "суток" if is_daily else "месяцев"

    deposit = data.get("deposit", "").strip()
    has_deposit = deposit and deposit != "прочерк" and deposit != "-"

    story = []

    story.append(Paragraph("ДОГОВОР АРЕНДЫ ГАРАЖА", center_bold))
    story.append(Spacer(1, 4))
    header_data = [
        [
            Paragraph(f"{place}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    def _party_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        reg = data.get(prefix + "_registration_address", "")
        if ps and pn:
            return f"{name}, паспорт серии {ps} № {pn}, выдан {pi}, код {pc}, зарегистрирован(а) по адресу: {reg}"
        return f"{name}, зарегистрирован(а) по адресу: {reg}"

    story.append(Paragraph(
        f"Мы, нижеподписавшиеся, {_party_text('landlord')}, именуемый(ая) в дальнейшем «Арендодатель», с одной стороны, и {_party_text('tenant')}, именуемый(ая) в дальнейшем «Арендатор», с другой стороны, заключили настоящий договор о нижеследующем:",
        normal
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("1. Предмет договора", bold))
    story.append(Paragraph(
        f"1.1. Арендодатель предоставляет, а Арендатор получает во временное пользование (аренду) нежилое помещение — гараж, расположенный по адресу: {data.get('garage_address', '')}. Общая площадь гаража составляет {data.get('garage_area', '')} кв. м.",
        normal
    ))
    story.append(Paragraph(
        f"1.2. Гараж принадлежит Арендодателю на основании: {data.get('ownership_basis', '')}.",
        normal
    ))
    story.append(Paragraph(
        f"1.3. Гараж предоставляется Арендатору с целью: {data.get('garage_purpose', '')}.",
        normal
    ))

    story.append(Paragraph("2. Арендная плата и порядок расчётов", bold))
    story.append(Paragraph(
        f"2.1. Арендная плата устанавливается в денежной форме и составляет {data.get('rent_amount', '')} руб. за один {period_label}.",
        normal
    ))
    story.append(Paragraph(
        f"2.2. Арендатор оплачивает арендную плату Арендодателю в порядке: {data.get('payment_terms', '')}.",
        normal
    ))
    if not is_daily:
        story.append(Paragraph(
            f"2.3. Стоимость коммунальных услуг и потребляемой Арендатором электроэнергии в арендную плату не входит и оплачивается им отдельно: {data.get('utilities_terms', '')}.",
            normal
        ))
    if has_deposit:
        deposit_point = "2.4." if not is_daily else "2.3."
        story.append(Paragraph(
            f"{deposit_point} При заключении настоящего договора Арендатор вносит Арендодателю залог в размере {deposit} руб., который возвращается Арендатору при расторжении договора и возврате гаража в надлежащем состоянии.",
            normal
        ))

    story.append(Paragraph("3. Права и обязанности сторон", bold))
    story.append(Paragraph("3.1. Арендатор имеет право:", normal))
    story.append(Paragraph("3.1.1. На приоритетное заключение договора аренды на новый срок в случае надлежащего исполнения своих обязанностей по договору;", normal))
    story.append(Paragraph("3.1.2. С согласия Арендодателя производить улучшения арендованного имущества;", normal))
    story.append(Paragraph("3.1.3. Требовать расторжения договора и возмещения убытков в случае не зависящего от него существенного ухудшения эксплуатационных характеристик гаража.", normal))

    story.append(Paragraph("3.2. Арендатор обязан:", normal))
    story.append(Paragraph("3.2.1. Своевременно вносить арендную плату за пользование гаражом;", normal))
    story.append(Paragraph("3.2.2. Пользоваться арендованным имуществом в соответствии с условиями настоящего договора аренды и целевым назначением гаража;", normal))
    story.append(Paragraph("3.2.3. Поддерживать гараж в надлежащем состоянии;", normal))
    story.append(Paragraph("3.2.4. Возвратить гараж Арендодателю в срок, установленный настоящим договором, в состоянии, соответствующем состоянию на момент передачи, с учётом нормального износа.", normal))

    story.append(Paragraph("3.3. Арендодатель обязан:", normal))
    story.append(Paragraph("3.3.1. Передать гараж Арендатору в состоянии, пригодном для использования по назначению;", normal))
    story.append(Paragraph("3.3.2. Не чинить препятствий Арендатору в пользовании гаражом в соответствии с условиями договора;", normal))
    story.append(Paragraph("3.3.3. Устранять неполадки, не зависящие от действий Арендатора, своими силами и за свой счёт.", normal))

    story.append(Paragraph("4. Ответственность сторон", bold))
    story.append(Paragraph(
        "4.1. За нарушение условий настоящего договора стороны несут ответственность в соответствии с действующим законодательством Российской Федерации.",
        normal
    ))
    story.append(Paragraph(
        "4.2. В случае нанесения ущерба гаражу или имуществу, находящемуся в нём, Арендатор обязуется возместить Арендодателю причинённый ущерб в полном объёме.",
        normal
    ))

    story.append(Paragraph("5. Срок действия договора", bold))
    story.append(Paragraph(
        f"5.1. Настоящий договор вступает в силу с момента его подписания и действует в течение {data.get('term', '')}.",
        normal
    ))
    if not is_daily:
        story.append(Paragraph(
            "5.2. По истечении срока действия договор считается расторгнутым, если стороны не пришли к соглашению о его продлении.",
            normal
        ))

    story.append(Paragraph("6. Прочие условия", bold))
    story.append(Paragraph(
        "6.1. Изменения и дополнения к настоящему договору могут вноситься только по соглашению сторон путём подписания дополнительного соглашения.",
        normal
    ))
    story.append(Paragraph(
        "6.2. Все споры между сторонами, связанные с настоящим договором, решаются путём переговоров, а при невозможности урегулирования — в соответствии с законодательством РФ.",
        normal
    ))
    story.append(Spacer(1, 6))

    sign_data = [
        [Paragraph("Арендодатель:", bold), Paragraph("Арендатор:", bold)],
        [Paragraph(f"{data.get('landlord_name', '')} ________________", normal), Paragraph(f"{data.get('tenant_name', '')} ________________", normal)],
        [Paragraph("(Ф.И.О.)                               (подпись)", small_center), Paragraph("(Ф.И.О.)                               (подпись)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _receipt_pdf(output_path: str, subtype_key: str, city: str, date: str, data: dict, styles) -> str:
    if subtype_key == "receipt_debt":
        return _receipt_debt_pdf(output_path, data, styles)
    if subtype_key == "receipt_return":
        return _receipt_return_pdf(output_path, data, styles)
    return _fallback_pdf("receipt", subtype_key, data)


def _receipt_debt_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    normal = ParagraphStyle(name="ArialReceipt", fontName="Arial", fontSize=11, leading=15, alignment=0)
    bold = ParagraphStyle(name="ArialReceiptBold", fontName="ArialBold", fontSize=11, leading=15, alignment=0)
    center_bold = ParagraphStyle(name="ArialReceiptBoldCenter", fontName="ArialBold", fontSize=14, leading=18, alignment=1)
    small_center = ParagraphStyle(name="ArialReceiptSmallCenter", fontName="Arial", fontSize=9, leading=11, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    return_day, return_month, return_year = _format_date(data.get("return_date", ""))
    city = data.get("city", "")

    interest_amount = data.get('interest_amount', '').strip()
    has_interest = interest_amount and interest_amount not in ('прочерк', '-', '')

    def _person_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        address = data.get(prefix + "_address", "")
        return f"{name}, паспорт: серия {ps} № {pn}, выдан {pi}, проживающий(ая) по адресу: {address}"

    story = []

    story.append(Paragraph("РАСПИСКА", center_bold))
    story.append(Paragraph("в получении суммы займа", center_bold))
    story.append(Spacer(1, 12))

    header_data = [
        [
            Paragraph(f"г. {city}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        f"Я, {_person_text('borrower')} (далее — Заёмщик), получил(а) денежные средства в сумме {data.get('amount', '')} ({data.get('amount_words', '')}) рублей от {_person_text('lender')} (далее — Займодавец).",
        normal
    ))
    story.append(Spacer(1, 8))

    if has_interest:
        story.append(Paragraph(
            f"Также заёмщик обязуется уплатить проценты по займу в сумме {interest_amount} ({data.get('interest_amount_words', '')}) рублей.",
            normal
        ))
        story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"Я обязуюсь возвратить Займодавцу сумму займа в полном объёме в срок до «{return_day}» {return_month} {return_year} г.",
        normal
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Настоящая расписка составлена в двух экземплярах, имеющих равную юридическую силу, по одному для каждой из Сторон.",
        normal
    ))
    story.append(Spacer(1, 24))

    sign_data = [
        [Paragraph("Займодавец:", bold), Paragraph("Заёмщик:", bold)],
        [Paragraph(f"{data.get('lender_name', '')} ________________", normal), Paragraph(f"{data.get('borrower_name', '')} ________________", normal)],
        [Paragraph("(подпись / Ф.И.О.)", small_center), Paragraph("(подпись / Ф.И.О.)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _receipt_return_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    normal = ParagraphStyle(name="ArialReceiptReturn", fontName="Arial", fontSize=11, leading=15, alignment=0)
    bold = ParagraphStyle(name="ArialReceiptReturnBold", fontName="ArialBold", fontSize=11, leading=15, alignment=0)
    center_bold = ParagraphStyle(name="ArialReceiptReturnBoldCenter", fontName="ArialBold", fontSize=14, leading=18, alignment=1)
    small_center = ParagraphStyle(name="ArialReceiptReturnSmallCenter", fontName="Arial", fontSize=9, leading=11, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    city = data.get("city", "")

    def _person_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        address = data.get(prefix + "_address", "")
        return f"{name}, паспорт: серия {ps} № {pn}, выдан {pi}, зарегистрированный(ая) по адресу: {address}"

    story = []

    story.append(Paragraph("РАСПИСКА", center_bold))
    story.append(Paragraph("о возврате денежных средств", center_bold))
    story.append(Spacer(1, 12))

    header_data = [
        [
            Paragraph(f"г. {city}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    interest_amount = data.get('interest_amount', '').strip()
    has_interest = interest_amount and interest_amount not in ('прочерк', '-', '')

    story.append(Paragraph(
        f"Я, {_person_text('lender')} (далее — Займодавец), подтверждаю, что получил(а) от {_person_text('borrower')} (далее — Заёмщик) денежные средства в размере {data.get('amount', '')} ({data.get('amount_words', '')}) рублей в счёт исполнения обязательств по расписке.",
        normal
    ))
    story.append(Spacer(1, 8))

    if has_interest:
        story.append(Paragraph(
            f"Также получены проценты по займу в сумме {interest_amount} ({data.get('interest_amount_words', '')}) рублей.",
            normal
        ))
        story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Указанная сумма получена мной полностью, обязательства заёмщика по возврату займа считаю исполненными в полном объёме. Претензий к заёмщику не имею.",
        normal
    ))
    story.append(Spacer(1, 24))

    sign_data = [
        [Paragraph("Займодавец:", bold), Paragraph("", bold)],
        [Paragraph(f"{data.get('lender_name', '')} ________________", normal), Paragraph("", normal)],
        [Paragraph("(подпись / Ф.И.О.)", small_center), Paragraph("", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _claim_product_pdf(output_path: str, city: str, date: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    normal = styles["Arial"]
    bold = styles["ArialBold"]
    small_center = styles["ArialSmallCenter"]
    story = []

    # Шапка: кому и от кого
    story.append(Paragraph(f"Кому: {data.get('organization_name', '')}", normal))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"От: {data.get('claimant_name', '')}", normal))
    story.append(Spacer(1, 24))

    # Заголовок
    story.append(Paragraph("ПРЕТЕНЗИЯ", styles["ArialBoldCenter"]))
    story.append(Spacer(1, 24))

    # Основной текст
    purchase_place = data.get("purchase_place", "")
    purchase_date = data.get("purchase_date", "")
    story.append(Paragraph(
        f"Мной «{purchase_date}» {purchase_place} у Вас был приобретен товар, а именно: "
        f"{data.get('product_name', '')}.",
        normal,
    ))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        f"Этот товар не отвечает требованиям качества, т.к. {data.get('issue_description', '')}.",
        normal,
    ))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Прошу: {data.get('demands', '')}.", normal))
    story.append(Spacer(1, 24))

    attachments = data.get("attachments", "")
    if attachments and attachments.lower() not in ("прочерк", "-", ""):
        story.append(Paragraph(f"Приложение: {attachments} на (___) листах.", normal))
        story.append(Spacer(1, 36))
    else:
        story.append(Paragraph("Приложение: ________________________ на (___) листах.", normal))
        story.append(Spacer(1, 36))

    # Подпись заявителя
    sign_data = [
        [Paragraph(f"Дата: {date}", normal), Paragraph("Подпись: ________________", normal)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 36))

    # Отметка о получении
    story.append(Paragraph(
        f"Претензию получил: ________________ Подпись: ________________ Дата: ________________",
        normal,
    ))

    doc.build(story)
    return output_path


def _act_pdf(output_path: str, city: str, date: str, data: dict, styles) -> str:
    sections = [
        ("", [
            "Исполнитель: {contractor_name}.",
            "Заказчик: {customer_name}.",
            "Договор/заявка: {contract_number}.",
            "Описание выполненных работ: {work_description}.",
            "Стоимость работ: {work_cost} руб.",
            "Период выполнения: {period}."
        ]),
    ]
    return _simple_contract_pdf(output_path, "АКТ ВЫПОЛНЕННЫХ РАБОТ", city, date, data, "Исполнитель", "contractor_name", "Заказчик", "customer_name", sections, styles)


def _act_default_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    normal = ParagraphStyle(name="ArialActDefault", fontName="Arial", fontSize=11, leading=15, alignment=0)
    bold = ParagraphStyle(name="ArialActDefaultBold", fontName="ArialBold", fontSize=11, leading=15, alignment=0)
    center_bold = ParagraphStyle(name="ArialActDefaultBoldCenter", fontName="ArialBold", fontSize=14, leading=18, alignment=1)
    small_center = ParagraphStyle(name="ArialActDefaultSmallCenter", fontName="Arial", fontSize=9, leading=11, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    city = data.get("city", "")

    story = []

    story.append(Paragraph("АКТ ВЫПОЛНЕННЫХ РАБОТ", center_bold))
    story.append(Spacer(1, 12))

    header_data = [
        [
            Paragraph(f"г. {city}", normal),
            Paragraph(""),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
    ]
    header_table = Table(header_data, colWidths=[3 * cm, 10 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"Исполнитель: {data.get('contractor_name', '')}", normal))
    story.append(Paragraph(f"Заказчик: {data.get('customer_name', '')}", normal))
    story.append(Paragraph(f"Договор/заявка: {data.get('contract_number', '')}", normal))
    story.append(Spacer(1, 8))

    # Таблица выполненных работ
    table_data = [
        [
            Paragraph("№", bold),
            Paragraph("Наименование работы (услуги)", bold),
            Paragraph("Ед. изм.", bold),
            Paragraph("Количество", bold),
            Paragraph("Цена", bold),
            Paragraph("Сумма", bold),
        ],
        [
            Paragraph("1", normal),
            Paragraph(data.get("work_name", ""), normal),
            Paragraph(data.get("work_unit", ""), normal),
            Paragraph(data.get("work_quantity", ""), normal),
            Paragraph(data.get("work_price", ""), normal),
            Paragraph(data.get("work_cost", ""), normal),
        ],
    ]
    work_table = Table(table_data, colWidths=[1.2 * cm, 7.5 * cm, 2 * cm, 2.3 * cm, 2.2 * cm, 2.3 * cm])
    work_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(work_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"Период выполнения: {data.get('period', '')}", normal))
    story.append(Paragraph(f"Всего оказано услуг на сумму: {data.get('work_cost', '')} руб.", normal))
    story.append(Spacer(1, 24))

    sign_data = [
        [Paragraph("Исполнитель:", bold), Paragraph("Заказчик:", bold)],
        [Paragraph(f"{data.get('contractor_name', '')} ________________", normal), Paragraph(f"{data.get('customer_name', '')} ________________", normal)],
        [Paragraph("(подпись / Ф.И.О.)", small_center), Paragraph("(подпись / Ф.И.О.)", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _act_goods_transfer_pdf(output_path: str, data: dict, styles) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    normal = ParagraphStyle(name="ArialAct", fontName="Arial", fontSize=10, leading=13, alignment=0)
    bold = ParagraphStyle(name="ArialActBold", fontName="ArialBold", fontSize=10, leading=13, alignment=0)
    center_bold = ParagraphStyle(name="ArialActBoldCenter", fontName="ArialBold", fontSize=12, leading=15, alignment=1)
    small_center = ParagraphStyle(name="ArialActSmallCenter", fontName="Arial", fontSize=7, leading=9, alignment=1, textColor=colors.grey)

    day, month, year = _format_date(data.get("date", ""))
    place = data.get("place", "")
    contract_day, contract_month, contract_year = _format_date(data.get("contract_date", ""))

    story = []

    # Приложение
    story.append(Paragraph(
        f"Приложение № __ к договору № {data.get('contract_number', '__')} от «{contract_day}» {contract_month} {contract_year} г.",
        normal
    ))
    story.append(Spacer(1, 12))

    # Заголовок
    story.append(Paragraph("АКТ ПРИЁМА-ПЕРЕДАЧИ ТОВАРА", center_bold))
    story.append(Spacer(1, 12))

    # Место и дата
    header_data = [
        [
            Paragraph(f"г. {place}", normal),
            Paragraph(f"«{day}» {month} {year} г.", normal),
        ],
        [
            Paragraph("(населённый пункт)", small_center),
            Paragraph("(дата)", small_center),
        ],
    ]
    header_table = Table(header_data, colWidths=[8.35 * cm, 8.35 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    # Стороны
    def _party_text(prefix):
        name = data.get(prefix + "_name", "")
        ps = data.get(prefix + "_passport_series", "")
        pn = data.get(prefix + "_passport_number", "")
        pi = data.get(prefix + "_passport_issued", "")
        pc = data.get(prefix + "_passport_code", "")
        address = data.get(prefix + "_address", "")
        if ps and pn:
            return f"{name}, паспорт серии {ps} № {pn}, выдан {pi}, код {pc}, адрес: {address}"
        return f"{name}, адрес: {address}"

    story.append(Paragraph(
        f"Мы, нижеподписавшиеся, Продавец: {_party_text('seller')}, с одной стороны, и Покупатель: {_party_text('buyer')}, с другой стороны,",
        normal
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"составили настоящий акт приёма-передачи товара к договору купли-продажи № {data.get('contract_number', '__')} от «{contract_day}» {contract_month} {contract_year} г.",
        normal
    ))
    story.append(Spacer(1, 8))

    # Таблица товара
    table_header = ["№", "Наименование", "Ед.<br/>изм.", "Кол-<br/>во", "Примечание<br/>комплектность", "Цена за<br/>ед., руб.", "НДС", "Стоимость,<br/>руб."]
    table_row = [
        "1",
        data.get("product_name", ""),
        data.get("product_unit", ""),
        data.get("product_quantity", ""),
        data.get("product_assortment", ""),
        data.get("product_price", ""),
        data.get("product_vat", ""),
        data.get("product_total", ""),
    ]
    table_data = [
        [Paragraph(cell, bold) for cell in table_header],
        [Paragraph(cell, normal) for cell in table_row],
    ]
    goods_table = Table(table_data, colWidths=[0.8 * cm, 3.0 * cm, 1.0 * cm, 1.0 * cm, 3.6 * cm, 1.7 * cm, 1.5 * cm, 2.2 * cm], repeatRows=1)
    goods_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ]))
    story.append(goods_table)
    story.append(Spacer(1, 8))

    # Итого и примечание
    story.append(Paragraph(
        f"Итого стоимость товара составляет: {data.get('product_total', '')} руб.",
        bold
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Примечание / претензии: {data.get('transfer_notes', 'претензий не имеется')}",
        normal
    ))
    story.append(Spacer(1, 8))

    # Положения акта
    story.append(Paragraph(
        "Товар передан Продавцом и принят Покупателем в количестве, качестве и комплектности, указанных в настоящем акте. Стороны претензий друг к другу не имеют.",
        normal
    ))
    story.append(Spacer(1, 12))

    # Подписи
    sign_data = [
        [Paragraph("Продавец", bold), Paragraph("Покупатель", bold)],
        [Paragraph("Товар передал", normal), Paragraph("Товар принял", normal)],
        [Paragraph("________________ / ________________", normal), Paragraph("________________ / ________________", normal)],
        [Paragraph("(подпись и Ф.И.О. полностью)", small_center), Paragraph("(подпись и Ф.И.О. полностью)", small_center)],
        [Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center), Paragraph("«___» __________ 20__ г.<br/>М.П.", small_center)],
    ]
    sign_table = Table(sign_data, colWidths=[8.35 * cm, 8.35 * cm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    doc.build(story)
    return output_path


def _fallback_pdf(doc_key: str, subtype_key: str, data: dict) -> str:
    output_path = _pdf_path(doc_key, subtype_key, data)
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = _styles()
    story = [Paragraph(f"Документ {html.escape(doc_key)} — {html.escape(subtype_key)}", styles["ArialBoldCenter"])]
    story.append(Spacer(1, 16))
    story.append(Paragraph("Заполненные данные:", styles["Arial"]))
    for key, value in data.items():
        story.append(Paragraph(f"<b>{html.escape(key)}:</b> {html.escape(str(value))}", styles["Arial"]))
    story.append(Spacer(1, 24))
    story.append(Paragraph("Сформировано автоматически ботом «Бланк-бот».", styles["ArialSmallCenter"]))
    doc.build(story)
    return output_path
