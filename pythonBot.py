import logging
import jwt
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Настройки
SERVICE_ACCOUNT_ID = "ajebsc55t1vkj1tjjjvh"  # ID сервисного аккаунта
KEY_ID = "aje0o8bak93hltrnnksi"  # ID ключа сервисного аккаунта
PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCtbXjS5l9a9EdZ
GzU7K/tTb4pD2k1BY7o8U28tdDhXL2HWtk25nL6EA6oP7CQNEjxoDpNkSGaHj7LV
EApm4wlOmAbigRHrI0qI0bS0rEpkjr14Ko8zynPCpKv18XginrRJDFhkfr3njZIx
KTfLGONCrPOjtTFfMr9uV2kcLnMysj8F+d+rofxMmHjXAh85ETWwwN++VRbwW7cq
ik4oyuHvzn8pd3yruKFeIuwbW3SCwGcmDIpkXI+SNVkvY/JBsCSdNrhyuQxJ6stV
a4c6tQLeRl4ButNDi5XccW0T2mKmIWRYO1ijUMUOHSEHKBqlEaVkPxVefUb97yew
RIvfrnM9AgMBAAECggEAApc3Ddd5Jy+s/SzF38tpZras1xSkwMxPlOUeLQymZs8D
ZCS3BoXL5sbzPGenpjZWhqtpEj9uoKnJ3xrtPNo5Yl4tBCcvcFbHn0GatHQ6bEQh
mnDwULK+hfLVyse/pqy+PrUbgOzPw2y++VMHTVZi1rUkspZbVXO5nllZ7ZzYBbLT
o2NobWAXRXR8jfCgQO7/EW5fjTGsNcHLRd+srS+3UDXuqtcbgk7JM1vpy4JxW2QM
Vpf7joNtmFkFJ7U0qU5KkBscBE1U2xLIWKDN600WOjl/C9RJIy7mH9G4OMxQOSuI
MTj7Qo57dYj8TPIu1B59r+RfZ5dvXTfdyPGoAAd/YQKBgQDCaqF4VYo6kaEkmU1o
hFQekQa0CvZFVYtqdFF7/2DwGBfNEfaiB/OOU5b54Z3iOuN59S56CI73XA7ick5Y
29VIrd3CNvlWZeDCzgFGP/pDsyr0lgNXUhe7roUaMbRrTe38dqlI/35FmJoqZoeV
EcG/9vXKTChEIMSLPgNh1ojzNQKBgQDkXNY6rY6Q80AFa65jJNpgfb+qoxlq/N8y
Y1fLZj0ZWNN92l+NpxeSnG3VnMiWxQLp4pj9qbtDBiLu1ZH4+E1tOGOmoeahpmv7
m8Wh9xEpg5A6RGf/36lgqN1oc6i0zKDgOzd1exjVvyLHDc3RlyahmbllOue4KwfU
+mBL2a+46QKBgQC27uKUedihF5qK93zw1WLZiBjInG/x+XY/asepZzjtcZ4jpb1t
5RF1YI30/igzULnubZeX2Cm98u9Gf8vcrK1Zv8+kCVo/w4jjhDeKxHRV82Z90hG+
vk36mVJAvXhIZ4GBRp4vQ8iq79ZQAz2cNKMcX+ISweo5gKOvaWCBVP5z6QKBgQCh
wp1BrWUaiiRkcpVxx04lIY4eOjAsF/mmgLZU7xQCm2gccw5SkfThtosa0FdKbT2W
HRwQOyXZ4UPneENRX9nArzvvcimjgfZloT8Kbq+qf3Yvv/sHRhB91sAXWC49++FN
VMUBI/RAnIbvB3kuqOoFeJXZ/jLbwydmFwEVWZre2QKBgEmfcIvimKQAIGXHetZN
CEyOkLlYAEuMPLqiSZJOk4dvaDDfssvMgu4abU0bOJG9GyOS71jVQ8vkEqADPBr6
ReVN1yYWQ5Ofu3jDaYM2EFhRIPdaMl6oFUPcb0GlnRrt1g1uXHWnJR8dvezcsObM
FU8XROuGSpGfgJDIyqXEtW95
-----END PRIVATE KEY-----
"""
FOLDER_ID = "b1g5r8fpphppr2vqh3ir"  # ID каталога Yandex Cloud
TELEGRAM_TOKEN = "8438031981:AAGWAQvsjo1_7rsCf3F67R2EbR1y621Wfn4"  # Токен Telegram-бота
# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class YandexGPTBot:
    def __init__(self):
        self.iam_token = None
        self.token_expires = 0

    def get_iam_token(self):
        """Получение IAM-токена (с кэшированием на 1 час)"""
        if self.iam_token and time.time() < self.token_expires:
            return self.iam_token

        try:
            now = int(time.time())
            payload = {
                'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                'iss': SERVICE_ACCOUNT_ID,
                'iat': now,
                'exp': now + 3600
            }

            encoded_token = jwt.encode(
                payload,
                PRIVATE_KEY,
                algorithm='PS256',
                headers={'kid': KEY_ID}
            )

            response = requests.post(
                'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                json={'jwt': encoded_token},
                timeout=10
            )

            if response.status_code != 200:
                raise Exception(f"Ошибка генерации токена: {response.text}")

            token_data = response.json()
            self.iam_token = token_data['iamToken']
            self.token_expires = now + 3500  # На 100 секунд меньше срока действия

            logger.info("IAM token generated successfully")
            return self.iam_token

        except Exception as e:
            logger.error(f"Error generating IAM token: {str(e)}")
            raise

    def ask_gpt(self, question):
        """Запрос к Yandex GPT API"""
        try:
            iam_token = self.get_iam_token()

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {iam_token}',
                'x-folder-id': FOLDER_ID
            }

            data = {
                "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 2000
                },
                "messages": [
                    {
                        "role": "user",
                        "text": question
                    }
                ]
            }

            response = requests.post(
                'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Yandex GPT API error: {response.text}")
                raise Exception(f"Ошибка API: {response.status_code}")

            return response.json()['result']['alternatives'][0]['message']['text']

        except Exception as e:
            logger.error(f"Error in ask_gpt: {str(e)}")
            raise


# Создаем экземпляр бота
yandex_bot = YandexGPTBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! Я бот для работы с Yandex GPT. Просто напиши мне свой вопрос"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_message = update.message.text

    if not user_message.strip():
        await update.message.reply_text("Пожалуйста, введите вопрос")
        return

    try:
        # Показываем статус "печатает"
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        response = yandex_bot.ask_gpt(user_message)
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")
        await update.message.reply_text(
            "Извините, произошла ошибка при обработке вашего запроса. "
            "Пожалуйста, попробуйте позже."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже."
        )


def main():
    """Основная функция"""
    try:
        # Проверяем возможность генерации токена при запуске
        yandex_bot.get_iam_token()
        logger.info("IAM token test successful")

        application = Application.builder().token(TELEGRAM_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)

        logger.info("Бот запускается...")
        application.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")


if __name__ == "__main__":
    main()