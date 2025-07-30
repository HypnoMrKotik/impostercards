import json
import os
import time
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)
import random
import pprint

# --- Конфигурация ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BALANCES_FILE = os.path.join(BASE_DIR, "user_balances.json")
COOLDOWNS_FILE = os.path.join(BASE_DIR, "user_cooldowns.json")
COLLECTION_FILE = os.path.join(BASE_DIR, "user_collection.json")
BONUSES_FILE = os.path.join(BASE_DIR, "user_bonuses.json") # Новый файл для бонусов

# --- Параметры перезарядки ---
IMPOSTERCARD_COOLDOWN_MINUTES = 10
IMPOSTERCARD_COOLDOWN_SECONDS = IMPOSTERCARD_COOLDOWN_MINUTES * 60

# --- Цены и Товары в Магазине ---
BONUS_SKIP_COOLDOWN_PRICE = 30
SHOP_ITEMS = {
    "skip_cooldown": {
        "name": "Убрать перезарядку",
        "description": "Позволяет использовать /impostercard один раз без перезарядки.",
        "price": BONUS_SKIP_COOLDOWN_PRICE,
        "type": "bonus"
    }
}

# --- ЗАПОЛНИ ЭТО! ---
cards = [
    {"name": "веселый космонавт", "rarity": 0.50, "coins": 5, "image_id": "AgACAgIAAxkBAAMPaIjTDAABa1XdHP-K7PsC32vF2tKRAAIp7zEbce9ISGn6c69erHVqAQADAgADeAADNgQ"}, # Пример file_id (замени на свой!)
    {"name": "капустота", "rarity": 0.10, "coins": 1, "image_id": "AgACAgIAAxkBAAMNaIjSuz1fmDRwrT6_OW8vu0nCNckAAoT0MRt1P0BIN3NoLgtN6oIBAAMCAAN5AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "мороженное", "rarity": 0.10, "coins": 50, "image_id": "AgACAgIAAxkBAAMzaIjUmPvSuUBERfFI31qQaqEFjTkAAoz0MRt1P0BIx7UCEm7Ey-8BAAMCAANtAAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "snowbat", "rarity": 0.01, "coins": 100, "image_id": "AgACAgIAAxkBAAPMaIn99fcz8_BOB3f2RSKNJb6kMPMAAo_vMRt1P1BIUM91id5qRrkBAAMCAAN4AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "флауи", "rarity": 0.05, "coins": 50, "image_id": "AgACAgIAAxkBAAPLaIn91IVTMy3dYNE9l4sQWAdiDb8AAgf2MRsIn1BInSYKAzFMnAIBAAMCAAN4AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "пиксельный импостер", "rarity": 0.20, "coins": 30, "image_id": "AgACAgIAAxkBAAPNaIoBPWnVDrgI4-fnoL1fxnC1hF0AAqfvMRt1P1BIXjCIeFBcAmEBAAMCAAN5AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "батарейки", "rarity": 0.001, "coins": 100, "image_id": "AgACAgIAAxkBAAPbaIoUEOqgijkag2A1ii4TFlNOVBkAAsrwMRt1P1BISBXvWcQmiBMBAAMCAAN4AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "миникосмонавт", "rarity": 0.01, "coins": 70, "image_id": "AgACAgIAAxkBAAPcaIoUELsnXxX353mISjQz6CFAL7EAAsnwMRt1P1BIVCBFC4KhuTMBAAMCAAN4AAM2BA"}, # Пример file_id (замени на свой!)
    {"name": "иконка импостера", "rarity": 0.30, "coins": 20, "image_id": "AgACAgIAAxkBAAMOaIjS5V8vG0zXCUJJuO9-VY3HuNkAAob0MRt1P0BIV8NEGy3f1-wBAAMCAANtAAM2BA"}, # Пример file_id (замени на свой!)
]
CARD_BY_NAME = {card["name"].lower(): card for card in cards}

# --- Функции вспомогательные ---

def escape_markdown(text):
    """Экранирует специальные символы Markdown для безопасного отображения."""
    if not isinstance(text, str):
        return text 
    text = text.replace('*', '\\*')
    text = text.replace('_', '\\_')
    text = text.replace('`', '\\`')
    text = text.replace('[', '\\[')
    text = text.replace('\\', '\\\\')
    text = text.replace(']', '\\]')
    return text

def load_json_file(filepath):
    """Загружает данные из JSON файла."""
    print(f"[init] Попытка загрузить данные из: {filepath}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                print(f"[init] Файл {os.path.basename(filepath)} пуст. Начинаем с пустого словаря.")
                return {}
            return json.loads(content)
    except FileNotFoundError:
        print(f"[init] Файл {os.path.basename(filepath)} не найден. Будет создан новый при первом сохранении.")
        return {}
    except json.JSONDecodeError:
        print(f"[init] Ошибка декодирования JSON в файле {filepath}. Файл поврежден или имеет некорректный формат.")
        return {}

def save_json_file(filepath, data):
    """Сохраняет данные в JSON файл."""
    print(f"[save] Попытка сохранить данные в: {filepath}")
    seen_ids = set()
    duplicates_in_dict = False
    for key in data:
        if key in seen_ids:
            print(f"[DEBUG] !!! ОБНАРУЖЕН ДУБЛИКАТ КЛЮЧА В СЛОВАРЕ: '{key}'")
            duplicates_in_dict = True
        seen_ids.add(key)

    if duplicates_in_dict:
        print(f"[DEBUG] Содержимое словаря ({os.path.basename(filepath)}) перед сохранением (с дубликатами):")
        pprint.pprint(data)
    else:
        print(f"[DEBUG] Дубликатов ключей в словаре ({os.path.basename(filepath)}) перед сохранением не найдено.")

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[save] Данные в файл {os.path.basename(filepath)} успешно сохранены.")
    except IOError as e:
        print(f"[ERROR] Не удалось сохранить файл {filepath}: {e}")
    except Exception as e:
        print(f"[ERROR] Произошла непредвиденная ошибка при сохранении {filepath}: {e}")

# --- Загрузка данных ---
user_balances = load_json_file(BALANCES_FILE)
user_cooldowns = load_json_file(COOLDOWNS_FILE)
user_collection = load_json_file(COLLECTION_FILE)
user_bonuses = load_json_file(BONUSES_FILE) # Загрузка данных о бонусах

# --- Вспомогательные функции для управления данными пользователя ---

# --- Функции для баланса ---
def get_user_balance_data(user_id_str, user_name=None, username=None):
    """Получает или создает запись баланса пользователя."""
    if user_id_str not in user_balances:
        user_balances[user_id_str] = {
            "balance": 0,
            "name": user_name if user_name else str(user_id_str),
            "username": username
        }
        print(f"[balance_manager] Создана новая запись баланса для пользователя {user_id_str}.")
    else:
        user_data = user_balances[user_id_str]
        if user_name and user_data.get("name") != user_name:
            user_data["name"] = user_name
            print(f"[balance_manager] Обновлено имя пользователя {user_id_str} на '{user_name}'.")
        if username and user_data.get("username") != username:
            user_data["username"] = username
            print(f"[balance_manager] Обновлен username пользователя {user_id_str} на '{username}'.")
    return user_balances[user_id_str]

def get_balance(user_id_str):
    """Возвращает текущий баланс пользователя."""
    return get_user_balance_data(user_id_str).get("balance", 0)

def add_coins(user_id_str, amount, user_name=None, username=None):
    """Добавляет/списывает монеты у пользователя."""
    user_data = get_user_balance_data(user_id_str, user_name, username)
    user_data["balance"] = user_data.get("balance", 0) + amount
    save_json_file(BALANCES_FILE, user_balances)
    return user_data["balance"]

def get_user_display_name(user_id_str):
    """Возвращает отображаемое имя пользователя (username или first_name)."""
    user_data = get_user_balance_data(user_id_str)
    return user_data.get("username") or user_data.get("name", str(user_id_str))

# --- Функции для перезарядки ---
def get_cooldown_data(user_id_str):
    """Получает словарь перезарядки пользователя."""
    if user_id_str not in user_cooldowns:
        user_cooldowns[user_id_str] = {}
        print(f"[cooldown_manager] Создана новая запись перезарядки для пользователя {user_id_str}.")
    return user_cooldowns[user_id_str]

def get_last_use_time(user_id_str, command_name):
    """Возвращает время последнего использования команды."""
    user_cooldowns_data = get_cooldown_data(user_id_str)
    return user_cooldowns_data.get(command_name, 0)

def update_last_use_time(user_id_str, command_name):
    """Обновляет время последнего использования команды."""
    user_cooldowns_data = get_cooldown_data(user_id_str)
    user_cooldowns_data[command_name] = time.time()
    save_json_file(COOLDOWNS_FILE, user_cooldowns)
    return user_cooldowns_data[command_name]

# --- Функции для коллекции ---
def get_user_collection_data(user_id_str):
    """Получает словарь коллекции пользователя."""
    if user_id_str not in user_collection:
        user_collection[user_id_str] = {}
        print(f"[collection_manager] Создана новая запись коллекции для пользователя {user_id_str}.")
    return user_collection[user_id_str]

def add_card_to_collection(user_id_str, card_name):
    """Добавляет карту в коллекцию пользователя."""
    user_collection_data = get_user_collection_data(user_id_str)
    user_collection_data[card_name] = user_collection_data.get(card_name, 0) + 1
    save_json_file(COLLECTION_FILE, user_collection)
    print(f"Карта '{card_name}' добавлена в коллекцию пользователя {user_id_str}. Общее количество: {user_collection_data[card_name]}.")

def remove_card_from_collection(user_id_str, card_name):
    """Удаляет одну карту из коллекции пользователя."""
    user_collection_data = get_user_collection_data(user_id_str)
    if card_name in user_collection_data and user_collection_data[card_name] > 0:
        user_collection_data[card_name] -= 1
        if user_collection_data[card_name] == 0:
            del user_collection_data[card_name] # Удаляем, если количество стало 0
        save_json_file(COLLECTION_FILE, user_collection)
        print(f"Карта '{card_name}' удалена из коллекции пользователя {user_id_str}. Осталось: {user_collection_data.get(card_name, 0)}.")
        return True
    else:
        print(f"Ошибка: Карта '{card_name}' не найдена или ее нет в коллекции у пользователя {user_id_str}.")
        return False

def get_collection(user_id_str):
    """Возвращает коллекцию пользователя."""
    return get_user_collection_data(user_id_str)

# --- Функции для бонусов ---
def get_user_bonuses(user_id_str):
    """Получает словарь бонусов пользователя."""
    if user_id_str not in user_bonuses:
        user_bonuses[user_id_str] = {}
        print(f"[bonus_manager] Создана новая запись бонусов для пользователя {user_id_str}.")
    return user_bonuses[user_id_str]

def add_bonus(user_id_str, bonus_type, quantity=1):
    """Добавляет бонус пользователю."""
    user_bonus_data = get_user_bonuses(user_id_str)
    user_bonus_data[bonus_type] = user_bonus_data.get(bonus_type, 0) + quantity
    save_json_file(BONUSES_FILE, user_bonuses)
    print(f"Бонус '{bonus_type}' в количестве {quantity} добавлен пользователю {user_id_str}. Текущее кол-во: {user_bonus_data[bonus_type]}.")

def use_bonus(user_id_str, bonus_type):
    """Использует один бонус у пользователя. Возвращает True, если бонус был успешно использован, False иначе."""
    user_bonus_data = get_user_bonuses(user_id_str)
    if bonus_type in user_bonus_data and user_bonus_data[bonus_type] > 0:
        user_bonus_data[bonus_type] -= 1
        if user_bonus_data[bonus_type] == 0:
            del user_bonus_data[bonus_type] # Удаляем, если количество стало 0
        save_json_file(BONUSES_FILE, user_bonuses)
        print(f"Бонус '{bonus_type}' использован пользователем {user_id_str}. Осталось: {user_bonus_data.get(bonus_type, 0)}.")
        return True
    else:
        print(f"Ошибка: Бонус '{bonus_type}' не найден или недоступен у пользователя {user_id_str}.")
        return False

def get_bonus_count(user_id_str, bonus_type):
    """Возвращает количество бонусов определенного типа у пользователя."""
    user_bonus_data = get_user_bonuses(user_id_str)
    return user_bonus_data.get(bonus_type, 0)

# --- Функции команд бота ---

async def impostercard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /impostercard: получение карточки."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)
    command_name = "impostercard"

    print(f"\n--- Обработка /{command_name} для {user_name} (ID: {user_id_str}, Username: {username}) ---")

    # --- Проверка бонуса "Убрать перезарядку" ---
    skip_cooldown_bonus_available = False
    if get_bonus_count(user_id_str, "skip_cooldown") > 0:
        skip_cooldown_bonus_available = True
        await update.message.reply_text("✨ Использую бонус 'Убрать перезарядку'...")
        if use_bonus(user_id_str, "skip_cooldown"):
            print(f"Бонус 'skip_cooldown' успешно использован пользователем {user_id_str}.")
        else:
            # Если use_bonus вернул False, значит что-то пошло не так
            skip_cooldown_bonus_available = False # Сбрасываем флаг
            print(f"Не удалось использовать бонус 'skip_cooldown' для {user_id_str}, несмотря на наличие.")

    # --- Если бонус не использован или недоступен, проверяем обычную перезарядку ---
    if not skip_cooldown_bonus_available:
        last_use_time = get_last_use_time(user_id_str, command_name)
        current_time = time.time()

        if current_time - last_use_time < IMPOSTERCARD_COOLDOWN_SECONDS:
            time_remaining = IMPOSTERCARD_COOLDOWN_SECONDS - (current_time - last_use_time)
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            await update.message.reply_text(
                f"☕ Перезарядка! Попробуй еще раз через {minutes} минут {seconds} секунд."
            )
            print(f"Пользователь {user_id_str} попытался использовать /{command_name} раньше времени. Осталось: {minutes}м {seconds}с.")
            return

    # --- Если мы здесь, значит, либо бонус использован, либо перезарядка прошла ---
    # Обновляем время последнего использования, даже если бонус был использован
    update_last_use_time(user_id_str, command_name)
    print(f"Обновлено время последнего использования /{command_name} для {user_id_str}.")

    # --- Остальная логика получения карты ---
    card = choose_card()
    if not card or card.get("name") == "пусто":
        await update.message.reply_text("Извините, произошла ошибка при получении карточки.")
        return

    print(f"Выпавшая карточка: '{card['name']}' ({card['coins']} монет)")

    coins_to_add = card.get("coins", 0)
    if not isinstance(coins_to_add, (int, float)):
        print(f"[WARNING] Некорректное количество монет в карточке '{card['name']}': {coins_to_add}. Используем 0.")
        coins_to_add = 0
    new_balance = add_coins(user_id_str, coins_to_add, user_name=user_name, username=username)
    print(f"Баланс пользователя {user_id_str} обновлен. Текущий баланс: {new_balance}.")

    card_name_to_add = card.get("name")
    if card_name_to_add and card_name_to_add != "пусто" and card_name_to_add != "ошибка структуры":
        add_card_to_collection(user_id_str, card_name_to_add)
    else:
        print(f"[WARNING] Не удалось добавить карту в коллекцию: некорректное имя карты ('{card_name_to_add}').")

    caption_text = (
        f"Привет, {user_name}! Ты получил карточку {card['name']}!\n"
        f"Получено монет: {card['coins']}\n"
        f"Твой новый баланс: {new_balance}"
    )
    image_to_send = card.get("image_id")

    message_thread_id = update.message.message_thread_id if update.message else None
    print(f"[DEBUG] Полученный message_thread_id: {message_thread_id}")

    if image_to_send and image_to_send.startswith(("AgAC", "CAAC", "BQAC")):
        try:
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=image_to_send,
                caption=caption_text,
                message_thread_id=message_thread_id
            )
            print(f"Фото '{image_to_send}' успешно отправлено с подписью в тему ID: {message_thread_id}.")
        except Exception as e:
            print(f"[ERROR] Не удалось отправить фото '{image_to_send}': {e}")
            await update.message.reply_text(caption_text)
            print("Отправлен только текстовый вариант сообщения.")
    else:
        if not image_to_send:
            print("Для карточки не указан image_id.")
        else:
            print(f"image_id '{image_to_send}' имеет некорректный формат. Проверьте его.")
        await update.message.reply_text(caption_text)
        print("Отправлен только текстовый вариант сообщения.")

    print(f"--- Завершение /{command_name} ---")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает баланс пользователя, User ID и активные бонусы."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)
    command_name = "impostercard"

    print(f"\n--- Обработка /balance для {user_name} (ID: {user_id_str}, Username: {username}) ---")
    get_user_balance_data(user_id_str, user_name=user_name, username=username)

    user_balance = get_balance(user_id_str)
    skip_cooldown_bonuses = get_bonus_count(user_id_str, "skip_cooldown")

    last_use_time = get_last_use_time(user_id_str, command_name)
    current_time = time.time()

    message_parts = [f"Привет, {user_name}!"]
    message_parts.append(f"Твой текущий баланс: {user_balance} монет.")
    message_parts.append(f"Твой User ID: {user_id_str}")

    if skip_cooldown_bonuses > 0:
        message_parts.append(f"🚀 У тебя есть {skip_cooldown_bonuses} бонусов 'Убрать перезарядку'.")

    # Проверяем, нужно ли показывать информацию о перезарядке
    # Если есть бонус, то нет смысла показывать время перезарядки
    if skip_cooldown_bonuses == 0 and last_use_time > 0 and current_time - last_use_time < IMPOSTERCARD_COOLDOWN_SECONDS:
        time_remaining = IMPOSTERCARD_COOLDOWN_SECONDS - (current_time - last_use_time)
        minutes = int(time_remaining // 60)
        seconds = int(time_remaining % 60)
        message_parts.append(f"До следующего получения карточки осталось: {minutes} минут {seconds} секунд.")

    # Сообщение о возможности получить карточку, если нет перезарядки или есть бонус
    if skip_cooldown_bonuses > 0 or (last_use_time == 0 or current_time - last_use_time >= IMPOSTERCARD_COOLDOWN_SECONDS):
        message_parts.append("Ты можешь получить новую карточку прямо сейчас!")

    await update.message.reply_text("\n".join(message_parts))
    print(f"Информация о балансе и бонусах для {user_id_str} отправлена.")
    print("--- Завершение /balance ---")


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Позволяет пользователям переводить монеты друг другу."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)

    print(f"\n--- Обработка /pay от {user_name} (ID: {user_id_str}, Username: {username}) ---")

    try:
        if len(context.args) != 2:
            await update.message.reply_text(
                "Неверный формат команды. Используй: /pay <user_id_получателя> <количество_монет>"
            )
            print("Неверный формат команды /pay.")
            return

        recipient_id_str = context.args[0]
        amount_str = context.args[1]

        recipient_id = int(recipient_id_str)
        recipient_id_str = str(recipient_id)

        amount = int(amount_str)

        if amount <= 0:
            await update.message.reply_text("Количество монет для перевода должно быть больше нуля.")
            print("Количество монет для перевода <= 0.")
            return

        if user_id_str == recipient_id_str:
            await update.message.reply_text("Ты не можешь перевести монеты самому себе.")
            print("Попытка перевода самому себе.")
            return

        sender_balance = get_balance(user_id_str)
        if sender_balance < amount:
            await update.message.reply_text("У тебя недостаточно монет для этого перевода.")
            print(f"Недостаточно средств у отправителя {user_id_str}. Баланс: {sender_balance}, нужно: {amount}.")
            return

        add_coins(recipient_id_str, amount) # Добавляем монеты получателю
        add_coins(user_id_str, -amount, user_name=user_name, username=username) # Списываем монеты отправителю

        await update.message.reply_text(
            f"✅ Отлично, {user_name}! Ты успешно перевел {amount} монет пользователю с ID {recipient_id_str}."
        )

        # Отправляем уведомление получателю
        try:
            await context.bot.send_message(chat_id=recipient_id_str, text=f"🚀 Тебе пришло {amount} монет от пользователя с ID {user_id_str} ({user_name}).")
            print(f"Уведомление отправлено получателю {recipient_id_str}.")
        except Exception as e:
            print(f"[ERROR] Не удалось отправить уведомление получателю {recipient_id_str}: {e}")

    except ValueError:
        await update.message.reply_text(
            "Ошибка: ID пользователя и количество монет должны быть числами. Используй: /pay <user_id_получателя> <количество_монет>"
        )
        print("Ошибка ValueError при обработке /pay. Некорректные числовые аргументы.")
    except Exception as e:
        await update.message.reply_text(f"Произошла непредвиденная ошибка: {e}")
        print(f"[ERROR] Непредвиденная ошибка в /pay: {e}")
    print("--- Завершение /pay ---")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сообщает пользователю его Telegram User ID."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)

    print(f"\n--- Обработка /myid для {user_name} (ID: {user_id_str}, Username: {username}) ---")
    get_user_balance_data(user_id_str, user_name=user_name, username=username) # Обновляем данные пользователя
    await update.message.reply_text(f"Привет, {user_name}! Твой User ID: {user_id_str}")
    print(f"Отправлен User ID: {user_id_str}")
    print("--- Завершение /myid ---")

async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает коллекцию карт пользователя."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)

    print(f"\n--- Обработка /me для {user_name} (ID: {user_id_str}, Username: {username}) ---")
    get_user_balance_data(user_id_str, user_name=user_name, username=username) # Обновляем данные пользователя

    user_collection_data = get_collection(user_id_str)

    if not user_collection_data:
        await update.message.reply_text(
            f"Привет, {user_name}! Твоя коллекция карт пока пуста. "
            f"Попробуй команду /impostercard, чтобы получить первые карты!"
        )
        print(f"Коллекция пользователя {user_id_str} пуста.")
        return

    message_parts = [f"🌟 **{user_name}, твоя коллекция карт:** 🌟\n"]

    # Сортируем карты по названию для более удобного отображения
    sorted_cards = sorted(user_collection_data.items())

    for card_name, count in sorted_cards:
        message_parts.append(f"- {card_name.capitalize()}: {count} шт.")

    await update.message.reply_text("\n".join(message_parts), parse_mode="Markdown")
    print(f"Коллекция пользователя {user_id_str} успешно отображена.")
    print("--- Завершение /me ---")

# --- Функции для топов ---

def get_all_users_with_balances_and_names():
    """Собирает данные всех пользователей с положительным балансом для формирования топа."""
    users_for_top = []
    for user_id, data in user_balances.items():
        balance = data.get("balance", 0)
        if balance > 0:
            display_name = get_user_display_name(user_id)
            users_for_top.append((display_name, balance))
    return users_for_top

async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает топ 10 пользователей по балансу монет."""
    print("\n--- Обработка /top10 ---")

    all_users_data = get_all_users_with_balances_and_names()

    if not all_users_data:
        await update.message.reply_text("Пока никто не накопил монет. Попробуй команду /impostercard!")
        print("Нет данных для отображения /top10.")
        return

    # Сортируем пользователей по балансу (по убыванию)
    sorted_users = sorted(all_users_data, key=lambda item: item[1], reverse=True)

    # Берем топ 10
    top_users = sorted_users[:10]

    message_parts = ["👑 **Топ 10 пользователей по балансу:** 👑\n"]

    rank = 1
    for display_name, balance in top_users:
        # Экранируем имя пользователя, чтобы избежать ошибок форматирования Markdown
        escaped_display_name = escape_markdown(display_name)
        message_parts.append(f"{rank}. **{escaped_display_name}** - {balance} монет")
        rank += 1

    await update.message.reply_text("\n".join(message_parts), parse_mode="Markdown")
    print(f"Топ 10 пользователей отображен. Количество участников: {len(top_users)}.")
    print("--- Завершение /top10 ---")

async def top10chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Псевдоним для /top10, для использования в группах."""
    print("\n--- Обработка /top10chat ---")
    await top10(update, context)
    print("--- Завершение /top10chat (показывает общий топ) ---")

# --- КОМАНДА: /send ---
async def send_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Позволяет игрокам отправлять карты из своей коллекции другим игрокам."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    user_id_str = str(user_id)

    print(f"\n--- Обработка /send от {user_name} (ID: {user_id_str}) ---")

    if len(context.args) < 2: # Нужно минимум 2 аргумента: ID и название карты
        await update.message.reply_text(
            "Неверный формат команды. Используй: /send <user_id_получателя> <название_карты>\n"
            "Название карты может состоять из нескольких слов (например: 'веселого космонавта')."
        )
        print("Неверный формат команды /send (слишком мало аргументов).")
        return

    recipient_id_str = context.args[0]
    # Объединяем все аргументы, начиная со второго (индекс 1), в одно название карты.
    card_name_input = " ".join(context.args[1:]).lower()

    try:
        recipient_id = int(recipient_id_str)
        recipient_id_str = str(recipient_id)
    except ValueError:
        await update.message.reply_text("Ошибка: User ID получателя должен быть числом.")
        print("Некорректный User ID получателя в /send.")
        return

    if user_id_str == recipient_id_str:
        await update.message.reply_text("Ты не можешь отправить карту самому себе.")
        print("Попытка отправить карту самому себе.")
        return

    # --- Проверка существования карты ---
    if card_name_input not in CARD_BY_NAME:
        available_cards = ", ".join([c["name"].capitalize() for c in cards])
        await update.message.reply_text(
            f"Извини, карта с названием '{context.args[1]}' (или похожее) не найдена. \n"
            f"Попробуй ввести точное название, как оно отображается в /me. \n"
            f"Доступные карты: {available_cards}"
        )
        print(f"Карта '{card_name_input}' не найдена для команды /send.")
        return

    # Получаем нормализованное название карты (из CARD_BY_NAME)
    actual_card_name = CARD_BY_NAME[card_name_input]["name"]

    # --- Проверка наличия карты у отправителя ---
    sender_collection = get_collection(user_id_str)

    if actual_card_name not in sender_collection or sender_collection[actual_card_name] <= 0:
        await update.message.reply_text(
            f"У тебя нет карты '{actual_card_name.capitalize()}' в коллекции, чтобы отправить ее."
        )
        print(f"У отправителя {user_id_str} нет карты '{actual_card_name}'.")
        return

    # --- Проверка существования получателя ---
    # get_user_balance_data создаст запись, если ее нет.
    recipient_data = get_user_balance_data(recipient_id_str) 

    # --- Выполнение перевода карты ---
    if remove_card_from_collection(user_id_str, actual_card_name):
        add_card_to_collection(recipient_id_str, actual_card_name)

        # --- Уведомления ---
        sender_display_name = get_user_display_name(user_id_str)

        await update.message.reply_text(
            f"✅ Ты успешно отправил карту '{actual_card_name.capitalize()}' пользователю с ID {recipient_id_str}."
        )
        print(f"Отправитель {user_id_str} ({sender_display_name}) отправил карту '{actual_card_name}' получателю {recipient_id_str}.")

        # Отправляем уведомление получателю
        try:
            await context.bot.send_message(
                chat_id=recipient_id_str,
                text=f"🎁 Тебе пришла карта '{actual_card_name.capitalize()}' от пользователя {sender_display_name} (ID: {user_id_str})."
            )
            print(f"Уведомление о получении карты отправлено получателю {recipient_id_str}.")
        except Exception as e:
            print(f"[ERROR] Не удалось отправить уведомление получателю {recipient_id_str} о получении карты: {e}")
    else:
        # Если remove_card_from_collection вернула False, значит, была ошибка (уже выведено в логи)
        print(f"Перевод карты '{actual_card_name}' от {user_id_str} к {recipient_id_str} не удался.")

    print("--- Завершение /send ---")

# --- КОМАНДА: /shop ---
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает товары в магазине."""
    print("\n--- Обработка /shop ---")

    message_parts = ["🛒 **Добро пожаловать в магазин!** 🛒\n"]
    message_parts.append("Здесь вы можете приобрести полезные бонусы за монеты.")
    message_parts.append("\n**Доступные товары:**\n")

    # Проходимся по всем товарам в SHOP_ITEMS
    for item_key, item_data in SHOP_ITEMS.items():
        item_name = item_data.get("name", "Неизвестный товар")
        item_description = item_data.get("description", "Нет описания")
        item_price = item_data.get("price", "?")

        message_parts.append(f"• **{item_name}** ({item_price} монет)")
        message_parts.append(f" {item_description}") # Небольшой отступ для описания
        message_parts.append("") # Пустая строка для разделения товаров

    message_parts.append("Чтобы купить товар, используйте команду /buy <название_товара> (например, `/buy Убрать перезарядку`).")

    await update.message.reply_text("\n".join(message_parts), parse_mode="Markdown")
    print("Магазин успешно отображен.")
    print("--- Завершение /shop ---")

# --- КОМАНДА: /buy ---
async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает покупку товара в магазине."""
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    username = update.message.from_user.username
    user_id_str = str(user_id)

    print(f"\n--- Обработка /buy от {user_name} (ID: {user_id_str}) ---")

    if len(context.args) < 1:
        await update.message.reply_text("Пожалуйста, укажите, что вы хотите купить. Используйте /shop, чтобы увидеть список товаров.")
        print("Неверный формат команды /buy (нет названия товара).")
        return

    # Объединяем все аргументы в строку и приводим к нижнему регистру для поиска
    item_name_input = " ".join(context.args).lower()

    found_item = None
    found_item_key = None # Ключ найденного товара (например, "skip_cooldown")

    # Ищем товар по его названию (в нижнем регистре)
    for item_key, item_data in SHOP_ITEMS.items():
        if item_data.get("name", "").lower() == item_name_input:
            found_item = item_data
            found_item_key = item_key
            break

    if not found_item:
        # Если товар не найден, выводим список доступных для покупки
        available_items = ", ".join([f"'{data['name']}'" for data in SHOP_ITEMS.values()])
        await update.message.reply_text(
            f"Товар с названием '{context.args[0]}' (или похожим) не найден в магазине. \n"
            f"Попробуйте одно из этих названий: {available_items}."
        )
        print(f"Попытка купить несуществующий товар '{item_name_input}'.")
        return

    item_name = found_item.get("name")
    item_price = found_item.get("price")
    item_type = found_item.get("type")

    # --- Проверка баланса ---
    sender_balance = get_balance(user_id_str)
    if sender_balance < item_price:
        await update.message.reply_text(
            f"У тебя недостаточно монет для покупки '{item_name}'. Тебе нужно {item_price} монет, а у тебя {sender_balance}."
        )
        print(f"Недостаточно средств у {user_id_str} для покупки '{item_name}'. Баланс: {sender_balance}, цена: {item_price}.")
        return

    # --- Обработка покупки ---
    if item_type == "bonus":
        # --- Покупка бонуса ---
        if found_item_key == "skip_cooldown":
            # Списываем монеты
            add_coins(user_id_str, -item_price, user_name=user_name, username=username)

            # Добавляем бонус
            add_bonus(user_id_str, "skip_cooldown")

            await update.message.reply_text(
                f"✅ Поздравляем! Ты успешно купил бонус '{item_name}' за {item_price} монет.\n"
                f"Теперь ты можешь использовать его один раз, чтобы пропустить перезарядку /impostercard."
            )
            print(f"{user_id_str} ({user_name}) купил бонус '{item_name}'.")
        else:
            await update.message.reply_text("Произошла ошибка при обработке покупки этого бонуса.")
            print(f"Неизвестный тип бонуса '{item_type}' для товара '{item_name}'.")

    else:
        await update.message.reply_text("Произошла ошибка при обработке покупки этого товара.")
        print(f"Неизвестный тип товара '{item_type}' для товара '{item_name}'.")

    print("--- Завершение /buy ---")


# --- Функция логирования всех сообщений ---
async def log_message_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует тип каждого полученного сообщения для отладки."""
    message = update.message
    user = message.from_user
    if not user: # Пропускаем, если нет информации о пользователе
        return

    print(f"\n[LOG_MSG] Получено сообщение от {user.first_name} (ID: {user.id}, Username: {user.username}).")

    if message.document:
        print(f"[LOG_MSG] Тип сообщения: Document")
        doc_info = message.document.to_dict()
        print(f"[LOG_MSG] Сообщение содержит документ: {doc_info}")
        main_file_id = doc_info.get('file_id')
        if main_file_id:
            print(f"[LOG_MSG] ----> ОСНОВНОЙ FILE_ID: {main_file_id}")
    elif message.photo:
        print(f"[LOG_MSG] Тип сообщения: Photo")
        file_id = message.photo[-1].file_id # Берем file_id самого большого фото
        print(f"[LOG_MSG] File ID самого большого фото: {file_id}")
    elif message.text:
        print(f"[LOG_MSG] Тип сообщения: Text. Текст: '{message.text}'")
    else:
        print(f"[LOG_MSG] Тип сообщения: Другой ({type(message)})")


# --- Вспомогательная функция для выбора карточки ---
def choose_card():
    """Выбирает карточку случайным образом на основе редкости."""
    weights = [card.get("rarity", 0.0) for card in cards]
    if not cards or sum(weights) == 0:
        print("[WARNING] Список карточек пуст или сумма редкостей равна 0. Возвращаем пустую карточку.")
        return {"name": "пусто", "coins": 0, "image_id": None}

    try:
        chosen = random.choices(cards, weights=weights, k=1)[0]
        # Проверяем, что в выбранной карточке есть все нужные ключи
        if not all(key in chosen for key in ["name", "coins", "image_id"]):
            print(f"[WARNING] Выбранная карточка '{chosen.get('name', 'Неизвестно')}' имеет некорректную структуру. Отсутствуют 'name', 'coins' или 'image_id'.")
            return {"name": "ошибка структуры", "coins": 0, "image_id": None}
        return chosen
    except IndexError:
        print("[ERROR] Не удалось выбрать карточку. Список карт пуст.")
        return {"name": "пусто", "coins": 0, "image_id": None}
    except Exception as e:
        print(f"[ERROR] Произошла ошибка при выборе карточки: {e}")
        return {"name": "ошибка выбора", "coins": 0, "image_id": None}

# --- Основная функция запуска бота ---
def main():
    """Инициализирует и запускает бота."""
    TOKEN = '7731355172:AAEe5lz1zJpArepUpTbTW9S09cO0RrWgYBE' # <<< ЗАМЕНИТЕ НА ВАШ ТОКЕН БОТА

    if not TOKEN:
        print("Ошибка: Токен бота не установлен. Пожалуйста, укажите токен в переменной TOKEN.")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    # --- Регистрация обработчиков команд ---
    application.add_handler(CommandHandler("impostercard", impostercard))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("me", me))
    application.add_handler(CommandHandler("top10", top10))
    application.add_handler(CommandHandler("top10chat", top10chat))
    application.add_handler(CommandHandler("send", send_card))
    application.add_handler(CommandHandler("shop", shop))     # Команда для открытия магазина
    application.add_handler(CommandHandler("buy", buy_item))   # Команда для покупки товаров

    # --- Регистрация обработчика для логирования ВСЕХ сообщений ---
    # Это поможет отслеживать, какие сообщения приходят боту
    application.add_handler(MessageHandler(filters.ALL, log_message_type))

    # --- Информация о запуске ---
    print("="*50)
    print(" БОТ ЗАПУСКАЕТСЯ...")
    print("="*50)
    print(f"Балансы пользователей: {BALANCES_FILE}")
    print(f"Перезарядки пользователей: {COOLDOWNS_FILE}")
    print(f"Коллекции пользователей: {COLLECTION_FILE}")
    print(f"Бонусы пользователей: {BONUSES_FILE}")
    print(f"Карточек в системе: {len(cards)}")
    print(f"Перезарядка для /impostercard: {IMPOSTERCARD_COOLDOWN_MINUTES} минут")
    print(f"Стоимость бонуса 'Убрать перезарядку': {BONUS_SKIP_COOLDOWN_PRICE} монет")
    print("Нажмите Ctrl+C для остановки бота.")
    print("Ожидание сообщений...")

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()