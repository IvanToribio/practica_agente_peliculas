# app/telegram_bot.py

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.chatbot_service import handle_chat_message


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def split_long_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Divide mensajes largos para evitar superar el límite de Telegram.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += "\n" + line if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def send_text(update: Update, text: str) -> None:
    """
    Envía texto al usuario dividiéndolo si es demasiado largo.
    """
    message = update.effective_message

    if message is None:
        return

    for chunk in split_long_message(text):
        await message.reply_text(
            chunk,
            disable_web_page_preview=True,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler del comando /start.
    """
    text = (
        "🎬 ¡Hola! Soy tu asistente de películas.\n\n"
        "Puedes preguntarme cosas como:\n\n"
        "• Busca Dune\n"
        "• ¿Quién dirigió Interstellar?\n"
        "• ¿Cuánto dura Oppenheimer?\n"
        "• ¿De qué va Matrix?\n"
        "• Recomiéndame una película de ciencia ficción con nota mayor de 7\n\n"
        "Usa /help si quieres ver más ejemplos."
    )

    await send_text(update, text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler del comando /help.
    """
    text = (
        "Puedes escribirme en lenguaje natural.\n\n"
        "Ejemplos:\n\n"
        "🔎 Búsqueda:\n"
        "• Busca Dune\n"
        "• Quiero información sobre Matrix\n\n"
        "🎥 Datos concretos:\n"
        "• ¿Quién dirigió Dune?\n"
        "• ¿Cuánto dura Interstellar?\n"
        "• ¿Qué nota tiene Oppenheimer?\n"
        "• ¿Qué géneros tiene Barbie?\n\n"
        "📝 Resumen:\n"
        "• Resume Dune\n"
        "• Explícame de qué trata Interestellar\n\n"
        "🍿 Recomendaciones:\n"
        "• Recomiéndame una película\n"
        "• Recomiéndame ciencia ficción\n"
        "• Quiero una película de terror con nota mayor de 7"
    )

    await send_text(update, text)


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler del comando /buscar.
    Convierte /buscar Dune en un mensaje normal para tu chatbot_service.py.
    """
    title = " ".join(context.args).strip()

    if not title:
        await send_text(
            update,
            "Escribe el título después del comando.\n\nEjemplo:\n/buscar Dune"
        )
        return

    await process_user_message(update, f"Busca {title}")


async def recomendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler del comando /recomendar.
    """
    preferences = " ".join(context.args).strip()

    if preferences:
        user_message = f"Recomiéndame una película de {preferences}"
    else:
        user_message = "Recomiéndame una película"

    await process_user_message(update, user_message)


async def process_user_message(update: Update, user_message: str) -> None:
    """
    Punto común para procesar cualquier mensaje del usuario.

    Este método es la conexión real entre Telegram y tu backend.
    """
    await send_text(update, "🎬 Pensando...")

    try:
        response = await asyncio.to_thread(
            handle_chat_message,
            user_message,
        )

    except Exception:
        logger.exception("Error inesperado procesando el mensaje")
        await send_text(
            update,
            "Ha ocurrido un error inesperado. Prueba de nuevo más tarde."
        )
        return

    answer = response.get("answer")

    if not answer:
        answer = "No he podido generar una respuesta."

    await send_text(update, answer)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para cualquier mensaje normal de texto.
    """
    message = update.effective_message

    if message is None or not message.text:
        return

    user_message = message.text.strip()

    if not user_message:
        await send_text(update, "Escríbeme una pregunta sobre películas.")
        return

    await process_user_message(update, user_message)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global de errores.
    """
    logger.exception("Error en Telegram bot:", exc_info=context.error)


def main() -> None:
    """
    Arranca el bot con polling.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN en el archivo .env")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("buscar", buscar))
    application.add_handler(CommandHandler("recomendar", recomendar))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    application.add_error_handler(error_handler)

    logger.info("Bot de Telegram iniciado")
    application.run_polling()


if __name__ == "__main__":
    main()