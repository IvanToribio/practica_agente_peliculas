# tests/test_movie_search.py

import pytest

from app.movie_service import (
    Movie,
    MovieCandidate,
    get_movie_by_title,
    recommend_now_playing_movies,
    search_movie_candidates,
    search_movie_results,
)


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


def test_search_movie_candidates_returns_normalized_candidates(monkeypatch):
    fake_results = [
        {
            "id": 438631,
            "title": "Dune",
            "original_title": "Dune",
            "release_date": "2021-09-15",
            "vote_average": 7.8,
            "vote_count": 13000,
            "poster_path": "/dune_poster.jpg",
        }
    ]

    def fake_search_movies(title, year=None):
        return fake_results

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.search_movies",
        fake_search_movies,
    )

    candidates = search_movie_candidates("Dune", year=2021)

    assert len(candidates) == 1
    assert isinstance(candidates[0], MovieCandidate)
    assert candidates[0].tmdb_id == 438631
    assert candidates[0].title == "Dune"
    assert candidates[0].year == 2021
    assert candidates[0].poster_url == "https://image.tmdb.org/t/p/w500/dune_poster.jpg"


def test_search_movie_candidates_respects_limit(monkeypatch):
    fake_results = [
        {"id": 1, "title": "Dune"},
        {"id": 2, "title": "Dune"},
        {"id": 3, "title": "Dune"},
    ]

    def fake_search_movies(title, year=None):
        return fake_results

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.search_movies",
        fake_search_movies,
    )

    candidates = search_movie_candidates("Dune", limit=2)

    assert len(candidates) == 2
    assert [candidate.tmdb_id for candidate in candidates] == [1, 2]


def test_search_movie_candidates_empty_title_raises_error():
    with pytest.raises(ValueError):
        search_movie_candidates("   ")


def test_get_movie_by_title_returns_movie_object(monkeypatch):
    """
    Comprueba que get_movie_by_title:
    1. busca la película,
    2. toma el primer resultado,
    3. pide detalles completos,
    4. devuelve un objeto Movie normalizado.
    """

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

    def fake_search_movie_candidates(title, year=None, limit=5):
        assert title == "Dune"
        assert year == 2021
        assert limit == 1
        return [
            MovieCandidate(
                tmdb_id=438631,
                title="Dune",
                original_title="Dune",
                year=2021,
                release_date="2021-09-15",
                vote_average=7.8,
                vote_count=13000,
                poster_url=None,
            )
        ]

    def fake_get_movie_full_details(movie_id, language=None):
        return fake_full_details

    monkeypatch.setattr(
        "app.movie_service.search_movie_candidates",
        fake_search_movie_candidates,
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

    def fake_search_movie_candidates(title, year=None, limit=5):
        return []

    monkeypatch.setattr(
        "app.movie_service.search_movie_candidates",
        fake_search_movie_candidates,
    )

    movie = get_movie_by_title("Película que no existe")

    assert movie is None


def test_recommend_movies_with_year_uses_discover_and_filters(monkeypatch):
    def fake_discover_movies(
        year=None,
        genre_id=None,
        min_votes=None,
        page=1,
        language=None,
        region=None,
        sort_by="vote_average.desc",
    ):
        assert year == 2020
        assert genre_id == 878
        assert min_votes == 100
        return [
            {"id": 1},
            {"id": 2},
        ]

    def fake_get_movie_by_id(movie_id):
        movies = {
            1: Movie(
                tmdb_id=1,
                imdb_id=None,
                title="Ciencia futura",
                original_title="Future Science",
                year=2020,
                release_date="2020-05-01",
                vote_average=7.8,
                vote_count=1200,
                overview="Una historia de ciencia ficción.",
                overview_language="es-ES",
                director="Directora Uno",
                runtime=110,
                genres=["Ciencia ficción"],
                poster_url=None,
            ),
            2: Movie(
                tmdb_id=2,
                imdb_id=None,
                title="Drama 2020",
                original_title="Drama 2020",
                year=2020,
                release_date="2020-06-01",
                vote_average=8.1,
                vote_count=2000,
                overview="Un drama.",
                overview_language="es-ES",
                director="Director Dos",
                runtime=100,
                genres=["Drama"],
                poster_url=None,
            ),
        }
        return movies[movie_id]

    monkeypatch.setattr(
        "app.movie_service.tmdb_client.discover_movies",
        fake_discover_movies,
    )
    monkeypatch.setattr(
        "app.movie_service.get_movie_by_id",
        fake_get_movie_by_id,
    )

    movies = recommend_now_playing_movies(
        genre="ciencia ficción",
        year=2020,
        limit=5,
    )

    assert len(movies) == 1
    assert movies[0].title == "Ciencia futura"
    assert movies[0].year == 2020
