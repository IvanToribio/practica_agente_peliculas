from app.llm_service import _validate_intent_data


def test_validate_intent_data_coerces_numeric_strings():
    data = _validate_intent_data(
        {
            "intent": "recommend_movie",
            "title": None,
            "field": None,
            "year": "2020",
            "genre": "ciencia ficción",
            "min_rating": "7.5",
        }
    )

    assert data["year"] == 2020
    assert data["min_rating"] == 7.5
