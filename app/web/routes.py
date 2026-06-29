# app/web/routes.py

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.formatters import format_candidate_list_for_web, format_movie_for_web
from app.movie_service import (
    MovieServiceError,
    get_movie_by_id,
    search_movie_candidates,
)
from app.web.web_config import templates

from typing import Any

from pydantic import BaseModel

from app.chatbot_service import ChatbotServiceError, handle_chat_message


router = APIRouter()


# Rutas web

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Página inicial de la web.

    Muestra:
    - título de la aplicación
    - formulario de búsqueda de películas
    """
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "page_title": "Buscador de películas",
            "error": None,
            "last_search": "",
            "last_year": "",
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search_movie(
    request: Request,
    title: str = Query(default="", description="Título de la película a buscar"),
    year: str | None = Query(default=None, description="Año opcional de estreno"),
):
    """
    Busca una película por título.

    Flujo:
    1. Recibe el título desde el formulario.
    2. Valida que no esté vacío.
    3. Llama a movie_service.search_movie_candidates().
    4. Si no encuentra candidatos, renderiza not_found.html.
    5. Si encuentra candidatos, los formatea para web.
    6. Renderiza search_results.html.

    Importante:
    Esta ruta NO llama directamente a tmdb_client.py.
    """
    clean_title = title.strip()
    clean_year: int | None = None

    if year is not None and year.strip():
        try:
            clean_year = int(year)
        except ValueError:
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "page_title": "Buscador de películas",
                    "error": "Introduce un año válido o deja el campo vacío.",
                    "last_search": clean_title,
                    "last_year": year,
                },
            )

    if not clean_title:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "page_title": "Buscador de películas",
                "error": "Introduce un título para buscar una película.",
                "last_search": title,
                "last_year": year or "",
            },
        )

    try:
        candidates = search_movie_candidates(title=clean_title, year=clean_year)

    except ValueError as error:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "page_title": "Buscador de películas",
                "error": str(error),
                "last_search": clean_title,
                "last_year": year or "",
            },
        )

    except MovieServiceError:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {
                "page_title": "Error al buscar película",
                "searched_title": clean_title,
                "message": (
                    "Ha ocurrido un problema al consultar la información de la película. "
                    "Prueba de nuevo más tarde."
                ),
            },
            status_code=500,
        )

    if not candidates:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {
                "page_title": "Película no encontrada",
                "searched_title": clean_title,
                "message": (
                    f"No he encontrado ninguna película con el título "
                    f"'{clean_title}'. Prueba con otro título o añade el año."
                ),
            },
            status_code=404,
        )

    candidate_list = format_candidate_list_for_web(candidates)

    return templates.TemplateResponse(
        request,
        "search_results.html",
        {
            "page_title": f"Resultados para {clean_title}",
            "searched_title": clean_title,
            "searched_year": clean_year,
            "candidates": candidate_list,
        },
    )


@router.get("/movie/{tmdb_id}", response_class=HTMLResponse)
def movie_detail(
    request: Request,
    tmdb_id: int,
):
    """
    Muestra la ficha de una película a partir de su TMDB ID.

    Esta ruta será útil más adelante si:
    - muestras varias opciones de búsqueda;
    - quieres enlazar directamente a una película;
    - el chatbot devuelve un TMDB ID;
    - las recomendaciones muestran tarjetas clicables.
    """
    try:
        movie = get_movie_by_id(tmdb_id)

    except MovieServiceError:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {
                "page_title": "Película no encontrada",
                "searched_title": str(tmdb_id),
                "message": (
                    "No se ha podido obtener la información de esta película. "
                    "Prueba de nuevo más tarde."
                ),
            },
            status_code=404,
        )

    movie_data = format_movie_for_web(movie)

    return templates.TemplateResponse(
        request,
        "movie_detail.html",
        {
            "page_title": movie_data["title"],
            "movie": movie_data,
        },
    )


# Chatbot API endpoint

class ChatRequest(BaseModel):
    """
    Estructura del mensaje que envía el frontend al chatbot.
    """

    message: str


class ChatResponse(BaseModel):
    """
    Estructura de la respuesta que devuelve el chatbot al frontend.
    """

    answer: str
    intent: str
    data: Any | None = None
    error: str | None = None
    

@router.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(chat_request: ChatRequest):
    """
    Endpoint del chatbot web.

    Flujo:
    1. Recibe el mensaje del usuario desde el frontend.
    2. Llama a chatbot_service.handle_chat_message().
    3. Devuelve una respuesta JSON al frontend.

    Importante:
    Esta ruta NO llama directamente a TMDB.
    Esta ruta NO llama directamente a Ollama.
    La coordinación la hace chatbot_service.py.
    """
    message = chat_request.message.strip()

    if not message:
        return ChatResponse(
            answer="Escribe una pregunta sobre películas.",
            intent="unknown",
            data=None,
            error=None,
        )

    try:
        response = handle_chat_message(message)

    except ChatbotServiceError as error:
        return ChatResponse(
            answer="Ha ocurrido un problema al procesar tu mensaje.",
            intent="unknown",
            data=None,
            error=str(error),
        )

    return ChatResponse(
        answer=response.get("answer", "No he podido generar una respuesta."),
        intent=response.get("intent", "unknown"),
        data=response.get("data"),
        error=response.get("error"),
    )