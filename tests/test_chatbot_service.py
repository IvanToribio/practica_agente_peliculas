from app.movie_service import Movie
from app.chatbot_service import handle_chat_message


def test_recommendation_uses_year_from_message_when_llm_misses_it(monkeypatch):
    def fake_interpret_user_intent(user_message):
        return {
            "intent": "recommend_movie",
            "title": None,
            "field": None,
            "year": None,
            "genre": None,
            "min_rating": 7.0,
        }

    def fake_recommend_now_playing_movies(
        min_rating=7.0,
        min_votes=100,
        genre=None,
        year=None,
        limit=5,
    ):
        assert min_rating == 7.0
        assert genre == "ciencia ficción"
        assert year == 2020
        return [
            Movie(
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
            )
        ]

    def fake_generate_natural_response(user_message, intent_data, factual_data):
        assert factual_data["year"] == 2020
        assert factual_data["genre"] == "ciencia ficción"
        return "Te recomiendo Ciencia futura (2020)."

    monkeypatch.setattr(
        "app.chatbot_service.interpret_user_intent",
        fake_interpret_user_intent,
    )
    monkeypatch.setattr(
        "app.chatbot_service.recommend_now_playing_movies",
        fake_recommend_now_playing_movies,
    )
    monkeypatch.setattr(
        "app.chatbot_service.generate_natural_response",
        fake_generate_natural_response,
    )

    response = handle_chat_message(
        "Recomiéndame una película de ciencia ficción del año 2020"
    )

    assert response["intent"] == "recommend_movie"
    assert response["data"]["year"] == 2020
    assert response["data"]["genre"] == "ciencia ficción"
    assert "Ciencia futura" in response["answer"]
