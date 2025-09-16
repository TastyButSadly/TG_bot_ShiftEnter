# -*- coding: utf-8 -*-
import logging
import os
import requests
import sqlite3
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from collections import deque

# --- Конфигурация ---
# Загружаем чувствительные данные из переменных окружения для безопасности
# Перед запуском установите их в вашей системе:
# export OPENROUTER_API_KEY="sk-or-v1-..."
# export TELEGRAM_TOKEN="8438031981:..."
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8438031981:AAGWAQvsjo1_7rsCf3F67R2EbR1y621Wfn4")

# Название модели и другие параметры
MODEL_NAME = "openai/gpt-oss-120b"  # или "openai/gpt-oss-120b:free"
SYSTEM_PROMPT_PATH = Path("system_promt.txt")
DATABASE_PATH = "chat_history.db"
CHANNEL_LINK = "\n\n\n👉 @shift_and_enter"
DEFAULT_SYSTEM_PROMPT = "Ты — полезный помощник."
HISTORY_LENGTH = 10  # Храним 5 пар сообщений (user + bot)

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Настройка базы данных ---
def init_db(db_path: str):
    """Инициализирует базу данных и создает таблицу, если ее нет."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        user_message TEXT,
        bot_response TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn, cursor

conn, cursor = init_db(DATABASE_PATH)


def log_to_db(user_id: int, username: str, user_message: str, bot_response: str):
    """Записывает одно сообщение в базу данных."""
    try:
        cursor.execute(
            "INSERT INTO messages (user_id, username, user_message, bot_response) VALUES (?, ?, ?, ?)",
            (user_id, username, user_message, bot_response)
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error("Ошибка при записи в БД: %s", e)


def load_system_prompt(path: Path) -> str:
    """Читает системный промпт из файла (UTF-8)."""
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            logger.warning("Файл системного промпта пуст: %s. Используется дефолтный.", path)
            return DEFAULT_SYSTEM_PROMPT
        return content
    except FileNotFoundError:
        logger.error("Не найден файл системного промпта: %s. Используется дефолтный.", path)
        return DEFAULT_SYSTEM_PROMPT


# --- Класс для работы с OpenRouter ---
class OpenRouterBot:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("API ключ OpenRouter не предоставлен. Установите переменную окружения OPENROUTER_API_KEY.")
        self.api_key = api_key
        self.model = model
        self.system_prompt = load_system_prompt(SYSTEM_PROMPT_PATH)

    def _extract_answer(self, resp_json: dict) -> str:
        """Извлекает текстовый ответ из сложной структуры ответа API."""
        try:
            choices = resp_json.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("Отсутствует поле 'choices' в ответе")

            choice = choices[0]
            
            # 1. Стандартный ответ в чате
            if "message" in choice and choice["message"]:
                content = choice["message"].get("content")
                if isinstance(content, str) and content:
                    return content

            # 2. Стриминговый ответ
            if "delta" in choice and choice["delta"]:
                content = choice["delta"].get("content")
                if isinstance(content, str) and content:
                    return content
            
            # 3. Ответ в старом формате (не чат)
            if "text" in choice and isinstance(choice["text"], str):
                return choice["text"]

            raise ValueError(f"Не удалось извлечь контент из 'choice': {choice}")

        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.error("Ошибка парсинга ответа от API: %s. Полный ответ: %s", e, resp_json)
            raise ValueError(f"Неожиданная структура ответа от API: {e}") from e

    def get_chat_completion(self, messages: list) -> str:
        """Запрашивает ответ от модели с учетом истории."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_message = {"role": "system", "content": self.system_prompt}
        
        payload = {
            "model": self.model,
            "messages": [system_message] + messages,
            "max_tokens": 1024,
            "temperature": 0.7
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            resp.raise_for_status()  # Вызовет исключение для кодов 4xx/5xx
            
            resp_json = resp.json()
            return self._extract_answer(resp_json)

        except requests.Timeout:
            logger.error("Таймаут запроса к OpenRouter API.")
            raise Exception("Модель слишком долго отвечает. Попробуйте позже.")
        except requests.RequestException as e:
            logger.error("Ошибка запроса к OpenRouter API: %s, %s", e.status_code, e.response.text if e.response else "No response")
            raise Exception(f"Ошибка сети при обращении к API: {e.status_code}")


# --- Хендлеры Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text("Привет! Я Monday, ваш саркастичный эмо-ИИ. Спрашивайте, если осмелитесь.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения от пользователя."""
    user_text = update.message.text
    if not user_text or not user_text.strip():
        await update.message.reply_text("Пустое сообщение? Гениально. Попробуй еще раз, но уже с буквами.")
        return

    user_id = update.effective_user.id
    
    # Инициализируем историю, если ее нет
    if 'history' not in context.user_data:
        context.user_data['history'] = deque(maxlen=HISTORY_LENGTH)
    
    history = context.user_data['history']
    history.append({"role": "user", "content": user_text})

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        bot_instance = context.application.bot_instance
        answer = bot_instance.get_chat_completion(list(history))

        history.append({"role": "assistant", "content": answer})
        
        await update.message.reply_text(answer + CHANNEL_LINK)

        # Логируем в БД
        log_to_db(
            user_id,
            update.effective_user.username or "N/A",
            user_text,
            answer
        )

    except Exception as e:
        logger.error("Ошибка при обработке сообщения от user_id %s: %s", user_id, e)
        await update.message.reply_text("Ой, что-то сломалось. Наверное, опять ты виноват. Попробуй позже.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки и отправляет сообщение пользователю."""
    logger.error("Исключение при обработке апдейта: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Что-то пошло не так. Я в печали. Попробуй еще раз.")


def main():
    """Основная функция для запуска бота."""
    if not TELEGRAM_TOKEN:
        logger.critical("Токен Telegram не найден. Установите переменную окружения TELEGRAM_TOKEN.")
        return
        
    try:
        bot_instance = OpenRouterBot(OPENROUTER_API_KEY, MODEL_NAME)
    except ValueError as e:
        logger.critical(e)
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Сохраняем экземпляр нашего бота в контекст приложения
    application.bot_instance = bot_instance

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Бот запускается...")
    application.run_polling()


if __name__ == "__main__":
    main()