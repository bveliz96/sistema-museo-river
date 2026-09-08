import os
import sys
import secrets
from pathlib import Path


NOMBRE_CARPETA_DATOS = "SistemaMuseoRiver"


def obtener_carpeta_programa():

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def obtener_carpeta_datos():

    # Mientras se ejecuta desde Python, conserva los datos
    # dentro de la carpeta actual del proyecto.
    if not getattr(sys, "frozen", False):
        return obtener_carpeta_programa()

    # Cuando se convierta en .exe, los datos permanentes
    # se guardarán en C:\ProgramData\SistemaMuseoRiver.
    programdata = os.environ.get("PROGRAMDATA")

    if programdata:
        return Path(programdata) / NOMBRE_CARPETA_DATOS

    return (
        Path.home()
        / "AppData"
        / "Local"
        / NOMBRE_CARPETA_DATOS
    )

def obtener_carpeta_recursos():

    return Path(__file__).resolve().parent

CARPETA_PROGRAMA = obtener_carpeta_programa()
CARPETA_DATOS = obtener_carpeta_datos()

CARPETA_DATABASE = CARPETA_DATOS / "database"
ARCHIVO_DATABASE = CARPETA_DATABASE / "database.db"

CARPETA_BACKUPS = CARPETA_DATOS / "backups"
CARPETA_LOGS = CARPETA_DATOS / "logs"
ARCHIVO_LOG_SERVIDOR = CARPETA_LOGS / "servidor.log"

CARPETA_CONFIGURACION = CARPETA_DATOS / "config"
ARCHIVO_CONFIGURACION_PANEL = (
    CARPETA_CONFIGURACION
    / "panel_servidor.json"
)
ARCHIVO_SECRET_KEY = (
    CARPETA_CONFIGURACION
    / "secret_key.txt"
)
CARPETA_RECURSOS = obtener_carpeta_recursos()

CARPETA_TEMPLATES = (
    CARPETA_RECURSOS
    / "templates"
)

CARPETA_STATIC = (
    CARPETA_RECURSOS
    / "static"
)

def crear_carpetas_sistema():

    carpetas = (
        CARPETA_DATABASE,
        CARPETA_BACKUPS,
        CARPETA_LOGS,
        CARPETA_CONFIGURACION
    )

    for carpeta in carpetas:
        carpeta.mkdir(
            parents=True,
            exist_ok=True
        )

def obtener_secret_key():

    # Durante el desarrollo permite seguir usando
    # la variable configurada en Windows.
    clave_entorno = os.environ.get(
        "SISTEMA_MUSEO_SECRET_KEY"
    )

    if clave_entorno:
        return clave_entorno

    crear_carpetas_sistema()

    if ARCHIVO_SECRET_KEY.exists():

        clave_guardada = (
            ARCHIVO_SECRET_KEY
            .read_text(encoding="utf-8")
            .strip()
        )

        if clave_guardada:
            return clave_guardada

    clave_nueva = secrets.token_hex(32)

    archivo_temporal = (
        ARCHIVO_SECRET_KEY
        .with_suffix(".tmp")
    )

    archivo_temporal.write_text(
        clave_nueva,
        encoding="utf-8"
    )

    archivo_temporal.replace(
        ARCHIVO_SECRET_KEY
    )

    return clave_nueva