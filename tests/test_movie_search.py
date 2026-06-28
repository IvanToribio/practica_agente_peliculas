# tests/test_movie_search.py

import pytest

from app.movie_service import Movie, get_movie_by_title, search_movie_results


def test_search_movie_results_returns_candidates(monkeypatch):
    """
    Comprueba que search_movie_results devuelve candidatos
    cuando TMDB encuentra resultados.
    """

    fake_results = [
        {
            "id": 438631,
            "title": "Dune",
            "original_title": "Dune",
            "release_date": "2021-09-15",
            "vote_average": 7.8,
            "vote_count": 13000,
        }
    ]

    def fake_search_movies(title, year=None):
        return fake_results

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.search_movies",
        fake_search_movies,
    )

    results = search_movie_results("Dune", year=2021)

    assert len(results) == 1
    assert results[0]["id"] == 438631
    assert results[0]["title"] == "Dune"


def test_search_movie_results_empty_title_raises_error():
    """
    Comprueba que no se permite buscar con un título vacío.
    """

    with pytest.raises(ValueError):
        search_movie_results("")


def test_get_movie_by_title_returns_movie_object(monkeypatch):
    """
    Comprueba que get_movie_by_title:
    1. busca la película,
    2. toma el primer resultado,
    3. pide detalles completos,
    4. devuelve un objeto Movie normalizado.
    """

    fake_search_results = [
        {
            "id": 438631,
            "title": "Dune",
            "release_date": "2021-09-15",
        }
    ]

    fake_full_details = {
        "id": 438631,
        "external_ids": {
            "imdb_id": "tt1160419",
        },
        "title": "Dune",
        "original_title": "Dune",
        "release_date": "2021-09-15",
        "vote_average": 7.8,
        "vote_count": 13000,
        "overview": "Arrakis, también denominado Dune...",
        "credits": {
            "crew": [
                {
                    "job": "Director",
                    "name": "Denis Villeneuve",
                }
            ]
        },
        "runtime": 155,
        "genres": [
            {"id": 878, "name": "Ciencia ficción"},
            {"id": 12, "name": "Aventura"},
        ],
        "poster_path": "/dune_poster.jpg",
    }

    def fake_search_movies(title, year=None):
        return fake_search_results

    def fake_get_movie_full_details(movie_id, language=None):
        return fake_full_details

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.search_movies",
        fake_search_movies,
    )

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.get_movie_full_details",
        fake_get_movie_full_details,
    )

    movie = get_movie_by_title("Dune", year=2021)

    assert isinstance(movie, Movie)
    assert movie.tmdb_id == 438631
    assert movie.imdb_id == "tt1160419"
    assert movie.title == "Dune"
    assert movie.original_title == "Dune"
    assert movie.year == 2021
    assert movie.release_date == "2021-09-15"
    assert movie.vote_average == 7.8
    assert movie.vote_count == 13000
    assert movie.director == "Denis Villeneuve"
    assert movie.runtime == 155
    assert movie.genres == ["Ciencia ficción", "Aventura"]
    assert movie.poster_url == "https://image.tmdb.org/t/p/w500/dune_poster.jpg"


def test_get_movie_by_title_returns_none_when_no_results(monkeypatch):
    """
    Comprueba que si TMDB no devuelve resultados,
    el servicio devuelve None.
    """

    def fake_search_movies(title, year=None):
        return []

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.search_movies",
        fake_search_movies,
    )

    movie = get_movie_by_title("Película que no existe")

    assert movie is None