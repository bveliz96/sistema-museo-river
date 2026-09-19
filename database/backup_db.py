import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo

from rutas_sistema import (
    ARCHIVO_DATABASE,
    CARPETA_BACKUPS,
    crear_carpetas_sistema
)


def limpiar_backups(cantidad_maxima=30):

    if cantidad_maxima < 1:
        raise ValueError(
            "La cantidad máxima de backups "
            "debe ser mayor que cero."
        )

    CARPETA_BACKUPS.mkdir(
        parents=True,
        exist_ok=True
    )

    archivos = sorted(
        CARPETA_BACKUPS.glob(
            "database_*.db"
        ),
        key=lambda archivo: archivo.stat().st_mtime,
        reverse=True
    )

    archivos_antiguos = archivos[
        cantidad_maxima:
    ]

    for archivo in archivos_antiguos:

        try:
            archivo.unlink()

        except OSError as error:
            print(
                "No se pudo eliminar "
                f"{archivo.name}: {error}"
            )

    if archivos_antiguos:

        print(
            f"Se eliminaron "
            f"{len(archivos_antiguos)} "
            "backups antiguos."
        )


def crear_backup():

    crear_carpetas_sistema()

    if not ARCHIVO_DATABASE.exists():

        raise FileNotFoundError(
            "No se encontró la base de datos:\n"
            f"{ARCHIVO_DATABASE}"
        )

    fecha_hora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d_%H-%M-%S-%f"
    )

    archivo_destino = (
        CARPETA_BACKUPS
        / f"database_{fecha_hora}.db"
    )

    conexion_origen = None
    conexion_destino = None

    try:

        conexion_origen = sqlite3.connect(
            ARCHIVO_DATABASE,
            timeout=10
        )

        conexion_origen.execute(
            "PRAGMA busy_timeout = 10000"
        )

        conexion_destino = sqlite3.connect(
            archivo_destino,
            timeout=10
        )

        conexion_destino.execute(
            "PRAGMA busy_timeout = 10000"
        )

        conexion_origen.backup(
            conexion_destino
        )

        resultado_integridad = (
            conexion_destino.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
        )

        if resultado_integridad != "ok":

            raise RuntimeError(
                "El backup fue creado, pero no superó "
                "la comprobación de integridad."
            )

    except Exception:

        if archivo_destino.exists():

            try:
                archivo_destino.unlink()

            except OSError:
                pass

        raise

    finally:

        if conexion_destino is not None:
            conexion_destino.close()

        if conexion_origen is not None:
            conexion_origen.close()

    limpiar_backups(
        cantidad_maxima=30
    )

    print(
        "Backup creado correctamente:"
    )

    print(archivo_destino)

    return archivo_destino


if __name__ == "__main__":
    crear_backup()