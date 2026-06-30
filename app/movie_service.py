# app/movie_service.py

from dataclasses import dataclass
import unicodedata

from app import tmdb_client
from app.config import settings
from app.tmdb_client import TMDBClientError


class MovieServiceError(Exception):
    """Error general de la capa de servicio de películas."""
    pass


class MovieNotFoundError(MovieServiceError):
    """Error para casos en los que no se encuentra una película."""
    pass


TMDB_GENRE_IDS = {
    "accion": 28,
    "action": 28,
    "aventura": 12,
    "adventure": 12,
    "animacion": 16,
    "animation": 16,
    "comedia": 35,
    "comedy": 35,
    "crimen": 80,
    "crime": 80,
    "documental": 99,
    "documentary": 99,
    "drama": 18,
    "familia": 10751,
    "family": 10751,
    "fantasia": 14,
    "fantasy": 14,
    "historia": 36,
    "history": 36,
    "terror": 27,
    "horror": 27,
    "musica": 10402,
    "music": 10402,
    "misterio": 9648,
    "mystery": 9648,
    "romance": 10749,
    "ciencia ficcion": 878,
    "science fiction": 878,
    "sci fi": 878,
    "scifi": 878,
    "thriller": 53,
    "suspense": 53,
    "guerra": 10752,
    "war": 10752,
    "western": 37,
}


@dataclass(frozen=True)
class Movie:
    """
    Representa una película normalizada dentro de nuestra aplicación.

    Esta clase evita que la web, Telegram o Alexa dependan directamente
    del JSON bruto que devuelve TMDB.
    """

    tmdb_id: int
    imdb_id: str | None
    title: str
    original_title: str | None
    year: int | None
    release_date: str | None
    vote_average: float | None
    vote_count: int | None
    overview: str | None
    overview_language: str | None
    director: str | None
    runtime: int | None
    genres: list[str]
    poster_url: str | None


@dataclass(frozen=True)
class MovieCandidate:
    """
    Representa un resultado parcial de búsqueda.

    A diferencia de Movie, no contiene detalles completos como director,
    duración o sinopsis. Sirve para que web y Telegram puedan mostrar opciones
    sin cargar la ficha completa de cada resultado.
    """

    tmdb_id: int
    title: str
    original_title: str | None
    year: int | None
    release_date: str | None
    vote_average: float | None
    vote_count: int | None
    poster_url: str | None


def _clean_text(value: str | None) -> str | None:
    """
    Limpia textos vacíos.

    TMDB a veces devuelve strings vacíos. Para el resto del proyecto
    es más cómodo trabajar con None cuando no hay información real.
    """
    if value is None:
        return None

    value = value.strip()

    if value == "":
        return None

    return value


def _normalize_text_for_matching(value: str) -> str:
    """
    Normaliza texto para comparar géneros sin depender de acentos o mayúsculas.
    """
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.lower().split())


def _get_genre_id(genre: str | None) -> int | None:
    """
    Convierte un género común en el ID que espera TMDB discover.
    """
    if not genre:
        return None

    return TMDB_GENRE_IDS.get(_normalize_text_for_matching(genre))


def _movie_matches_genre(movie: Movie, genre: str | None) -> bool:
    """
    Comprueba si una película contiene el género solicitado.
    """
    if genre is None:
        return True

    requested_genre = _normalize_text_for_matching(genre)

    return any(
        requested_genre == _normalize_text_for_matching(movie_genre)
        for movie_genre in movie.genres
    )


def _extract_year(release_date: str | None) -> int | None:
    """
    Extrae el año a partir de una fecha tipo '2021-09-15'.
    """
    if not release_date:
        return None

    try:
        return int(release_date.split("-")[0])
    except (ValueError, IndexError):
        return None


def _extract_genres(movie_data: dict) -> list[str]:
    """
    Extrae los géneros desde la respuesta completa de TMDB.
    """
    genres = movie_data.get("genres", [])

    return [
        genre.get("name")
        for genre in genres
        if genre.get("name")
    ]


def _extract_director(movie_data: dict) -> str | None:
    """
    Extrae un único director desde credits.crew.

    Decisión tomada:
    - Usamos solo un director para simplificar Telegram, Alexa y web.
    - Si hubiera varios directores, se devuelve el primero encontrado.
    """
    credits = movie_data.get("credits", {})
    crew = credits.get("crew", [])

    for person in crew:
        if person.get("job") == "Director":
            return person.get("name")

    return None


def _get_imdb_id(movie_data: dict) -> str | None:
    """
    Extrae el IMDb ID desde external_ids.

    No es obligatorio para que el sistema funcione,
    pero se guarda porque puede ser útil en la web o futuras integraciones.
    """
    external_ids = movie_data.get("external_ids", {})
    return external_ids.get("imdb_id")


def _get_overview_language(movie_data: dict) -> str | None:
    """
    Determina el idioma de la sinopsis principal.

    Si la sinopsis existe en la respuesta inicial, asumimos que está
    en el idioma por defecto configurado, normalmente es-ES.
    """
    overview = _clean_text(movie_data.get("overview"))

    if overview:
        return settings.default_language

    return None


def _apply_english_overview_fallback(movie_id: int, movie_data: dict) -> tuple[dict, str | None]:
    """
    Aplica fallback de sinopsis en inglés.

    Flujo:
    1. Si la sinopsis en español existe, se mantiene.
    2. Si no existe, se consulta la película en inglés.
    3. Si existe sinopsis en inglés, se guarda en overview.
    4. Si tampoco existe, overview queda como None.

    Importante:
    No traducimos ni inventamos sinopsis aquí.
    Eso se podría añadir más adelante con un LLM en otra capa.
    """
    current_overview = _clean_text(movie_data.get("overview"))

    if current_overview:
        movie_data = movie_data.copy()
        movie_data["overview"] = current_overview
        return movie_data, settings.default_language

    try:
        english_data = tmdb_client.get_movie_full_details(
            movie_id=movie_id,
            language="en-US",
        )
    except TMDBClientError:
        return movie_data, None

    english_overview = _clean_text(english_data.get("overview"))

    if english_overview:
        movie_data = movie_data.copy()
        movie_data["overview"] = english_overview
        return movie_data, "en-US"

    return movie_data, None


def _normalize_movie(movie_data: dict, overview_language: str | None) -> Movie:
    """
    Convierte la respuesta completa de TMDB en un objeto Movie.

    Esta es la normalización principal del proyecto.
    A partir de aquí, web, Telegram, Alexa y futuros servicios
    trabajan con Movie, no con JSON bruto.
    """
    tmdb_id = movie_data.get("id")

    if tmdb_id is None:
        raise MovieServiceError("No se puede normalizar una película sin TMDB ID.")

    release_date = movie_data.get("release_date")

    title = (
        _clean_text(movie_data.get("title"))
        or _clean_text(movie_data.get("original_title"))
        or "Título desconocido"
    )

    return Movie(
        tmdb_id=tmdb_id,
        imdb_id=_get_imdb_id(movie_data),
        title=title,
        original_title=_clean_text(movie_data.get("original_title")),
        year=_extract_year(release_date),
        release_date=release_date,
        vote_average=movie_data.get("vote_average"),
        vote_count=movie_data.get("vote_count"),
        overview=_clean_text(movie_data.get("overview")),
        overview_language=overview_language,
        director=_extract_director(movie_data),
        runtime=movie_data.get("runtime"),
        genres=_extract_genres(movie_data),
        poster_url=tmdb_client.build_poster_url(movie_data.get("poster_path")),
    )


def _normalize_candidate(raw_movie: dict) -> MovieCandidate:
    """
    Convierte un resultado parcial de /search/movie en MovieCandidate.
    """
    tmdb_id = raw_movie.get("id")

    if tmdb_id is None:
        raise MovieServiceError("No se puede normalizar un candidato sin TMDB ID.")

    release_date = raw_movie.get("release_date")

    title = (
        _clean_text(raw_movie.get("title"))
        or _clean_text(raw_movie.get("original_title"))
        or "Título desconocido"
    )

    return MovieCandidate(
        tmdb_id=tmdb_id,
        title=title,
        original_title=_clean_text(raw_movie.get("original_title")),
        year=_extract_year(release_date),
        release_date=release_date,
        vote_average=raw_movie.get("vote_average"),
        vote_count=raw_movie.get("vote_count"),
        poster_url=tmdb_client.build_poster_url(raw_movie.get("poster_path")),
    )


def search_movie_results(
    title: str,
    year: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Busca películas por título y devuelve resultados parciales de TMDB.

    Esta función puede ser útil para la web o para el chatbot,
    porque permite mostrar varias opciones si el usuario busca algo ambiguo.

    """
    title = title.strip()

    if not title:
        raise ValueError("El título de la película no puede estar vacío.")

    try:
        results = tmdb_client.search_movies(title=title, year=year)
    except TMDBClientError as error:
        raise MovieServiceError(f"No se pudo buscar la película: {title}") from error

    return results[:limit]


def search_movie_candidates(
    title: str,
    year: int | None = None,
    limit: int = 5,
) -> list[MovieCandidate]:
    """
    Busca películas por título y devuelve candidatos normalizados.

    Esta función separa buscar de elegir. No obtiene detalles completos:
    solo normaliza la respuesta parcial de TMDB para que web y Telegram
    muestren opciones al usuario.
    """
    raw_results = search_movie_results(title=title, year=year, limit=limit)
    candidates: list[MovieCandidate] = []

    for raw_movie in raw_results:
        try:
            candidates.append(_normalize_candidate(raw_movie))
        except MovieServiceError:
            continue

    return candidates


def get_movie_by_id(movie_id: int) -> Movie:
    """
    Obtiene una película completa a partir de su TMDB ID.

    Flujo:
    1. Pide detalles completos a TMDB usando get_movie_full_details().
    2. Aplica fallback de sinopsis en inglés si falta la sinopsis en español.
    3. Normaliza todo a un objeto Movie.
    """
    try:
        movie_data = tmdb_client.get_movie_full_details(movie_id=movie_id)
    except TMDBClientError as error:
        raise MovieServiceError(
            f"No se pudieron obtener los detalles de la película con ID {movie_id}."
        ) from error

    movie_data, overview_language = _apply_english_overview_fallback(
        movie_id=movie_id,
        movie_data=movie_data,
    )

    return _normalize_movie(
        movie_data=movie_data,
        overview_language=overview_language,
    )


def get_movie_by_title(
    title: str,
    year: int | None = None,
) -> Movie | None:
    """
    Busca una película por título y devuelve la primera coincidencia.

    Uso:
    - Alexa.
    - Respuestas rápidas.
    - Casos donde se quiera escoger automáticamente la primera coincidencia.

    Decisión tomada:
    - Para esta versión automática, se escoge el primer candidato.
    - Más adelante se podrá mejorar resolviendo ambigüedades con opciones,
      ranking o confirmación del usuario.
    """
    candidates = search_movie_candidates(title=title, year=year, limit=1)

    if not candidates:
        return None

    return get_movie_by_id(candidates[0].tmdb_id)


def get_movie_field(
    title: str,
    field: str,
    year: int | None = None,
) -> object | None:
    """
    Devuelve un campo concreto de una película.

    Esto será útil para Alexa, Telegram y el futuro chatbot web.

    Ejemplos:
    - get_movie_field("Dune", "vote_average")
    - get_movie_field("Dune", "director")
    - get_movie_field("Dune", "runtime")
    """
    allowed_fields = {
        "tmdb_id",
        "imdb_id",
        "title",
        "original_title",
        "year",
        "release_date",
        "vote_average",
        "vote_count",
        "overview",
        "overview_language",
        "director",
        "runtime",
        "genres",
        "poster_url",
    }

    if field not in allowed_fields:
        raise ValueError(f"Campo no permitido: {field}")

    movie = get_movie_by_title(title=title, year=year)

    if movie is None:
        return None

    return getattr(movie, field)


def get_now_playing_movies(
    limit: int = 10,
) -> list[Movie]:
    """
    Obtiene películas actualmente en cartelera según la región configurada.

    Actualmente usa TMDB now_playing con region=ES.
    Esto es una aproximación a cartelera en España, no cartelera exacta de Madrid.

    Más adelante, si añades una fuente específica de cartelera de Madrid,
    esa lógica debería conectarse aquí o en un módulo separado.
    """
    try:
        raw_movies = tmdb_client.get_now_playing_movies()
    except TMDBClientError as error:
        raise MovieServiceError("No se pudo obtener la cartelera actual.") from error

    movies: list[Movie] = []

    for raw_movie in raw_movies[:limit]:
        movie_id = raw_movie.get("id")

        if movie_id is None:
            continue

        try:
            movie = get_movie_by_id(movie_id)
            movies.append(movie)
        except MovieServiceError:
            # Si una película concreta falla, no rompemos toda la cartelera.
            continue

    return movies


def recommend_now_playing_movies(
    min_rating: float = 7.0,
    min_votes: int = 100,
    genre: str | None = None,
    year: int | None = None,
    limit: int = 5,
) -> list[Movie]:
    """
    Recomienda películas usando criterios sencillos.

    Criterios:
    - nota media mínima
    - número mínimo de votos
    - género opcional
    - año opcional
    - orden por nota y número de votos

    Si se indica un año, se usa discover/movie para buscar películas de ese año.
    Si no se indica año, mantiene el comportamiento original de cartelera actual.

    Esta función será útil para:
    - web
    - Telegram
    - Alexa
    - cron semanal
    """
    if year is not None:
        try:
            raw_movies = tmdb_client.discover_movies(
                year=year,
                genre_id=_get_genre_id(genre),
                min_votes=min_votes,
                sort_by="vote_average.desc",
            )
        except TMDBClientError as error:
            raise MovieServiceError("No se pudieron descubrir películas para recomendar.") from error

        movies = []

        for raw_movie in raw_movies[: max(limit * 3, limit)]:
            movie_id = raw_movie.get("id")

            if movie_id is None:
                continue

            try:
                movies.append(get_movie_by_id(movie_id))
            except MovieServiceError:
                continue
    else:
        movies = get_now_playing_movies(limit=20)

    filtered_movies: list[Movie] = []

    for movie in movies:
        vote_average = movie.vote_average or 0
        vote_count = movie.vote_count or 0

        if vote_average < min_rating:
            continue

        if vote_count < min_votes:
            continue

        if year is not None and movie.year != year:
            continue

        if not _movie_matches_genre(movie, genre):
            continue

        filtered_movies.append(movie)

    filtered_movies.sort(
        key=lambda movie: (
            movie.vote_average or 0,
            movie.vote_count or 0,
        ),
        reverse=True,
    )

    return filtered_movies[:limit]


if __name__ == "__main__":
    movie = get_movie_by_title("Dune", year=2021)

    if movie is None:
        print("No se ha encontrado la película.")
    else:
        print(movie)
