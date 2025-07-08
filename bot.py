import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from datetime import datetime
import json
from typing import Dict, Any, List, Optional

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
# Цей рядок раніше містив захардкожений токен і був видалений.
# Токен тепер береться зі змінних оточення Render.
CHANNEL_ID = "@ulx_ukraine" # Замените на ID вашего канала

# Ограничения
MAX_PHOTOS = 5
MAX_PHOTO_SIZE = 20 * 1024 * 1024  # 20MB
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000
MIN_PRICE = 0.01
MAX_PRICE = 1000000

# Состояния conversation handler
(
    CHOOSING_CATEGORY,
    CHOOSING_SUBCATEGORY,
    ADDING_MANUAL_SUBCATEGORY,
    CHOOSING_REGION,
    CHOOSING_CITY,
    ADDING_MANUAL_CITY,
    CHOOSING_CONDITION,
    ADDING_TITLE,
    ADDING_DESCRIPTION,
    ADDING_PRICE,
    ADDING_PHOTOS,
    CONFIRMING,
    TYPING_MANUAL_SUBCATEGORY, # Добавьте этот, если он используется в вашем ConversationHandler
    TYPING_MANUAL_CITY, # Добавьте этот, если он используется в вашем ConversationHandler
    TYPING_TITLE, # Добавьте этот, если он используется
    TYPING_DESCRIPTION, # Добавьте этот, если он используется
    TYPING_PRICE, # Добавьте этот, если он используется
) = map(chr, range(16)) # Убедитесь, что количество символов совпадает с количеством состояний.
                       # Я добавил несколько общих, если у вас были свои.
                       # Возможно, вам нужно будет скорректировать это.

# Загрузка данных
try:
    with open("categories.json", "r", encoding="utf-8") as f:
        CATEGORIES = json.load(f)
except FileNotFoundError:
    CATEGORIES = {}
    logger.error("categories.json not found. Please create it.")

try:
    with open("regions.json", "r", encoding="utf-8") as f:
        REGIONS = json.load(f)
except FileNotFoundError:
    REGIONS = {}
    logger.error("regions.json not found. Please create it.")

try:
    with open("conditions.json", "r", encoding="utf-8") as f:
        CONDITIONS = json.load(f)
except FileNotFoundError:
    CONDITIONS = {}
    logger.error("conditions.json not found. Please create it.")

# Хранение данных для объявлений (в памяти, для прода нужно использовать БД)
user_data_listings: Dict[int, Dict[str, Any]] = {}

# --- Функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет главное меню при вводе /start."""
    keyboard = [
        [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать в ULX Ukraine Bot!\n\n"
        "Здесь вы можете легко и быстро публиковать объявления о продаже или обмене товаров.\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает пользователя в главное меню."""
    query = update.callback_query
    if query:
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query.message.text: # If it's not an inline keyboard from /start
             await query.edit_message_text(
                "🏠 Главное меню. Выберите действие:", reply_markup=reply_markup
            )
        else: # If it's a message from /start
            await query.message.reply_text(
                "🏠 Главное меню. Выберите действие:", reply_markup=reply_markup
            )
    return ConversationHandler.END # End current conversation if going to main menu

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с помощью."""
    text = (
        "<b>ULX Ukraine Bot - Помощь</b>\n\n"
        "Этот бот позволяет публиковать объявления о продаже товаров.\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Перезапустить бота и вернуться в главное меню.\n"
        "/sell - Начать процесс создания объявления.\n"
        "/help - Показать это сообщение помощи.\n\n"
        "<b>Как создать объявление:</b>\n"
        "1. Нажмите на '🚀 Создать объявление' или используйте команду /sell.\n"
        "2. Следуйте инструкциям бота, выбирая категорию, регион, город, состояние товара, "
        "вводя название, описание, цену и загружая фото.\n"
        "3. Подтвердите объявление, и оно будет опубликовано в канале."
    )
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает процесс создания объявления."""
    return await start_selling(update, context)

async def start_selling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает или перезапускает процесс создания объявления."""
    user_id = update.effective_user.id
    user_data_listings[user_id] = {
        "photos": [],
        "user_id": user_id,
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name
    }

    keyboard = []
    for category_id, category_name in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(category_name, callback_data=f"category|{category_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "✅ Отлично! Давайте создадим объявление.\n\n" \
              "<b>Шаг 1 из 9: Выберите категорию товара:</b>"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return CHOOSING_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category_id = query.data.split("|")[1]
    context.user_data["current_listing"] = user_data_listings.get(update.effective_user.id, {})
    context.user_data["current_listing"]["category_id"] = category_id
    context.user_data["current_listing"]["category_name"] = CATEGORIES.get(category_id)

    subcategories = CATEGORIES.get(category_id, {}).get("subcategories", {})
    keyboard = []
    for sub_id, sub_name in subcategories.items():
        keyboard.append([InlineKeyboardButton(sub_name, callback_data=f"subcategory|{category_id}|{sub_id}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_subcategory")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"<b>Шаг 2 из 9: Выберите подкатегорию для '{CATEGORIES.get(category_id)}' или введите вручную:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_SUBCATEGORY

async def manual_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>Введите название подкатегории:</b>\n"
        "(Например: 'Игровые ПК', 'Женская одежда', 'Детские книги')",
        parse_mode=ParseMode.HTML
    )
    return ADDING_MANUAL_SUBCATEGORY

async def add_manual_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    manual_sub = update.message.text.strip()
    if not manual_sub:
        await update.message.reply_text("Пожалуйста, введите непустое название подкатегории.")
        return ADDING_MANUAL_SUBCATEGORY

    context.user_data["current_listing"]["subcategory_id"] = "manual"
    context.user_data["current_listing"]["subcategory_name"] = manual_sub
    return await prompt_region(update, context)


async def choose_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, category_id, sub_id = query.data.split("|")

    context.user_data["current_listing"] = user_data_listings.get(update.effective_user.id, {})
    
    # Ensure current_listing is correctly set up if not already
    if "category_id" not in context.user_data["current_listing"]:
        context.user_data["current_listing"]["category_id"] = category_id
        context.user_data["current_listing"]["category_name"] = CATEGORIES.get(category_id, "Неизвестно")


    subcategories = CATEGORIES.get(category_id, {}).get("subcategories", {})
    context.user_data["current_listing"]["subcategory_id"] = sub_id
    context.user_data["current_listing"]["subcategory_name"] = subcategories.get(sub_id)

    return await prompt_region(update, context)

async def prompt_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = []
    for region_id, region_data in REGIONS.items():
        keyboard.append([InlineKeyboardButton(region_data["name"], callback_data=f"region|{region_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к подкатегориям", callback_data="back_to_subcategories")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await (update.callback_query or update.message).reply_text(
        "<b>Шаг 3 из 9: Выберите регион:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_REGION

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    region_id = query.data.split("|")[1]
    context.user_data["current_listing"]["region_id"] = region_id
    context.user_data["current_listing"]["region_name"] = REGIONS.get(region_id, {}).get("name")

    cities = REGIONS.get(region_id, {}).get("cities", {})
    keyboard = []
    for city_id, city_name in cities.items():
        keyboard.append([InlineKeyboardButton(city_name, callback_data=f"city|{region_id}|{city_id}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_city")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к регионам", callback_data="back_to_regions")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"<b>Шаг 4 из 9: Выберите город для '{REGIONS.get(region_id, {}).get('name')}' или введите вручную:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_CITY

async def manual_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>Введите название города:</b>\n"
        "(Например: 'Киев', 'Одесса', 'Львов')",
        parse_mode=ParseMode.HTML
    )
    return ADDING_MANUAL_CITY

async def add_manual_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    manual_city_name = update.message.text.strip()
    if not manual_city_name:
        await update.message.reply_text("Пожалуйста, введите непустое название города.")
        return ADDING_MANUAL_CITY

    context.user_data["current_listing"]["city_id"] = "manual"
    context.user_data["current_listing"]["city_name"] = manual_city_name
    return await prompt_condition(update, context)

async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, region_id, city_id = query.data.split("|")

    cities = REGIONS.get(region_id, {}).get("cities", {})
    context.user_data["current_listing"]["city_id"] = city_id
    context.user_data["current_listing"]["city_name"] = cities.get(city_id)

    return await prompt_condition(update, context)

async def prompt_condition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = []
    for condition_id, condition_name in CONDITIONS.items():
        keyboard.append([InlineKeyboardButton(condition_name, callback_data=f"condition|{condition_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к выбору города", callback_data="back_to_cities")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "<b>Шаг 5 из 9: Выберите состояние товара:</b>"
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else: # This path is for manual city, where we got a message instead of callback
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return CHOOSING_CONDITION

async def choose_condition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    condition_id = query.data.split("|")[1]
    context.user_data["current_listing"]["condition_id"] = condition_id
    context.user_data["current_listing"]["condition_name"] = CONDITIONS.get(condition_id)

    await query.edit_message_text(
        "<b>Шаг 6 из 9: Введите название товара (до 100 символов):</b>\n"
        "(Например: 'Ноутбук HP Pavilion', 'Кроссовки Nike Air Max')",
        parse_mode=ParseMode.HTML
    )
    return ADDING_TITLE

async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title or len(title) > MAX_TITLE_LENGTH:
        await update.message.reply_text(
            f"Название не может быть пустым и должно содержать до {MAX_TITLE_LENGTH} символов. Попробуйте еще раз:"
        )
        return ADDING_TITLE
    context.user_data["current_listing"]["title"] = title
    await update.message.reply_text(
        "<b>Шаг 7 из 9: Введите описание товара (до 1000 символов):</b>\n"
        "(Например: 'Продаю свой ноутбук, в отличном состоянии, использовался 1 год...', "
        "укажите особенности, комплектацию, дефекты и т.д.)",
        parse_mode=ParseMode.HTML
    )
    return ADDING_DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    if not description or len(description) > MAX_DESCRIPTION_LENGTH:
        await update.message.reply_text(
            f"Описание не может быть пустым и должно содержать до {MAX_DESCRIPTION_LENGTH} символов. Попробуйте еще раз:"
        )
        return ADDING_DESCRIPTION
    context.user_data["current_listing"]["description"] = description
    await update.message.reply_text(
        "<b>Шаг 8 из 9: Введите цену товара в UAH (например, 1500.50):</b>\n"
        "(Можно указать 'Бесплатно' или 'Обмен'.)",
        parse_mode=ParseMode.HTML
    )
    return ADDING_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_str = update.message.text.strip().replace(',', '.')
    context.user_data["current_listing"]["price_raw"] = price_str # Store raw for display
    
    price_value = None
    if price_str.lower() == "бесплатно":
        price_value = 0.0
    elif price_str.lower() == "обмен":
        price_value = -1.0 # Special value for exchange
    else:
        try:
            price_value = float(price_str)
            if not (MIN_PRICE <= price_value <= MAX_PRICE):
                raise ValueError("Price out of range")
        except ValueError:
            await update.message.reply_text(
                f"Некорректный формат цены. Введите число (например, 1500.50), 'Бесплатно' или 'Обмен'."
            )
            return ADDING_PRICE
    
    context.user_data["current_listing"]["price"] = price_value

    keyboard = [
        [InlineKeyboardButton("📸 Добавить фото", callback_data="add_photos")],
        [InlineKeyboardButton("➡️ Пропустить (без фото)", callback_data="skip_photos")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "<b>Шаг 9 из 9: Добавьте фотографии (до 5 шт.) или пропустите:</b>\n"
        "<i>(Максимальный размер фото: 20 МБ)</i>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADDING_PHOTOS

async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data.get("current_listing", {})
    photos = user_data.get("photos", [])

    if len(photos) >= MAX_PHOTOS:
        await update.message.reply_text(f"Вы уже добавили максимальное количество фото ({MAX_PHOTOS}).")
        return ADDING_PHOTOS
    
    photo_file = update.message.photo[-1] # Get the largest photo version
    if photo_file.file_size > MAX_PHOTO_SIZE:
        await update.message.reply_text(f"Фотография слишком большая (макс. {MAX_PHOTO_SIZE / (1024 * 1024):.0f} МБ). Пожалуйста, загрузите меньшее фото.")
        return ADDING_PHOTOS

    photos.append(photo_file.file_id)
    user_data["photos"] = photos
    
    keyboard = []
    if len(photos) > 0:
        keyboard.append([InlineKeyboardButton("🗑️ Удалить последнее фото", callback_data="remove_last_photo")])
    if len(photos) < MAX_PHOTOS:
        keyboard.append([InlineKeyboardButton("📸 Добавить еще фото", callback_data="add_photos")])
    keyboard.append([InlineKeyboardButton("✅ Завершить добавление фото", callback_data="photos_done")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Фото добавлено. Добавлено фото: {len(photos)}/{MAX_PHOTOS}.\n"
        "Вы можете добавить еще или завершить.",
        reply_markup=reply_markup
    )
    return ADDING_PHOTOS

async def add_photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data.get("current_listing", {})
    photos_count = len(user_data.get("photos", []))

    if photos_count >= MAX_PHOTOS:
        await query.edit_message_text(f"Вы уже добавили максимальное количество фото ({MAX_PHOTOS}). Нажмите 'Завершить'.")
    else:
        await query.edit_message_text(
            f"Отправьте следующую фотографию ({photos_count+1}/{MAX_PHOTOS}):"
        )
    return ADDING_PHOTOS

async def remove_last_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_data = context.user_data.get("current_listing", {})
    photos = user_data.get("photos", [])

    if photos:
        photos.pop()
        user_data["photos"] = photos
        keyboard = []
        if len(photos) > 0:
            keyboard.append([InlineKeyboardButton("🗑️ Удалить последнее фото", callback_data="remove_last_photo")])
        if len(photos) < MAX_PHOTOS:
            keyboard.append([InlineKeyboardButton("📸 Добавить еще фото", callback_data="add_photos")])
        keyboard.append([InlineKeyboardButton("✅ Завершить добавление фото", callback_data="photos_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Последнее фото удалено. Добавлено фото: {len(photos)}/{MAX_PHOTOS}.\n"
            "Вы можете добавить еще или завершить.",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text("Нет фотографий для удаления.")
    return ADDING_PHOTOS

async def skip_photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["current_listing"]["photos"] = [] # Ensure it's empty if skipped
    return await preview_listing(update, context)

async def photos_done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await preview_listing(update, context)

async def preview_listing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data.get("current_listing", {})
    
    # Debugging: check if essential data is missing
    if not all(key in user_data for key in ["category_name", "subcategory_name", "region_name", "city_name", "condition_name", "title", "description", "price_raw"]):
        error_message = "Не удалось сформировать объявление. Отсутствуют некоторые данные. Начните сначала с /sell."
        keyboard = [[InlineKeyboardButton("🔄 Начать заново", callback_data="start_sell")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text(error_message, reply_markup=reply_markup)
        return ConversationHandler.END


    preview_text = f"""
    ✨ <b>Предварительный просмотр объявления:</b>
    
    <b>Категория:</b> {user_data.get('category_name')}
    <b>Подкатегория:</b> {user_data.get('subcategory_name')}
    <b>Регион:</b> {user_data.get('region_name')}
    <b>Город:</b> {user_data.get('city_name')}
    <b>Состояние:</b> {user_data.get('condition_name')}
    
    <b>Название:</b> {user_data.get('title')}
    <b>Описание:</b> {user_data.get('description')}
    <b>Цена:</b> {user_data.get('price_raw')} UAH
    
    <b>Фото:</b> {len(user_data.get('photos', []))} шт.
    """

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и опубликовать", callback_data="confirm")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="edit")],
        [InlineKeyboardButton("🗑️ Отменить", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send preview with photos if available
    photos_to_send = user_data.get('photos', [])
    if photos_to_send:
        media = []
        for i, photo_id in enumerate(photos_to_send):
            if i == 0: # First photo can have caption
                media.append(InputMediaPhoto(media=photo_id, caption=preview_text, parse_mode=ParseMode.HTML))
            else:
                media.append(InputMediaPhoto(media=photo_id))
        
        if update.callback_query:
            await update.callback_query.message.reply_media_group(media=media)
            await update.callback_query.message.reply_text(
                "Проверьте объявление и подтвердите публикацию:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif update.message:
            await update.message.reply_media_group(media=media)
            await update.message.reply_text(
                "Проверьте объявление и подтвердите публикацию:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    else:
        # If no photos, send only text
        if update.callback_query:
            await update.callback_query.edit_message_text(
                preview_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        elif update.message:
            await update.message.reply_text(
                preview_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )

    return CONFIRMING

async def edit_listing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Функция редактирования пока не реализована. Начните сначала.")
    # Implement specific edit options if needed
    keyboard = [
        [InlineKeyboardButton("🔄 Начать заново", callback_data="start_sell")],
        [InlineKeyboardButton("◀️ Назад к предварительному просмотру", callback_data="back_to_preview")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Функция редактирования не реализована. Вы можете начать объявление заново.",
        reply_markup=reply_markup
    )
    return CONFIRMING # Stay in CONFIRMING state to allow back to preview

async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await start_selling(update, context)

async def back_to_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category_id = context.user_data["current_listing"]["category_id"]
    
    subcategories = CATEGORIES.get(category_id, {}).get("subcategories", {})
    keyboard = []
    for sub_id, sub_name in subcategories.items():
        keyboard.append([InlineKeyboardButton(sub_name, callback_data=f"subcategory|{category_id}|{sub_id}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_subcategory")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"<b>Шаг 2 из 9: Выберите подкатегорию для '{CATEGORIES.get(category_id)}' или введите вручную:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_SUBCATEGORY

async def back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await prompt_region(update, context)

async def back_to_cities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    region_id = context.user_data["current_listing"]["region_id"]

    cities = REGIONS.get(region_id, {}).get("cities", {})
    keyboard = []
    for city_id, city_name in cities.items():
        keyboard.append([InlineKeyboardButton(city_name, callback_data=f"city|{region_id}|{city_id}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести вручную", callback_data="manual_city")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к регионам", callback_data="back_to_regions")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"<b>Шаг 4 из 9: Выберите город для '{REGIONS.get(region_id, {}).get('name')}' или введите вручную:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return CHOOSING_CITY

async def back_to_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await preview_listing(update, context)

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Публикуем объявление...")

    user_data = context.user_data.get("current_listing", {})

    # Проверяем наличие всех необходимых данных перед публикацией
    required_fields = [
        "category_name", "subcategory_name", "region_name", "city_name",
        "condition_name", "title", "description", "price_raw"
    ]
    if not all(field in user_data for field in required_fields):
        error_message = "Произошла ошибка: не все данные объявления заполнены. Пожалуйста, начните создание объявления заново командой /sell."
        await query.edit_message_text(error_message, parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    photos_to_send = user_data.get("photos", [])
    media = []
    if photos_to_send:
        for i, photo_id in enumerate(photos_to_send):
            if i == 0:
                media.append(InputMediaPhoto(media=photo_id, caption=format_listing_message(user_data), parse_mode=ParseMode.HTML))
            else:
                media.append(InputMediaPhoto(media=photo_id))
    else:
        # If no photos, just send the text message
        pass

    try:
        if media:
            await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=format_listing_message(user_data), parse_mode=ParseMode.HTML)

        await query.edit_message_text(
            "✅ Ваше объявление успешно опубликовано в канале!\n\n"
            "Используйте /start для создания нового объявления или для возврата в главное меню.",
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Failed to send message to channel: {e}")
        error_msg = f"❌ Произошла ошибка при публикации объявления. Попробуйте позже или свяжитесь с поддержкой.\nОшибка: {e}"
        await query.edit_message_text(error_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"An unexpected error occurred during confirmation: {e}")
        await query.edit_message_text("❌ Произошла непредвиденная ошибка при публикации объявления.", parse_mode=ParseMode.HTML)

    context.user_data.clear() # Clear user data after successful submission
    return ConversationHandler.END

def format_listing_message(data: Dict[str, Any]) -> str:
    """Форматирует данные объявления для отправки в канал."""
    price_display = ""
    if data.get('price') == 0.0:
        price_display = "Бесплатно"
    elif data.get('price') == -1.0:
        price_display = "Обмен"
    else:
        price_display = f"{data.get('price_raw')} UAH"

    username = f"@{data.get('username')}" if data.get('username') else f"{data.get('first_name')} {data.get('last_name') or ''}".strip()
    if not username: # Fallback if no username and no name
        username = f"Пользователь ID: {data.get('user_id')}"


    message = f"""
✨ <b>Новое объявление на ULX Ukraine!</b>

<b>Название:</b> {data.get('title')}
<b>Цена:</b> {price_display}

<b>Описание:</b>
{data.get('description')}

<b>Категория:</b> {data.get('category_name')} / {data.get('subcategory_name')}
<b>Местоположение:</b> {data.get('city_name')}, {data.get('region_name')}
<b>Состояние:</b> {data.get('condition_name')}

<b>Опубликовано:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
<b>Продавец:</b> {username}
"""
    return message

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий процесс создания объявления."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Создание объявления отменено.\n"
            "Используйте /start для начала нового объявления или возврата в главное меню.",
            parse_mode=ParseMode.HTML
        )
    elif update.message:
        await update.message.reply_text(
            "❌ Создание объявления отменено.\n"
            "Используйте /start для начала нового объявления или возврата в главное меню.",
            parse_mode=ParseMode.HTML
        )
    context.user_data.clear()
    return ConversationHandler.END

async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на неизвестные callback-запросы."""
    query = update.callback_query
    if query:
        await query.answer("Неизвестное действие. Пожалуйста, попробуйте еще раз.")
        await query.edit_message_text(
            "Произошла ошибка или действие не распознано. "
            "Пожалуйста, используйте кнопки или /start для перезапуска.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Начать заново", callback_data="start_sell")]])
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки в обновлениях."""
    logger.error(f"Exception while handling an update: {context.error}")

    try:
        # Try to send a message back to the user
        if isinstance(update, Update):
            if update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Произошла техническая ошибка. Пожалуйста, попробуйте еще раз или используйте /start.",
                    parse_mode=ParseMode.HTML
                )
            elif update.callback_query:
                await update.callback_query.answer("❌ Произошла ошибка")
                await update.callback_query.edit_message_text(
                    "❌ <b>Произошла техническая ошибка</b>\n\n"
                    "Используйте /start для перезапуска.",
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        logger.error(f"Error in error_handler's response: {e}")


# Главная функция
def main() -> None:
    print("🚀 Запуск ULX Ukraine Bot...")
    print(f"📊 Загружено {len(REGIONS)} областей")
    print(f"🏙️ Загружено {sum(len(c) for c in REGIONS.values())} городов")
    print(f"🏷️ Загружено {len(CATEGORIES)} категорий")
    print(f"🔧 Загружено {len(CONDITIONS)} состояний товаров")

    # Отримуємо токен зі змінних оточення Render
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    # Отримуємо URL сервісу зі змінних оточення Render
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

    # Перевіряємо, чи є токен
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN environment variable not set.")

    # Створюємо ApplicationBuilder
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Реєструємо хендлери
    # conv_handler має бути визначений ВИЩЕ функції main() або в глобальній області видимості
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_selling),
            CallbackQueryHandler(start_selling, pattern="^start_sell$"),
            CommandHandler("sell", start_selling)
        ],
        states={
            CHOOSING_CATEGORY: [
                CallbackQueryHandler(choose_category, pattern="^category\\|.*$")
            ],
            CHOOSING_SUBCATEGORY: [
                CallbackQueryHandler(choose_subcategory, pattern="^subcategory\\|.*$"),
                CallbackQueryHandler(manual_subcategory, pattern="^manual_subcategory$"),
                CallbackQueryHandler(back_to_categories, pattern="^back_to_categories$")
            ],
            ADDING_MANUAL_SUBCATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_manual_subcategory)
            ],
            CHOOSING_REGION: [
                CallbackQueryHandler(choose_region, pattern="^region\\|.*$"),
                CallbackQueryHandler(back_to_subcategories, pattern="^back_to_subcategories$")
            ],
            CHOOSING_CITY: [
                CallbackQueryHandler(choose_city, pattern="^city\\|.*$"),
                CallbackQueryHandler(back_to_regions, pattern="^back_to_regions$")
            ],
            ADDING_MANUAL_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_manual_city)
            ],
            CHOOSING_CONDITION: [
                CallbackQueryHandler(choose_condition, pattern="^condition\\|.*$"),
                CallbackQueryHandler(back_to_cities, pattern="^back_to_cities$")
            ],
            ADDING_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)
            ],
            ADDING_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)
            ],
            ADDING_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)
            ],
            ADDING_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_photos),
                CallbackQueryHandler(add_photos_handler, pattern="^add_photos$"),
                CallbackQueryHandler(skip_photos_handler, pattern="^skip_photos$"),
                CallbackQueryHandler(photos_done_handler, pattern="^photos_done$"),
                CallbackQueryHandler(remove_last_photo_handler, pattern="^remove_last_photo$")
            ],
            CONFIRMING: [
                CallbackQueryHandler(confirm, pattern="^confirm$"),
                CallbackQueryHandler(edit_listing, pattern="^edit$"),
                CallbackQueryHandler(back_to_preview, pattern="^back_to_preview$"),
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CommandHandler("start", start),
            CallbackQueryHandler(main_menu_handler, pattern="^main_menu$")
        ]
    )
    app.add_handler(conv_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(unknown_callback))
    app.add_error_handler(error_handler)

    # Запускаємо бота
    if RENDER_EXTERNAL_URL:
        port = int(os.environ.get("PORT", "8080"))

        asyncio.get_event_loop().run_until_complete(
            app.bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{TELEGRAM_TOKEN}")
        )
        print(f"✅ Вебхук встановлено: {RENDER_EXTERNAL_URL}/{TELEGRAM_TOKEN}")

        app.run_webhook(listen="0.0.0.0", port=port, url_path=TELEGRAM_TOKEN)
        print(f"✅ ULX Ukraine Bot запущено за допомогою вебхуків на порту {port}")
    else:
        print("✅ ULX Ukraine Bot запущен локально (polling)!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
