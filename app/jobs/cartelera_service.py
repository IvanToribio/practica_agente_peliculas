# app/services/madrid_cinema_service.py

"""
Servicio de integración entre el scraper de cartelera de Madrid
y el backend de películas basado en TMDB.

Entrada:
    list[str] con títulos de películas scrapeadas desde eCartelera.

Salida:
    list[Movie] con información enriquecida desde TMDB.

Este archivo NO formatea para Telegram y NO envía mensajes.
Eso se hará en el siguiente archivo del flujo.
"""

import logging

from app.movie_service import (
    Movie,
    MovieServiceError,
    get_movie_by_title,
)
from app.jobs.scrapper_cartelera import fetch_madrid_cinema_movies


logger = logging.getLogger(__name__)


class MadridCinemaServiceError(Exception):
    """
    Error general de la capa de integración de cartelera de Madrid.
    """
    pass


def _clean_title(title: str) -> str:
    """
    Limpia un título scrapeado antes de buscarlo en TMDB.

    El objetivo es evitar errores por espacios raros, saltos de línea
    o textos vacíos.
    """
    return " ".join(title.strip().split())


def _remove_duplicate_titles(titles: list[str]) -> list[str]:
    """
    Elimina títulos duplicados manteniendo el orden original.
    """
    unique_titles: list[str] = []
    seen_titles: set[str] = set()

    for title in titles:
        clean_title = _clean_title(title)

        if not clean_title:
            continue

        normalized_title = clean_title.lower()

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)
        unique_titles.append(clean_title)

    return unique_titles


def get_movie_from_scraped_title(title: str) -> Movie | None:
    """
    Busca en TMDB una película a partir de un título scrapeado.

    Devuelve:
    - Movie si encuentra una coincidencia.
    - None si no encuentra nada o si ocurre un error controlado.

    Decisión:
    Usamos get_movie_by_title() porque tu backend ya encapsula el flujo:
    título -> candidatos -> primer candidato -> detalles completos.
    """
    clean_title = _clean_title(title)

    if not clean_title:
        return None

    try:
        return get_movie_by_title(clean_title)

    except MovieServiceError:
        logger.exception(
            "No se ha podido obtener información de TMDB para: %s",
            clean_title,
        )
        return None

    except ValueError:
        logger.exception(
            "Título no válido al buscar en TMDB: %s",
            clean_title,
        )
        return None


def enrich_scraped_movies_with_tmdb(
    movie_titles: list[str],
    limit: int | None = None,
) -> list[Movie]:
    """
    Enriquece una lista de títulos scrapeados con información de TMDB.

    Parámetros:
        movie_titles:
            Lista de títulos obtenidos desde el scraper.

        limit:
            Número máximo de títulos a procesar.
            Si es None, procesa todos.

    Retorna:
        list[Movie]:
            Lista de películas encontradas y normalizadas por movie_service.py.

    Flujo:
        1. Limpia títulos.
        2. Elimina duplicados.
        3. Itera por cada título.
        4. Busca la película en TMDB usando movie_service.py.
        5. Guarda solo las películas encontradas.
    """
    clean_titles = _remove_duplicate_titles(movie_titles)

    if limit is not None:
        clean_titles = clean_titles[:limit]

    movies: list[Movie] = []

    for title in clean_titles:
        movie = get_movie_from_scraped_title(title)

        if movie is None:
            logger.warning("Película no encontrada en TMDB: %s", title)
            continue

        movies.append(movie)

    return movies


def get_madrid_cinema_movies_from_tmdb(
    limit: int | None = None,
) -> list[Movie]:
    """
    Función principal del servicio.

    Esta función conecta directamente:
        scraper de eCartelera -> backend TMDB

    Es la función que usará el siguiente archivo del flujo semanal.
    """
    try:
        scraped_titles = fetch_madrid_cinema_movies()

    except Exception as error:
        raise MadridCinemaServiceError(
            "No se ha podido obtener la lista de películas scrapeadas."
        ) from error

    return enrich_scraped_movies_with_tmdb(
        movie_titles=scraped_titles,
        limit=limit,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    movies = get_madrid_cinema_movies_from_tmdb(limit=40)

    print(f"Películas enriquecidas con TMDB: {len(movies)}")
    print("-" * 60)

    for movie in movies:
        year = f" ({movie.year})" if movie.year else ""
        rating = (
            f" - ⭐ {movie.vote_average:.1f}/10"
            if movie.vote_average is not None
            else ""
        )
        director = f" - {movie.director}" if movie.director else ""

        print(f"{movie.title}{year}{rating}{director}")
        
        