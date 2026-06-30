# app/telegram_bot_comandos.py

"""
Bot de Telegram basado en comandos.

Este bot NO usa LLM ni chatbot_service.py.
Funciona por reglas, de forma parecida a una skill de Alexa:

- Cada comando de Telegram llama directamente a una función concreta.
- movie_service.py contiene la lógica de películas.
- formatters.py define cómo se redactan las respuestas.
- tmdb_client.py se usa indirectamente desde movie_service.py.

Ejecutar desde la raíz del proyecto:

    python -m app.telegram_bot_comandos
"""

import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.formatters import (
    format_candidate_list_for_telegram,
    format_director_for_alexa,
    format_genres_for_alexa,
    format_movie_for_telegram,
    format_movie_list_for_telegram,
    format_not_found_for_telegram,
    format_overview_for_alexa,
    format_rating_for_alexa,
    format_recommendations_for_telegram,
    format_release_date_for_alexa,
    format_runtime_for_alexa,
)
from app.movie_service import (
    Movie,
    MovieCandidate,
    MovieServiceError,
    get_movie_by_id,
    get_movie_by_title,
    get_now_playing_movies,
    recommend_now_playing_movies,
    search_movie_candidates,
)


# ============================================================
# Configuración básica
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


# ============================================================
# Utilidades generales
# ============================================================

def _extract_year_from_text(text: str) -> int | None:
    """
    Extrae un año de cuatro cifras de un texto.

    Ejemplos:
    - "Dune 2021" -> 2021
    - "Matrix" -> None
    """
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", text)

    if not match:
        return None

    return int(match.group(1))


def _remove_year_from_text(text: str) -> str:
    """
    Elimina el año del texto para quedarse con el título limpio.
    """
    return re.sub(r"\b(19\d{2}|20\d{2}|21\d{2})\b", "", text).strip()


def _parse_title_and_year(args: list[str]) -> tuple[str | None, int | None]:
    """
    Convierte los argumentos de un comando en título y año opcional.

    Ejemplos:
    - /pelicula Dune
        -> ("Dune", None)

    - /pelicula Dune 2021
        -> ("Dune", 2021)
    """
    raw_text = " ".join(args).strip()

    if not raw_text:
        return None, None

    year = _extract_year_from_text(raw_text)
    title = _remove_year_from_text(raw_text) if year else raw_text

    if not title:
        return None, year

    return title, year


def _parse_recommendation_args(args: list[str]) -> tuple[str | None, int | None, float]:
    """
    Extrae género, año y nota mínima de /recomendar.

    Formatos soportados:
    - /recomendar
    - /recomendar ciencia ficcion
    - /recomendar ciencia ficcion 2021
    - /recomendar ciencia ficcion 2021 7.5
    - /recomendar terror nota=7
    - /recomendar comedia min=6.5
    """
    if not args:
        return None, None, 7.0

    year: int | None = None
    min_rating = 7.0
    genre_tokens: list[str] = []

    for token in args:
        clean_token = token.strip().lower().replace(",", ".")

        if re.fullmatch(r"19\d{2}|20\d{2}|21\d{2}", clean_token):
            year = int(clean_token)
            continue

        if clean_token.startswith("nota=") or clean_token.startswith("min="):
            _, raw_rating = clean_token.split("=", 1)

            try:
                min_rating = float(raw_rating)
            except ValueError:
                pass

            continue

        try:
            numeric_value = float(clean_token)

            if 0 <= numeric_value <= 10:
                min_rating = numeric_value
                continue

        except ValueError:
            pass

        genre_tokens.append(token)

    genre = " ".join(genre_tokens).strip() or None

    return genre, year, min_rating


def _split_long_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Telegram tiene límite de tamaño por mensaje.
    Esta función divide mensajes largos sin cortar líneas a mitad.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current_chunk = ""

    for line in text.split("\n"):
        next_chunk = f"{current_chunk}\n{line}" if current_chunk else line

        if len(next_chunk) > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk = next_chunk

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def _reply(update: Update, text: str) -> None:
    """
    Responde al mensaje actual del usuario.
    """
    message = update.effective_message

    if message is None:
        return

    for chunk in _split_long_message(text):
        await message.reply_text(
            chunk,
            disable_web_page_preview=True,
        )


async def _safe_run(update: Update, action_name: str, function, *args, **kwargs):
    """
    Ejecuta funciones síncronas del backend en un hilo separado.

    movie_service.py usa requests, por lo que sus llamadas son bloqueantes.
    Para no bloquear el bot, se ejecutan con asyncio.to_thread().
    """
    try:
        return await asyncio.to_thread(function, *args, **kwargs)

    except MovieServiceError:
        logger.exception("Error de MovieService en %s", action_name)
        await _reply(
            update,
            "Ha ocurrido un problema consultando la información de películas. "
            "Prueba de nuevo más tarde.",
        )

    except ValueError as error:
        logger.exception("Error de validación en %s", action_name)
        await _reply(update, f"Datos no válidos: {error}")

    except Exception:
        logger.exception("Error inesperado en %s", action_name)
        await _reply(update, "Ha ocurrido un error inesperado.")

    return None


async def _get_movie_from_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    usage_example: str,
) -> Movie | None:
    """
    Utilidad común para comandos que necesitan una película concreta.
    """
    title, year = _parse_title_and_year(context.args)

    if not title:
        await _reply(
            update,
            "Falta el título de la película.\n\n"
            f"Ejemplo:\n{usage_example}",
        )
        return None

    movie = await _safe_run(
        update,
        "get_movie_by_title",
        get_movie_by_title,
        title,
        year,
    )

    if movie is None:
        await _reply(update, format_not_found_for_telegram(title))
        return None

    return movie


# ============================================================
# Comandos principales
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start
    """
    text = (
        "🎬 ¡Hola! Soy tu bot de películas por comandos.\n\n"
        "Este bot no usa LLM. Funciona con comandos concretos, como una skill de Alexa.\n\n"
        "Comandos principales:\n"
        "/buscar Dune\n"
        "/pelicula Dune 2021\n"
        "/director Dune\n"
        "/duracion Interstellar\n"
        "/nota Oppenheimer\n"
        "/estreno Matrix\n"
        "/generos Barbie\n"
        "/resumen Dune\n"
        "/recomendar ciencia ficcion 2021 7\n"
        "/cartelera\n\n"
        "Después de /buscar, puedes responder con un número para ver la ficha completa."
    )

    await _reply(update, text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help
    """
    text = (
        "📌 Ayuda del bot\n\n"
        "Búsqueda:\n"
        "/buscar <título> [año]\n"
        "Ejemplo: /buscar Dune 2021\n\n"
        "Ficha completa:\n"
        "/pelicula <título> [año]\n"
        "Ejemplo: /pelicula Interstellar\n\n"
        "Datos concretos:\n"
        "/director <título> [año]\n"
        "/duracion <título> [año]\n"
        "/nota <título> [año]\n"
        "/estreno <título> [año]\n"
        "/generos <título> [año]\n"
        "/resumen <título> [año]\n\n"
        "Recomendaciones:\n"
        "/recomendar\n"
        "/recomendar <género>\n"
        "/recomendar <género> <año>\n"
        "/recomendar <género> <año> <nota mínima>\n\n"
        "Ejemplos:\n"
        "/recomendar terror\n"
        "/recomendar ciencia ficcion 2021\n"
        "/recomendar comedia 2019 7.5\n\n"
        "Cartelera aproximada:\n"
        "/cartelera"
    )

    await _reply(update, text)


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /buscar <título> [año]

    Muestra candidatos y guarda la lista en user_data para permitir
    que el usuario responda con 1, 2, 3...
    """
    title, year = _parse_title_and_year(context.args)

    if not title:
        await _reply(
            update,
            "Falta el título de la película.\n\n"
            "Ejemplo:\n/buscar Dune 2021",
        )
        return

    candidates = await _safe_run(
        update,
        "search_movie_candidates",
        search_movie_candidates,
        title,
        year,
        5,
    )

    if candidates is None:
        return

    context.user_data["last_candidates"] = candidates

    await _reply(update, format_candidate_list_for_telegram(candidates))


async def pelicula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /pelicula <título> [año]

    Devuelve la ficha completa de la primera coincidencia.
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/pelicula Dune 2021",
    )

    if movie is None:
        return

    await _reply(update, format_movie_for_telegram(movie))


async def director(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /director <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/director Dune 2021",
    )

    if movie is None:
        return

    await _reply(update, format_director_for_alexa(movie))


async def duracion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /duracion <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/duracion Interstellar",
    )

    if movie is None:
        return

    await _reply(update, format_runtime_for_alexa(movie))


async def nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /nota <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/nota Oppenheimer",
    )

    if movie is None:
        return

    await _reply(update, format_rating_for_alexa(movie))


async def estreno(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /estreno <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/estreno Matrix",
    )

    if movie is None:
        return

    await _reply(update, format_release_date_for_alexa(movie))


async def generos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /generos <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/generos Barbie",
    )

    if movie is None:
        return

    await _reply(update, format_genres_for_alexa(movie))


async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /resumen <título> [año]
    """
    movie = await _get_movie_from_command(
        update,
        context,
        "/resumen Dune 2021",
    )

    if movie is None:
        return

    await _reply(update, format_overview_for_alexa(movie))


async def recomendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /recomendar [género] [año] [nota mínima]
    """
    genre, year, min_rating = _parse_recommendation_args(context.args)

    movies = await _safe_run(
        update,
        "recommend_now_playing_movies",
        recommend_now_playing_movies,
        min_rating,
        100,
        genre,
        year,
        5,
    )

    if movies is None:
        return

    await _reply(update, format_recommendations_for_telegram(movies))


async def cartelera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /cartelera

    Muestra películas en cartelera aproximada según la región configurada.
    """
    movies = await _safe_run(
        update,
        "get_now_playing_movies",
        get_now_playing_movies,
        10,
    )

    if movies is None:
        return

    await _reply(
        update,
        format_movie_list_for_telegram(
            movies=movies,
            title="🎟️ Cartelera aproximada",
        ),
    )


# ============================================================
# Selección numérica después de /buscar
# ============================================================

async def handle_numeric_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Permite que el usuario responda con un número tras /buscar.

    Ejemplo:
    Usuario: /buscar Dune
    Bot: 1. Dune (2021), 2. Dune (1984)...
    Usuario: 1
    Bot: ficha completa de Dune (2021)
    """
    message = update.effective_message

    if message is None or message.text is None:
        return

    user_text = message.text.strip()

    if not user_text.isdigit():
        await _reply(
            update,
            "No entiendo mensajes libres en este modo.\n"
            "Usa /help para ver los comandos disponibles.",
        )
        return

    candidates: list[MovieCandidate] = context.user_data.get("last_candidates", [])

    if not candidates:
        await _reply(
            update,
            "No tengo ninguna búsqueda activa. Primero usa /buscar.\n\n"
            "Ejemplo:\n/buscar Dune",
        )
        return

    selected_index = int(user_text) - 1

    if selected_index < 0 or selected_index >= len(candidates):
        await _reply(
            update,
            f"Elige un número entre 1 y {len(candidates)}.",
        )
        return

    selected_candidate = candidates[selected_index]

    movie = await _safe_run(
        update,
        "get_movie_by_id",
        get_movie_by_id,
        selected_candidate.tmdb_id,
    )

    if movie is None:
        await _reply(
            update,
            "No he podido cargar los detalles de esa película.",
        )
        return

    await _reply(update, format_movie_for_telegram(movie))


# ============================================================
# Handler global de errores
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Captura errores no controlados por los handlers.
    """
    logger.exception("Error en telegram_bot_comandos:", exc_info=context.error)


# ============================================================
# Arranque de la aplicación
# ============================================================

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
    application.add_handler(CommandHandler("pelicula", pelicula))
    application.add_handler(CommandHandler("director", director))
    application.add_handler(CommandHandler("duracion", duracion))
    application.add_handler(CommandHandler("nota", nota))
    application.add_handler(CommandHandler("estreno", estreno))
    application.add_handler(CommandHandler("generos", generos))
    application.add_handler(CommandHandler("resumen", resumen))
    application.add_handler(CommandHandler("recomendar", recomendar))
    application.add_handler(CommandHandler("cartelera", cartelera))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_numeric_selection)
    )

    application.add_error_handler(error_handler)

    logger.info("Bot de Telegram por comandos iniciado")
    application.run_polling()


if __name__ == "__main__":
    main()
