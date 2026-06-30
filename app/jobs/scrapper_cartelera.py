# app/scrapers/madrid_cinema_scraper.py

import requests
from bs4 import BeautifulSoup


ECARTELERA_MADRID_URL = "https://www.ecartelera.com/cines/0,30,1.html"
REQUEST_TIMEOUT = 10


class MadridCinemaScraperError(Exception):
    """
    Error general del scraper de cartelera de Madrid.
    """
    pass


def _is_movie_title(text: str) -> bool:
    """
    Filtra enlaces que no son títulos de películas.

    En la página aparecen también enlaces como:
    - Horarios: 78 cines
    - Ver tráiler
    - imágenes de carteles
    """
    if not text:
        return False

    forbidden_texts = [
        "Ver tráiler",
        "Ver trailer",
    ]

    forbidden_prefixes = [
        "Horarios:",
        "Image:",
        "Cartel de",
    ]

    if text in forbidden_texts:
        return False

    if any(text.startswith(prefix) for prefix in forbidden_prefixes):
        return False

    return True


def fetch_madrid_cinema_movies() -> list[str]:
    """
    Obtiene los títulos de las películas en cartelera en Madrid
    desde eCartelera.

    Flujo:
    1. Descarga el HTML de la página.
    2. Busca el texto "Películas en cartelera en Madrid".
    3. Recorre los enlaces posteriores.
    4. Se queda solo con los títulos de películas.
    5. Para al llegar a la siguiente sección.
    6. Devuelve una lista de títulos sin duplicados.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; MadridCinemaScraper/1.0)"
        )
    }

    try:
        response = requests.get(
            ECARTELERA_MADRID_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    except requests.exceptions.RequestException as error:
        raise MadridCinemaScraperError(
            "No se ha podido descargar la cartelera de Madrid."
        ) from error

    soup = BeautifulSoup(response.text, "html.parser")

    section_title = soup.find(
        string=lambda text: (
            text is not None
            and "Películas en cartelera en Madrid" in text
        )
    )

    if section_title is None:
        raise MadridCinemaScraperError(
            "No se ha encontrado la sección de películas en cartelera en Madrid."
        )

    movie_titles: list[str] = []
    seen_titles: set[str] = set()

    for element in section_title.find_all_next():
        element_text = element.get_text(" ", strip=True)

        if "Cartelera en otras ciudades cercanas a Madrid" in element_text:
            break

        if element.name != "a":
            continue

        title = element.get_text(" ", strip=True)

        if not _is_movie_title(title):
            continue

        normalized_title = title.lower().strip()

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)
        movie_titles.append(title)

    return movie_titles


if __name__ == "__main__":
    titles = fetch_madrid_cinema_movies()

    print(f"Películas encontradas: {len(titles)}")
    print("-" * 40)

    for title in titles:
        print(title)