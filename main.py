from telegram import Update, ReplyKeyboard Markup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, Context Types
# from yandexgpt_client import ask_yandexgpt






async def start(update: Update, context:ContextTypes.DEFAULT_TYPE):
    welcome_text = "бот на базе Yandex GPT."
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )