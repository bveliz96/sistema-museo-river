import argparse

from waitress import serve

from rutas_sistema import (
    ARCHIVO_DATABASE,
    crear_carpetas_sistema
)

from database.init_db import (
    inicializar_base_datos
)

from database.backup_db import (
    crear_backup
)


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
    # CREAR CARPETAS DEL SISTEMA
    # --------------------------------

    crear_carpetas_sistema()


    # --------------------------------
    # COMPROBAR SI YA EXISTÍA LA BASE
    # --------------------------------

    base_existia = (
        ARCHIVO_DATABASE.exists()
    )


    # --------------------------------
    # INICIALIZAR BASE DE DATOS
    # --------------------------------

    inicializar_base_datos()


    # --------------------------------
    # BACKUP AUTOMÁTICO
    # --------------------------------

    # En la primera ejecución no hacemos
    # backup porque la base acaba de ser
    # creada y todavía está vacía.

    if base_existia:

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
    # CARGAR APLICACIÓN
    # --------------------------------

    # Lo importamos después de haber
    # inicializado la base de datos.

    from app import app


    # --------------------------------
    # INICIAR SERVIDOR
    # --------------------------------

    print(
        "------------------------------------------"
    )

    print(
        "Sistema Museo iniciado correctamente"
    )

    print(
        f"Puerto: {puerto}"
    )

    print(
        f"Abrir localmente: "
        f"http://127.0.0.1:{puerto}"
    )

    print(
        "------------------------------------------"
    )


    serve(
        app,
        host="0.0.0.0",
        port=puerto,
        threads=4
    )


if __name__ == "__main__":

    iniciar_servidor()