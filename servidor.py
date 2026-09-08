import argparse

from waitress import serve

from app import app
from database.backup_db import crear_backup


def leer_argumentos():

    parser = argparse.ArgumentParser(
        description="Servidor del Sistema Museo River"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Puerto en el que funcionará el servidor"
    )

    return parser.parse_args()


def iniciar_servidor():

    argumentos = leer_argumentos()
    puerto = argumentos.port


    # --------------------------------
    # VALIDAR PUERTO
    # --------------------------------

    if puerto < 1024 or puerto > 65535:

        raise ValueError(
            "El puerto debe estar entre 1024 y 65535."
        )


    # --------------------------------
    # BACKUP AUTOMÁTICO
    # --------------------------------

    try:

        ruta_backup = crear_backup()

        print(
            "Backup automático creado correctamente."
        )

        if ruta_backup:

            print(
                f"Backup: {ruta_backup}"
            )


    except Exception as error:

        print(
            "No se pudo crear el backup automático."
        )

        print(
            f"Error: {error}"
        )


    # --------------------------------
    # INICIAR SERVIDOR
    # --------------------------------

    print("------------------------------------------")
    print("Sistema Museo iniciado correctamente")
    print(f"Puerto: {puerto}")
    print(f"Abrir: http://127.0.0.1:{puerto}")
    print("------------------------------------------")


    serve(
        app,
        host="0.0.0.0",
        port=puerto,
        threads=4
    )


if __name__ == "__main__":

    iniciar_servidor()