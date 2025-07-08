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
TOKEN = "8112684210:AAH1eo9dbi5_6SUdbBpLAacBl99aaMoN758"
CHANNEL_ID = "@ulx_ukraine"

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
    CONFIRMING
) = range(12)

# Улучшенные категории и подкатегории
CATEGORIES = {
    "🏠 Недвижимость": {
        "subcategories": ["Квартиры", "Дома", "Участки", "Коммерческая", "Аренда", "Гаражи", "Другое"],
        "has_condition": True
    },
    "🚗 Транспорт": {
        "subcategories": ["Легковые", "Грузовые", "Мотоциклы", "Водный транспорт", "Велосипеды", "Запчасти", "Другое"],
        "has_condition": True
    },
    "💼 Работа": {
        "subcategories": ["Вакансии", "Резюме", "Фриланс", "Стажировки", "Подработка", "Другое"],
        "has_condition": False
    },
    "📱 Электроника": {
        "subcategories": ["Телефоны", "Ноутбуки", "Фото/видео", "Аудио", "Игры", "Бытовая техника", "Другое"],
        "has_condition": True
    },
    "🏡 Дом и сад": {
        "subcategories": ["Мебель", "Техника", "Инструменты", "Ремонт", "Продукты", "Растения", "Другое"],
        "has_condition": True
    },
    "👗 Мода и красота": {
        "subcategories": ["Одежда", "Обувь", "Аксессуары", "Часы", "Украшения", "Косметика", "Другое"],
        "has_condition": True
    },
    "🧸 Дети": {
        "subcategories": ["Одежда", "Игрушки", "Коляски", "Школьные принадлежности", "Детская мебель", "Другое"],
        "has_condition": True
    },
    "🎯 Хобби и спорт": {
        "subcategories": ["Спорт", "Музыка", "Книги", "Коллекционирование", "Рукоделие", "Туризм", "Другое"],
        "has_condition": True
    },
    "🐕 Животные": {
        "subcategories": ["Собаки", "Кошки", "Птицы", "Рыбы", "Товары для животных", "Другое"],
        "has_condition": False
    },
    "🔧 Услуги": {
        "subcategories": ["Ремонт", "Красота", "Обучение", "Перевозки", "Клининг", "IT-услуги", "Другое"],
        "has_condition": False
    }
}

# ПОЛНЫЙ СПИСОК ВСЕХ ОБЛАСТЕЙ И ГОРОДОВ УКРАИНЫ
REGIONS = {
    "🌻 Винницкая обл.": [
        "Винница", "Жмеринка", "Хмельник", "Калинка", "Тульчин", 
        "Гайсин", "Козятын", "Липовец", "Могилёв-Подольский", "Ильинцы", "Другой"
    ],
    "🌲 Волынская обл.": [
        "Луцк", "Ковель", "Нововолынск", "Любомль", "Владимир-Волынский", 
        "Камень-Каширский", "Горохов", "Локачи", "Ратно", "Турийск", "Другой"
    ],
    "⚡ Днепропетровская обл.": [
        "Днепр", "Кривой Рог", "Никополь", "Покров", "Каменское", 
        "Марганец", "Желтые Воды", "Терновка", "Новомосковск", "Павлоград", "Другой"
    ],
    "🌿 Житомирская обл.": [
        "Житомир", "Коростень", "Малин", "Новоград-Волынский", "Бердичев", 
        "Чуднов", "Радомышль", "Овруч", "Андрушевка", "Емільчино", "Другой"
    ],
    "🏔️ Закарпатская обл.": [
        "Ужгород", "Мукачево", "Хуст", "Берегово", "Рахов", 
        "Виноградов", "Иршава", "Тячев", "Великий Березный", "Перечин", "Другой"
    ],
    "🌾 Запорожская обл.": [
        "Запорожье", "Мелитополь", "Пологи", "Бердянск", "Токмак", 
        "Васильевка", "Каменка-Днепровская", "Орехов", "Энергодар", "Гуляйполе", "Другой"
    ],
    "🎿 Ивано-Франковская обл.": [
        "Ивано-Франковск", "Коломыя", "Калуш", "Бурштын", "Надворная", 
        "Долина", "Городенка", "Болехов", "Снятын", "Яремче", "Другой"
    ],
    "🏛️ Киевская обл.": [
        "Киев", "Бровары", "Белая Церковь", "Борисполь", "Ирпень", 
        "Буча", "Васильков", "Обухов", "Переяслав", "Сквира", "Другой"
    ],
    "🌻 Кировоградская обл.": [
        "Кропивницкий", "Знаменка", "Светловодск", "Бобринец", "Новомиргород", 
        "Долинская", "Александрия", "Малая Виска", "Петрово", "Гайворон", "Другой"
    ],
    "🦁 Львовская обл.": [
        "Львов", "Дрогобыч", "Стрый", "Червоноград", "Самбор", 
        "Трускавец", "Борислав", "Моршин", "Новый Роздол", "Яворов", "Другой"
    ],
    "⚓ Николаевская обл.": [
        "Николаев", "Южноукраинск", "Первомайск", "Вознесенск", "Очаков", 
        "Баштанка", "Снигиревка", "Новая Одесса", "Березанка", "Арбузинка", "Другой"
    ],
    "🌊 Одесская обл.": [
        "Одесса", "Черноморск", "Белгород-Днестровский", "Измаил", "Подольск", 
        "Южный", "Теплодар", "Рени", "Килия", "Татарбунары", "Другой"
    ],
    "🌾 Полтавская обл.": [
        "Полтава", "Кременчуг", "Лубны", "Горишние Плавни", "Миргород", 
        "Пирятин", "Гадяч", "Зиньков", "Карловка", "Котельва", "Другой"
    ],
    "🌲 Ровенская обл.": [
        "Ровно", "Вараш", "Дубно", "Здолбунов", "Костополь", 
        "Сарны", "Березное", "Острог", "Демидовка", "Корец", "Другой"
    ],
    "🌿 Сумская обл.": [
        "Сумы", "Конотоп", "Шостка", "Ахтырка", "Ромны", 
        "Глухов", "Лебедин", "Тростянец", "Кролевец", "Путивль", "Другой"
    ],
    "🌾 Тернопольская обл.": [
        "Тернополь", "Кременец", "Чортков", "Бережаны", "Збараж", 
        "Гусятин", "Монастыриска", "Теребовля", "Шумск", "Залещики", "Другой"
    ],
    "🎓 Харьковская обл.": [
        "Харьков", "Чугуев", "Изюм", "Лозовая", "Первомайский", 
        "Балаклея", "Красноград", "Купянск", "Дергачи", "Мерефа", "Другой"
    ],
    "🌊 Херсонская обл.": [
        "Херсон", "Скадовск", "Новая Каховка", "Каховка", "Геническ", 
        "Голая Пристань", "Берислав", "Цюрупинск", "Армянск", "Таврийск", "Другой"
    ],
    "🌾 Хмельницкая обл.": [
        "Хмельницкий", "Шепетовка", "Нетешин", "Славута", "Каменец-Подольский", 
        "Старокостянтинов", "Хмельник", "Волочиск", "Изяслав", "Полонное", "Другой"
    ],
    "🌻 Черкасская обл.": [
        "Черкассы", "Умань", "Смела", "Каменка", "Звенигородка", 
        "Золотоноша", "Городище", "Канев", "Корсунь-Шевченковский", "Тальное", "Другой"
    ],
    "🌹 Черновицкая обл.": [
        "Черновцы", "Новоднестровск", "Кицмань", "Сторожинец", "Вижница", 
        "Заставна", "Кельменцы", "Глыбока", "Хотин", "Берегомет", "Другой"
    ],
    "🌲 Черниговская обл.": [
        "Чернигов", "Нежин", "Прилуки", "Бахмач", "Новгород-Северский", 
        "Корюковка", "Щорс", "Городня", "Мена", "Семеновка", "Другой"
    ]
}

CONDITIONS = ["✨ Новое", "⭐ Отличное", "👍 Хорошее", "🔧 Удовлетворительное", "🛠️ Требует ремонта"]

# Валидация данных
def validate_price(price_text: str) -> Optional[float]:
    """Валидация цены"""
    try:
        # Убираем пробелы и заменяем запятые на точки
        price_text = price_text.replace(' ', '').replace(',', '.')
        price = float(price_text)
        
        if MIN_PRICE <= price <= MAX_PRICE:
            return price
        return None
    except (ValueError, TypeError):
        return None

def validate_title(title: str) -> bool:
    """Валидация заголовка"""
    return 3 <= len(title.strip()) <= MAX_TITLE_LENGTH

def validate_description(description: str) -> bool:
    """Валидация описания"""
    return 10 <= len(description.strip()) <= MAX_DESCRIPTION_LENGTH

# Функции для создания клавиатур
def create_keyboard(items: List[str], callback_prefix: str, columns: int = 1) -> List[List[InlineKeyboardButton]]:
    """Создает клавиатуру с кнопками"""
    keyboard = []
    for i in range(0, len(items), columns):
        row = []
        for j in range(columns):
            if i + j < len(items):
                item = items[i + j]
                # Ограничиваем длину callback_data до 64 символов
                callback_data = f"{callback_prefix}|{item}"
                if len(callback_data) > 64:
                    callback_data = callback_data[:64]
                row.append(InlineKeyboardButton(item, callback_data=callback_data))
        keyboard.append(row)
    return keyboard

def back_button(callback_data: str) -> List[InlineKeyboardButton]:
    """Создает кнопку Назад"""
    return [InlineKeyboardButton("⬅️ Назад", callback_data=callback_data)]

def cancel_button() -> List[InlineKeyboardButton]:
    """Создает кнопку Отмена"""
    return [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]

# Функции для работы с данными пользователя
def get_user_data(context: ContextTypes.DEFAULT_TYPE, key: str, default=None):
    """Получает данные пользователя"""
    return context.user_data.get(key, default)

def set_user_data(context: ContextTypes.DEFAULT_TYPE, key: str, value):
    """Устанавливает данные пользователя"""
    context.user_data[key] = value

def clear_user_data(context: ContextTypes.DEFAULT_TYPE):
    """Очищает данные пользователя"""
    context.user_data.clear()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Стартовое сообщение"""
    welcome_text = """
🎉 <b>Добро пожаловать в ULX Ukraine!</b>

Это ваш надежный помощник для размещения объявлений о продаже товаров и услуг по всей Украине.

<b>Что вы можете сделать:</b>
• 📝 Создать объявление о продаже
• 🏷️ Выбрать из множества категорий
• 🌍 Указать свой город и область
• 📸 Добавить фотографии товара
• 💰 Указать цену

<b>Готовы начать?</b>
Нажмите кнопку ниже, чтобы создать свое первое объявление!
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    
    try:
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Ошибка отправки стартового сообщения: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда помощи"""
    help_text = """
<b>📋 Инструкция по использованию бота:</b>

<b>1. Создание объявления:</b>
• Нажмите "Создать объявление"
• Выберите категорию товара
• Укажите подкатегорию
• Выберите область и город
• Укажите состояние товара (если применимо)
• Введите название объявления (3-100 символов)
• Добавьте описание (10-1000 символов)
• Укажите цену (от 0.01 до 1,000,000)
• Загрузите фотографии (до 5 штук)
• Подтвердите публикацию

<b>2. Команды:</b>
• /start - Главное меню
• /sell - Создать объявление
• /help - Эта справка

<b>3. Ограничения:</b>
• Максимум 5 фотографий
• Размер фото до 20MB каждое
• Название: 3-100 символов
• Описание: 10-1000 символов

<b>4. Поддержка:</b>
При возникновении проблем используйте команду /start для перезапуска.
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    try:
        if update.message:
            await update.message.reply_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
    except TelegramError as e:
        logger.error(f"Ошибка отправки справки: {e}")

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена создания объявления"""
    query = update.callback_query
    if query:
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        
        await query.edit_message_text(
            "❌ <b>Создание объявления отменено</b>\n\n"
            "Все введенные данные удалены.\n"
            "Вы можете начать заново в любое время.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ Создание объявления отменено.",
            parse_mode=ParseMode.HTML
        )
    
    clear_user_data(context)
    return ConversationHandler.END

# Начало создания объявления
async def start_selling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса создания объявления"""
    query = update.callback_query
    await query.answer()
    
    clear_user_data(context)
    
    keyboard = create_keyboard(list(CATEGORIES.keys()), "category", 2)
    keyboard.extend([cancel_button()])
    
    await query.edit_message_text(
        "🏷️ <b>Выберите категорию для вашего объявления:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_CATEGORY

# Выбор категории
async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора категории"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.edit_message_text("❌ Ошибка выбора категории. Попробуйте снова.")
        return ConversationHandler.END
    
    category = data[1]
    
    if category not in CATEGORIES:
        await query.edit_message_text("❌ Неверная категория. Попробуйте снова.")
        return ConversationHandler.END
    
    set_user_data(context, 'category', category)
    
    subcategories = CATEGORIES[category]["subcategories"]
    keyboard = create_keyboard(subcategories, "subcategory", 2)
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить свою", callback_data="manual_subcategory")],
        back_button("back_to_categories"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"📂 <b>Категория:</b> {category}\n\n"
        f"<b>Выберите подкатегорию:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_SUBCATEGORY

# Выбор подкатегории
async def choose_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора подкатегории"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.edit_message_text("❌ Ошибка выбора подкатегории.")
        return ConversationHandler.END
    
    subcategory = data[1]
    set_user_data(context, 'subcategory', subcategory)
    
    # Переход к выбору региона
    keyboard = create_keyboard(list(REGIONS.keys()), "region", 1)
    keyboard.extend([
        back_button("back_to_subcategories"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"📍 <b>Выберите область:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_REGION

# Ручной ввод подкатегории
async def manual_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ручной ввод подкатегории"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✏️ <b>Введите название подкатегории:</b>\n\n"
        "Например: Смартфоны, Зимняя одежда, Детские книги",
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_MANUAL_SUBCATEGORY

async def add_manual_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение ручной подкатегории"""
    subcategory = update.message.text.strip()
    
    if not subcategory or len(subcategory) > 50:
        await update.message.reply_text(
            "❌ Название подкатегории должно содержать от 1 до 50 символов. Попробуйте снова:"
        )
        return ADDING_MANUAL_SUBCATEGORY
    
    set_user_data(context, 'subcategory', subcategory)
    
    keyboard = create_keyboard(list(REGIONS.keys()), "region", 1)
    keyboard.extend([cancel_button()])
    
    await update.message.reply_text(
        f"📍 <b>Выберите область:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_REGION

# Выбор региона
async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора региона"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.edit_message_text("❌ Ошибка выбора области.")
        return ConversationHandler.END
    
    region = data[1]
    
    if region not in REGIONS:
        await query.edit_message_text("❌ Неверная область.")
        return ConversationHandler.END
    
    set_user_data(context, 'region', region)
    
    cities = REGIONS[region]
    keyboard = create_keyboard(cities, "city", 2)
    keyboard.extend([
        back_button("back_to_regions"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"🏙️ <b>Область:</b> {region}\n\n"
        f"<b>Выберите город:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_CITY

# Выбор города
async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора города"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.edit_message_text("❌ Ошибка выбора города.")
        return ConversationHandler.END
    
    city = data[1]
    
    if city == "Другой":
        await query.edit_message_text(
            "✏️ <b>Введите название вашего города:</b>",
            parse_mode=ParseMode.HTML
        )
        return ADDING_MANUAL_CITY
    
    set_user_data(context, 'city', city)
    
    # Проверяем, нужно ли указывать состояние
    category = get_user_data(context, 'category')
    if CATEGORIES[category]["has_condition"]:
        keyboard = create_keyboard(CONDITIONS, "condition", 1)
        keyboard.extend([
            back_button("back_to_cities"),
            cancel_button()
        ])
        
        await query.edit_message_text(
            f"🔧 <b>Укажите состояние товара:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        return CHOOSING_CONDITION
    else:
        # Переходим сразу к названию
        await query.edit_message_text(
            f"📝 <b>Введите название объявления:</b>\n\n"
            f"Например: iPhone 13 Pro 128GB, Квартира 2-комн в центре\n\n"
            f"<i>Длина: от 3 до {MAX_TITLE_LENGTH} символов</i>",
            parse_mode=ParseMode.HTML
        )
        
        return ADDING_TITLE

# Ручной ввод города
async def add_manual_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение ручного города"""
    city = update.message.text.strip()
    
    if not city or len(city) > 50:
        await update.message.reply_text(
            "❌ Название города должно содержать от 1 до 50 символов. Попробуйте снова:"
        )
        return ADDING_MANUAL_CITY
    
    set_user_data(context, 'city', city)
    
    # Проверяем, нужно ли указывать состояние
    category = get_user_data(context, 'category')
    if CATEGORIES[category]["has_condition"]:
        keyboard = create_keyboard(CONDITIONS, "condition", 1)
        keyboard.extend([cancel_button()])
        
        await update.message.reply_text(
            f"🔧 <b>Укажите состояние товара:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        return CHOOSING_CONDITION
    else:
        await update.message.reply_text(
            f"📝 <b>Введите название объявления:</b>\n\n"
            f"Например: iPhone 13 Pro 128GB, Квартира 2-комн в центре\n\n"
            f"<i>Длина: от 3 до {MAX_TITLE_LENGTH} символов</i>",
            parse_mode=ParseMode.HTML
        )
        
        return ADDING_TITLE

# Выбор состояния
async def choose_condition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора состояния"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.edit_message_text("❌ Ошибка выбора состояния.")
        return ConversationHandler.END
    
    condition = data[1]
    set_user_data(context, 'condition', condition)
    
    await query.edit_message_text(
        f"📝 <b>Введите название объявления:</b>\n\n"
        f"Например: iPhone 13 Pro 128GB, Квартира 2-комн в центре\n\n"
        f"<i>Длина: от 3 до {MAX_TITLE_LENGTH} символов</i>",
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_TITLE

# Добавление названия
async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавление названия объявления"""
    title = update.message.text.strip()
    
    if not validate_title(title):
        await update.message.reply_text(
            f"❌ Название должно содержать от 3 до {MAX_TITLE_LENGTH} символов. Попробуйте снова:"
        )
        return ADDING_TITLE
    
    set_user_data(context, 'title', title)
    
    await update.message.reply_text(
        f"📄 <b>Добавьте описание товара:</b>\n\n"
        f"Опишите детали, особенности, причину продажи и т.д.\n\n"
        f"<i>Длина: от 10 до {MAX_DESCRIPTION_LENGTH} символов</i>",
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_DESCRIPTION

# Добавление описания
async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавление описания объявления"""
    description = update.message.text.strip()
    
    if not validate_description(description):
        await update.message.reply_text(
            f"❌ Описание должно содержать от 10 до {MAX_DESCRIPTION_LENGTH} символов. Попробуйте снова:"
        )
        return ADDING_DESCRIPTION
    
    set_user_data(context, 'description', description)
    
    await update.message.reply_text(
        f"💰 <b>Укажите цену в грн:</b>\n\n"
        f"Например: 1500, 25000, 500.50\n\n"
        f"<i>Диапазон: от {MIN_PRICE} до {MAX_PRICE:,.0f} грн</i>",
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_PRICE

# Добавление цены
async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавление цены"""
    price_text = update.message.text.strip()
    price = validate_price(price_text)
    
    if price is None:
        await update.message.reply_text(
            f"❌ Неверная цена. Укажите число от {MIN_PRICE} до {MAX_PRICE:,.0f}. Попробуйте снова:"
        )
        return ADDING_PRICE
    
    set_user_data(context, 'price', price)
    
    keyboard = [
        [InlineKeyboardButton("📸 Добавить фото", callback_data="add_photos")],
        [InlineKeyboardButton("⏭️ Пропустить фото", callback_data="skip_photos")]
    ]
    
    await update.message.reply_text(
        f"📸 <b>Добавьте фотографии товара:</b>\n\n"
        f"Можете загрузить до {MAX_PHOTOS} фотографий.\n"
        f"Максимальный размер одного фото: {MAX_PHOTO_SIZE // (1024*1024)}MB\n\n"
        f"<i>Фотографии помогают продать товар быстрее!</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_PHOTOS

# Обработка фотографий
async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка добавленных фотографий"""
    if update.message.photo:
        photos = get_user_data(context, 'photos', [])
        
        if len(photos) >= MAX_PHOTOS:
            await update.message.reply_text(
                f"❌ Максимум {MAX_PHOTOS} фотографий. Нажмите 'Готово' для продолжения."
            )
            return ADDING_PHOTOS
        
        # Получаем фото наилучшего качества
        photo = update.message.photo[-1]
        
        if photo.file_size and photo.file_size > MAX_PHOTO_SIZE:
            await update.message.reply_text(
                f"❌ Фото слишком большое. Максимум {MAX_PHOTO_SIZE // (1024*1024)}MB."
            )
            return ADDING_PHOTOS
        
        photos.append(photo.file_id)
        set_user_data(context, 'photos', photos)
        
        keyboard = [
            [InlineKeyboardButton("✅ Готово", callback_data="photos_done")],
            [InlineKeyboardButton("🗑️ Удалить последнее", callback_data="remove_last_photo")]
        ]
        
        await update.message.reply_text(
            f"✅ Фото добавлено! ({len(photos)}/{MAX_PHOTOS})\n\n"
            f"Отправьте еще фото или нажмите 'Готово'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ADDING_PHOTOS
    
    return ADDING_PHOTOS

async def add_photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало добавления фотографий"""
    query = update.callback_query
    await query.answer()
    
    set_user_data(context, 'photos', [])
    
    await query.edit_message_text(
        f"📸 <b>Отправьте фотографии товара:</b>\n\n"
        f"Максимум {MAX_PHOTOS} фото, до {MAX_PHOTO_SIZE // (1024*1024)}MB каждое",
        parse_mode=ParseMode.HTML
    )
    
    return ADDING_PHOTOS

async def skip_photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск добавления фотографий"""
    query = update.callback_query
    await query.answer()
    
    set_user_data(context, 'photos', [])
    return await show_confirmation(update, context)

async def photos_done_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершение добавления фотографий"""
    query = update.callback_query
    await query.answer()
    
    return await show_confirmation(update, context)

async def remove_last_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удаление последней фотографии"""
    query = update.callback_query
    await query.answer()
    
    photos = get_user_data(context, 'photos', [])
    if photos:
        photos.pop()
        set_user_data(context, 'photos', photos)
        
        if photos:
            keyboard = [
                [InlineKeyboardButton("✅ Готово", callback_data="photos_done")],
                [InlineKeyboardButton("🗑️ Удалить последнее", callback_data="remove_last_photo")]
            ]
            
            await query.edit_message_text(
                f"🗑️ Последнее фото удалено! ({len(photos)}/{MAX_PHOTOS})\n\n"
                f"Отправьте еще фото или нажмите 'Готово'",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                f"📸 <b>Отправьте фотографии товара:</b>\n\n"
                f"Максимум {MAX_PHOTOS} фото, до {MAX_PHOTO_SIZE // (1024*1024)}MB каждое",
                parse_mode=ParseMode.HTML
            )
    
    return ADDING_PHOTOS

# Показ подтверждения
async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает предварительный просмотр объявления"""
    data = context.user_data
    photos = get_user_data(context, 'photos', [])
    
    # Формируем текст предварительного просмотра
    preview_text = f"""
📋 <b>Предварительный просмотр объявления:</b>

🏷️ <b>Категория:</b> {data.get('category', 'Не указана')}
📂 <b>Подкатегория:</b> {data.get('subcategory', 'Не указана')}
📍 <b>Область:</b> {data.get('region', 'Не указана')}
🏙️ <b>Город:</b> {data.get('city', 'Не указан')}
"""
    
    if 'condition' in data:
        preview_text += f"🔧 <b>Состояние:</b> {data['condition']}\n"
    
    preview_text += f"""
📝 <b>Название:</b> {data.get('title', 'Не указано')}
📄 <b>Описание:</b> {data.get('description', 'Не указано')}
💰 <b>Цена:</b> {data.get('price', 0):,.0f} грн
📸 <b>Фотографий:</b> {len(photos)}

<i>Проверьте данные и подтвердите публикацию</i>
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Опубликовать", callback_data="confirm")],
        [InlineKeyboardButton("📝 Редактировать", callback_data="edit")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    return CONFIRMING

# Подтверждение публикации
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Публикация объявления в канал"""
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    photos = get_user_data(context, 'photos', [])
    
    # Формируем текст объявления для канала
    post_text = f"""
🆕 <b>НОВОЕ ОБЪЯВЛЕНИЕ</b>

📝 <b>{data.get('title', 'Без названия')}</b>

📄 <b>Описание:</b>
{data.get('description', 'Без описания')}

🏷️ <b>Категория:</b> {data.get('category', 'Не указана')} → {data.get('subcategory', 'Не указана')}
📍 <b>Местоположение:</b> {data.get('region', 'Не указана')}, {data.get('city', 'Не указан')}
"""
    
    if 'condition' in data:
        post_text += f"🔧 <b>Состояние:</b> {data['condition']}\n"
    
    post_text += f"""
💰 <b>Цена:</b> {data.get('price', 0):,.0f} грн

👤 <b>Продавец:</b> @{query.from_user.username or 'Не указан'}
📞 <b>Контакт:</b> @{query.from_user.username or 'Написать в личку'}

⏰ <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

#объявление #{data.get('category', 'категория').replace(' ', '_').replace('🏠', '').replace('🚗', '').replace('💼', '').replace('📱', '').replace('🏡', '').replace('👗', '').replace('🧸', '').replace('🎯', '').replace('🐕', '').replace('🔧', '').strip()}
"""
    
    try:
        # Отправляем объявление в канал
        if photos:
            # Если есть фото, отправляем их группой
            media_group = []
            for i, photo_id in enumerate(photos[:MAX_PHOTOS]):
                if i == 0:
                    # Первое фото с текстом
                    media_group.append(InputMediaPhoto(media=photo_id, caption=post_text, parse_mode=ParseMode.HTML))
                else:
                    # Остальные фото без текста
                    media_group.append(InputMediaPhoto(media=photo_id))
            
            await context.bot.send_media_group(
                chat_id=CHANNEL_ID,
                media=media_group
            )
        else:
            # Если фото нет, отправляем только текст
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                parse_mode=ParseMode.HTML
            )
        
        success_text = f"""
✅ <b>Объявление успешно опубликовано!</b>

Ваше объявление размещено в канале {CHANNEL_ID}

<b>📊 Статистика публикации:</b>
• Название: {len(data.get('title', ''))} символов
• Описание: {len(data.get('description', ''))} символов
• Фотографий: {len(photos)}
• Категория: {data.get('category', 'Не указана')}
• Локация: {data.get('city', 'Не указан')}, {data.get('region', 'Не указана')}

<b>🚀 Что дальше?</b>
• Ваше объявление увидят подписчики канала
• Заинтересованные покупатели свяжутся с вами
• Объявление останется в канале до продажи

<i>Спасибо за использование ULX Ukraine!</i>
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Создать еще объявление", callback_data="start_sell")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Объявление опубликовано пользователем {query.from_user.username or query.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await query.edit_message_text(
            "❌ <b>Ошибка публикации</b>\n\n"
            "Произошла ошибка при публикации объявления. "
            "Возможные причины:\n"
            "• Проблемы с подключением к каналу\n"
            "• Бот не является администратором канала\n"
            "• Временные технические проблемы\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode=ParseMode.HTML
        )
    
    clear_user_data(context)
    return ConversationHandler.END

# Редактирование объявления
async def edit_listing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к редактированию объявления"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Изменить название", callback_data="edit_title")],
        [InlineKeyboardButton("📄 Изменить описание", callback_data="edit_description")],
        [InlineKeyboardButton("💰 Изменить цену", callback_data="edit_price")],
        [InlineKeyboardButton("📸 Изменить фото", callback_data="edit_photos")],
        [InlineKeyboardButton("⬅️ Назад к просмотру", callback_data="back_to_preview")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    
    await query.edit_message_text(
        "📝 <b>Что хотите изменить?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CONFIRMING

# Навигация назад
async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору категорий"""
    query = update.callback_query
    await query.answer()
    
    clear_user_data(context)
    
    keyboard = create_keyboard(list(CATEGORIES.keys()), "category", 2)
    keyboard.extend([cancel_button()])
    
    await query.edit_message_text(
        "🏷️ <b>Выберите категорию для вашего объявления:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_CATEGORY

async def back_to_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору подкатегорий"""
    query = update.callback_query
    await query.answer()
    
    category = get_user_data(context, 'category')
    if not category:
        return await back_to_categories(update, context)
    
    subcategories = CATEGORIES[category]["subcategories"]
    keyboard = create_keyboard(subcategories, "subcategory", 2)
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить свою", callback_data="manual_subcategory")],
        back_button("back_to_categories"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"📂 <b>Категория:</b> {category}\n\n"
        f"<b>Выберите подкатегорию:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_SUBCATEGORY

async def back_to_regions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору регионов"""
    query = update.callback_query
    await query.answer()
    
    keyboard = create_keyboard(list(REGIONS.keys()), "region", 1)
    keyboard.extend([
        back_button("back_to_subcategories"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"📍 <b>Выберите область:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_REGION

async def back_to_cities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору городов"""
    query = update.callback_query
    await query.answer()
    
    region = get_user_data(context, 'region')
    if not region:
        return await back_to_regions(update, context)
    
    cities = REGIONS[region]
    keyboard = create_keyboard(cities, "city", 2)
    keyboard.extend([
        back_button("back_to_regions"),
        cancel_button()
    ])
    
    await query.edit_message_text(
        f"🏙️ <b>Область:</b> {region}\n\n"
        f"<b>Выберите город:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return CHOOSING_CITY

async def back_to_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к предварительному просмотру"""
    query = update.callback_query
    await query.answer()
    
    return await show_confirmation(update, context)


# Обработка неизвестных callback
async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка неизвестных callback запросов"""
    query = update.callback_query
    await query.answer("❌ Неизвестная команда")
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "❌ <b>Произошла ошибка</b>\n\n"
        "Неизвестная команда. Вернитесь в главное меню.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# Обработка главного меню
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    clear_user_data(context)
    
    welcome_text = """
🎉 <b>Добро пожаловать в ULX Ukraine!</b>

Это ваш надежный помощник для размещения объявлений о продаже товаров и услуг по всей Украине.

<b>Что вы можете сделать:</b>
• 📝 Создать объявление о продаже
• 🏷️ Выбрать из множества категорий
• 🌍 Указать свой город и область
• 📸 Добавить фотографии товара
• 💰 Указать цену

<b>Готовы начать?</b>
Нажмите кнопку ниже, чтобы создать свое первое объявление!
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Создать объявление", callback_data="start_sell")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    
    await query.edit_message_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# Команда /sell
async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sell для быстрого создания объявления"""
    welcome_text = """
🚀 <b>Создание объявления</b>

Начнем создание вашего объявления!
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 Начать", callback_data="start_sell")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    try:
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.message:
            await update.message.reply_text(
                "❌ <b>Произошла техническая ошибка</b>\n\n"
                "Попробуйте:\n"
                "• Использовать команду /start\n"
                "• Обратиться к администратору\n"
                "• Попробовать позже",
                parse_mode=ParseMode.HTML
            )
        elif update and update.callback_query:
            try:
                await update.callback_query.answer("❌ Произошла ошибка")
                await update.callback_query.edit_message_text(
                    "❌ <b>Произошла техническая ошибка</b>\n\n"
                    "Используйте /start для перезапуска.",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
    except Exception as e:
        print(f"Error in error_handler: {e}")
# Главная функция
def main() -> None:
    print("🚀 Запуск ULX Ukraine Bot...")
    print(f"📊 Загружено {len(REGIONS)} областей")
    print(f"🏙️ Загружено {sum(len(c) for c in REGIONS.values())} городов")
    print(f"🏷️ Загружено {len(CATEGORIES)} категорий")
    print(f"🔧 Загружено {len(CONDITIONS)} состояний товаров")
    
    # 1) Создаём приложение
    app = ApplicationBuilder().token(TOKEN).build()
    
    # 2) Регистрируем хэндлеры
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_selling),
            CallbackQueryHandler(start_selling, pattern="^start_sell$"),
            CommandHandler("sell", start_selling) # Changed from sell_command to start_selling for consistency
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
                # Add handlers for specific edits if you implement them
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CommandHandler("start", start), # Allow /start to reset the conversation
            CallbackQueryHandler(main_menu_handler, pattern="^main_menu$") # Allow main_menu to reset
        ]
    )
    app.add_handler(conv_handler)
    
    app.add_handler(CommandHandler("start", start)) # This is the initial /start, separate from conv_handler's entry_point
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(help_command,     pattern="^help$"))
    app.add_handler(CallbackQueryHandler(main_menu_handler,pattern="^main_menu$"))
    # Catch any unhandled callback queries and messages that aren't part of the conversation
    app.add_handler(CallbackQueryHandler(unknown_callback))
    app.add_error_handler(error_handler)
    
    # 3) Запускаем бота локально
    print("✅ ULX Ukraine Bot запущен локально!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
