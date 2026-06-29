import pytest

pytest.importorskip(
    "httpx2",
    reason="fastapi.testclient necesita httpx2 en esta version de Starlette.",
)

from fastapi.testclient import TestClient

from app.movie_service import Movie, MovieCandidate
from app.web.main import app


client = TestClient(app)


def create_sample_movie() -> Movie:
    return Movie(
        tmdb_id=438631,
        imdb_id="tt1160419",
        title="Dune",
        original_title="Dune",
        year=2021,
        release_date="2021-09-15",
        vote_average=7.8,
        vote_count=13000,
        overview="Arrakis, tambien denominado Dune, es un planeta clave.",
        overview_language="es-ES",
        director="Denis Villeneuve",
        runtime=155,
        genres=["Ciencia ficcion", "Aventura"],
        poster_url="https://image.tmdb.org/t/p/w500/dune_poster.jpg",
    )


def create_sample_candidate() -> MovieCandidate:
    return MovieCandidate(
        tmdb_id=438631,
        title="Dune",
        original_title="Dune",
        year=2021,
        release_date="2021-09-15",
        vote_average=7.8,
        vote_count=13000,
        poster_url="https://image.tmdb.org/t/p/w500/dune_poster.jpg",
    )


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_renders_search_form():
    response = client.get("/")

    assert response.status_code == 200
    assert "FilmTail" in response.text
    assert "Practica de Sistemas Inteligentes: Ivan Toribio" in response.text
    assert 'name="title"' in response.text
    assert 'name="year"' not in response.text
    assert 'action="/search"' in response.text
    assert "chatbot.js" in response.text
    assert 'data-chatbot-form' in response.text


def test_search_empty_title_renders_form_error():
    response = client.get("/search", params={"title": "   "})

    assert response.status_code == 200
    assert "Introduce un título para buscar una película." in response.text
    assert 'name="title"' in response.text


def test_search_found_candidates_renders_results(monkeypatch):
    def fake_search_movie_candidates(title, year=None):
        assert title == "Dune"
        assert year == 2021
        return [create_sample_candidate()]

    monkeypatch.setattr(
        "app.web.routes.search_movie_candidates",
        fake_search_movie_candidates,
    )

    response = client.get("/search", params={"title": " Dune ", "year": 2021})

    assert response.status_code == 200
    assert "Resultados para" in response.text
    assert "Dune" in response.text
    assert "7.8/10" in response.text
    assert "Ver detalles" in response.text
    assert "/movie/438631" in response.text


def test_search_empty_year_is_treated_as_optional(monkeypatch):
    def fake_search_movie_candidates(title, year=None):
        assert title == "Dune"
        assert year is None
        return [create_sample_candidate()]

    monkeypatch.setattr(
        "app.web.routes.search_movie_candidates",
        fake_search_movie_candidates,
    )

    response = client.get("/search", params={"title": "Dune", "year": ""})

    assert response.status_code == 200
    assert "Dune" in response.text


def test_search_not_found_renders_not_found(monkeypatch):
    def fake_search_movie_candidates(title, year=None):
        return []

    monkeypatch.setattr(
        "app.web.routes.search_movie_candidates",
        fake_search_movie_candidates,
    )

    response = client.get("/search", params={"title": "No existe"})

    assert response.status_code == 404
    assert "No se ha encontrado la pelicula" in response.text
    assert "No existe" in response.text


def test_movie_detail_by_id_renders_detail(monkeypatch):
    def fake_get_movie_by_id(tmdb_id):
        assert tmdb_id == 438631
        return create_sample_movie()

    monkeypatch.setattr(
        "app.web.routes.get_movie_by_id",
        fake_get_movie_by_id,
    )

    response = client.get("/movie/438631")

    assert response.status_code == 200
    assert "Ficha de pelicula" in response.text
    assert "Dune" in response.text
    assert "Poster de Dune" in response.text
