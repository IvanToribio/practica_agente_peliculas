# app/config.py

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Ruta al archivo .env
ENV_PATH = BASE_DIR / ".env"

# Cargar variables de entorno desde .env
load_dotenv(ENV_PATH)


def get_required_env(name: str) -> str:
    """
    Obtiene una variable de entorno obligatoria.
    Si no existe, lanza un error claro.
    """
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Falta la variable de entorno obligatoria: {name}. "
            f"Revísala en el archivo .env"
        )

    return value


def get_optional_env(name: str, default: str) -> str:
    """
    Obtiene una variable de entorno opcional.
    Si no existe, devuelve un valor por defecto.
    """
    value = os.getenv(name)
    return value if value else default


@dataclass(frozen=True)
class Settings:
    """
    Configuración global del proyecto.

    Este objeto centraliza las claves, URLs y valores por defecto
    que usará el resto de la aplicación.
    """

    # TMDB
    tmdb_bearer_token: str
    tmdb_base_url: str

    # Configuración por defecto de TMDB
    default_language: str
    default_region: str

    # Telegram
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


settings = Settings(
    tmdb_bearer_token=get_required_env("TMDB_BEARER_TOKEN"),
    tmdb_base_url=get_optional_env("TMDB_BASE_URL", "https://api.themoviedb.org/3"),
    default_language=get_optional_env("DEFAULT_LANGUAGE", "es-ES"),
    default_region=get_optional_env("DEFAULT_REGION", "ES"),
    telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
)
