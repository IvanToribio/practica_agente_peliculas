# tests/test_formatters.py

from app.movie_service import Movie
from app.formatters import (
    format_movie_for_telegram,
    format_movie_for_alexa,
    format_movie_for_web,
    format_movie_list_for_telegram,
    format_movie_list_for_alexa,
    format_movie_list_for_web,
    format_recommendations_for_telegram,
    format_recommendations_for_alexa,
    format_recommendations_for_web,
    format_not_found_for_telegram,
    format_not_found_for_alexa,
)


def create_sample_movie() -> Movie:
    """
    Crea una película completa de ejemplo para probar los formatters.

    No llamamos a TMDB porque estos tests solo prueban presentación,
    no integración con la API.
    """
    return Movie(
        tmdb_id=438631,
        imdb_id="tt1160419",
        title="Dune",
        original_title="Dune",
        year=2021,
        release_date="2021-09-15",
        vote_average=7.8,
        vote_count=13000,
        overview="Arrakis, también denominado Dune, es el planeta más importante del universo.",
        overview_language="es-ES",
        director="Denis Villeneuve",
        runtime=155,
        genres=["Ciencia ficción", "Aventura"],
        poster_url="https://image.tmdb.org/t/p/w500/dune_poster.jpg",
    )


def create_movie_with_missing_fields() -> Movie:
    """
    Crea una película con campos vacíos para comprobar
    que se muestra 'No disponible' correctamente.
    """
    return Movie(
        tmdb_id=123,
        imdb_id=None,
        title="Película incompleta",
        original_title=None,
        year=None,
        release_date=None,
        vote_average=None,
        vote_count=None,
        overview=None,
        overview_language=None,
        director=None,
        runtime=None,
        genres=[],
        poster_url=None,
    )


def test_format_movie_for_telegram_contains_main_fields():
    movie = create_sample_movie()

    message = format_movie_for_telegram(movie)

    assert isinstance(message, str)

    assert "🎬 Dune (2021)" in message
    assert "⭐ Nota: 7.8/10" in message
    assert "🗳️ Votos: 13.000" in message
    assert "🎥 Director: Denis Villeneuve" in message
    assert "⏱️ Duración: 155 min" in message
    assert "🎭 Géneros: Ciencia ficción, Aventura" in message
    assert "📝 Sinopsis:" in message
    assert "Arrakis" in message
    assert "🖼️ Póster: https://image.tmdb.org/t/p/w500/dune_poster.jpg" in message
    assert "🔗 IMDb: https://www.imdb.com/title/tt1160419/" in message


def test_format_movie_for_alexa_is_brief_and_natural():
    movie = create_sample_movie()

    message = format_movie_for_alexa(movie)

    assert isinstance(message, str)

    assert "Dune" in message
    assert "Denis Villeneuve" in message
    assert "2021" in message
    assert "7.8 sobre 10" in message
    assert "155 minutos" in message

    # Alexa no debería leer enlaces ni IDs técnicos.
    assert "IMDb" not in message
    assert "tt1160419" not in message
    assert "https://" not in message
    assert "438631" not in message


def test_format_movie_for_web_returns_complete_dict():
    movie = create_sample_movie()

    data = format_movie_for_web(movie)

    assert isinstance(data, dict)

    assert data["title"] == "Dune"
    assert data["original_title"] == "Dune"
    assert data["year"] == 2021
    assert data["year_label"] == "2021"
    assert data["release_date"] == "2021-09-15"
    assert data["vote_average"] == 7.8
    assert data["vote_average_label"] == "7.8/10"
    assert data["vote_count"] == 13000
    assert data["vote_count_label"] == "13.000"
    assert data["director"] == "Denis Villeneuve"
    assert data["runtime"] == 155
    assert data["runtime_label"] == "155 min"
    assert data["genres"] == ["Ciencia ficción", "Aventura"]
    assert data["genres_label"] == "Ciencia ficción, Aventura"
    assert "Arrakis" in data["overview"]
    assert data["overview_language"] == "es-ES"
    assert data["poster_url"] == "https://image.tmdb.org/t/p/w500/dune_poster.jpg"
    assert data["tmdb_id"] == 438631
    assert data["imdb_id"] == "tt1160419"
    assert data["imdb_url"] == "https://www.imdb.com/title/tt1160419/"


def test_formatters_handle_missing_fields_gracefully():
    movie = create_movie_with_missing_fields()

    telegram_message = format_movie_for_telegram(movie)
    alexa_message = format_movie_for_alexa(movie)
    web_data = format_movie_for_web(movie)

    assert "No disponible" in telegram_message
    assert "No tengo disponible su nota ni su duración." in alexa_message

    assert web_data["original_title"] == "No disponible"
    assert web_data["year_label"] == "No disponible"
    assert web_data["release_date"] == "No disponible"
    assert web_data["vote_average_label"] == "No disponible"
    assert web_data["vote_count_label"] == "No disponible"
    assert web_data["director"] == "No disponible"
    assert web_data["runtime_label"] == "No disponible"
    assert web_data["genres"] == []
    assert web_data["genres_label"] == "No disponible"
    assert web_data["overview"] == "No disponible"
    assert web_data["overview_language"] == "No disponible"
    assert web_data["poster_url"] is None
    assert web_data["imdb_id"] == "No disponible"
    assert web_data["imdb_url"] is None


def test_format_movie_with_english_overview_adds_note_in_telegram():
    movie = Movie(
        tmdb_id=438631,
        imdb_id="tt1160419",
        title="Dune",
        original_title="Dune",
        year=2021,
        release_date="2021-09-15",
        vote_average=7.8,
        vote_count=13000,
        overview="English overview fallback.",
        overview_language="en-US",
        director="Denis Villeneuve",
        runtime=155,
        genres=["Science Fiction"],
        poster_url=None,
    )

    message = format_movie_for_telegram(movie)

    assert "Sinopsis no disponible en español" in message
    assert "English overview fallback." in message


def test_format_movie_list_for_telegram():
    movies = [
        create_sample_movie(),
        Movie(
            tmdb_id=2,
            imdb_id=None,
            title="Interstellar",
            original_title="Interstellar",
            year=2014,
            release_date="2014-11-07",
            vote_average=8.4,
            vote_count=20000,
            overview="Una película sobre viajes espaciales.",
            overview_language="es-ES",
            director="Christopher Nolan",
            runtime=169,
            genres=["Ciencia ficción", "Drama"],
            poster_url=None,
        ),
    ]

    message = format_movie_list_for_telegram(movies)

    assert isinstance(message, str)

    assert "🎬 Películas encontradas" in message
    assert "1. 🎬 Dune (2021) — ⭐ 7.8/10" in message
    assert "2. 🎬 Interstellar (2014) — ⭐ 8.4/10" in message
    assert "Denis Villeneuve" in message
    assert "Christopher Nolan" in message


def test_format_movie_list_for_telegram_when_empty():
    message = format_movie_list_for_telegram([])

    assert message == "No se han encontrado películas."


def test_format_movie_list_for_alexa():
    movies = [
        create_sample_movie(),
        Movie(
            tmdb_id=2,
            imdb_id=None,
            title="Interstellar",
            original_title="Interstellar",
            year=2014,
            release_date="2014-11-07",
            vote_average=8.4,
            vote_count=20000,
            overview="Una película sobre viajes espaciales.",
            overview_language="es-ES",
            director="Christopher Nolan",
            runtime=169,
            genres=["Ciencia ficción", "Drama"],
            poster_url=None,
        ),
        Movie(
            tmdb_id=3,
            imdb_id=None,
            title="Oppenheimer",
            original_title="Oppenheimer",
            year=2023,
            release_date="2023-07-21",
            vote_average=8.1,
            vote_count=15000,
            overview="Película biográfica.",
            overview_language="es-ES",
            director="Christopher Nolan",
            runtime=180,
            genres=["Drama", "Historia"],
            poster_url=None,
        ),
    ]

    message = format_movie_list_for_alexa(movies)

    assert isinstance(message, str)

    assert message == (
        "Te recomiendo Dune (2021), Interstellar (2014) "
        "y Oppenheimer (2023)."
    )


def test_format_movie_list_for_alexa_when_empty():
    message = format_movie_list_for_alexa([])

    assert message == "No he encontrado películas disponibles."


def test_format_movie_list_for_web():
    movies = [create_sample_movie()]

    data = format_movie_list_for_web(movies)

    assert isinstance(data, list)
    assert len(data) == 1
    assert isinstance(data[0], dict)
    assert data[0]["title"] == "Dune"
    assert data[0]["year"] == 2021
    assert data[0]["imdb_url"] == "https://www.imdb.com/title/tt1160419/"


def test_format_recommendations_for_telegram():
    movies = [create_sample_movie()]

    message = format_recommendations_for_telegram(movies)

    assert "🍿 Recomendaciones de películas" in message
    assert "Dune (2021)" in message


def test_format_recommendations_for_alexa():
    movies = [create_sample_movie()]

    message = format_recommendations_for_alexa(movies)

    assert message == "Te recomiendo Dune (2021)."


def test_format_recommendations_for_alexa_when_empty():
    message = format_recommendations_for_alexa([])

    assert message == "Ahora mismo no tengo recomendaciones disponibles."


def test_format_recommendations_for_web():
    movies = [create_sample_movie()]

    data = format_recommendations_for_web(movies)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Dune"


def test_format_not_found_for_telegram():
    message = format_not_found_for_telegram("Dune falsa")

    assert "❌" in message
    assert "Dune falsa" in message
    assert "Prueba con otro título" in message


def test_format_not_found_for_alexa():
    message = format_not_found_for_alexa("Dune falsa")

    assert "No he encontrado ninguna película llamada Dune falsa" in message
    assert "Prueba con otro título" in message