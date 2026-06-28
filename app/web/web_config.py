# app/web/web_config.py

from pathlib import Path

from fastapi.templating import Jinja2Templates


# Carpeta base de la parte web
WEB_DIR = Path(__file__).resolve().parent

# Carpetas de templates y archivos estáticos
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Objeto de plantillas Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))