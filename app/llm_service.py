# app/llm_service.py

import json
import os
import re
from typing import Any

import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:latest")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
REQUEST_TIMEOUT = 100


class LLMServiceError(Exception):
    """
    Error general de la capa de conexión con el LLM.
    """
    pass


# ============================================================
# Esquema de intención del chatbot
# ============================================================

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "search_movie",
                "movie_field",
                "movie_summary",
                "recommend_movie",
                "unknown",
            ],
        },
        "title": {
            "type": ["string", "null"],
            "description": "Título de la película si aparece en el mensaje.",
        },
        "field": {
            "type": ["string", "null"],
            "enum": [
                "director",
                "runtime",
                "vote_average",
                "vote_count",
                "overview",
                "genres",
                "release_date",
                "year",
                "original_title",
                None,
            ],
            "description": "Campo concreto solicitado si la intención es movie_field.",
        },
        "year": {
            "type": ["integer", "null"],
            "description": "Año de estreno si el usuario lo especifica.",
        },
        "genre": {
            "type": ["string", "null"],
            "description": "Género solicitado si pide recomendaciones.",
        },
        "min_rating": {
            "type": ["number", "null"],
            "description": "Nota mínima solicitada si aparece en el mensaje.",
        },
    },
    "required": [
        "intent",
        "title",
        "field",
        "year",
        "genre",
        "min_rating",
    ],
}


# ============================================================
# Funciones internas de conexión con Ollama
# ============================================================

def _call_ollama_chat(
    messages: list[dict[str, str]],
    format_schema: dict | None = None,
    temperature: float = 0.1,
) -> str:
    """
    Llama al endpoint /api/chat de Ollama.

    messages:
        Lista de mensajes con role/content.

    format_schema:
        Si se proporciona, se pide a Ollama que devuelva una salida
        estructurada según ese esquema JSON.

    temperature:
        Temperatura baja para reducir respuestas impredecibles.
    """
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    if format_schema is not None:
        payload["format"] = format_schema

    try:
        response = requests.post(
            OLLAMA_CHAT_ENDPOINT,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    except requests.exceptions.ConnectionError as error:
        raise LLMServiceError(
            "No se ha podido conectar con Ollama. "
            "Comprueba que Ollama está abierto y que el modelo está disponible."
        ) from error

    except requests.exceptions.Timeout as error:
        raise LLMServiceError(
            "La llamada al modelo ha tardado demasiado."
        ) from error

    except requests.exceptions.HTTPError as error:
        status_code = error.response.status_code if error.response else "unknown"
        raise LLMServiceError(
            f"Error HTTP al llamar a Ollama. Status code: {status_code}."
        ) from error

    except requests.exceptions.RequestException as error:
        raise LLMServiceError(
            f"Error inesperado al llamar a Ollama: {error}"
        ) from error

    try:
        data = response.json()
    except ValueError as error:
        raise LLMServiceError(
            "La respuesta de Ollama no es JSON válido."
        ) from error

    try:
        return data["message"]["content"]
    except KeyError as error:
        raise LLMServiceError(
            "La respuesta de Ollama no tiene el formato esperado."
        ) from error


def _extract_json_from_text(text: str) -> dict:
    """
    Extrae un JSON de una respuesta de texto.

    Aunque se pida JSON estructurado, algunos modelos pueden devolver
    texto adicional. Esta función intenta recuperar el primer bloque JSON.
    """
    clean_text = text.strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # Fallback: buscar el primer objeto JSON dentro del texto
    match = re.search(r"\{.*\}", clean_text, re.DOTALL)

    if not match:
        raise LLMServiceError(
            f"No se ha encontrado JSON válido en la respuesta del modelo: {text}"
        )

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as error:
        raise LLMServiceError(
            f"El modelo devolvió un JSON mal formado: {match.group(0)}"
        ) from error


def _validate_intent_data(data: dict) -> dict:
    """
    Valida de forma sencilla que el JSON de intención tenga las claves esperadas.

    No usamos Pydantic aquí para mantener el archivo simple.
    """
    allowed_intents = {
        "search_movie",
        "movie_field",
        "movie_summary",
        "recommend_movie",
        "unknown",
    }

    allowed_fields = {
        "director",
        "runtime",
        "vote_average",
        "vote_count",
        "overview",
        "genres",
        "release_date",
        "year",
        "original_title",
        None,
    }

    intent = data.get("intent")

    if intent not in allowed_intents:
        data["intent"] = "unknown"

    field = data.get("field")

    if field not in allowed_fields:
        data["field"] = None

    year = data.get("year")

    if isinstance(year, str):
        try:
            data["year"] = int(year)
        except ValueError:
            data["year"] = None

    min_rating = data.get("min_rating")

    if isinstance(min_rating, str):
        try:
            data["min_rating"] = float(min_rating)
        except ValueError:
            data["min_rating"] = None

    # Aseguramos que todas las claves existan.
    return {
        "intent": data.get("intent", "unknown"),
        "title": data.get("title"),
        "field": data.get("field"),
        "year": data.get("year"),
        "genre": data.get("genre"),
        "min_rating": data.get("min_rating"),
    }


# ============================================================
# Función pública: interpretar intención
# ============================================================

def interpret_user_intent(user_message: str) -> dict:
    """
    Interpreta la intención del usuario y devuelve un diccionario estructurado.

    Esta función NO busca películas.
    Solo convierte lenguaje natural en una intención usable por chatbot_service.py.

    Ejemplos de salida:

    {
        "intent": "movie_field",
        "title": "Dune",
        "field": "director",
        "year": null,
        "genre": null,
        "min_rating": null
    }

    {
        "intent": "recommend_movie",
        "title": null,
        "field": null,
        "year": null,
        "genre": "ciencia ficción",
        "min_rating": 7
    }
    """
    if not user_message or not user_message.strip():
        return {
            "intent": "unknown",
            "title": None,
            "field": None,
            "year": None,
            "genre": None,
            "min_rating": None,
        }

    system_prompt = """
Eres un clasificador de intención para una aplicación de películas.

Tu tarea es leer el mensaje del usuario y devolver SOLO JSON válido.
No respondas en lenguaje natural.
No inventes datos de películas.
No incluyas explicaciones.
No uses Markdown.

Intenciones disponibles:

1. search_movie
Usar cuando el usuario quiere buscar una película o pide información general sin campo concreto.
Ejemplos:
- "Busca Dune"
- "Quiero información sobre Interstellar"
- "Háblame de Oppenheimer"

2. movie_field
Usar cuando el usuario pregunta por un campo concreto de una película.
Campos permitidos:
- director
- runtime
- vote_average
- vote_count
- overview
- genres
- release_date
- year
- original_title

Ejemplos:
- "¿Quién dirigió Dune?" -> field = "director"
- "¿Cuánto dura Dune?" -> field = "runtime"
- "¿Qué nota tiene Dune?" -> field = "vote_average"
- "¿De qué va Dune?" -> field = "overview"
- "¿Qué géneros tiene Dune?" -> field = "genres"
- "¿Cuándo se estrenó Dune?" -> field = "release_date"

3. movie_summary
Usar cuando el usuario quiere una explicación/resumen de una película concreta.
Ejemplos:
- "Resume Dune"
- "Explícame de qué trata Interstellar"

4. recommend_movie
Usar cuando el usuario pide recomendaciones.
Ejemplos:
- "Recomiéndame una película"
- "Recomiéndame ciencia ficción"
- "Quiero una película con nota mayor de 7"

5. unknown
Usar cuando no se puede entender la intención o no tiene relación con películas.

Devuelve siempre estas claves:
{
  "intent": "...",
  "title": "... o null",
  "field": "... o null",
  "year": 2021 o null,
  "genre": "... o null",
  "min_rating": 7.0 o null
}
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_message.strip(),
        },
    ]

    raw_response = _call_ollama_chat(
        messages=messages,
        format_schema=INTENT_SCHEMA,
        temperature=0.0,
    )

    data = _extract_json_from_text(raw_response)

    return _validate_intent_data(data)


# ============================================================
# Función pública: redactar respuesta natural
# ============================================================

def generate_natural_response(
    user_message: str,
    intent_data: dict,
    factual_data: dict | str,
) -> str:
    """
    Redacta una respuesta natural usando datos reales ya obtenidos.

    Importante:
    factual_data debe venir de movie_service.py o de una lógica controlada.
    El modelo puede redactar, pero no debe inventar datos nuevos.

    Esta función se usará desde chatbot_service.py después de consultar
    los datos reales de la película.
    """
    system_prompt = """
Eres un asistente de películas integrado en una web y en Telegram.

Tu tarea es redactar una respuesta breve, clara y natural en español.

Reglas obligatorias:
- Usa solo los datos proporcionados en "datos_reales".
- No inventes director, duración, nota, sinopsis, géneros ni fechas.
- Si un dato aparece como null, None o "No disponible", di que no está disponible.
- No menciones TMDB salvo que sea necesario.
- No expliques el proceso interno.
- No devuelvas JSON.
- Responde en 1 o 2 frases, salvo que el usuario pida una explicación más larga.
""".strip()

    user_prompt = f"""
Mensaje original del usuario:
{user_message}

Intención interpretada:
{json.dumps(intent_data, ensure_ascii=False)}

Datos reales:
{json.dumps(factual_data, ensure_ascii=False, default=str)}

Redacta la respuesta final para el usuario:
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    response = _call_ollama_chat(
        messages=messages,
        temperature=0.3,
    )

    return response.strip()


# ============================================================
# Prueba manual
# ============================================================

if __name__ == "__main__":
    question = "¿Quién dirigió Dune?"

    print("Pregunta:")
    print(question)

    print("\nIntención detectada:")
    intent = interpret_user_intent(question)
    print(intent)

    print("\nRespuesta natural de prueba:")
    answer = generate_natural_response(
        user_message=question,
        intent_data=intent,
        factual_data={
            "title": "Dune",
            "director": "Denis Villeneuve",
        },
    )
    print(answer)
