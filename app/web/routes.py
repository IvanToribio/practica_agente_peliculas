# app/web/routes.py

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.formatters import format_movie_for_web
from app.movie_service import (
    MovieServiceError,
    get_movie_by_id,
    get_movie_by_title,
)
from app.web.web_config import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Página inicial de la web.

    Muestra:
    - título de la aplicación
    - formulario de búsqueda de películas
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "page_title": "Buscador de películas",
            "error": None,
            "last_search": "",
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search_movie(
    request: Request,
    title: str = Query(default="", description="Título de la película a buscar"),
    year: int | None = Query(default=None, description="Año opcional de estreno"),
):
    """
    Busca una película por título.

    Flujo:
    1. Recibe el título desde el formulario.
    2. Valida que no esté vacío.
    3. Llama a movie_service.get_movie_by_title().
    4. Si no encuentra película, renderiza not_found.html.
    5. Si encuentra película, la formatea para web.
    6. Renderiza movie_detail.html.

    Importante:
    Esta ruta NO llama directamente a tmdb_client.py.
    """
    clean_title = title.strip()

    if not clean_title:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "page_title": "Buscador de películas",
                "error": "Introduce un título para buscar una película.",
                "last_search": title,
            },
        )

    try:
        movie = get_movie_by_title(title=clean_title, year=year)

    except MovieServiceError:
        return templates.TemplateResponse(
            "not_found.html",
            {
                "request": request,
                "page_title": "Error al buscar película",
                "searched_title": clean_title,
                "message": (
                    "Ha ocurrido un problema al consultar la información de la película. "
                    "Prueba de nuevo más tarde."
                ),
            },
            status_code=500,
        )

    if movie is None:
        return templates.TemplateResponse(
            "not_found.html",
            {
                "request": request,
                "page_title": "Película no encontrada",
                "searched_title": clean_title,
                "message": (
                    f"No he encontrado ninguna película con el título "
                    f"'{clean_title}'. Prueba con otro título o añade el año."
                ),
            },
            status_code=404,
        )

    movie_data = format_movie_for_web(movie)

    return templates.TemplateResponse(
        "movie_detail.html",
        {
            "request": request,
            "page_title": movie_data["title"],
            "movie": movie_data,
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
            "not_found.html",
            {
                "request": request,
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
        "movie_detail.html",
        {
            "request": request,
            "page_title": movie_data["title"],
            "movie": movie_data,
        },
    )


@router.get("/back", response_class=HTMLResponse)
def back_to_home():
    """
    Redirección simple a la página inicial.

    No es imprescindible, pero puede ser útil para botones internos.
    """
    return RedirectResponse(url="/")