# app/tmdb_client.py

import requests

from app.config import settings


POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
REQUEST_TIMEOUT = 10


class TMDBClientError(Exception):
    """
    Error personalizado para problemas al llamar a TMDB.

    Esta excepción permite que movie_service.py capture errores del cliente
    sin depender directamente de requests.
    """
    pass


def get_headers() -> dict:
    """
    Crea los headers necesarios para autenticarse en TMDB usando Bearer Token.
    """
    return {
        "Authorization": f"Bearer {settings.tmdb_bearer_token}",
        "accept": "application/json",
    }


def _get(endpoint: str, params: dict | None = None) -> dict:
    """
    Función interna para hacer peticiones GET a TMDB.

    Responsabilidad:
    - construir la URL final
    - enviar headers de autenticación
    - aplicar timeout
    - controlar errores HTTP
    - devolver la respuesta JSON como diccionario

    endpoint:
        Ruta de la API, por ejemplo: '/search/movie'

    params:
        Parámetros query string, por ejemplo:
        {'query': 'Dune', 'language': 'es-ES'}
    """
    url = f"{settings.tmdb_base_url}{endpoint}"

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as error:
        response = error.response

        if response is not None:
            status_code = response.status_code
            response_text = response.text
        else:
            status_code = "unknown"
            response_text = "No response body"

        raise TMDBClientError(
            f"Error HTTP al llamar a TMDB. "
            f"Status code: {status_code}. "
            f"Respuesta: {response_text}"
        ) from error

    except requests.exceptions.Timeout as error:
        raise TMDBClientError("Timeout al llamar a TMDB.") from error

    except requests.exceptions.RequestException as error:
        raise TMDBClientError(f"Error de conexión con TMDB: {error}") from error

    except ValueError as error:
        raise TMDBClientError("La respuesta de TMDB no es un JSON válido.") from error


def search_movies(
    title: str,
    year: int | None = None,
    page: int = 1,
    language: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """
    Busca películas por título usando el endpoint /search/movie.

    Devuelve una lista de resultados parciales de TMDB.

    Importante:
    Esta función NO decide qué película es la correcta.
    Solo devuelve candidatos. La decisión se toma en movie_service.py.
    """
    params = {
        "query": title,
        "language": language or settings.default_language,
        "region": region or settings.default_region,
        "page": page,
        "include_adult": False,
    }

    if year is not None:
        params["year"] = year

    data = _get("/search/movie", params=params)

    return data.get("results", [])


def get_movie_details(
    movie_id: int,
    language: str | None = None,
) -> dict:
    """
    Obtiene los detalles principales de una película por TMDB ID.

    Devuelve el JSON bruto de TMDB.
    """
    params = {
        "language": language or settings.default_language,
    }

    return _get(f"/movie/{movie_id}", params=params)


def get_movie_credits(
    movie_id: int,
    language: str | None = None,
) -> dict:
    """
    Obtiene reparto y equipo técnico de una película.

    De aquí movie_service.py podrá extraer el director,
    pero este cliente no hace esa extracción.
    """
    params = {
        "language": language or settings.default_language,
    }

    return _get(f"/movie/{movie_id}/credits", params=params)


def get_external_ids(movie_id: int) -> dict:
    """
    Obtiene IDs externos de una película.

    Por ejemplo:
    - IMDb ID
    - Wikidata ID
    - Facebook ID
    - Instagram ID
    - Twitter/X ID

    Devuelve el JSON bruto de TMDB.
    """
    return _get(f"/movie/{movie_id}/external_ids")


def get_movie_full_details(
    movie_id: int,
    language: str | None = None,
) -> dict:
    """
    Obtiene detalles completos de una película usando append_to_response.

    Incluye:
    - detalles principales
    - credits
    - external_ids

    Esta función es la que usará normalmente movie_service.py,
    porque evita hacer varias llamadas separadas.
    """
    params = {
        "language": language or settings.default_language,
        "append_to_response": "credits,external_ids",
    }

    return _get(f"/movie/{movie_id}", params=params)


def get_now_playing_movies(
    page: int = 1,
    language: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """
    Obtiene películas actualmente en cartelera según región.

    Para España se usará region='ES'.

    Importante:
    Esto no equivale exactamente a cartelera de Madrid.
    Es una aproximación usando la cartelera por país/región de TMDB.
    """
    params = {
        "language": language or settings.default_language,
        "region": region or settings.default_region,
        "page": page,
    }

    data = _get("/movie/now_playing", params=params)

    return data.get("results", [])


def build_poster_url(poster_path: str | None) -> str | None:
    """
    Construye la URL completa del póster a partir del poster_path de TMDB.

    Esta función se mantiene aquí porque la URL de imágenes es un detalle
    específico de TMDB, no una decisión de negocio.
    """
    if not poster_path:
        return None

    return f"{POSTER_BASE_URL}{poster_path}"


if __name__ == "__main__":
    """
    Prueba rápida del cliente TMDB.

    Ejecutar desde la raíz del proyecto con:

        python -m app.tmdb_client

    Esta prueba solo comprueba que el cliente conecta con TMDB.
    La normalización completa se prueba desde movie_service.py.
    """
    results = search_movies("Dune", year=2021)

    if not results:
        print("No se encontraron resultados.")
    else:
        first_result = results[0]
        movie_id = first_result["id"]

        print("Primer resultado encontrado:")
        print(first_result)

        print("\nDetalles completos:")
        details = get_movie_full_details(movie_id)
        print(details)