# app/formatters.py

from app.movie_service import Movie, MovieCandidate


DEFAULT_EMPTY_VALUE = "No disponible"
IMDB_BASE_URL = "https://www.imdb.com/title"


# ============================================================
# Funciones auxiliares privadas
# ============================================================

def _safe_text(value: object, default: str = DEFAULT_EMPTY_VALUE) -> str:
    """
    Convierte valores vacíos en un texto amable para el usuario.

    Evita respuestas como:
    - None
    - ""
    - []

    Y las convierte en:
    - "No disponible"
    """
    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()
        return value if value else default

    if isinstance(value, list):
        return str(value) if value else default

    return str(value)


def _format_year(year: int | None) -> str:
    """
    Formatea el año de la película.
    """
    if year is None:
        return DEFAULT_EMPTY_VALUE

    return str(year)


def _format_rating(rating: float | None) -> str:
    """
    Formatea la nota media de la película.
    """
    if rating is None:
        return DEFAULT_EMPTY_VALUE

    return f"{rating:.1f}/10"


def _format_votes(vote_count: int | None) -> str:
    """
    Formatea el número de votos con separador de miles.
    """
    if vote_count is None:
        return DEFAULT_EMPTY_VALUE

    return f"{vote_count:,}".replace(",", ".")


def _format_runtime(runtime: int | None) -> str:
    """
    Formatea la duración de la película.
    """
    if runtime is None:
        return DEFAULT_EMPTY_VALUE

    return f"{runtime} min"


def _format_runtime_for_alexa(runtime: int | None) -> str:
    """
    Formatea la duración de forma más natural para Alexa.
    """
    if runtime is None:
        return "duración no disponible"

    return f"{runtime} minutos"


def _format_genres(genres: list[str] | None) -> str:
    """
    Formatea la lista de géneros.
    """
    if not genres:
        return DEFAULT_EMPTY_VALUE

    return ", ".join(genres)


def _join_items_naturally(items: list[str]) -> str:
    """
    Une elementos en lenguaje natural para respuestas de voz.
    """
    clean_items = [
        item.strip()
        for item in items
        if item and item.strip()
    ]

    if not clean_items:
        return DEFAULT_EMPTY_VALUE

    if len(clean_items) == 1:
        return clean_items[0]

    if len(clean_items) == 2:
        return f"{clean_items[0]} y {clean_items[1]}"

    return f"{', '.join(clean_items[:-1])} y {clean_items[-1]}"


def _build_imdb_url(imdb_id: str | None) -> str | None:
    """
    Construye la URL de IMDb a partir del IMDb ID.

    Ejemplo:
    tt1160419 -> https://www.imdb.com/title/tt1160419/
    """
    if not imdb_id:
        return None

    return f"{IMDB_BASE_URL}/{imdb_id}/"


def _format_title_with_year(movie: Movie) -> str:
    """
    Devuelve el título con el año si está disponible.

    Ejemplo:
    Dune (2021)
    """
    if movie.year is None:
        return movie.title

    return f"{movie.title} ({movie.year})"


def _format_candidate_title_with_year(candidate: MovieCandidate) -> str:
    """
    Devuelve el título del candidato con año si está disponible.
    """
    if candidate.year is None:
        return candidate.title

    return f"{candidate.title} ({candidate.year})"


def _format_overview_note(movie: Movie) -> str | None:
    """
    Devuelve una nota si la sinopsis no está en español.

    Esta función no traduce. Solo avisa de que la sinopsis puede venir
    de un fallback en inglés.
    """
    if movie.overview_language == "en-US":
        return "Sinopsis no disponible en español. Mostrando versión en inglés."

    return None


# ============================================================
# Formateadores de película individual
# ============================================================

def format_movie_for_telegram(movie: Movie) -> str:
    """
    Convierte un objeto Movie en un mensaje de texto para Telegram.

    Telegram permite respuestas más visuales, con emojis, saltos de línea
    y enlaces. El póster se incluye como URL para que más adelante el bot
    pueda usarla también para enviar una imagen.
    """
    imdb_url = _build_imdb_url(movie.imdb_id)
    overview_note = _format_overview_note(movie)

    lines = [
        f"🎬 {_format_title_with_year(movie)}",
        "",
        f"⭐ Nota: {_format_rating(movie.vote_average)}",
        f"🗳️ Votos: {_format_votes(movie.vote_count)}",
        f"🎥 Director: {_safe_text(movie.director)}",
        f"⏱️ Duración: {_format_runtime(movie.runtime)}",
        f"🎭 Géneros: {_format_genres(movie.genres)}",
        "",
        "📝 Sinopsis:",
    ]

    if overview_note:
        lines.append(f"ℹ️ {overview_note}")

    lines.append(_safe_text(movie.overview))

    if movie.poster_url:
        lines.extend([
            "",
            f"🖼️ Póster: {movie.poster_url}",
        ])

    if imdb_url:
        lines.extend([
            "",
            f"🔗 IMDb: {imdb_url}",
        ])

    return "\n".join(lines)


def format_movie_for_alexa(movie: Movie) -> str:
    """
    Convierte un objeto Movie en una respuesta breve y natural para Alexa.

    Alexa debe ser concisa. No se incluyen enlaces, póster, TMDB ID ni IMDb ID.
    """
    title = movie.title
    director = movie.director
    year = movie.year
    rating = movie.vote_average
    runtime = movie.runtime

    parts: list[str] = []

    if director and year:
        parts.append(f"{title}, de {director}, es una película de {year}.")
    elif director:
        parts.append(f"{title} es una película de {director}.")
    elif year:
        parts.append(f"{title} es una película de {year}.")
    else:
        parts.append(f"{title} es una película.")

    if rating is not None and runtime is not None:
        parts.append(
            f"Tiene una nota media de {rating:.1f} sobre 10 "
            f"y dura {_format_runtime_for_alexa(runtime)}."
        )
    elif rating is not None:
        parts.append(f"Tiene una nota media de {rating:.1f} sobre 10.")
    elif runtime is not None:
        parts.append(f"Dura {_format_runtime_for_alexa(runtime)}.")
    else:
        parts.append("No tengo disponible su nota ni su duración.")

    return " ".join(parts)


# ============================================================
# Formateadores específicos de Alexa por intent
# ============================================================

def format_search_movie_for_alexa(movie: Movie) -> str:
    """
    Formatea una respuesta general para SearchMovieIntent.
    """
    return format_movie_for_alexa(movie)


def format_director_for_alexa(movie: Movie) -> str:
    """
    Formatea el director para GetDirectorIntent.
    """
    if not movie.director:
        return f"He encontrado {movie.title}, pero no tengo información sobre su director."

    return f"{movie.title} fue dirigida por {movie.director}."


def format_rating_for_alexa(movie: Movie) -> str:
    """
    Formatea la nota media para GetRatingIntent.
    """
    if movie.vote_average is None:
        return f"He encontrado {movie.title}, pero no tengo su nota disponible."

    if movie.vote_count is not None:
        return (
            f"La nota de {movie.title} es {movie.vote_average:.1f} sobre 10, "
            f"basada en {movie.vote_count} votos."
        )

    return f"La nota de {movie.title} es {movie.vote_average:.1f} sobre 10."


def format_release_date_for_alexa(movie: Movie) -> str:
    """
    Formatea el año o fecha de estreno para GetReleaseDateIntent.
    """
    if movie.year is not None:
        return f"{movie.title} se estrenó en {movie.year}."

    if movie.release_date:
        return f"{movie.title} se estrenó el {movie.release_date}."

    return f"He encontrado {movie.title}, pero no tengo su fecha de estreno disponible."


def format_runtime_for_alexa(movie: Movie) -> str:
    """
    Formatea la duración para GetRuntimeIntent.
    """
    if movie.runtime is None:
        return f"He encontrado {movie.title}, pero no tengo su duración disponible."

    return f"{movie.title} dura {_format_runtime_for_alexa(movie.runtime)}."


def format_overview_for_alexa(movie: Movie, max_length: int = 450) -> str:
    """
    Formatea la sinopsis para GetOverviewIntent.
    """
    overview = movie.overview.strip() if movie.overview else ""

    if not overview:
        return f"No tengo una sinopsis disponible para {movie.title}."

    if len(overview) > max_length:
        overview = overview[:max_length].rstrip() + "..."

    if movie.overview_language == "en-US":
        return (
            "No he encontrado la sinopsis en español. "
            f"{movie.title} trata sobre lo siguiente: {overview}"
        )

    return f"{movie.title} trata sobre lo siguiente: {overview}"


def format_genres_for_alexa(movie: Movie) -> str:
    """
    Formatea los géneros para GetGenresIntent.
    """
    if not movie.genres:
        return f"He encontrado {movie.title}, pero no tengo sus géneros disponibles."

    genres = [
        genre.lower()
        for genre in movie.genres
    ]

    if len(genres) == 1:
        return f"El género de {movie.title} es {genres[0]}."

    return f"Los géneros de {movie.title} son {_join_items_naturally(genres)}."


def format_movie_for_alexa_intent(movie: Movie, intent_name: str) -> str:
    """
    Mapea un intent de Alexa a su formateador específico.
    """
    intent_formatters = {
        "SearchMovieIntent": format_search_movie_for_alexa,
        "GetDirectorIntent": format_director_for_alexa,
        "GetRatingIntent": format_rating_for_alexa,
        "GetReleaseDateIntent": format_release_date_for_alexa,
        "GetRuntimeIntent": format_runtime_for_alexa,
        "GetOverviewIntent": format_overview_for_alexa,
        "GetGenresIntent": format_genres_for_alexa,
    }

    formatter = intent_formatters.get(intent_name)

    if formatter is None:
        return "No sé responder todavía a esa consulta sobre la película."

    return formatter(movie)


def format_movie_for_web(movie: Movie) -> dict:
    """
    Convierte un objeto Movie en un diccionario para la web.

    La web es el canal más completo. Se devuelven los campos separados
    para que el frontend decida qué mostrar y cómo mostrarlo.
    """
    imdb_url = _build_imdb_url(movie.imdb_id)

    return {
        "title": _safe_text(movie.title),
        "original_title": _safe_text(movie.original_title),
        "year": movie.year,
        "year_label": _format_year(movie.year),
        "release_date": _safe_text(movie.release_date),
        "vote_average": movie.vote_average,
        "vote_average_label": _format_rating(movie.vote_average),
        "vote_count": movie.vote_count,
        "vote_count_label": _format_votes(movie.vote_count),
        "director": _safe_text(movie.director),
        "runtime": movie.runtime,
        "runtime_label": _format_runtime(movie.runtime),
        "genres": movie.genres if movie.genres else [],
        "genres_label": _format_genres(movie.genres),
        "overview": _safe_text(movie.overview),
        "overview_language": _safe_text(movie.overview_language),
        "poster_url": movie.poster_url,
        "tmdb_id": movie.tmdb_id,
        "imdb_id": _safe_text(movie.imdb_id),
        "imdb_url": imdb_url,
    }


# ============================================================
# Formateadores de candidatos
# ============================================================

def format_candidate_for_web(candidate: MovieCandidate) -> dict:
    """
    Convierte un MovieCandidate en un diccionario para resultados web.
    """
    return {
        "tmdb_id": candidate.tmdb_id,
        "title": _safe_text(candidate.title),
        "original_title": _safe_text(candidate.original_title),
        "year": candidate.year,
        "year_label": _format_year(candidate.year),
        "release_date": _safe_text(candidate.release_date),
        "vote_average": candidate.vote_average,
        "vote_average_label": _format_rating(candidate.vote_average),
        "vote_count": candidate.vote_count,
        "vote_count_label": _format_votes(candidate.vote_count),
        "poster_url": candidate.poster_url,
    }


def format_candidate_list_for_web(candidates: list[MovieCandidate]) -> list[dict]:
    """
    Formatea una lista de candidatos para la web.
    """
    return [format_candidate_for_web(candidate) for candidate in candidates]


def format_candidate_list_for_telegram(candidates: list[MovieCandidate]) -> str:
    """
    Formatea candidatos para que Telegram pida una elección numérica.
    """
    if not candidates:
        return "No he encontrado películas para elegir."

    lines = [
        "He encontrado varias películas:",
        "",
    ]

    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            f"{index}. {_format_candidate_title_with_year(candidate)} "
            f"— ⭐ {_format_rating(candidate.vote_average)}"
        )

    lines.extend([
        "",
        "Responde con el número de la película que quieres consultar.",
    ])

    return "\n".join(lines)


# ============================================================
# Formateadores de listas
# ============================================================

def format_movie_list_for_telegram(
    movies: list[Movie],
    title: str = "🎬 Películas encontradas",
) -> str:
    """
    Formatea una lista de películas para Telegram.

    Se usa para búsquedas, cartelera o recomendaciones.
    """
    if not movies:
        return "No se han encontrado películas."

    lines = [
        title,
        "",
    ]

    for index, movie in enumerate(movies, start=1):
        line = (
            f"{index}. 🎬 {_format_title_with_year(movie)} "
            f"— ⭐ {_format_rating(movie.vote_average)}"
        )

        if movie.director:
            line += f" — 🎥 {movie.director}"

        lines.append(line)

    return "\n".join(lines)


def format_movie_list_for_alexa(
    movies: list[Movie],
    max_movies: int = 3,
) -> str:
    """
    Formatea una lista de películas para Alexa.

    Alexa debe dar pocas recomendaciones para no ser pesada.
    """
    if not movies:
        return "No he encontrado películas disponibles."

    selected_movies = movies[:max_movies]
    titles = [_format_title_with_year(movie) for movie in selected_movies]

    if len(titles) == 1:
        return f"Te recomiendo {titles[0]}."

    if len(titles) == 2:
        return f"Te recomiendo {titles[0]} y {titles[1]}."

    first_titles = ", ".join(titles[:-1])
    last_title = titles[-1]

    return f"Te recomiendo {first_titles} y {last_title}."


def format_movie_list_for_web(movies: list[Movie]) -> list[dict]:
    """
    Formatea una lista de películas para la web.

    Devuelve una lista de diccionarios reutilizando format_movie_for_web().
    """
    return [format_movie_for_web(movie) for movie in movies]


# ============================================================
# Formateadores de recomendaciones
# ============================================================

def format_recommendations_for_telegram(movies: list[Movie]) -> str:
    """
    Formatea recomendaciones para Telegram.
    """
    return format_movie_list_for_telegram(
        movies=movies,
        title="🍿 Recomendaciones de películas",
    )


def format_recommendations_for_alexa(movies: list[Movie]) -> str:
    """
    Formatea recomendaciones para Alexa.
    """
    if not movies:
        return "Ahora mismo no tengo recomendaciones disponibles."

    return format_movie_list_for_alexa(movies)


def format_recommendations_for_web(movies: list[Movie]) -> list[dict]:
    """
    Formatea recomendaciones para la web.
    """
    return format_movie_list_for_web(movies)


# ============================================================
# Formateadores de errores simples
# ============================================================

def format_not_found_for_telegram(title: str) -> str:
    """
    Mensaje para Telegram cuando no se encuentra una película.
    """
    return (
        f"❌ No he encontrado ninguna película con el título: {title}.\n"
        "Prueba con otro título o añade el año de estreno."
    )


def format_not_found_for_alexa(title: str) -> str:
    """
    Mensaje para Alexa cuando no se encuentra una película.
    """
    return (
        f"No he encontrado ninguna película llamada {title}. "
        "Prueba con otro título o especifica el año de estreno."
    )
    
if __name__ == "__main__":
    from app.movie_service import get_movie_by_title

    movie = get_movie_by_title("Dune", year=2021)

    if movie:
        print("=== TELEGRAM ===")
        print(format_movie_for_telegram(movie))

        print("\n=== ALEXA ===")
        print(format_movie_for_alexa(movie))

        print("\n=== WEB ===")
