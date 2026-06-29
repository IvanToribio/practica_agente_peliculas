# app/chatbot_service.py

from dataclasses import asdict
import re
from typing import Any

from app.llm_service import (
    LLMServiceError,
    generate_natural_response,
    interpret_user_intent,
)
from app.movie_service import (
    Movie,
    MovieCandidate,
    MovieServiceError,
    get_movie_by_title,
    recommend_now_playing_movies,
    search_movie_candidates,
)


class ChatbotServiceError(Exception):
    """
    Error general de la capa de chatbot.
    """
    pass


# ============================================================
# Funciones auxiliares
# ============================================================

def _empty_response(message: str) -> dict:
    """
    Respuesta estándar cuando el usuario no escribe nada útil.
    """
    return {
        "answer": message,
        "intent": "unknown",
        "data": None,
        "error": None,
    }


def _error_response(message: str, intent: str = "unknown") -> dict:
    """
    Respuesta estándar para errores controlados.
    """
    return {
        "answer": message,
        "intent": intent,
        "data": None,
        "error": message,
    }


def _movie_to_factual_data(movie: Movie) -> dict:
    """
    Convierte un objeto Movie en un diccionario de datos reales.

    Estos datos se pasan al LLM para redactar, pero el LLM no debe inventar
    nada fuera de esta información.
    """
    return asdict(movie)


def _candidate_to_factual_data(candidate: MovieCandidate) -> dict:
    """
    Convierte un MovieCandidate en un diccionario sencillo.

    Los candidatos son resultados parciales de búsqueda, no fichas completas.
    """
    return asdict(candidate)


def _get_field_value(movie: Movie, field: str | None) -> Any:
    """
    Obtiene un campo concreto de una película.

    Si el campo no existe o no está permitido, devuelve None.
    """
    if field is None:
        return None

    allowed_fields = {
        "director",
        "runtime",
        "vote_average",
        "vote_count",
        "overview",
        "genres",
        "release_date",
        "year",
        "original_title",
    }

    if field not in allowed_fields:
        return None

    return getattr(movie, field, None)


def _fallback_answer_for_field(movie: Movie, field: str | None) -> str:
    """
    Respuesta sencilla si el LLM falla al redactar un campo concreto.
    """
    value = _get_field_value(movie, field)

    if value is None or value == "" or value == []:
        return f"No tengo disponible ese dato para {movie.title}."

    if field == "director":
        return f"{movie.title} fue dirigida por {value}."

    if field == "runtime":
        return f"{movie.title} dura {value} minutos."

    if field == "vote_average":
        return f"{movie.title} tiene una nota media de {value:.1f} sobre 10."

    if field == "vote_count":
        return f"{movie.title} tiene {value} votos registrados."

    if field == "overview":
        return f"{movie.title} trata sobre: {value}"

    if field == "genres":
        genres = ", ".join(value)
        return f"Los géneros de {movie.title} son: {genres}."

    if field == "release_date":
        return f"{movie.title} se estrenó el {value}."

    if field == "year":
        return f"{movie.title} es una película de {value}."

    if field == "original_title":
        return f"El título original de {movie.title} es {value}."

    return f"He encontrado información sobre {movie.title}, pero no sé cómo mostrar ese campo."


def _fallback_answer_for_candidates(candidates: list[MovieCandidate]) -> str:
    """
    Respuesta sencilla si el LLM falla al redactar una búsqueda de candidatos.
    """
    if not candidates:
        return "No he encontrado películas con ese título."

    lines = ["He encontrado estas películas:"]

    for index, candidate in enumerate(candidates, start=1):
        year = f" ({candidate.year})" if candidate.year else ""
        rating = (
            f" — nota {candidate.vote_average:.1f}/10"
            if candidate.vote_average is not None
            else ""
        )
        lines.append(f"{index}. {candidate.title}{year}{rating}")

    lines.append("Elige una para ver más detalles.")

    return "\n".join(lines)


def _fallback_answer_for_recommendations(movies: list[Movie]) -> str:
    """
    Respuesta sencilla si el LLM falla al redactar recomendaciones.
    """
    if not movies:
        return "Ahora mismo no tengo recomendaciones disponibles."

    titles = [
        f"{movie.title} ({movie.year})" if movie.year else movie.title
        for movie in movies
    ]

    if len(titles) == 1:
        return f"Te recomiendo {titles[0]}."

    return f"Te recomiendo: {', '.join(titles)}."


def _generate_answer_with_fallback(
    user_message: str,
    intent_data: dict,
    factual_data: dict | list | str,
    fallback_answer: str,
) -> str:
    """
    Intenta redactar con el LLM.

    Si el LLM falla, devuelve una respuesta básica construida por código.
    Esto hace que el chatbot siga siendo funcional aunque Ollama falle.
    """
    try:
        return generate_natural_response(
            user_message=user_message,
            intent_data=intent_data,
            factual_data=factual_data,
        )
    except LLMServiceError:
        return fallback_answer


def _extract_year_from_message(user_message: str) -> int | None:
    """
    Extrae un año de cuatro cifras del mensaje del usuario.

    Sirve como respaldo determinista si el LLM no rellena year.
    """
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", user_message)

    if not match:
        return None

    return int(match.group(1))


def _extract_genre_from_message(user_message: str) -> str | None:
    """
    Extrae géneros frecuentes si el LLM no los identifica.
    """
    normalized_message = user_message.lower()

    genre_keywords = {
        "ciencia ficción": ["ciencia ficción", "ciencia ficcion", "sci-fi", "scifi"],
        "terror": ["terror", "horror"],
        "comedia": ["comedia"],
        "drama": ["drama"],
        "acción": ["acción", "accion"],
        "aventura": ["aventura"],
        "romance": ["romance"],
        "thriller": ["thriller", "suspense"],
        "fantasía": ["fantasía", "fantasia"],
    }

    for genre, keywords in genre_keywords.items():
        if any(keyword in normalized_message for keyword in keywords):
            return genre

    return None


# ============================================================
# Handlers por intención
# ============================================================

def _handle_search_movie(user_message: str, intent_data: dict) -> dict:
    """
    Maneja intención search_movie.

    Uso:
    - El usuario quiere buscar una película.
    - Se devuelven candidatos, no una ficha completa.
    - Ideal para web y Telegram.
    """
    title = intent_data.get("title")
    year = intent_data.get("year")

    if not title:
        return _empty_response(
            "¿Qué película quieres buscar? Escríbeme el título."
        )

    try:
        candidates = search_movie_candidates(
            title=title,
            year=year,
            limit=5,
        )
    except (MovieServiceError, ValueError):
        return _error_response(
            "Ha ocurrido un problema al buscar la película. Prueba de nuevo más tarde.",
            intent="search_movie",
        )

    if not candidates:
        return {
            "answer": f"No he encontrado películas con el título {title}.",
            "intent": "search_movie",
            "data": {
                "candidates": [],
                "title": title,
                "year": year,
            },
            "error": None,
        }

    factual_data = {
        "type": "movie_candidates",
        "title_searched": title,
        "year": year,
        "candidates": [
            _candidate_to_factual_data(candidate)
            for candidate in candidates
        ],
    }

    fallback_answer = _fallback_answer_for_candidates(candidates)

    answer = _generate_answer_with_fallback(
        user_message=user_message,
        intent_data=intent_data,
        factual_data=factual_data,
        fallback_answer=fallback_answer,
    )

    return {
        "answer": answer,
        "intent": "search_movie",
        "data": factual_data,
        "error": None,
    }


def _handle_movie_field(user_message: str, intent_data: dict) -> dict:
    """
    Maneja intención movie_field.

    Uso:
    - El usuario pregunta por un dato concreto:
      director, duración, nota, géneros, año, sinopsis...
    - Se busca automáticamente la primera coincidencia.
    """
    title = intent_data.get("title")
    field = intent_data.get("field")
    year = intent_data.get("year")

    if not title:
        return _empty_response(
            "¿Sobre qué película quieres consultar ese dato?"
        )

    if not field:
        return _empty_response(
            "¿Qué dato quieres saber de la película? Por ejemplo: director, nota o duración."
        )

    try:
        movie = get_movie_by_title(title=title, year=year)
    except MovieServiceError:
        return _error_response(
            "Ha ocurrido un problema al obtener la información de la película.",
            intent="movie_field",
        )

    if movie is None:
        return {
            "answer": f"No he encontrado ninguna película llamada {title}.",
            "intent": "movie_field",
            "data": {
                "title": title,
                "field": field,
                "movie": None,
            },
            "error": None,
        }

    field_value = _get_field_value(movie, field)

    factual_data = {
        "type": "movie_field",
        "movie": _movie_to_factual_data(movie),
        "requested_field": field,
        "field_value": field_value,
    }

    fallback_answer = _fallback_answer_for_field(movie, field)

    answer = _generate_answer_with_fallback(
        user_message=user_message,
        intent_data=intent_data,
        factual_data=factual_data,
        fallback_answer=fallback_answer,
    )

    return {
        "answer": answer,
        "intent": "movie_field",
        "data": factual_data,
        "error": None,
    }


def _handle_movie_summary(user_message: str, intent_data: dict) -> dict:
    """
    Maneja intención movie_summary.

    Uso:
    - El usuario quiere una explicación o resumen de una película.
    - Se busca automáticamente la primera coincidencia.
    """
    title = intent_data.get("title")
    year = intent_data.get("year")

    if not title:
        return _empty_response(
            "¿De qué película quieres que te haga un resumen?"
        )

    try:
        movie = get_movie_by_title(title=title, year=year)
    except MovieServiceError:
        return _error_response(
            "Ha ocurrido un problema al obtener la película.",
            intent="movie_summary",
        )

    if movie is None:
        return {
            "answer": f"No he encontrado ninguna película llamada {title}.",
            "intent": "movie_summary",
            "data": {
                "title": title,
                "movie": None,
            },
            "error": None,
        }

    factual_data = {
        "type": "movie_summary",
        "movie": _movie_to_factual_data(movie),
    }

    fallback_answer = (
        f"{movie.title} trata sobre: {movie.overview}"
        if movie.overview
        else f"No tengo sinopsis disponible para {movie.title}."
    )

    answer = _generate_answer_with_fallback(
        user_message=user_message,
        intent_data=intent_data,
        factual_data=factual_data,
        fallback_answer=fallback_answer,
    )

    return {
        "answer": answer,
        "intent": "movie_summary",
        "data": factual_data,
        "error": None,
    }


def _handle_recommend_movie(user_message: str, intent_data: dict) -> dict:
    """
    Maneja intención recommend_movie.

    Uso:
    - El usuario pide recomendaciones.
    - Se usan películas en cartelera/recomendadas desde movie_service.py.
    """
    genre = intent_data.get("genre") or _extract_genre_from_message(user_message)
    year = intent_data.get("year") or _extract_year_from_message(user_message)
    min_rating = intent_data.get("min_rating")

    if min_rating is None:
        min_rating = 7.0

    try:
        movies = recommend_now_playing_movies(
            min_rating=float(min_rating),
            genre=genre,
            year=year,
            limit=5,
        )
    except MovieServiceError:
        return _error_response(
            "Ha ocurrido un problema al obtener recomendaciones.",
            intent="recommend_movie",
        )

    factual_data = {
        "type": "movie_recommendations",
        "genre": genre,
        "year": year,
        "min_rating": min_rating,
        "movies": [
            _movie_to_factual_data(movie)
            for movie in movies
        ],
    }

    fallback_answer = _fallback_answer_for_recommendations(movies)

    answer = _generate_answer_with_fallback(
        user_message=user_message,
        intent_data=intent_data,
        factual_data=factual_data,
        fallback_answer=fallback_answer,
    )

    return {
        "answer": answer,
        "intent": "recommend_movie",
        "data": factual_data,
        "error": None,
    }


def _handle_unknown() -> dict:
    """
    Maneja mensajes que el LLM no sabe clasificar.
    """
    return {
        "answer": (
            "No he entendido bien la consulta. Puedes preguntarme cosas como: "
            "'¿Quién dirigió Dune?', '¿Cuánto dura Interstellar?' o "
            "'Recomiéndame una película'."
        ),
        "intent": "unknown",
        "data": None,
        "error": None,
    }


# ============================================================
# Función pública principal
# ============================================================

def handle_chat_message(user_message: str) -> dict:
    """
    Punto de entrada principal del chatbot.

    Flujo:
    1. Recibe el mensaje del usuario.
    2. Usa llm_service.interpret_user_intent() para clasificar la intención.
    3. Según la intención, llama a movie_service.py.
    4. Usa llm_service.generate_natural_response() para redactar.
    5. Devuelve una respuesta lista para web o Telegram.

    Retorno estándar:
    {
        "answer": str,
        "intent": str,
        "data": dict | list | None,
        "error": str | None
    }
    """
    if not user_message or not user_message.strip():
        return _empty_response("Escribe una pregunta sobre películas.")

    clean_message = user_message.strip()

    try:
        intent_data = interpret_user_intent(clean_message)
    except LLMServiceError:
        return _error_response(
            "No he podido conectar con el modelo de lenguaje. "
            "Comprueba que Ollama está funcionando.",
            intent="unknown",
        )

    intent = intent_data.get("intent", "unknown")

    if intent == "search_movie":
        return _handle_search_movie(clean_message, intent_data)

    if intent == "movie_field":
        return _handle_movie_field(clean_message, intent_data)

    if intent == "movie_summary":
        return _handle_movie_summary(clean_message, intent_data)

    if intent == "recommend_movie":
        return _handle_recommend_movie(clean_message, intent_data)

    return _handle_unknown()


# ============================================================
# Prueba manual
# ============================================================

if __name__ == "__main__":
    examples = [
        "Busca Dune",
        "¿Quién dirigió Dune?",
        "¿Cuánto dura Interstellar?",
        "¿Qué nota tiene Oppenheimer?",
        "¿De qué va Dune?",
        "Recomiéndame una película de ciencia ficción con nota mayor de 7",
    ]

    for question in examples:
        print("\n" + "=" * 60)
        print(f"Usuario: {question}")

        response = handle_chat_message(question)

        print(f"Intención: {response['intent']}")
        print(f"Respuesta: {response['answer']}")
