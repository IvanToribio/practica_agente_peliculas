# app/web/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.web.routes import router
from app.web.web_config import STATIC_DIR


# ============================================================
# Instancia principal de FastAPI
# ============================================================

app = FastAPI(
    title="Movie Project",
    description="Web para consultar información y recomendaciones de películas usando TMDB.",
    version="1.0.0",
)


# ============================================================
# Configuración de archivos estáticos
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ============================================================
# Inclusión de rutas
# ============================================================

app.include_router(router)


# ============================================================
# Ruta simple de comprobación
# ============================================================

@app.get("/health")
def health_check() -> dict:
    """
    Ruta sencilla para comprobar que la aplicación web está funcionando.
    """
    return {"status": "ok"}