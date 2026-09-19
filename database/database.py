import sqlite3

from rutas_sistema import (
    ARCHIVO_DATABASE,
    crear_carpetas_sistema
)


def conectar():

    crear_carpetas_sistema()

    conexion = sqlite3.connect(
        ARCHIVO_DATABASE,
        timeout=10
    )

    conexion.row_factory = sqlite3.Row

    conexion.execute(
        "PRAGMA foreign_keys = ON"
    )

    conexion.execute(
        "PRAGMA busy_timeout = 10000"
    )

    return conexion