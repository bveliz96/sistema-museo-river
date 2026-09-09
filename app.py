import json
import os
from database.init_db import inicializar_base_datos
from rutas_sistema import (
    CARPETA_TEMPLATES,
    CARPETA_STATIC,
    obtener_secret_key
)

from flask import (
    Flask,
    render_template,
    redirect,
    request,
    url_for,
    send_file,
    session,
    flash
)

from flask_wtf.csrf import CSRFProtect

from database.database import conectar

from openpyxl import Workbook

from io import BytesIO

from datetime import datetime

from zoneinfo import ZoneInfo

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from functools import wraps


app = Flask(
    __name__,
    template_folder=str(
        CARPETA_TEMPLATES
    ),
    static_folder=str(
        CARPETA_STATIC
    )
)

app.config["SECRET_KEY"] = (
    obtener_secret_key()
)

csrf = CSRFProtect(app)

inicializar_base_datos()

def texto_mayusculas(valor):
    return (valor or "").strip().upper()

def obtener_usuario_actual():

    usuario_id = session.get("usuario_id")

    if not usuario_id:
        return None

    conexion = conectar()

    usuario = conexion.execute("""
        SELECT
            id,
            nombre,
            usuario,
            rol,
            estado
        FROM usuarios
        WHERE id = ?
    """, (usuario_id,)).fetchone()

    conexion.close()

    if usuario is None or usuario["estado"] != "ACTIVO":
        session.clear()
        return None

    # Actualiza los datos de sesión por si el administrador
    # modificó el nombre o rol del usuario.
    session["usuario_nombre"] = usuario["nombre"]
    session["usuario_rol"] = usuario["rol"]

    return usuario


def login_required(funcion):

    @wraps(funcion)
    def funcion_protegida(*args, **kwargs):

        usuario = obtener_usuario_actual()

        if usuario is None:
            return redirect(url_for("login"))

        return funcion(*args, **kwargs)

    return funcion_protegida


def admin_required(funcion):

    @wraps(funcion)
    def funcion_protegida(*args, **kwargs):

        usuario = obtener_usuario_actual()

        if usuario is None:
            return redirect(url_for("login"))

        if usuario["rol"] != "ADMIN":
            return "No tenés permiso para acceder a esta sección.", 403

        return funcion(*args, **kwargs)

    return funcion_protegida

def registrar_historial(
    conexion,
    reserva_id,
    accion,
    detalle,
    datos_anteriores=None,
    datos_nuevos=None
):

    fecha_hora = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).strftime("%Y-%m-%d %H:%M:%S")

    anteriores_json = None
    nuevos_json = None

    if datos_anteriores is not None:
        anteriores_json = json.dumps(
            datos_anteriores,
            ensure_ascii=False
        )

    if datos_nuevos is not None:
        nuevos_json = json.dumps(
            datos_nuevos,
            ensure_ascii=False
        )

    conexion.execute("""
        INSERT INTO historial_reservas (
            reserva_id,
            usuario_id,
            accion,
            detalle,
            datos_anteriores,
            datos_nuevos,
            fecha_hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        reserva_id,
        session["usuario_id"],
        accion,
        detalle,
        anteriores_json,
        nuevos_json,
        fecha_hora
    ))

def registrar_historial_protocolo(
    conexion,
    protocolo_id,
    accion,
    detalle,
    datos_anteriores=None,
    datos_nuevos=None
):

    fecha_hora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    anteriores_json = None
    nuevos_json = None

    if datos_anteriores is not None:

        anteriores_json = json.dumps(
            datos_anteriores,
            ensure_ascii=False
        )

    if datos_nuevos is not None:

        nuevos_json = json.dumps(
            datos_nuevos,
            ensure_ascii=False
        )

    conexion.execute("""
        INSERT INTO historial_protocolos (
            protocolo_id,
            usuario_id,
            accion,
            detalle,
            datos_anteriores,
            datos_nuevos,
            fecha_hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        protocolo_id,
        session["usuario_id"],
        accion,
        detalle,
        anteriores_json,
        nuevos_json,
        fecha_hora
    ))

@app.route("/protocolos")
@login_required
def protocolos():

    conexion = conectar()

    # --------------------------------
    # CATÁLOGOS
    # --------------------------------

    tipos_protocolo = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_protocolo
        ORDER BY nombre
    """).fetchall()

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # FILTROS
    # --------------------------------

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_protocolo_id = request.args.get(
        "tipo_protocolo_id",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )


    # --------------------------------
    # PAGINACIÓN
    # --------------------------------

    try:

        pagina = int(
            request.args.get(
                "pagina",
                1
            )
        )

    except ValueError:

        pagina = 1

    if pagina < 1:
        pagina = 1

    por_pagina = 50


    # --------------------------------
    # CONDICIONES
    # --------------------------------

    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "protocolos.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "protocolos.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_protocolo_id:

        condiciones.append(
            "protocolos.tipo_protocolo_id = ?"
        )

        parametros.append(
            tipo_protocolo_id
        )


    if tipo_visita_id:

        condiciones.append(
            "protocolos.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if estado:

        condiciones.append(
            "protocolos.estado = ?"
        )

        parametros.append(
            estado
        )


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # --------------------------------
    # CANTIDAD DE REGISTROS
    # --------------------------------

    total_registros = conexion.execute(
        f"""
        SELECT COUNT(*)
        FROM protocolos
        {where_sql}
        """,
        parametros
    ).fetchone()[0]


    # --------------------------------
    # TOTAL DE ENTRADAS
    # --------------------------------

    total_entradas = conexion.execute(
        f"""
        SELECT
            COALESCE(
                SUM(protocolos.cantidad),
                0
            )

        FROM protocolos

        {where_sql}
        """,
        parametros
    ).fetchone()[0]


    # --------------------------------
    # PÁGINAS
    # --------------------------------

    total_paginas = max(
        1,
        (
            total_registros
            + por_pagina
            - 1
        )
        // por_pagina
    )

    if pagina > total_paginas:
        pagina = total_paginas

    offset = (
        pagina - 1
    ) * por_pagina


    # --------------------------------
    # OBTENER PROTOCOLOS
    # --------------------------------

    registros = conexion.execute(
        f"""
        SELECT
            protocolos.*,

            tipos_protocolo.nombre
                AS tipo_protocolo_nombre,

            tipos_visita.nombre
                AS tipo_visita_nombre,

            usuarios.nombre
                AS usuario_nombre

        FROM protocolos

        INNER JOIN tipos_protocolo
            ON protocolos.tipo_protocolo_id
                = tipos_protocolo.id

        INNER JOIN tipos_visita
            ON protocolos.tipo_visita_id
                = tipos_visita.id

        INNER JOIN usuarios
            ON protocolos.usuario_id
                = usuarios.id

        {where_sql}

        ORDER BY
            protocolos.fecha DESC,
            protocolos.id DESC

        LIMIT ? OFFSET ?
        """,
        parametros
        + [
            por_pagina,
            offset
        ]
    ).fetchall()

    conexion.close()


    paginas = range(
        max(
            1,
            pagina - 2
        ),
        min(
            total_paginas,
            pagina + 2
        ) + 1
    )


    return render_template(
        "protocolos.html",
        protocolos=registros,
        tipos_protocolo=tipos_protocolo,
        tipos_visita=tipos_visita,
        total_entradas=total_entradas,
        total_registros=total_registros,
        pagina=pagina,
        total_paginas=total_paginas,
        paginas=paginas,
        filtros={
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "tipo_protocolo_id":
                tipo_protocolo_id,
            "tipo_visita_id":
                tipo_visita_id,
            "estado": estado
        }
    )

@app.route(
    "/protocolos/nuevo",
    methods=["GET", "POST"]
)
@login_required
def nuevo_protocolo():

    conexion = conectar()


    # --------------------------------
    # TIPOS ACTIVOS
    # --------------------------------

    tipos_protocolo = conexion.execute("""
        SELECT
            id,
            nombre
        FROM tipos_protocolo
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre
        FROM tipos_visita
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    fecha_predeterminada = (
        request.form.get("fecha")
        or ahora.strftime("%Y-%m-%d")
    )


    # --------------------------------
    # GUARDAR
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        tipo_protocolo_id = request.form.get(
            "tipo_protocolo_id",
            ""
        )

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        cantidad_texto = request.form.get(
            "cantidad",
            ""
        ).strip()
        descripcion = texto_mayusculas(
            request.form.get("descripcion", "")
        )

        # --------------------------------
        # VALIDAR CANTIDAD
        # --------------------------------

        try:

            cantidad = int(
                cantidad_texto
            )

        except ValueError:

            cantidad = 0

        if cantidad <= 0:

            conexion.close()

            flash(
                "La cantidad debe ser mayor a 0.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_protocolo"
                )
            )


        # --------------------------------
        # VALIDAR TIPO DE PROTOCOLO
        # --------------------------------

        tipo_protocolo = conexion.execute("""
            SELECT id
            FROM tipos_protocolo
            WHERE id = ?
            AND estado = 'ACTIVO'
        """, (
            tipo_protocolo_id,
        )).fetchone()

        if tipo_protocolo is None:

            conexion.close()

            flash(
                "El tipo de protocolo seleccionado no es válido.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_protocolo"
                )
            )


        # --------------------------------
        # VALIDAR TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE id = ?
            AND estado = 'ACTIVO'
        """, (
            tipo_visita_id,
        )).fetchone()

        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no es válido.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_protocolo"
                )
            )


        # --------------------------------
        # USUARIO
        # --------------------------------

        usuario_id = session.get(
            "usuario_id"
        )

        if not usuario_id:

            conexion.close()

            session.clear()

            return redirect(
                url_for("login")
            )


        creado_en = ahora.strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # --------------------------------
        # INSERT
        # --------------------------------

        cursor=conexion.execute("""
                INSERT INTO protocolos (
                    fecha,
                    tipo_protocolo_id,
                    tipo_visita_id,
                    cantidad,
                    descripcion,
                    creado_en,
                    usuario_id,
                    estado
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'ACTIVO'
                )
            """, (
                fecha,
                tipo_protocolo_id,
                tipo_visita_id,
                cantidad,
                descripcion,
                creado_en,
                usuario_id
            ))

        protocolo_id = cursor.lastrowid

        protocolo_nuevo = conexion.execute("""
            SELECT *
            FROM protocolos
            WHERE id = ?
        """, (
            protocolo_id,
        )).fetchone()

        registrar_historial_protocolo(
            conexion=conexion,
            protocolo_id=protocolo_id,
            accion="CREADO",
            detalle="Se creó el protocolo.",
            datos_nuevos=dict(
                protocolo_nuevo
            )
        )

        conexion.commit()
        conexion.close()

        flash(
            "Protocolo cargado correctamente.",
            "exito"
        )

        return redirect(
            url_for("protocolos")
        )


    conexion.close()

    return render_template(
        "nuevo_protocolo.html",
        tipos_protocolo=tipos_protocolo,
        tipos_visita=tipos_visita,
        fecha_predeterminada=
            fecha_predeterminada
    )

@app.route("/inmersivo")
@login_required
def inmersivo():

    conexion = conectar()


    # --------------------------------
    # TIPOS DE VISITA
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # FILTROS
    # --------------------------------

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    medio_pago = request.args.get(
        "medio_pago",
        ""
    )

    marca = request.args.get(
        "marca",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )


    # --------------------------------
    # PAGINACIÓN
    # --------------------------------

    try:

        pagina = int(
            request.args.get(
                "pagina",
                1
            )
        )

    except ValueError:

        pagina = 1

    if pagina < 1:
        pagina = 1

    por_pagina = 50


    # --------------------------------
    # CONDICIONES
    # --------------------------------

    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "inmersivo.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "inmersivo.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_visita_id:

        condiciones.append(
            "inmersivo.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if medio_pago:

        condiciones.append(
            "inmersivo.medio_pago = ?"
        )

        parametros.append(
            medio_pago
        )


    if marca == "SIN_MARCA":

        condiciones.append(
            "inmersivo.marca IS NULL"
        )

    elif marca:

        condiciones.append(
            "inmersivo.marca = ?"
        )

        parametros.append(
            marca
        )


    if estado:

        condiciones.append(
            "inmersivo.estado = ?"
        )

        parametros.append(
            estado
        )


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # --------------------------------
    # CANTIDAD DE REGISTROS
    # --------------------------------

    total_registros = conexion.execute(
        f"""
        SELECT COUNT(*)

        FROM inmersivo

        {where_sql}
        """,
        parametros
    ).fetchone()[0]


    # --------------------------------
    # TOTALES
    # --------------------------------

    totales = conexion.execute(
        f"""
        SELECT

            COALESCE(
                SUM(cantidad),
                0
            ) AS total_personas,

            COALESCE(
                SUM(
                    CASE
                        WHEN medio_pago = 'EFECTIVO'
                        THEN cantidad
                        ELSE 0
                    END
                ),
                0
            ) AS total_efectivo,

            COALESCE(
                SUM(
                    CASE
                        WHEN medio_pago = 'TARJETA'
                        THEN cantidad
                        ELSE 0
                    END
                ),
                0
            ) AS total_tarjeta,

            COALESCE(
                SUM(
                    CASE
                        WHEN marca = 'ONLINE'
                        THEN cantidad
                        ELSE 0
                    END
                ),
                0
            ) AS total_online,

            COALESCE(
                SUM(
                    CASE
                        WHEN marca = 'DIFERENCIA'
                        THEN cantidad
                        ELSE 0
                    END
                ),
                0
            ) AS total_diferencia

        FROM inmersivo

        {where_sql}
        """,
        parametros
    ).fetchone()


    # --------------------------------
    # PÁGINAS
    # --------------------------------

    total_paginas = max(
        1,
        (
            total_registros
            + por_pagina
            - 1
        )
        // por_pagina
    )

    if pagina > total_paginas:
        pagina = total_paginas

    offset = (
        pagina - 1
    ) * por_pagina


    # --------------------------------
    # OBTENER REGISTROS
    # --------------------------------

    registros = conexion.execute(
        f"""
        SELECT
            inmersivo.*,

            tipos_visita.nombre
                AS tipo_visita_nombre,

            usuarios.nombre
                AS usuario_nombre

        FROM inmersivo

        INNER JOIN tipos_visita
            ON inmersivo.tipo_visita_id
                = tipos_visita.id

        INNER JOIN usuarios
            ON inmersivo.usuario_id
                = usuarios.id

        {where_sql}

        ORDER BY
            inmersivo.fecha DESC,
            inmersivo.hora DESC,
            inmersivo.id DESC

        LIMIT ? OFFSET ?
        """,
        parametros
        + [
            por_pagina,
            offset
        ]
    ).fetchall()


    conexion.close()


    paginas = range(
        max(
            1,
            pagina - 2
        ),
        min(
            total_paginas,
            pagina + 2
        ) + 1
    )


    return render_template(
        "inmersivo.html",
        registros=registros,
        tipos_visita=tipos_visita,
        totales=totales,
        total_registros=total_registros,
        pagina=pagina,
        total_paginas=total_paginas,
        paginas=paginas,
        filtros={
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "tipo_visita_id": tipo_visita_id,
            "medio_pago": medio_pago,
            "marca": marca,
            "estado": estado
        }
    )

@app.route(
    "/inmersivo/nuevo",
    methods=["GET", "POST"]
)
@login_required
def nuevo_inmersivo():

    conexion = conectar()


    # --------------------------------
    # TIPOS DE VISITA ACTIVOS
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre
        FROM tipos_visita
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )


    fecha_predeterminada = (
        request.form.get("fecha")
        or ahora.strftime("%Y-%m-%d")
    )

    hora_predeterminada = (
        request.form.get("hora")
        or ahora.strftime("%H:%M")
    )


    # --------------------------------
    # GUARDAR
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        cantidad_texto = request.form.get(
            "cantidad",
            ""
        ).strip()

        medio_pago = request.form.get(
            "medio_pago",
            ""
        ).strip().upper()


        # --------------------------------
        # ONLINE / DIFERENCIA
        # --------------------------------

        online = (
            request.form.get("online")
            == "1"
        )

        diferencia = (
            request.form.get("diferencia")
            == "1"
        )


        if online and diferencia:

            conexion.close()

            flash(
                "Online y Diferencia no pueden seleccionarse al mismo tiempo.",
                "error"
            )

            return redirect(
                url_for("nuevo_inmersivo")
            )


        marca = None

        if online:

            marca = "ONLINE"

        elif diferencia:

            marca = "DIFERENCIA"


        # --------------------------------
        # MEDIO DE PAGO
        # --------------------------------

        if online:

            medio_pago = None

        else:

            if medio_pago not in (
                "EFECTIVO",
                "TARJETA"
            ):

                conexion.close()

                flash(
                    "Debés seleccionar un medio de pago.",
                    "error"
                )

                return redirect(
                    url_for("nuevo_inmersivo")
                )


        # --------------------------------
        # CANTIDAD
        # --------------------------------

        try:

            cantidad = int(
                cantidad_texto
            )

        except ValueError:

            cantidad = 0


        if cantidad <= 0:

            conexion.close()

            flash(
                "La cantidad debe ser mayor a 0.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_inmersivo"
                )
            )


        # --------------------------------
        # TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE id = ?
            AND estado = 'ACTIVO'
        """, (
            tipo_visita_id,
        )).fetchone()


        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no es válido.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_inmersivo"
                )
            )


        # --------------------------------
        # USUARIO / FECHA DE CARGA
        # --------------------------------

        usuario_id = session.get(
            "usuario_id"
        )

        if not usuario_id:

            conexion.close()

            session.clear()

            return redirect(
                url_for("login")
            )


        creado_en = ahora.strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # --------------------------------
        # INSERT
        # --------------------------------

        cursor = conexion.execute("""
            INSERT INTO inmersivo (
                fecha,
                hora,
                tipo_visita_id,
                cantidad,
                medio_pago,
                marca,
                creado_en,
                usuario_id,
                estado
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'ACTIVO'
            )
        """, (
            fecha,
            hora,
            tipo_visita_id,
            cantidad,
            medio_pago,
            marca,
            creado_en,
            usuario_id
        ))


        inmersivo_id = cursor.lastrowid


        registro_nuevo = conexion.execute("""
            SELECT *
            FROM inmersivo
            WHERE id = ?
        """, (
            inmersivo_id,
        )).fetchone()


        registrar_historial_inmersivo(
            conexion=conexion,
            inmersivo_id=inmersivo_id,
            accion="CREADO",
            detalle="Se creó el ingreso de inmersivo.",
            datos_nuevos=dict(
                registro_nuevo
            )
        )


        conexion.commit()
        conexion.close()


        flash(
            "Ingreso de inmersivo cargado correctamente.",
            "exito"
        )

        return redirect(
            url_for("inmersivo")
        )


    conexion.close()


    return render_template(
        "nuevo_inmersivo.html",
        tipos_visita=tipos_visita,
        fecha_predeterminada=fecha_predeterminada,
        hora_predeterminada=hora_predeterminada
    )

@app.route(
    "/inmersivo/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
def editar_inmersivo(id):

    conexion = conectar()

    registro = conexion.execute("""
        SELECT *
        FROM inmersivo
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if registro is None:

        conexion.close()

        return (
            "Ingreso de inmersivo no encontrado",
            404
        )


    # --------------------------------
    # TIPOS DE VISITA
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    nombres_visitas = {
        tipo["id"]: tipo["nombre"]
        for tipo in tipos_visita
    }


    # --------------------------------
    # GUARDAR CAMBIOS
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        cantidad_texto = request.form.get(
            "cantidad",
            ""
        ).strip()

        medio_pago = request.form.get(
            "medio_pago",
            ""
        ).strip().upper()


        # --------------------------------
        # ONLINE / DIFERENCIA
        # --------------------------------

        online = (
            request.form.get("online")
            == "1"
        )

        diferencia = (
            request.form.get("diferencia")
            == "1"
        )


        if online and diferencia:

            conexion.close()

            flash(
                "Online y Diferencia no pueden seleccionarse al mismo tiempo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_inmersivo",
                    id=id
                )
            )


        marca = None

        if online:

            marca = "ONLINE"

        elif diferencia:

            marca = "DIFERENCIA"


        # --------------------------------
        # CANTIDAD
        # --------------------------------

        try:

            cantidad = int(
                cantidad_texto
            )

        except ValueError:

            cantidad = 0


        if cantidad <= 0:

            conexion.close()

            flash(
                "La cantidad debe ser mayor a 0.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_inmersivo",
                    id=id
                )
            )


        # --------------------------------
        # MEDIO DE PAGO
        # --------------------------------

        if online:

            # Online ya viene pago,
            # por lo tanto no tiene
            # medio de pago.

            medio_pago = None

        else:

            if medio_pago not in (
                "EFECTIVO",
                "TARJETA"
            ):

                conexion.close()

                flash(
                    "Debés seleccionar un medio de pago.",
                    "error"
                )

                return redirect(
                    url_for(
                        "editar_inmersivo",
                        id=id
                    )
                )


        # --------------------------------
        # TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT
                id,
                nombre,
                estado
            FROM tipos_visita
            WHERE id = ?
        """, (
            tipo_visita_id,
        )).fetchone()


        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_inmersivo",
                    id=id
                )
            )


        if (
            tipo_visita["estado"] != "ACTIVO"
            and str(tipo_visita_id)
            != str(registro["tipo_visita_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar un tipo de visita inactivo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_inmersivo",
                    id=id
                )
            )


        # --------------------------------
        # DATOS ANTERIORES
        # --------------------------------

        datos_anteriores = dict(
            registro
        )


        # --------------------------------
        # ACTUALIZAR
        # --------------------------------

        conexion.execute("""
            UPDATE inmersivo

            SET
                fecha = ?,
                hora = ?,
                tipo_visita_id = ?,
                cantidad = ?,
                medio_pago = ?,
                marca = ?

            WHERE id = ?
        """, (
            fecha,
            hora,
            tipo_visita_id,
            cantidad,
            medio_pago,
            marca,
            id
        ))


        # --------------------------------
        # DATOS NUEVOS
        # --------------------------------

        registro_actualizado = conexion.execute("""
            SELECT *
            FROM inmersivo
            WHERE id = ?
        """, (
            id,
        )).fetchone()


        datos_nuevos = dict(
            registro_actualizado
        )


        # --------------------------------
        # DETECTAR CAMBIOS
        # --------------------------------

        cambios = []


        # FECHA

        if (
            datos_anteriores["fecha"]
            != datos_nuevos["fecha"]
        ):

            cambios.append(
                f"Fecha: "
                f"{datos_anteriores['fecha']} → "
                f"{datos_nuevos['fecha']}"
            )


        # HORA

        if (
            datos_anteriores["hora"]
            != datos_nuevos["hora"]
        ):

            cambios.append(
                f"Hora: "
                f"{datos_anteriores['hora']} → "
                f"{datos_nuevos['hora']}"
            )


        # TIPO DE VISITA

        if (
            str(
                datos_anteriores[
                    "tipo_visita_id"
                ]
            )
            != str(
                datos_nuevos[
                    "tipo_visita_id"
                ]
            )
        ):

            anterior = nombres_visitas.get(
                datos_anteriores[
                    "tipo_visita_id"
                ],
                "Desconocido"
            )

            nuevo = tipo_visita[
                "nombre"
            ]

            cambios.append(
                f"Tipo de visita: "
                f"{anterior} → {nuevo}"
            )


        # CANTIDAD

        if (
            datos_anteriores["cantidad"]
            != datos_nuevos["cantidad"]
        ):

            cambios.append(
                f"Cantidad: "
                f"{datos_anteriores['cantidad']} → "
                f"{datos_nuevos['cantidad']}"
            )


        # MEDIO DE PAGO

        medio_anterior = (
            datos_anteriores["medio_pago"]
            or "—"
        )

        medio_nuevo = (
            datos_nuevos["medio_pago"]
            or "—"
        )


        if medio_anterior != medio_nuevo:

            cambios.append(
                f"Medio de pago: "
                f"{medio_anterior} → "
                f"{medio_nuevo}"
            )


        # MARCA

        marca_anterior = (
            datos_anteriores["marca"]
            or "—"
        )

        marca_nueva = (
            datos_nuevos["marca"]
            or "—"
        )


        if marca_anterior != marca_nueva:

            cambios.append(
                f"Marca: "
                f"{marca_anterior} → "
                f"{marca_nueva}"
            )


        # --------------------------------
        # HISTORIAL
        # --------------------------------

        if cambios:

            registrar_historial_inmersivo(
                conexion=conexion,
                inmersivo_id=id,
                accion="EDITADO",
                detalle="; ".join(
                    cambios
                ),
                datos_anteriores=
                    datos_anteriores,
                datos_nuevos=
                    datos_nuevos
            )


        conexion.commit()
        conexion.close()


        flash(
            "Ingreso de inmersivo actualizado correctamente.",
            "exito"
        )

        return redirect(
            url_for("inmersivo")
        )


    # --------------------------------
    # MOSTRAR FORMULARIO
    # --------------------------------

    conexion.close()


    return render_template(
        "editar_inmersivo.html",
        registro=registro,
        tipos_visita=tipos_visita
    )

@app.route(
    "/inmersivo/<int:id>/anular",
    methods=["POST"]
)
@login_required
def anular_inmersivo(id):

    conexion = conectar()

    registro = conexion.execute("""
        SELECT *
        FROM inmersivo
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if registro is None:

        conexion.close()

        return (
            "Ingreso de inmersivo no encontrado",
            404
        )


    if registro["estado"] != "ACTIVO":

        conexion.close()

        flash(
            "El ingreso ya se encuentra anulado.",
            "error"
        )

        return redirect(
            url_for("inmersivo")
        )


    datos_anteriores = dict(
        registro
    )


    conexion.execute("""
        UPDATE inmersivo
        SET estado = 'ANULADO'
        WHERE id = ?
    """, (
        id,
    ))


    actualizado = conexion.execute("""
        SELECT *
        FROM inmersivo
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    registrar_historial_inmersivo(
        conexion=conexion,
        inmersivo_id=id,
        accion="ANULADO",
        detalle="Se anuló el ingreso de inmersivo.",
        datos_anteriores=
            datos_anteriores,
        datos_nuevos=dict(
            actualizado
        )
    )


    conexion.commit()
    conexion.close()


    flash(
        "Ingreso de inmersivo anulado correctamente.",
        "exito"
    )

    return redirect(
        url_for("inmersivo")
    )


@app.route(
    "/inmersivo/<int:id>/reactivar",
    methods=["POST"]
)
@login_required
def reactivar_inmersivo(id):

    conexion = conectar()

    registro = conexion.execute("""
        SELECT *
        FROM inmersivo
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if registro is None:

        conexion.close()

        return (
            "Ingreso de inmersivo no encontrado",
            404
        )


    if registro["estado"] != "ANULADO":

        conexion.close()

        flash(
            "El ingreso ya se encuentra activo.",
            "error"
        )

        return redirect(
            url_for("inmersivo")
        )


    datos_anteriores = dict(
        registro
    )


    conexion.execute("""
        UPDATE inmersivo
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))


    actualizado = conexion.execute("""
        SELECT *
        FROM inmersivo
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    registrar_historial_inmersivo(
        conexion=conexion,
        inmersivo_id=id,
        accion="REACTIVADO",
        detalle="Se reactivó el ingreso de inmersivo.",
        datos_anteriores=
            datos_anteriores,
        datos_nuevos=dict(
            actualizado
        )
    )


    conexion.commit()
    conexion.close()


    flash(
        "Ingreso de inmersivo reactivado correctamente.",
        "exito"
    )

    return redirect(
        url_for("inmersivo")
    )

def registrar_historial_inmersivo(
    conexion,
    inmersivo_id,
    accion,
    detalle,
    datos_anteriores=None,
    datos_nuevos=None
):

    fecha_hora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    anteriores_json = None
    nuevos_json = None

    if datos_anteriores is not None:

        anteriores_json = json.dumps(
            datos_anteriores,
            ensure_ascii=False
        )

    if datos_nuevos is not None:

        nuevos_json = json.dumps(
            datos_nuevos,
            ensure_ascii=False
        )

    conexion.execute("""
        INSERT INTO historial_inmersivo (
            inmersivo_id,
            usuario_id,
            accion,
            detalle,
            datos_anteriores,
            datos_nuevos,
            fecha_hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        inmersivo_id,
        session["usuario_id"],
        accion,
        detalle,
        anteriores_json,
        nuevos_json,
        fecha_hora
    ))

@app.route(
    "/inmersivo/<int:id>/historial"
)
@login_required
def historial_inmersivo(id):

    conexion = conectar()


    registro = conexion.execute("""
        SELECT
            inmersivo.*,

            tipos_visita.nombre
                AS tipo_visita_nombre

        FROM inmersivo

        INNER JOIN tipos_visita
            ON inmersivo.tipo_visita_id
                = tipos_visita.id

        WHERE inmersivo.id = ?
    """, (
        id,
    )).fetchone()


    if registro is None:

        conexion.close()

        return (
            "Ingreso de inmersivo no encontrado",
            404
        )


    historial = conexion.execute("""
        SELECT
            historial_inmersivo.*,

            usuarios.nombre
                AS usuario_nombre

        FROM historial_inmersivo

        INNER JOIN usuarios
            ON historial_inmersivo.usuario_id
                = usuarios.id

        WHERE historial_inmersivo.inmersivo_id = ?

        ORDER BY
            historial_inmersivo.fecha_hora DESC,
            historial_inmersivo.id DESC
    """, (
        id,
    )).fetchall()


    conexion.close()


    return render_template(
        "historial_inmersivo.html",
        registro=registro,
        historial=historial
    )

@app.route("/inmersivo/exportar")
@login_required
def exportar_inmersivo():

    conexion = conectar()


    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    medio_pago = request.args.get(
        "medio_pago",
        ""
    )

    marca = request.args.get(
        "marca",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )


    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "inmersivo.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "inmersivo.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_visita_id:

        condiciones.append(
            "inmersivo.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if medio_pago:

        condiciones.append(
            "inmersivo.medio_pago = ?"
        )

        parametros.append(
            medio_pago
        )


    if marca == "SIN_MARCA":

        condiciones.append(
            "inmersivo.marca IS NULL"
        )

    elif marca:

        condiciones.append(
            "inmersivo.marca = ?"
        )

        parametros.append(
            marca
        )


    if estado:

        condiciones.append(
            "inmersivo.estado = ?"
        )

        parametros.append(
            estado
        )


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    registros = conexion.execute(
        f"""
        SELECT
            inmersivo.fecha,
            inmersivo.hora,

            tipos_visita.nombre
                AS tipo_visita,

            inmersivo.cantidad,
            inmersivo.medio_pago,
            inmersivo.marca,

            usuarios.nombre
                AS usuario_nombre,

            inmersivo.creado_en,
            inmersivo.estado

        FROM inmersivo

        INNER JOIN tipos_visita
            ON inmersivo.tipo_visita_id
                = tipos_visita.id

        INNER JOIN usuarios
            ON inmersivo.usuario_id
                = usuarios.id

        {where_sql}

        ORDER BY
            inmersivo.fecha ASC,
            inmersivo.hora ASC,
            inmersivo.id ASC
        """,
        parametros
    ).fetchall()


    conexion.close()


    libro = Workbook()

    hoja = libro.active
    hoja.title = "Inmersivo"


    hoja.append([
        "Fecha",
        "Hora",
        "Tipo de visita",
        "Cantidad",
        "Medio de pago",
        "Marca",
        "Cargado por",
        "Cargado el",
        "Estado"
    ])


    total_personas = 0


    for registro in registros:

        fecha = datetime.strptime(
            registro["fecha"],
            "%Y-%m-%d"
        ).date()

        hora = datetime.strptime(
            registro["hora"],
            "%H:%M"
        ).time()

        creado_en = datetime.strptime(
            registro["creado_en"],
            "%Y-%m-%d %H:%M:%S"
        )

        total_personas += registro[
            "cantidad"
        ]


        hoja.append([
            fecha,
            hora,
            registro["tipo_visita"],
            registro["cantidad"],
            registro["medio_pago"] or "",
            registro["marca"] or "",
            registro["usuario_nombre"],
            creado_en,
            registro["estado"]
        ])


        fila = hoja.max_row

        hoja[
            f"A{fila}"
        ].number_format = "dd/mm/yyyy"

        hoja[
            f"B{fila}"
        ].number_format = "hh:mm"

        hoja[
            f"H{fila}"
        ].number_format = (
            "dd/mm/yyyy hh:mm"
        )


    fila_total = hoja.max_row + 2

    hoja[
        f"C{fila_total}"
    ] = "TOTAL PERSONAS"

    hoja[
        f"D{fila_total}"
    ] = total_personas


    anchos = {
        "A": 15,
        "B": 12,
        "C": 20,
        "D": 12,
        "E": 18,
        "F": 16,
        "G": 22,
        "H": 21,
        "I": 15
    }


    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    if registros:

        hoja.auto_filter.ref = (
            f"A1:I{len(registros) + 1}"
        )


    hoja.freeze_panes = "A2"


    archivo = BytesIO()

    libro.save(
        archivo
    )

    archivo.seek(0)


    fecha_archivo = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d"
    )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=(
            f"inmersivo_{fecha_archivo}.xlsx"
        ),
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )

@app.route("/usuarios")
@admin_required
def usuarios():

    conexion = conectar()

    usuarios = conexion.execute("""
        SELECT
            id,
            nombre,
            usuario,
            rol,
            estado
        FROM usuarios
        ORDER BY nombre
    """).fetchall()

    conexion.close()

    return render_template(
        "usuarios.html",
        usuarios=usuarios
    )

@app.route("/usuarios/<int:id>/inactivar", methods=["POST"])
@admin_required
def inactivar_usuario(id):

    # No permitir que el usuario conectado se inhabilite.
    if id == session["usuario_id"]:

        flash(
            "No podés inactivar tu propio usuario.",
            "error"
        )

        return redirect(url_for("usuarios"))

    conexion = conectar()

    usuario = conexion.execute("""
        SELECT
            id,
            nombre,
            rol,
            estado
        FROM usuarios
        WHERE id = ?
    """, (id,)).fetchone()

    if usuario is None:

        conexion.close()

        flash(
            "El usuario no existe.",
            "error"
        )

        return redirect(url_for("usuarios"))

    # Evitar que el sistema quede sin administradores.
    if (
        usuario["rol"] == "ADMIN"
        and usuario["estado"] == "ACTIVO"
    ):

        administradores_activos = conexion.execute("""
            SELECT COUNT(*)
            FROM usuarios
            WHERE rol = 'ADMIN'
            AND estado = 'ACTIVO'
        """).fetchone()[0]

        if administradores_activos <= 1:

            conexion.close()

            flash(
                "No se puede inactivar al último administrador activo.",
                "error"
            )

            return redirect(url_for("usuarios"))

    conexion.execute("""
        UPDATE usuarios
        SET estado = 'INACTIVO'
        WHERE id = ?
    """, (id,))

    conexion.commit()
    conexion.close()

    flash(
        "Usuario inactivado correctamente.",
        "exito"
    )

    return redirect(url_for("usuarios"))

@app.route("/usuarios/<int:id>/activar", methods=["POST"])
@admin_required
def activar_usuario(id):

    conexion = conectar()

    usuario = conexion.execute("""
        SELECT id
        FROM usuarios
        WHERE id = ?
    """, (id,)).fetchone()

    if usuario is None:

        conexion.close()

        flash(
            "El usuario no existe.",
            "error"
        )

        return redirect(url_for("usuarios"))

    conexion.execute("""
        UPDATE usuarios
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (id,))

    conexion.commit()
    conexion.close()

    flash(
        "Usuario activado correctamente.",
        "exito"
    )

    return redirect(url_for("usuarios"))

@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_usuario():

    error = None

    if request.method == "POST":

        nombre = request.form["nombre"].strip()
        nombre_usuario = request.form["usuario"].strip()
        password = request.form["password"]
        confirmacion = request.form["confirmacion"]
        rol = request.form["rol"]

        if not nombre or not nombre_usuario or not password:
            error = "Todos los campos obligatorios deben completarse."

        elif password != confirmacion:
            error = "Las contraseñas no coinciden."

        elif rol not in ("ADMIN", "OPERADOR"):
            error = "El rol seleccionado no es válido."

        else:
            conexion = conectar()

            usuario_existente = conexion.execute("""
                SELECT id
                FROM usuarios
                WHERE usuario = ?
            """, (nombre_usuario,)).fetchone()

            if usuario_existente:
                error = "Ese nombre de usuario ya existe."
                conexion.close()

            else:
                password_hash = generate_password_hash(password)

                conexion.execute("""
                    INSERT INTO usuarios (
                        nombre,
                        usuario,
                        password_hash,
                        rol,
                        estado
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    nombre,
                    nombre_usuario,
                    password_hash,
                    rol,
                    "ACTIVO"
                ))

                conexion.commit()
                conexion.close()

                return redirect(url_for("usuarios"))

    return render_template(
        "nuevo_usuario.html",
        error=error
    )

@app.route(
    "/usuarios/<int:id>/editar",
    methods=["GET", "POST"]
)
@admin_required
def editar_usuario(id):

    conexion = conectar()

    usuario = conexion.execute(
        """
        SELECT
            id,
            nombre,
            usuario,
            rol,
            estado
        FROM usuarios
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if usuario is None:
        conexion.close()

        flash(
            "El usuario no existe.",
            "error"
        )

        return redirect(url_for("usuarios"))

    error = None
    datos_formulario = dict(usuario)

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        nombre_usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        rol = request.form.get(
            "rol",
            ""
        )

        datos_formulario = {
            "id": id,
            "nombre": nombre,
            "usuario": nombre_usuario,
            "rol": rol,
            "estado": usuario["estado"]
        }

        if not nombre or not nombre_usuario:

            error = (
                "El nombre y el usuario "
                "son obligatorios."
            )

        elif rol not in ("ADMIN", "OPERADOR"):

            error = "El rol seleccionado no es válido."

        elif (
            id == session["usuario_id"]
            and rol != usuario["rol"]
        ):

            error = (
                "No podés cambiar el rol "
                "de tu propio usuario."
            )

        else:

            usuario_existente = conexion.execute(
                """
                SELECT id
                FROM usuarios
                WHERE LOWER(usuario) = LOWER(?)
                AND id != ?
                """,
                (nombre_usuario, id)
            ).fetchone()

            if usuario_existente:

                error = (
                    "Ese nombre de usuario "
                    "ya está siendo utilizado."
                )

            elif (
                usuario["rol"] == "ADMIN"
                and usuario["estado"] == "ACTIVO"
                and rol != "ADMIN"
            ):

                administradores_activos = conexion.execute(
                    """
                    SELECT COUNT(*)
                    FROM usuarios
                    WHERE rol = 'ADMIN'
                    AND estado = 'ACTIVO'
                    """
                ).fetchone()[0]

                if administradores_activos <= 1:

                    error = (
                        "No se puede cambiar el rol "
                        "del último administrador activo."
                    )

        if error is None:

            conexion.execute(
                """
                UPDATE usuarios
                SET
                    nombre = ?,
                    usuario = ?,
                    rol = ?
                WHERE id = ?
                """,
                (
                    nombre,
                    nombre_usuario,
                    rol,
                    id
                )
            )

            conexion.commit()

            # Actualizar el nombre mostrado en la sesión
            # cuando el administrador se edita a sí mismo.
            if id == session["usuario_id"]:
                session["nombre"] = nombre

            conexion.close()

            flash(
                "Usuario actualizado correctamente.",
                "exito"
            )

            return redirect(url_for("usuarios"))

    conexion.close()

    return render_template(
        "editar_usuario.html",
        usuario=datos_formulario,
        error=error
    )

@app.route(
    "/usuarios/<int:id>/cambiar-password",
    methods=["GET", "POST"]
)
@admin_required
def cambiar_password_usuario(id):

    conexion = conectar()

    usuario = conexion.execute(
        """
        SELECT
            id,
            nombre,
            usuario
        FROM usuarios
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if usuario is None:
        conexion.close()

        flash(
            "El usuario no existe.",
            "error"
        )

        return redirect(url_for("usuarios"))

    error = None

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirmacion = request.form.get(
            "confirmacion",
            ""
        )

        if not password:

            error = "Ingresá una contraseña nueva."

        elif len(password) < 8:

            error = (
                "La contraseña debe tener "
                "al menos 8 caracteres."
            )

        elif password != confirmacion:

            error = "Las contraseñas no coinciden."

        else:

            password_hash = generate_password_hash(
                password
            )

            conexion.execute(
                """
                UPDATE usuarios
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    password_hash,
                    id
                )
            )

            conexion.commit()
            conexion.close()

            flash(
                "Contraseña actualizada correctamente.",
                "exito"
            )

            return redirect(url_for("usuarios"))

    conexion.close()

    return render_template(
        "cambiar_password_usuario.html",
        usuario=usuario,
        error=error
    )

@app.route(
    "/configuracion-inicial",
    methods=["GET", "POST"]
)
def configuracion_inicial():

    conexion = conectar()

    cantidad_usuarios = conexion.execute(
        """
        SELECT COUNT(*)
        FROM usuarios
        """
    ).fetchone()[0]

    # La configuración inicial queda bloqueada
    # una vez que ya existe algún usuario.
    if cantidad_usuarios > 0:

        conexion.close()

        return redirect(
            url_for("login")
        )

    error = None

    if request.method == "POST":

        nombre = request.form.get(
            "nombre",
            ""
        ).strip()

        nombre_usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirmacion = request.form.get(
            "confirmacion",
            ""
        )

        if not nombre or not nombre_usuario or not password:

            error = (
                "Todos los campos son obligatorios."
            )

        elif len(password) < 8:

            error = (
                "La contraseña debe tener "
                "al menos 8 caracteres."
            )

        elif password != confirmacion:

            error = (
                "Las contraseñas no coinciden."
            )

        else:

            password_hash = generate_password_hash(
                password
            )

            conexion.execute(
                """
                INSERT INTO usuarios (
                    nombre,
                    usuario,
                    password_hash,
                    rol,
                    estado
                )
                VALUES (?, ?, ?, 'ADMIN', 'ACTIVO')
                """,
                (
                    nombre,
                    nombre_usuario,
                    password_hash
                )
            )

            conexion.commit()
            conexion.close()

            flash(
                "Administrador creado correctamente. "
                "Ya podés iniciar sesión.",
                "exito"
            )

            return redirect(
                url_for("login")
            )

    conexion.close()

    return render_template(
        "configuracion_inicial.html",
        error=error
    )

@app.route("/login", methods=["GET", "POST"])
def login():

    conexion = conectar()

    cantidad_usuarios = conexion.execute(
        """
        SELECT COUNT(*)
        FROM usuarios
        """
    ).fetchone()[0]

    conexion.close()

    if cantidad_usuarios == 0:

        return redirect(
            url_for("configuracion_inicial")
        )

    if "usuario_id" in session:
        return redirect(url_for("inicio"))

    error = None

    if request.method == "POST":

        nombre_usuario = request.form["usuario"].strip()
        password = request.form["password"]

        conexion = conectar()

        usuario = conexion.execute("""
            SELECT *
            FROM usuarios
            WHERE usuario = ?
            AND estado = 'ACTIVO'
        """, (nombre_usuario,)).fetchone()

        conexion.close()

        if usuario is None:
            error = "Usuario o contraseña incorrectos."

        elif not check_password_hash(
            usuario["password_hash"],
            password
        ):
            error = "Usuario o contraseña incorrectos."

        else:
            session.clear()

            session["usuario_id"] = usuario["id"]
            session["usuario_nombre"] = usuario["nombre"]
            session["usuario_rol"] = usuario["rol"]

            return redirect(url_for("inicio"))

    return render_template(
        "login.html",
        error=error
    )


@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect(url_for("login"))

@app.route("/")
@login_required
def inicio():

    conexion = conectar()

    hoy = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).strftime("%Y-%m-%d")


    # --------------------------------
    # RESERVAS ACTIVAS DE HOY
    # --------------------------------

    reservas_hoy = conexion.execute("""
        SELECT
            reservas.*,
            empresas.nombre AS empresa_nombre,
            tipos_visita.nombre AS tipo_visita_nombre

        FROM reservas

        INNER JOIN empresas
            ON reservas.empresa_id = empresas.id

        INNER JOIN tipos_visita
            ON reservas.tipo_visita_id = tipos_visita.id

        WHERE
            reservas.fecha = ?
            AND reservas.estado = 'ACTIVA'

        ORDER BY
            reservas.hora ASC,
            reservas.id ASC
    """, (
        hoy,
    )).fetchall()


    # --------------------------------
    # RESUMEN DE RESERVAS
    # --------------------------------

    cantidad_reservas = len(
        reservas_hoy
    )

    total_mayores = sum(
        reserva["mayores"]
        for reserva in reservas_hoy
    )

    total_menores = sum(
        reserva["menores"]
        for reserva in reservas_hoy
    )

    total_pasajeros = (
        total_mayores
        + total_menores
    )


    # --------------------------------
    # PROTOCOLOS DE HOY
    # --------------------------------

    total_protocolos = conexion.execute("""
        SELECT
            COALESCE(
                SUM(cantidad),
                0
            )

        FROM protocolos

        WHERE
            fecha = ?
            AND estado = 'ACTIVO'
    """, (
        hoy,
    )).fetchone()[0]


    # --------------------------------
    # INMERSIVO DE HOY
    # --------------------------------

    total_inmersivo = conexion.execute("""
        SELECT
            COALESCE(
                SUM(cantidad),
                0
            )

        FROM inmersivo

        WHERE
            fecha = ?
            AND estado = 'ACTIVO'
    """, (
        hoy,
    )).fetchone()[0]


    conexion.close()


    return render_template(
        "inicio.html",

        reservas_hoy=reservas_hoy,

        cantidad_reservas=
            cantidad_reservas,

        total_mayores=
            total_mayores,

        total_menores=
            total_menores,

        total_pasajeros=
            total_pasajeros,

        total_protocolos=
            total_protocolos,

        total_inmersivo=
            total_inmersivo
    )

@app.route("/empresas")
@admin_required
def empresas():

    conexion = conectar()

    empresas = conexion.execute("""
        SELECT *
        FROM empresas
        ORDER BY nombre
    """).fetchall()

    conexion.close()

    return render_template(
        "empresas.html",
        empresas=empresas
    )


@app.route("/empresas/nueva_empresa", methods=["GET", "POST"])
@admin_required
def nueva_empresa():

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if nombre:
            conexion = conectar()

            conexion.execute("""
                INSERT INTO empresas (
                    nombre,
                    estado
                )
                VALUES (?, ?)
                """, (
                    nombre,
                    "ACTIVA"
                ))

            conexion.commit()
            conexion.close()

        return redirect(url_for("empresas"))

    return render_template("nueva_empresa.html")

@app.route(
    "/empresas/<int:id>/editar",
    methods=["GET", "POST"]
)
@admin_required
def editar_empresa(id):

    conexion = conectar()

    empresa = conexion.execute(
        """
        SELECT
            id,
            nombre,
            estado
        FROM empresas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if empresa is None:

        conexion.close()

        flash(
            "La empresa no existe.",
            "error"
        )

        return redirect(url_for("empresas"))

    error = None
    nombre_formulario = empresa["nombre"]

    if request.method == "POST":

        nombre_formulario = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre_formulario:

            error = "El nombre de la empresa es obligatorio."

        else:

            empresa_existente = conexion.execute(
                """
                SELECT id
                FROM empresas
                WHERE LOWER(nombre) = LOWER(?)
                AND id != ?
                """,
                (
                    nombre_formulario,
                    id
                )
            ).fetchone()

            if empresa_existente:

                error = (
                    "Ya existe otra empresa "
                    "con ese nombre."
                )

        if error is None:

            conexion.execute(
                """
                UPDATE empresas
                SET nombre = ?
                WHERE id = ?
                """,
                (
                    nombre_formulario,
                    id
                )
            )

            conexion.commit()
            conexion.close()

            flash(
                "Empresa actualizada correctamente.",
                "exito"
            )

            return redirect(url_for("empresas"))

    conexion.close()

    return render_template(
        "editar_empresa.html",
        empresa=empresa,
        nombre_formulario=nombre_formulario,
        error=error
    )

@app.route("/reservas")
@login_required
def reservas():

    conexion = conectar()

    # -----------------------------
    # EMPRESAS PARA EL FILTRO
    # -----------------------------

    empresas = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM empresas
        ORDER BY nombre
    """).fetchall()


    # -----------------------------
    # TIPOS DE VISITA PARA EL FILTRO
    # -----------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    # -----------------------------
    # FILTROS
    # -----------------------------

    empresa_id = request.args.get(
        "empresa_id",
        ""
    )

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    nacionalidad = request.args.get(
        "nacionalidad",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVA"
    )

    busqueda = request.args.get(
        "busqueda",
        ""
    ).strip()


    # -----------------------------
    # PAGINACIÓN
    # -----------------------------

    try:
        pagina = int(
            request.args.get(
                "pagina",
                1
            )
        )

    except ValueError:
        pagina = 1

    if pagina < 1:
        pagina = 1

    por_pagina = 50


    # -----------------------------
    # ARMAR CONDICIONES
    # -----------------------------

    condiciones = []
    parametros = []

    if empresa_id:

        condiciones.append(
            "reservas.empresa_id = ?"
        )

        parametros.append(
            empresa_id
        )


    if fecha_desde:

        condiciones.append(
            "reservas.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "reservas.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_visita_id:

        condiciones.append(
            "reservas.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if nacionalidad:

        condiciones.append(
            "reservas.nacionalidad = ?"
        )

        parametros.append(
            nacionalidad
        )


    if estado:

        condiciones.append(
            "reservas.estado = ?"
        )

        parametros.append(
            estado
        )


    if busqueda:

        condiciones.append("""
            (
                reservas.nombre_reserva LIKE ?
                OR COALESCE(
                    reservas.voucher,
                    ''
                ) LIKE ?
            )
        """)

        texto = f"%{busqueda}%"

        parametros.append(texto)
        parametros.append(texto)


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # -----------------------------
    # CANTIDAD TOTAL
    # -----------------------------

    total = conexion.execute(
        f"""
        SELECT COUNT(*)

        FROM reservas

        {where_sql}
        """,
        parametros
    ).fetchone()[0]


    # -----------------------------
    # CALCULAR PÁGINAS
    # -----------------------------

    total_paginas = max(
        1,
        (
            total
            + por_pagina
            - 1
        )
        // por_pagina
    )

    if pagina > total_paginas:
        pagina = total_paginas

    offset = (
        pagina - 1
    ) * por_pagina


    # -----------------------------
    # OBTENER RESERVAS
    # -----------------------------

    reservas = conexion.execute(
        f"""
        SELECT
            reservas.*,

            empresas.nombre
                AS empresa_nombre,

            tipos_visita.nombre
                AS tipo_visita_nombre

        FROM reservas

        INNER JOIN empresas
            ON reservas.empresa_id
                = empresas.id

        INNER JOIN tipos_visita
            ON reservas.tipo_visita_id
                = tipos_visita.id

        {where_sql}

        ORDER BY
            reservas.fecha DESC,
            reservas.hora DESC,
            reservas.id DESC

        LIMIT ? OFFSET ?
        """,
        parametros
        + [
            por_pagina,
            offset
        ]
    ).fetchall()

    conexion.close()


    # -----------------------------
    # PÁGINAS PARA MOSTRAR
    # -----------------------------

    paginas = range(
        max(
            1,
            pagina - 2
        ),
        min(
            total_paginas,
            pagina + 2
        ) + 1
    )


    return render_template(
        "reservas.html",

        reservas=reservas,
        empresas=empresas,
        tipos_visita=tipos_visita,

        filtros={
            "empresa_id": empresa_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "tipo_visita_id": tipo_visita_id,
            "nacionalidad": nacionalidad,
            "estado": estado,
            "busqueda": busqueda
        },

        pagina=pagina,
        total=total,
        total_paginas=total_paginas,
        paginas=paginas
    )

@app.route("/reservas/nueva_reserva", methods=["GET", "POST"])
@login_required
def nueva_reserva():

    conexion = conectar()

    # --------------------------------
    # EMPRESAS ACTIVAS
    # --------------------------------

    empresas = conexion.execute("""
        SELECT
            id,
            nombre
        FROM empresas
        WHERE estado = 'ACTIVA'
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # TIPOS DE VISITA ACTIVOS
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre
        FROM tipos_visita
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # FECHA Y HORA PREDETERMINADAS
    # --------------------------------

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    fecha_predeterminada = (
        request.form.get("fecha")
        or ahora.strftime("%Y-%m-%d")
    )

    hora_predeterminada = (
        request.form.get("hora")
        or ahora.strftime("%H:%M")
    )


    # --------------------------------
    # GUARDAR RESERVA
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        empresa_id = request.form.get(
            "empresa_id",
            ""
        )

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        nombre_reserva = texto_mayusculas(
            request.form.get("nombre_reserva", "")
        )

        mayores = request.form.get(
            "mayores",
            "0"
        )

        menores = request.form.get(
            "menores",
            "0"
        )

        nacionalidad = texto_mayusculas(
            request.form.get("nacionalidad", "")
        )

        voucher = texto_mayusculas(
            request.form.get("voucher", "")
        )

        guia = texto_mayusculas(
            request.form.get("guia", "")
        )

        notas = texto_mayusculas(
            request.form.get("notas", "")
        )

        creado_en = ahora.strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # --------------------------------
        # VALIDAR TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE id = ?
            AND estado = 'ACTIVO'
        """, (
            tipo_visita_id,
        )).fetchone()

        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no es válido.",
                "error"
            )

            return redirect(
                url_for("nueva_reserva")
            )


        # --------------------------------
        # VALIDAR EMPRESA
        # --------------------------------

        empresa = conexion.execute("""
            SELECT id
            FROM empresas
            WHERE id = ?
            AND estado = 'ACTIVA'
        """, (
            empresa_id,
        )).fetchone()

        if empresa is None:

            conexion.close()

            flash(
                "La empresa seleccionada no es válida.",
                "error"
            )

            return redirect(
                url_for("nueva_reserva")
            )

        # --------------------------------
        # VALIDAR PASAJEROS
        # --------------------------------

        try:

            mayores = int(mayores)
            menores = int(menores)

        except ValueError:

            conexion.close()

            flash(
                "La cantidad de pasajeros debe ser un número válido.",
                "error"
            )

            return redirect(
                url_for("nueva_reserva")
            )


        if mayores < 0 or menores < 0:

            conexion.close()

            flash(
                "La cantidad de pasajeros no puede ser negativa.",
                "error"
            )

            return redirect(
                url_for("nueva_reserva")
            )


        if mayores + menores <= 0:

            conexion.close()

            flash(
                "La reserva debe tener al menos 1 pasajero.",
                "error"
            )

            return redirect(
                url_for("nueva_reserva")
            )

        # --------------------------------
        # INSERT
        # --------------------------------

        cursor = conexion.execute("""
            INSERT INTO reservas (
                fecha,
                hora,
                empresa_id,
                tipo_visita_id,
                nombre_reserva,
                mayores,
                menores,
                nacionalidad,
                voucher,
                guia,
                notas,
                estado,
                creado_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha,
            hora,
            empresa_id,
            tipo_visita_id,
            nombre_reserva,
            mayores,
            menores,
            nacionalidad,
            voucher,
            guia,
            notas,
            "ACTIVA",
            creado_en
        ))


        # --------------------------------
        # HISTORIAL
        # --------------------------------

        reserva_id = cursor.lastrowid

        reserva_nueva = conexion.execute("""
            SELECT *
            FROM reservas
            WHERE id = ?
        """, (
            reserva_id,
        )).fetchone()

        registrar_historial(
            conexion=conexion,
            reserva_id=reserva_id,
            accion="CREADA",
            detalle="Se creó la reserva.",
            datos_nuevos=dict(
                reserva_nueva
            )
        )

        conexion.commit()
        conexion.close()

        return redirect(
            url_for("reservas")
        )


    # --------------------------------
    # MOSTRAR FORMULARIO
    # --------------------------------

    conexion.close()

    return render_template(
        "nueva_reserva.html",
        empresas=empresas,
        tipos_visita=tipos_visita,
        fecha_predeterminada=fecha_predeterminada,
        hora_predeterminada=hora_predeterminada
    )

@app.route("/reservas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_reserva(id):

    conexion = conectar()

    # --------------------------------
    # OBTENER RESERVA
    # --------------------------------

    reserva = conexion.execute("""
        SELECT *
        FROM reservas
        WHERE id = ?
    """, (id,)).fetchone()

    if reserva is None:
        conexion.close()
        return "Reserva no encontrada", 404


    # --------------------------------
    # EMPRESAS
    # --------------------------------

    empresas = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM empresas
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # TIPOS DE VISITA
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # GUARDAR CAMBIOS
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        empresa_id = request.form.get(
            "empresa_id",
            ""
        )

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        nombre_reserva = texto_mayusculas(
            request.form.get("nombre_reserva", "")
        )

        mayores = request.form.get(
            "mayores",
            "0"
        )

        menores = request.form.get(
            "menores",
            "0"
        )

        nacionalidad = texto_mayusculas(
            request.form.get("nacionalidad", "")
        )

        voucher = texto_mayusculas(
            request.form.get("voucher", "")
        )

        guia = texto_mayusculas(
            request.form.get("guia", "")
        )

        notas = texto_mayusculas(
            request.form.get("notas", "")
        )


        # --------------------------------
        # VALIDAR TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT
                id,
                nombre,
                estado
            FROM tipos_visita
            WHERE id = ?
        """, (
            tipo_visita_id,
        )).fetchone()

        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )


        # Permitir conservar un tipo inactivo
        # si ya pertenecía a esta reserva.
        if (
            tipo_visita["estado"] != "ACTIVO"
            and str(tipo_visita_id)
            != str(reserva["tipo_visita_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar un tipo de visita inactivo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )

        # Permitir conservar un tipo inactivo
        # si ya pertenecía a esta reserva.
        if (
            tipo_visita["estado"] != "ACTIVO"
            and str(tipo_visita_id)
            != str(reserva["tipo_visita_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar un tipo de visita inactivo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )


        # --------------------------------
        # VALIDAR PASAJEROS
        # --------------------------------

        try:

            mayores = int(mayores)
            menores = int(menores)

        except ValueError:

            conexion.close()

            flash(
                "La cantidad de pasajeros debe ser un número válido.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )


        if mayores < 0 or menores < 0:

            conexion.close()

            flash(
                "La cantidad de pasajeros no puede ser negativa.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )


        if mayores + menores <= 0:

            conexion.close()

            flash(
                "La reserva debe tener al menos 1 pasajero.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_reserva",
                    id=id
                )
            )


        # --------------------------------
        # DATOS ANTERIORES
        # --------------------------------

        datos_anteriores = dict(reserva)


        # --------------------------------
        # DATOS ANTERIORES
        # --------------------------------

        datos_anteriores = dict(reserva)


        # --------------------------------
        # ACTUALIZAR
        # --------------------------------

        conexion.execute("""
            UPDATE reservas

            SET
                fecha = ?,
                hora = ?,
                empresa_id = ?,
                tipo_visita_id = ?,
                nombre_reserva = ?,
                mayores = ?,
                menores = ?,
                nacionalidad = ?,
                voucher = ?,
                guia = ?,
                notas = ?

            WHERE id = ?
        """, (
            fecha,
            hora,
            empresa_id,
            tipo_visita_id,
            nombre_reserva,
            mayores,
            menores,
            nacionalidad,
            voucher,
            guia,
            notas,
            id
        ))


        # --------------------------------
        # OBTENER DATOS NUEVOS
        # --------------------------------

        reserva_actualizada = conexion.execute("""
            SELECT *
            FROM reservas
            WHERE id = ?
        """, (
            id,
        )).fetchone()

        datos_nuevos = dict(
            reserva_actualizada
        )


        # --------------------------------
        # DETECTAR CAMBIOS
        # --------------------------------

        nombres_campos = {
            "fecha": "Día",
            "hora": "Hora de visita",
            "empresa_id": "Empresa",
            "tipo_visita_id": "Tipo de visita",
            "nombre_reserva": "Reserva",
            "mayores": "Mayores",
            "menores": "Menores",
            "nacionalidad": "Nacionalidad",
            "voucher": "Voucher",
            "guia": "Guía",
            "notas": "Notas"
        }

        cambios = []

        for campo, nombre_visible in nombres_campos.items():

            valor_anterior = datos_anteriores.get(
                campo
            )

            valor_nuevo = datos_nuevos.get(
                campo
            )

            if str(valor_anterior) != str(valor_nuevo):

                anterior_texto = (
                    str(valor_anterior)
                    if valor_anterior not in (
                        None,
                        ""
                    )
                    else "—"
                )

                nuevo_texto = (
                    str(valor_nuevo)
                    if valor_nuevo not in (
                        None,
                        ""
                    )
                    else "—"
                )

                cambios.append(
                    f"{nombre_visible}: "
                    f"{anterior_texto} → "
                    f"{nuevo_texto}"
                )


        # --------------------------------
        # HISTORIAL
        # --------------------------------

        if cambios:

            registrar_historial(
                conexion=conexion,
                reserva_id=id,
                accion="EDITADA",
                detalle="; ".join(
                    cambios
                ),
                datos_anteriores=datos_anteriores,
                datos_nuevos=datos_nuevos
            )


        conexion.commit()
        conexion.close()

        return redirect(
            url_for("reservas")
        )


    # --------------------------------
    # MOSTRAR FORMULARIO
    # --------------------------------

    conexion.close()

    return render_template(
        "editar_reserva.html",
        reserva=reserva,
        empresas=empresas,
        tipos_visita=tipos_visita
    )

@app.route("/reservas/<int:id>/anular", methods=["POST"])
@login_required
def anular_reserva(id):

    conexion = conectar()

    reserva = conexion.execute(
        """
        SELECT *
        FROM reservas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if reserva is None:
        conexion.close()
        return "Reserva no encontrada.", 404

    # Evita registrar dos anulaciones iguales.
    if reserva["estado"] == "ANULADA":
        conexion.close()
        return redirect(url_for("reservas"))

    datos_anteriores = dict(reserva)

    conexion.execute(
        """
        UPDATE reservas
        SET estado = 'ANULADA'
        WHERE id = ?
        """,
        (id,)
    )

    reserva_anulada = conexion.execute(
        """
        SELECT *
        FROM reservas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    registrar_historial(
        conexion=conexion,
        reserva_id=id,
        accion="ANULADA",
        detalle="Se anuló la reserva.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=dict(reserva_anulada)
    )

    conexion.commit()
    conexion.close()

    return redirect(url_for("reservas"))

@app.route("/reservas/<int:id>/reactivar", methods=["POST"])
@login_required
def reactivar_reserva(id):

    conexion = conectar()

    reserva = conexion.execute(
        """
        SELECT *
        FROM reservas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if reserva is None:
        conexion.close()
        return "Reserva no encontrada.", 404

    # Evita registrar dos reactivaciones iguales.
    if reserva["estado"] == "ACTIVA":
        conexion.close()
        return redirect(url_for("reservas"))

    datos_anteriores = dict(reserva)

    conexion.execute(
        """
        UPDATE reservas
        SET estado = 'ACTIVA'
        WHERE id = ?
        """,
        (id,)
    )

    reserva_reactivada = conexion.execute(
        """
        SELECT *
        FROM reservas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    registrar_historial(
        conexion=conexion,
        reserva_id=id,
        accion="REACTIVADA",
        detalle="Se reactivó la reserva.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=dict(reserva_reactivada)
    )

    conexion.commit()
    conexion.close()

    return redirect(url_for("reservas"))

@app.route("/reservas/<int:id>/historial")
@login_required
def historial_reserva(id):

    conexion = conectar()

    reserva = conexion.execute("""
        SELECT
            reservas.*,
            empresas.nombre AS empresa_nombre,
            tipos_visita.nombre AS tipo_visita_nombre

        FROM reservas
        INNER JOIN empresas
            ON reservas.empresa_id = empresas.id
        INNER JOIN tipos_visita
            ON reservas.tipo_visita_id = tipos_visita.id
        WHERE reservas.id = ?
    """, (id,)).fetchone()

    if reserva is None:
        conexion.close()
        return "Reserva no encontrada.", 404

    movimientos = conexion.execute("""
        SELECT
            historial_reservas.*,
            usuarios.nombre AS usuario_nombre
        FROM historial_reservas
        INNER JOIN usuarios
            ON historial_reservas.usuario_id = usuarios.id
        WHERE historial_reservas.reserva_id = ?
        ORDER BY
            historial_reservas.fecha_hora DESC,
            historial_reservas.id DESC
    """, (id,)).fetchall()

    conexion.close()

    return render_template(
        "historial_reserva.html",
        reserva=reserva,
        movimientos=movimientos
    )

@app.route("/reservas/exportar")
@login_required
def exportar_reservas():

    conexion = conectar()

    # -----------------------------
    # RECIBIR FILTROS
    # -----------------------------

    empresa_id = request.args.get(
        "empresa_id",
        ""
    )

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    nacionalidad = request.args.get(
        "nacionalidad",
        ""
    )

    # Por defecto exporta reservas activas.
    # Si el usuario selecciona "Todas",
    # llega vacío.
    estado = request.args.get(
        "estado",
        "ACTIVA"
    )

    busqueda = request.args.get(
        "busqueda",
        ""
    ).strip()


    # -----------------------------
    # ARMAR CONSULTA
    # -----------------------------

    condiciones = []
    parametros = []


    if empresa_id:

        condiciones.append(
            "reservas.empresa_id = ?"
        )

        parametros.append(
            empresa_id
        )


    if fecha_desde:

        condiciones.append(
            "reservas.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "reservas.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_visita_id:

        condiciones.append(
            "reservas.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if nacionalidad:

        condiciones.append(
            "reservas.nacionalidad = ?"
        )

        parametros.append(
            nacionalidad
        )


    if estado:

        condiciones.append(
            "reservas.estado = ?"
        )

        parametros.append(
            estado
        )


    if busqueda:

        condiciones.append("""
            (
                reservas.nombre_reserva LIKE ?
                OR COALESCE(
                    reservas.voucher,
                    ''
                ) LIKE ?
            )
        """)

        texto = f"%{busqueda}%"

        parametros.append(texto)
        parametros.append(texto)


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # -----------------------------
    # OBTENER DATOS
    # -----------------------------

    reservas = conexion.execute(
        f"""
        SELECT
            reservas.fecha,
            reservas.hora,
            reservas.creado_en,

            empresas.nombre
                AS empresa,

            tipos_visita.nombre
                AS tipo_visita,

            reservas.nombre_reserva,
            reservas.mayores,
            reservas.menores,
            reservas.nacionalidad,
            reservas.voucher,
            reservas.guia,
            reservas.notas,
            reservas.estado

        FROM reservas

        INNER JOIN empresas
            ON reservas.empresa_id
                = empresas.id

        INNER JOIN tipos_visita
            ON reservas.tipo_visita_id
                = tipos_visita.id

        {where_sql}

        ORDER BY
            reservas.fecha ASC,
            reservas.hora ASC,
            reservas.id ASC
        """,
        parametros
    ).fetchall()

    conexion.close()


    # -----------------------------
    # CREAR EXCEL
    # -----------------------------

    libro = Workbook()

    hoja = libro.active
    hoja.title = "Reservas"


    encabezados = [
        "Fecha de visita",
        "Hora de visita",
        "Cargada el",
        "Empresa",
        "Tipo de visita",
        "Reserva a nombre de",
        "Mayores",
        "Menores",
        "Nacionalidad",
        "Voucher",
        "Guía",
        "Notas",
        "Estado"
    ]

    hoja.append(encabezados)


    # -----------------------------
    # AGREGAR DATOS
    # -----------------------------

    for reserva in reservas:

        fecha_visita = None
        hora_visita = None
        fecha_carga = None


        if reserva["fecha"]:

            fecha_visita = datetime.strptime(
                reserva["fecha"],
                "%Y-%m-%d"
            ).date()


        if reserva["hora"]:

            hora_visita = datetime.strptime(
                reserva["hora"],
                "%H:%M"
            ).time()


        if reserva["creado_en"]:

            fecha_carga = datetime.strptime(
                reserva["creado_en"],
                "%Y-%m-%d %H:%M:%S"
            )


        hoja.append([
            fecha_visita,
            hora_visita,
            fecha_carga,
            reserva["empresa"],
            reserva["tipo_visita"],
            reserva["nombre_reserva"],
            reserva["mayores"],
            reserva["menores"],
            reserva["nacionalidad"],
            reserva["voucher"] or "",
            reserva["guia"] or "",
            reserva["notas"] or "",
            reserva["estado"]
        ])


        numero_fila = hoja.max_row


        hoja[
            f"A{numero_fila}"
        ].number_format = "dd/mm/yyyy"


        hoja[
            f"B{numero_fila}"
        ].number_format = "hh:mm"


        hoja[
            f"C{numero_fila}"
        ].number_format = "dd/mm/yyyy hh:mm"


    # -----------------------------
    # AJUSTAR COLUMNAS
    # -----------------------------

    anchos = {
        "A": 17,
        "B": 16,
        "C": 21,
        "D": 22,
        "E": 18,
        "F": 28,
        "G": 12,
        "H": 12,
        "I": 18,
        "J": 20,
        "K": 22,
        "L": 40,
        "M": 15
    }

    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    # -----------------------------
    # FILTRO Y ENCABEZADO FIJO
    # -----------------------------

    if hoja.max_row > 1:

        hoja.auto_filter.ref = (
            hoja.dimensions
        )

    hoja.freeze_panes = "A2"


    # -----------------------------
    # GUARDAR EN MEMORIA
    # -----------------------------

    archivo = BytesIO()

    libro.save(archivo)

    archivo.seek(0)


    fecha_archivo = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d"
    )


    nombre_archivo = (
        f"reservas_{fecha_archivo}.xlsx"
    )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )


@app.route("/empresas/<int:id>/inactivar", methods=["POST"])
@admin_required
def inactivar_empresa(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE empresas
        SET estado = 'INACTIVA'
        WHERE id = ?
    """, (id,))

    conexion.commit()
    conexion.close()

    return redirect(url_for("empresas"))

@app.route("/empresas/<int:id>/activar", methods=["POST"])
@admin_required
def activar_empresa(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE empresas
        SET estado = 'ACTIVA'
        WHERE id = ?
    """, (id,))

    conexion.commit()
    conexion.close()

    return redirect(url_for("empresas"))

@app.route("/herramientas")
@login_required
def herramientas():

    return render_template(
        "herramientas.html"
    )


@app.route("/herramientas/calculadora")
@login_required
def calculadora():

    return render_template(
        "calculadora.html"
    )


@app.route("/herramientas/contador-billetes")
@login_required
def contador_billetes():

    return render_template(
        "contador_billetes.html"
    )

@app.route("/herramientas/cierre-cajas")
@login_required
def cierre_cajas():

    return render_template(
        "cierre_cajas.html"
    )

@app.route("/administracion")
@login_required
@admin_required
def administracion():

    return render_template(
        "administracion.html"
    )

@app.route("/administracion/tipos-visita")
@login_required
@admin_required
def tipos_visita():

    conexion = conectar()

    tipos = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()

    conexion.close()

    return render_template(
        "tipos_visita.html",
        tipos=tipos
    )


@app.route(
    "/administracion/tipos-visita/nuevo",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def nuevo_tipo_visita():

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre:

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for("nuevo_tipo_visita")
            )

        conexion = conectar()

        existente = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE LOWER(nombre) = LOWER(?)
        """, (
            nombre,
        )).fetchone()

        if existente:

            conexion.close()

            flash(
                "Ya existe un tipo de visita con ese nombre.",
                "error"
            )

            return redirect(
                url_for("nuevo_tipo_visita")
            )

        conexion.execute("""
            INSERT INTO tipos_visita (
                nombre,
                estado
            )
            VALUES (?, 'ACTIVO')
        """, (
            nombre,
        ))

        conexion.commit()
        conexion.close()

        flash(
            "Tipo de visita creado correctamente.",
            "exito"
        )

        return redirect(
            url_for("tipos_visita")
        )

    return render_template(
        "nuevo_tipo_visita.html"
    )


@app.route(
    "/administracion/tipos-visita/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def editar_tipo_visita(id):

    conexion = conectar()

    tipo = conexion.execute("""
        SELECT *
        FROM tipos_visita
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if tipo is None:

        conexion.close()
        return "Tipo de visita no encontrado", 404

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre:

            conexion.close()

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_visita",
                    id=id
                )
            )

        existente = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE LOWER(nombre) = LOWER(?)
            AND id != ?
        """, (
            nombre,
            id
        )).fetchone()

        if existente:

            conexion.close()

            flash(
                "Ya existe otro tipo de visita con ese nombre.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_visita",
                    id=id
                )
            )

        conexion.execute("""
            UPDATE tipos_visita
            SET nombre = ?
            WHERE id = ?
        """, (
            nombre,
            id
        ))

        conexion.commit()
        conexion.close()

        flash(
            "Tipo de visita actualizado correctamente.",
            "exito"
        )

        return redirect(
            url_for("tipos_visita")
        )

    conexion.close()

    return render_template(
        "editar_tipo_visita.html",
        tipo=tipo
    )


@app.route(
    "/administracion/tipos-visita/<int:id>/inactivar",
    methods=["POST"]
)
@login_required
@admin_required
def inactivar_tipo_visita(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE tipos_visita
        SET estado = 'INACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Tipo de visita inactivado.",
        "exito"
    )

    return redirect(
        url_for("tipos_visita")
    )


@app.route(
    "/administracion/tipos-visita/<int:id>/activar",
    methods=["POST"]
)
@login_required
@admin_required
def activar_tipo_visita(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE tipos_visita
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Tipo de visita activado.",
        "exito"
    )

    return redirect(
        url_for("tipos_visita")
    )

@app.route("/administracion/tipos-protocolo")
@login_required
@admin_required
def tipos_protocolo():

    conexion = conectar()

    tipos = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_protocolo
        ORDER BY nombre
    """).fetchall()

    conexion.close()

    return render_template(
        "tipos_protocolo.html",
        tipos=tipos
    )


@app.route(
    "/administracion/tipos-protocolo/nuevo",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def nuevo_tipo_protocolo():

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre:

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for("nuevo_tipo_protocolo")
            )

        conexion = conectar()

        existente = conexion.execute("""
            SELECT id
            FROM tipos_protocolo
            WHERE LOWER(nombre) = LOWER(?)
        """, (
            nombre,
        )).fetchone()

        if existente:

            conexion.close()

            flash(
                "Ya existe un tipo de protocolo con ese nombre.",
                "error"
            )

            return redirect(
                url_for("nuevo_tipo_protocolo")
            )

        conexion.execute("""
            INSERT INTO tipos_protocolo (
                nombre,
                estado
            )
            VALUES (?, 'ACTIVO')
        """, (
            nombre,
        ))

        conexion.commit()
        conexion.close()

        flash(
            "Tipo de protocolo creado correctamente.",
            "exito"
        )

        return redirect(
            url_for("tipos_protocolo")
        )

    return render_template(
        "nuevo_tipo_protocolo.html"
    )


@app.route(
    "/administracion/tipos-protocolo/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def editar_tipo_protocolo(id):

    conexion = conectar()

    tipo = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_protocolo
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if tipo is None:

        conexion.close()

        return (
            "Tipo de protocolo no encontrado",
            404
        )

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre:

            conexion.close()

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_protocolo",
                    id=id
                )
            )

        existente = conexion.execute("""
            SELECT id
            FROM tipos_protocolo
            WHERE LOWER(nombre) = LOWER(?)
            AND id != ?
        """, (
            nombre,
            id
        )).fetchone()

        if existente:

            conexion.close()

            flash(
                "Ya existe otro tipo de protocolo con ese nombre.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_protocolo",
                    id=id
                )
            )

        conexion.execute("""
            UPDATE tipos_protocolo
            SET nombre = ?
            WHERE id = ?
        """, (
            nombre,
            id
        ))

        conexion.commit()
        conexion.close()

        flash(
            "Tipo de protocolo actualizado correctamente.",
            "exito"
        )

        return redirect(
            url_for("tipos_protocolo")
        )

    conexion.close()

    return render_template(
        "editar_tipo_protocolo.html",
        tipo=tipo
    )


@app.route(
    "/administracion/tipos-protocolo/<int:id>/inactivar",
    methods=["POST"]
)
@login_required
@admin_required
def inactivar_tipo_protocolo(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE tipos_protocolo
        SET estado = 'INACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Tipo de protocolo inactivado.",
        "exito"
    )

    return redirect(
        url_for("tipos_protocolo")
    )


@app.route(
    "/administracion/tipos-protocolo/<int:id>/activar",
    methods=["POST"]
)
@login_required
@admin_required
def activar_tipo_protocolo(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE tipos_protocolo
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Tipo de protocolo activado.",
        "exito"
    )

    return redirect(
        url_for("tipos_protocolo")
    )

@app.route(
    "/protocolos/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
def editar_protocolo(id):

    conexion = conectar()

    protocolo = conexion.execute("""
        SELECT *
        FROM protocolos
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if protocolo is None:

        conexion.close()

        return "Protocolo no encontrado", 404


    # --------------------------------
    # CATÁLOGOS
    # --------------------------------

    tipos_protocolo = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_protocolo
        ORDER BY nombre
    """).fetchall()

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    # Diccionarios para mostrar nombres
    # en el historial.

    nombres_protocolos = {
        tipo["id"]: tipo["nombre"]
        for tipo in tipos_protocolo
    }

    nombres_visitas = {
        tipo["id"]: tipo["nombre"]
        for tipo in tipos_visita
    }


    # --------------------------------
    # GUARDAR CAMBIOS
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        tipo_protocolo_id = request.form.get(
            "tipo_protocolo_id",
            ""
        )

        tipo_visita_id = request.form.get(
            "tipo_visita_id",
            ""
        )

        cantidad_texto = request.form.get(
            "cantidad",
            ""
        ).strip()

        descripcion = texto_mayusculas(
            request.form.get("descripcion", "")
        )


        # --------------------------------
        # CANTIDAD
        # --------------------------------

        try:

            cantidad = int(
                cantidad_texto
            )

        except ValueError:

            cantidad = 0


        if cantidad <= 0:

            conexion.close()

            flash(
                "La cantidad debe ser mayor a 0.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_protocolo",
                    id=id
                )
            )


        # --------------------------------
        # VALIDAR TIPO DE PROTOCOLO
        # --------------------------------

        tipo_protocolo = conexion.execute("""
            SELECT
                id,
                nombre,
                estado
            FROM tipos_protocolo
            WHERE id = ?
        """, (
            tipo_protocolo_id,
        )).fetchone()


        if tipo_protocolo is None:

            conexion.close()

            flash(
                "El tipo de protocolo seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_protocolo",
                    id=id
                )
            )


        # Puede conservar uno inactivo
        # si ya era el asignado.

        if (
            tipo_protocolo["estado"] != "ACTIVO"
            and str(tipo_protocolo_id)
            != str(protocolo["tipo_protocolo_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar un tipo de protocolo inactivo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_protocolo",
                    id=id
                )
            )


        # --------------------------------
        # VALIDAR TIPO DE VISITA
        # --------------------------------

        tipo_visita = conexion.execute("""
            SELECT
                id,
                nombre,
                estado
            FROM tipos_visita
            WHERE id = ?
        """, (
            tipo_visita_id,
        )).fetchone()


        if tipo_visita is None:

            conexion.close()

            flash(
                "El tipo de visita seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_protocolo",
                    id=id
                )
            )


        if (
            tipo_visita["estado"] != "ACTIVO"
            and str(tipo_visita_id)
            != str(protocolo["tipo_visita_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar un tipo de visita inactivo.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_protocolo",
                    id=id
                )
            )


        # --------------------------------
        # DATOS ANTERIORES
        # --------------------------------

        datos_anteriores = dict(
            protocolo
        )


        # --------------------------------
        # ACTUALIZAR
        # --------------------------------

        conexion.execute("""
            UPDATE protocolos

            SET
                fecha = ?,
                tipo_protocolo_id = ?,
                tipo_visita_id = ?,
                cantidad = ?,
                descripcion = ?

            WHERE id = ?
        """, (
            fecha,
            tipo_protocolo_id,
            tipo_visita_id,
            cantidad,
            descripcion,
            id
        ))


        # --------------------------------
        # DATOS NUEVOS
        # --------------------------------

        protocolo_actualizado = conexion.execute("""
            SELECT *
            FROM protocolos
            WHERE id = ?
        """, (
            id,
        )).fetchone()

        datos_nuevos = dict(
            protocolo_actualizado
        )


        # --------------------------------
        # DETECTAR CAMBIOS
        # --------------------------------

        cambios = []


        # Fecha

        if (
            datos_anteriores["fecha"]
            != datos_nuevos["fecha"]
        ):

            cambios.append(
                f"Fecha: "
                f"{datos_anteriores['fecha']} → "
                f"{datos_nuevos['fecha']}"
            )


        # Tipo de protocolo

        if (
            str(datos_anteriores["tipo_protocolo_id"])
            != str(datos_nuevos["tipo_protocolo_id"])
        ):

            nombre_anterior = nombres_protocolos.get(
                datos_anteriores["tipo_protocolo_id"],
                "Desconocido"
            )

            nombre_nuevo = tipo_protocolo[
                "nombre"
            ]

            cambios.append(
                f"Tipo de protocolo: "
                f"{nombre_anterior} → "
                f"{nombre_nuevo}"
            )


        # Tipo de visita

        if (
            str(datos_anteriores["tipo_visita_id"])
            != str(datos_nuevos["tipo_visita_id"])
        ):

            nombre_anterior = nombres_visitas.get(
                datos_anteriores["tipo_visita_id"],
                "Desconocido"
            )

            nombre_nuevo = tipo_visita[
                "nombre"
            ]

            cambios.append(
                f"Tipo de visita: "
                f"{nombre_anterior} → "
                f"{nombre_nuevo}"
            )


        # Cantidad

        if (
            datos_anteriores["cantidad"]
            != datos_nuevos["cantidad"]
        ):

            cambios.append(
                f"Cantidad: "
                f"{datos_anteriores['cantidad']} → "
                f"{datos_nuevos['cantidad']}"
            )


        # Descripción

        descripcion_anterior = (
            datos_anteriores["descripcion"]
            or "—"
        )

        descripcion_nueva = (
            datos_nuevos["descripcion"]
            or "—"
        )

        if (
            descripcion_anterior
            != descripcion_nueva
        ):

            cambios.append(
                f"Descripción: "
                f"{descripcion_anterior} → "
                f"{descripcion_nueva}"
            )


        # --------------------------------
        # REGISTRAR HISTORIAL
        # --------------------------------

        if cambios:

            registrar_historial_protocolo(
                conexion=conexion,
                protocolo_id=id,
                accion="EDITADO",
                detalle="; ".join(
                    cambios
                ),
                datos_anteriores=
                    datos_anteriores,
                datos_nuevos=
                    datos_nuevos
            )


        conexion.commit()
        conexion.close()

        flash(
            "Protocolo actualizado correctamente.",
            "exito"
        )

        return redirect(
            url_for("protocolos")
        )


    # --------------------------------
    # MOSTRAR FORMULARIO
    # --------------------------------

    conexion.close()

    return render_template(
        "editar_protocolo.html",
        protocolo=protocolo,
        tipos_protocolo=tipos_protocolo,
        tipos_visita=tipos_visita
    )

@app.route(
    "/protocolos/<int:id>/anular",
    methods=["POST"]
)
@login_required
def anular_protocolo(id):

    conexion = conectar()

    protocolo = conexion.execute("""
        SELECT *
        FROM protocolos
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if protocolo is None:

        conexion.close()

        return "Protocolo no encontrado", 404


    if protocolo["estado"] != "ACTIVO":

        conexion.close()

        flash(
            "El protocolo ya se encuentra anulado.",
            "error"
        )

        return redirect(
            url_for("protocolos")
        )


    datos_anteriores = dict(
        protocolo
    )


    conexion.execute("""
        UPDATE protocolos
        SET estado = 'ANULADO'
        WHERE id = ?
    """, (
        id,
    ))


    protocolo_actualizado = conexion.execute("""
        SELECT *
        FROM protocolos
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    registrar_historial_protocolo(
        conexion=conexion,
        protocolo_id=id,
        accion="ANULADO",
        detalle="Se anuló el protocolo.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=dict(
            protocolo_actualizado
        )
    )


    conexion.commit()
    conexion.close()


    flash(
        "Protocolo anulado correctamente.",
        "exito"
    )

    return redirect(
        url_for("protocolos")
    )


@app.route(
    "/protocolos/<int:id>/reactivar",
    methods=["POST"]
)
@login_required
def reactivar_protocolo(id):

    conexion = conectar()

    protocolo = conexion.execute("""
        SELECT *
        FROM protocolos
        WHERE id = ?
    """, (
        id,
    )).fetchone()

    if protocolo is None:

        conexion.close()

        return "Protocolo no encontrado", 404


    if protocolo["estado"] != "ANULADO":

        conexion.close()

        flash(
            "El protocolo ya se encuentra activo.",
            "error"
        )

        return redirect(
            url_for("protocolos")
        )


    datos_anteriores = dict(
        protocolo
    )


    conexion.execute("""
        UPDATE protocolos
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))


    protocolo_actualizado = conexion.execute("""
        SELECT *
        FROM protocolos
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    registrar_historial_protocolo(
        conexion=conexion,
        protocolo_id=id,
        accion="REACTIVADO",
        detalle="Se reactivó el protocolo.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=dict(
            protocolo_actualizado
        )
    )


    conexion.commit()
    conexion.close()


    flash(
        "Protocolo reactivado correctamente.",
        "exito"
    )

    return redirect(
        url_for("protocolos")
    )

@app.route(
    "/protocolos/<int:id>/historial"
)
@login_required
def historial_protocolo(id):

    conexion = conectar()

    protocolo = conexion.execute("""
        SELECT
            protocolos.*,

            tipos_protocolo.nombre
                AS tipo_protocolo_nombre,

            tipos_visita.nombre
                AS tipo_visita_nombre

        FROM protocolos

        INNER JOIN tipos_protocolo
            ON protocolos.tipo_protocolo_id
                = tipos_protocolo.id

        INNER JOIN tipos_visita
            ON protocolos.tipo_visita_id
                = tipos_visita.id

        WHERE protocolos.id = ?
    """, (
        id,
    )).fetchone()


    if protocolo is None:

        conexion.close()

        return "Protocolo no encontrado", 404


    historial = conexion.execute("""
        SELECT
            historial_protocolos.*,

            usuarios.nombre
                AS usuario_nombre

        FROM historial_protocolos

        INNER JOIN usuarios
            ON historial_protocolos.usuario_id
                = usuarios.id

        WHERE historial_protocolos.protocolo_id = ?

        ORDER BY
            historial_protocolos.fecha_hora DESC,
            historial_protocolos.id DESC
    """, (
        id,
    )).fetchall()


    conexion.close()


    return render_template(
        "historial_protocolo.html",
        protocolo=protocolo,
        historial=historial
    )

@app.route("/protocolos/exportar")
@login_required
def exportar_protocolos():

    conexion = conectar()

    # -----------------------------
    # RECIBIR FILTROS
    # -----------------------------

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    tipo_protocolo_id = request.args.get(
        "tipo_protocolo_id",
        ""
    )

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )


    # -----------------------------
    # ARMAR CONSULTA
    # -----------------------------

    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "protocolos.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "protocolos.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if tipo_protocolo_id:

        condiciones.append(
            "protocolos.tipo_protocolo_id = ?"
        )

        parametros.append(
            tipo_protocolo_id
        )


    if tipo_visita_id:

        condiciones.append(
            "protocolos.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if estado:

        condiciones.append(
            "protocolos.estado = ?"
        )

        parametros.append(
            estado
        )


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # -----------------------------
    # OBTENER DATOS
    # -----------------------------

    protocolos = conexion.execute(
        f"""
        SELECT
            protocolos.fecha,

            tipos_protocolo.nombre
                AS tipo_protocolo,

            tipos_visita.nombre
                AS tipo_visita,

            protocolos.cantidad,
            protocolos.descripcion,

            usuarios.nombre
                AS usuario_nombre,

            protocolos.creado_en,
            protocolos.estado

        FROM protocolos

        INNER JOIN tipos_protocolo
            ON protocolos.tipo_protocolo_id
                = tipos_protocolo.id

        INNER JOIN tipos_visita
            ON protocolos.tipo_visita_id
                = tipos_visita.id

        INNER JOIN usuarios
            ON protocolos.usuario_id
                = usuarios.id

        {where_sql}

        ORDER BY
            protocolos.fecha ASC,
            protocolos.id ASC
        """,
        parametros
    ).fetchall()

    conexion.close()


    # -----------------------------
    # CREAR EXCEL
    # -----------------------------

    libro = Workbook()

    hoja = libro.active
    hoja.title = "Protocolos"


    encabezados = [
        "Fecha",
        "Tipo de protocolo",
        "Tipo de visita",
        "Cantidad",
        "Descripción",
        "Cargado por",
        "Cargado el",
        "Estado"
    ]

    hoja.append(
        encabezados
    )


    # -----------------------------
    # AGREGAR DATOS
    # -----------------------------

    total_entradas = 0


    for protocolo in protocolos:

        fecha = None
        fecha_carga = None


        if protocolo["fecha"]:

            fecha = datetime.strptime(
                protocolo["fecha"],
                "%Y-%m-%d"
            ).date()


        if protocolo["creado_en"]:

            fecha_carga = datetime.strptime(
                protocolo["creado_en"],
                "%Y-%m-%d %H:%M:%S"
            )


        cantidad = protocolo[
            "cantidad"
        ]

        total_entradas += cantidad


        hoja.append([
            fecha,
            protocolo["tipo_protocolo"],
            protocolo["tipo_visita"],
            cantidad,
            protocolo["descripcion"] or "",
            protocolo["usuario_nombre"],
            fecha_carga,
            protocolo["estado"]
        ])


        numero_fila = hoja.max_row


        hoja[
            f"A{numero_fila}"
        ].number_format = "dd/mm/yyyy"


        hoja[
            f"G{numero_fila}"
        ].number_format = (
            "dd/mm/yyyy hh:mm"
        )


    # -----------------------------
    # TOTAL
    # -----------------------------

    fila_total = hoja.max_row + 2

    hoja[
        f"C{fila_total}"
    ] = "TOTAL DE ENTRADAS"

    hoja[
        f"D{fila_total}"
    ] = total_entradas


    # -----------------------------
    # ANCHOS
    # -----------------------------

    anchos = {
        "A": 15,
        "B": 25,
        "C": 20,
        "D": 12,
        "E": 40,
        "F": 22,
        "G": 21,
        "H": 15
    }

    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    # -----------------------------
    # FILTROS
    # -----------------------------

    if len(protocolos) > 0:

        hoja.auto_filter.ref = (
            f"A1:H{len(protocolos) + 1}"
        )


    hoja.freeze_panes = "A2"


    # -----------------------------
    # GUARDAR EN MEMORIA
    # -----------------------------

    archivo = BytesIO()

    libro.save(
        archivo
    )

    archivo.seek(0)


    fecha_archivo = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d"
    )


    nombre_archivo = (
        f"protocolos_{fecha_archivo}.xlsx"
    )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        )
    )

@app.route("/administracion/categorias-socio")
@login_required
@admin_required
def categorias_socio():

    conexion = conectar()

    categorias = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM categorias_socio
        ORDER BY nombre
    """).fetchall()

    conexion.close()

    return render_template(
        "categorias_socio.html",
        categorias=categorias
    )


@app.route(
    "/administracion/categorias-socio/nueva",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def nueva_categoria_socio():

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        if not nombre:

            flash(
                "Debés ingresar el nombre de la categoría.",
                "error"
            )

            return redirect(
                url_for("nueva_categoria_socio")
            )


        conexion = conectar()

        existente = conexion.execute("""
            SELECT id
            FROM categorias_socio
            WHERE UPPER(nombre) = UPPER(?)
        """, (
            nombre,
        )).fetchone()


        if existente is not None:

            conexion.close()

            flash(
                "Ya existe una categoría con ese nombre.",
                "error"
            )

            return redirect(
                url_for("nueva_categoria_socio")
            )


        conexion.execute("""
            INSERT INTO categorias_socio (
                nombre,
                estado
            )
            VALUES (?, 'ACTIVO')
        """, (
            nombre,
        ))

        conexion.commit()
        conexion.close()


        flash(
            "Categoría creada correctamente.",
            "exito"
        )

        return redirect(
            url_for("categorias_socio")
        )


    return render_template(
        "nueva_categoria_socio.html"
    )


@app.route(
    "/administracion/categorias-socio/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def editar_categoria_socio(id):

    conexion = conectar()

    categoria = conexion.execute("""
        SELECT *
        FROM categorias_socio
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if categoria is None:

        conexion.close()

        return (
            "Categoría no encontrada",
            404
        )


    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )


        if not nombre:

            conexion.close()

            flash(
                "Debés ingresar el nombre de la categoría.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_categoria_socio",
                    id=id
                )
            )


        existente = conexion.execute("""
            SELECT id
            FROM categorias_socio
            WHERE UPPER(nombre) = UPPER(?)
            AND id != ?
        """, (
            nombre,
            id
        )).fetchone()


        if existente is not None:

            conexion.close()

            flash(
                "Ya existe otra categoría con ese nombre.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_categoria_socio",
                    id=id
                )
            )


        conexion.execute("""
            UPDATE categorias_socio
            SET nombre = ?
            WHERE id = ?
        """, (
            nombre,
            id
        ))

        conexion.commit()
        conexion.close()


        flash(
            "Categoría actualizada correctamente.",
            "exito"
        )

        return redirect(
            url_for("categorias_socio")
        )


    conexion.close()

    return render_template(
        "editar_categoria_socio.html",
        categoria=categoria
    )


@app.post(
    "/administracion/categorias-socio/<int:id>/inactivar"
)
@login_required
@admin_required
def inactivar_categoria_socio(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE categorias_socio
        SET estado = 'INACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Categoría inactivada correctamente.",
        "exito"
    )

    return redirect(
        url_for("categorias_socio")
    )


@app.post(
    "/administracion/categorias-socio/<int:id>/activar"
)
@login_required
@admin_required
def activar_categoria_socio(id):

    conexion = conectar()

    conexion.execute("""
        UPDATE categorias_socio
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))

    conexion.commit()
    conexion.close()

    flash(
        "Categoría activada correctamente.",
        "exito"
    )

    return redirect(
        url_for("categorias_socio")
    )

def registrar_historial_nuevo_asociado(
    conexion,
    asociado_id,
    accion,
    detalle,
    datos_anteriores=None,
    datos_nuevos=None
):

    fecha_hora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    anteriores_json = (
        json.dumps(
            datos_anteriores,
            ensure_ascii=False
        )
        if datos_anteriores is not None
        else None
    )

    nuevos_json = (
        json.dumps(
            datos_nuevos,
            ensure_ascii=False
        )
        if datos_nuevos is not None
        else None
    )

    conexion.execute("""
        INSERT INTO historial_nuevos_asociados (
            asociado_id,
            usuario_id,
            accion,
            detalle,
            datos_anteriores,
            datos_nuevos,
            fecha_hora
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        asociado_id,
        session["usuario_id"],
        accion,
        detalle,
        anteriores_json,
        nuevos_json,
        fecha_hora
    ))

@app.route("/nuevos-asociados")
@login_required
def nuevos_asociados():

    conexion = conectar()


    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    categoria_socio_id = request.args.get(
        "categoria_socio_id",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )

    busqueda = request.args.get(
        "busqueda",
        ""
    ).strip()


    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "nuevos_asociados.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "nuevos_asociados.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if categoria_socio_id:

        condiciones.append(
            "nuevos_asociados.categoria_socio_id = ?"
        )

        parametros.append(
            categoria_socio_id
        )


    if estado:

        condiciones.append(
            "nuevos_asociados.estado = ?"
        )

        parametros.append(
            estado
        )


    if busqueda:

        condiciones.append("""
            (
                nuevos_asociados.nombre LIKE ?
                OR nuevos_asociados.dni LIKE ?
                OR categorias_socio.nombre LIKE ?
                OR usuarios_empleado.nombre LIKE ?
                OR nuevos_asociados.empleado_otro LIKE ?
            )
        """)

        busqueda_sql = (
            f"%{busqueda}%"
        )

        parametros.extend([
            busqueda_sql,
            busqueda_sql,
            busqueda_sql,
            busqueda_sql,
            busqueda_sql
        ])


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(
                condiciones
            )
        )


    asociados = conexion.execute(f"""
        SELECT
            nuevos_asociados.*,

            categorias_socio.nombre
                AS categoria_nombre,

            COALESCE(
                usuarios_empleado.nombre,
                nuevos_asociados.empleado_otro
            )
                AS empleado_nombre,

            usuarios_carga.nombre
                AS usuario_carga_nombre

        FROM nuevos_asociados

        INNER JOIN categorias_socio
            ON nuevos_asociados.categoria_socio_id
            = categorias_socio.id

        LEFT JOIN usuarios AS usuarios_empleado
            ON nuevos_asociados.empleado_usuario_id
            = usuarios_empleado.id

        INNER JOIN usuarios AS usuarios_carga
            ON nuevos_asociados.usuario_id
            = usuarios_carga.id

        {where_sql}

        ORDER BY
            nuevos_asociados.fecha DESC,
            nuevos_asociados.hora DESC,
            nuevos_asociados.id DESC
    """, parametros).fetchall()


    categorias = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM categorias_socio
        ORDER BY nombre
    """).fetchall()


    total_asociados = len(
        asociados
    )


    conexion.close()


    return render_template(
        "nuevos_asociados.html",
        asociados=asociados,
        categorias=categorias,
        total_asociados=total_asociados,

        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        categoria_socio_id=
            categoria_socio_id,
        estado=estado,
        busqueda=busqueda
    )

@app.route(
    "/nuevos-asociados/nuevo",
    methods=["GET", "POST"]
)
@login_required
def nuevo_asociado():

    conexion = conectar()


    categorias = conexion.execute("""
        SELECT
            id,
            nombre
        FROM categorias_socio
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    empleados = conexion.execute("""
        SELECT
            id,
            nombre
        FROM usuarios
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )


    fecha_predeterminada = (
        request.form.get("fecha")
        or ahora.strftime("%Y-%m-%d")
    )

    hora_predeterminada = (
        request.form.get("hora")
        or ahora.strftime("%H:%M")
    )


    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        nombre = texto_mayusculas(
            request.form.get(
                "nombre",
                ""
            )
        )

        dni = texto_mayusculas(
            request.form.get(
                "dni",
                ""
            )
        )

        categoria_socio_id = (
            request.form.get(
                "categoria_socio_id",
                ""
            )
        )

        empleado_seleccion = (
            request.form.get(
                "empleado",
                ""
            )
        )

        empleado_otro = texto_mayusculas(
            request.form.get(
                "empleado_otro",
                ""
            )
        )


        # --------------------------------
        # DATOS OBLIGATORIOS
        # --------------------------------

        if (
            not fecha
            or not hora
            or not nombre
            or not dni
        ):

            conexion.close()

            flash(
                "Completá todos los campos obligatorios.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_asociado"
                )
            )


        # --------------------------------
        # CATEGORÍA
        # --------------------------------

        categoria = conexion.execute("""
            SELECT id
            FROM categorias_socio
            WHERE id = ?
            AND estado = 'ACTIVO'
        """, (
            categoria_socio_id,
        )).fetchone()


        if categoria is None:

            conexion.close()

            flash(
                "La categoría seleccionada no es válida.",
                "error"
            )

            return redirect(
                url_for(
                    "nuevo_asociado"
                )
            )


        # --------------------------------
        # EMPLEADO
        # --------------------------------

        empleado_usuario_id = None


        if empleado_seleccion == "OTRO":

            if not empleado_otro:

                conexion.close()

                flash(
                    "Ingresá el nombre del empleado.",
                    "error"
                )

                return redirect(
                    url_for(
                        "nuevo_asociado"
                    )
                )

        else:

            empleado = conexion.execute("""
                SELECT id
                FROM usuarios
                WHERE id = ?
                AND estado = 'ACTIVO'
            """, (
                empleado_seleccion,
            )).fetchone()


            if empleado is None:

                conexion.close()

                flash(
                    "El empleado seleccionado no es válido.",
                    "error"
                )

                return redirect(
                    url_for(
                        "nuevo_asociado"
                    )
                )


            empleado_usuario_id = (
                empleado["id"]
            )

            empleado_otro = None


        # --------------------------------
        # USUARIO QUE CARGA
        # --------------------------------

        usuario_id = session.get(
            "usuario_id"
        )


        if not usuario_id:

            conexion.close()

            session.clear()

            return redirect(
                url_for("login")
            )


        creado_en = ahora.strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        # --------------------------------
        # INSERT
        # --------------------------------

        cursor = conexion.execute("""
            INSERT INTO nuevos_asociados (
                fecha,
                hora,
                nombre,
                dni,
                categoria_socio_id,
                empleado_usuario_id,
                empleado_otro,
                creado_en,
                usuario_id,
                estado
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'ACTIVO'
            )
        """, (
            fecha,
            hora,
            nombre,
            dni,
            categoria_socio_id,
            empleado_usuario_id,
            empleado_otro,
            creado_en,
            usuario_id
        ))


        asociado_id = (
            cursor.lastrowid
        )


        asociado_nuevo = conexion.execute("""
            SELECT *
            FROM nuevos_asociados
            WHERE id = ?
        """, (
            asociado_id,
        )).fetchone()


        registrar_historial_nuevo_asociado(
            conexion=conexion,
            asociado_id=asociado_id,
            accion="CREADO",
            detalle="Se creó el nuevo asociado.",
            datos_nuevos=dict(
                asociado_nuevo
            )
        )


        conexion.commit()
        conexion.close()


        flash(
            "Nuevo asociado cargado correctamente.",
            "exito"
        )


        return redirect(
            url_for(
                "nuevos_asociados"
            )
        )


    conexion.close()


    return render_template(
        "nuevo_asociado.html",
        categorias=categorias,
        empleados=empleados,
        fecha_predeterminada=
            fecha_predeterminada,
        hora_predeterminada=
            hora_predeterminada
    )

@app.post(
    "/nuevos-asociados/<int:id>/anular"
)
@login_required
def anular_asociado(id):

    conexion = conectar()


    asociado = conexion.execute("""
        SELECT *
        FROM nuevos_asociados
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if asociado is None:

        conexion.close()

        return (
            "Asociado no encontrado",
            404
        )


    if asociado["estado"] == "ANULADO":

        conexion.close()

        flash(
            "El asociado ya se encuentra anulado.",
            "error"
        )

        return redirect(
            url_for("nuevos_asociados")
        )


    datos_anteriores = dict(
        asociado
    )


    conexion.execute("""
        UPDATE nuevos_asociados
        SET estado = 'ANULADO'
        WHERE id = ?
    """, (
        id,
    ))


    asociado_actualizado = conexion.execute("""
        SELECT *
        FROM nuevos_asociados
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    datos_nuevos = dict(
        asociado_actualizado
    )


    registrar_historial_nuevo_asociado(
        conexion=conexion,
        asociado_id=id,
        accion="ANULADO",
        detalle="Se anuló el registro del asociado.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos
    )


    conexion.commit()
    conexion.close()


    flash(
        "Asociado anulado correctamente.",
        "exito"
    )


    return redirect(
        url_for("nuevos_asociados")
    )

@app.post(
    "/nuevos-asociados/<int:id>/reactivar"
)
@login_required
def reactivar_asociado(id):

    conexion = conectar()


    asociado = conexion.execute("""
        SELECT *
        FROM nuevos_asociados
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if asociado is None:

        conexion.close()

        return (
            "Asociado no encontrado",
            404
        )


    if asociado["estado"] == "ACTIVO":

        conexion.close()

        flash(
            "El asociado ya se encuentra activo.",
            "error"
        )

        return redirect(
            url_for("nuevos_asociados")
        )


    datos_anteriores = dict(
        asociado
    )


    conexion.execute("""
        UPDATE nuevos_asociados
        SET estado = 'ACTIVO'
        WHERE id = ?
    """, (
        id,
    ))


    asociado_actualizado = conexion.execute("""
        SELECT *
        FROM nuevos_asociados
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    datos_nuevos = dict(
        asociado_actualizado
    )


    registrar_historial_nuevo_asociado(
        conexion=conexion,
        asociado_id=id,
        accion="REACTIVADO",
        detalle="Se reactivó el registro del asociado.",
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos
    )


    conexion.commit()
    conexion.close()


    flash(
        "Asociado reactivado correctamente.",
        "exito"
    )


    return redirect(
        url_for("nuevos_asociados")
    )

@app.route(
    "/nuevos-asociados/<int:id>/editar",
    methods=["GET", "POST"]
)
@login_required
def editar_asociado(id):

    conexion = conectar()


    # --------------------------------
    # OBTENER ASOCIADO
    # --------------------------------

    asociado = conexion.execute("""
        SELECT *
        FROM nuevos_asociados
        WHERE id = ?
    """, (
        id,
    )).fetchone()


    if asociado is None:

        conexion.close()

        return (
            "Asociado no encontrado",
            404
        )


    # --------------------------------
    # CATEGORÍAS
    # --------------------------------

    categorias = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM categorias_socio
        ORDER BY nombre
    """).fetchall()


    nombres_categorias = {
        categoria["id"]: categoria["nombre"]
        for categoria in categorias
    }


    # --------------------------------
    # EMPLEADOS / USUARIOS
    # --------------------------------

    empleados = conexion.execute("""
        SELECT
            id,
            nombre,
            estado
        FROM usuarios
        ORDER BY nombre
    """).fetchall()


    nombres_empleados = {
        empleado["id"]: empleado["nombre"]
        for empleado in empleados
    }


    # --------------------------------
    # GUARDAR CAMBIOS
    # --------------------------------

    if request.method == "POST":

        fecha = request.form.get(
            "fecha",
            ""
        ).strip()

        hora = request.form.get(
            "hora",
            ""
        ).strip()

        nombre = texto_mayusculas(
            request.form.get(
                "nombre",
                ""
            )
        )

        dni = texto_mayusculas(
            request.form.get(
                "dni",
                ""
            )
        )

        categoria_socio_id = request.form.get(
            "categoria_socio_id",
            ""
        )

        empleado_seleccion = request.form.get(
            "empleado",
            ""
        )

        empleado_otro = texto_mayusculas(
            request.form.get(
                "empleado_otro",
                ""
            )
        )


        # --------------------------------
        # CAMPOS OBLIGATORIOS
        # --------------------------------

        if (
            not fecha
            or not hora
            or not nombre
            or not dni
        ):

            conexion.close()

            flash(
                "Completá todos los campos obligatorios.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_asociado",
                    id=id
                )
            )


        # --------------------------------
        # VALIDAR CATEGORÍA
        # --------------------------------

        categoria = conexion.execute("""
            SELECT
                id,
                nombre,
                estado
            FROM categorias_socio
            WHERE id = ?
        """, (
            categoria_socio_id,
        )).fetchone()


        if categoria is None:

            conexion.close()

            flash(
                "La categoría seleccionada no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_asociado",
                    id=id
                )
            )


        # Permitir conservar una categoría
        # inactiva si ya estaba asignada.

        if (
            categoria["estado"] != "ACTIVO"
            and str(categoria_socio_id)
            != str(asociado["categoria_socio_id"])
        ):

            conexion.close()

            flash(
                "No se puede seleccionar una categoría inactiva.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_asociado",
                    id=id
                )
            )


        # --------------------------------
        # VALIDAR EMPLEADO
        # --------------------------------

        empleado_usuario_id = None


        if empleado_seleccion == "OTRO":

            if not empleado_otro:

                conexion.close()

                flash(
                    "Ingresá el nombre del empleado.",
                    "error"
                )

                return redirect(
                    url_for(
                        "editar_asociado",
                        id=id
                    )
                )


        else:

            empleado = conexion.execute("""
                SELECT
                    id,
                    nombre,
                    estado
                FROM usuarios
                WHERE id = ?
            """, (
                empleado_seleccion,
            )).fetchone()


            if empleado is None:

                conexion.close()

                flash(
                    "El empleado seleccionado no existe.",
                    "error"
                )

                return redirect(
                    url_for(
                        "editar_asociado",
                        id=id
                    )
                )


            # Permitir conservar un usuario
            # inactivo si ya era quien lo asoció.

            if (
                empleado["estado"] != "ACTIVO"
                and str(empleado_seleccion)
                != str(asociado["empleado_usuario_id"])
            ):

                conexion.close()

                flash(
                    "No se puede seleccionar un empleado inactivo.",
                    "error"
                )

                return redirect(
                    url_for(
                        "editar_asociado",
                        id=id
                    )
                )


            empleado_usuario_id = (
                empleado["id"]
            )

            empleado_otro = None


        # --------------------------------
        # DATOS ANTERIORES
        # --------------------------------

        datos_anteriores = dict(
            asociado
        )


        # --------------------------------
        # ACTUALIZAR
        # --------------------------------

        conexion.execute("""
            UPDATE nuevos_asociados

            SET
                fecha = ?,
                hora = ?,
                nombre = ?,
                dni = ?,
                categoria_socio_id = ?,
                empleado_usuario_id = ?,
                empleado_otro = ?

            WHERE id = ?
        """, (
            fecha,
            hora,
            nombre,
            dni,
            categoria_socio_id,
            empleado_usuario_id,
            empleado_otro,
            id
        ))


        # --------------------------------
        # DATOS NUEVOS
        # --------------------------------

        asociado_actualizado = conexion.execute("""
            SELECT *
            FROM nuevos_asociados
            WHERE id = ?
        """, (
            id,
        )).fetchone()


        datos_nuevos = dict(
            asociado_actualizado
        )


        # --------------------------------
        # DETECTAR CAMBIOS
        # --------------------------------

        cambios = []


        # FECHA

        if (
            datos_anteriores["fecha"]
            != datos_nuevos["fecha"]
        ):

            cambios.append(
                f"Fecha: "
                f"{datos_anteriores['fecha']} → "
                f"{datos_nuevos['fecha']}"
            )


        # HORA

        if (
            datos_anteriores["hora"]
            != datos_nuevos["hora"]
        ):

            cambios.append(
                f"Hora: "
                f"{datos_anteriores['hora']} → "
                f"{datos_nuevos['hora']}"
            )


        # NOMBRE

        if (
            datos_anteriores["nombre"]
            != datos_nuevos["nombre"]
        ):

            cambios.append(
                f"Nombre: "
                f"{datos_anteriores['nombre']} → "
                f"{datos_nuevos['nombre']}"
            )


        # DNI

        if (
            datos_anteriores["dni"]
            != datos_nuevos["dni"]
        ):

            cambios.append(
                f"DNI: "
                f"{datos_anteriores['dni']} → "
                f"{datos_nuevos['dni']}"
            )


        # CATEGORÍA

        if (
            str(
                datos_anteriores[
                    "categoria_socio_id"
                ]
            )
            != str(
                datos_nuevos[
                    "categoria_socio_id"
                ]
            )
        ):

            categoria_anterior = (
                nombres_categorias.get(
                    datos_anteriores[
                        "categoria_socio_id"
                    ],
                    "Desconocida"
                )
            )

            categoria_nueva = (
                nombres_categorias.get(
                    datos_nuevos[
                        "categoria_socio_id"
                    ],
                    categoria["nombre"]
                )
            )

            cambios.append(
                f"Categoría: "
                f"{categoria_anterior} → "
                f"{categoria_nueva}"
            )


        # --------------------------------
        # EMPLEADO QUE LO ASOCIÓ
        # --------------------------------

        if datos_anteriores["empleado_usuario_id"]:

            empleado_anterior = (
                nombres_empleados.get(
                    datos_anteriores[
                        "empleado_usuario_id"
                    ],
                    "Desconocido"
                )
            )

        else:

            empleado_anterior = (
                datos_anteriores[
                    "empleado_otro"
                ]
                or "—"
            )


        if datos_nuevos["empleado_usuario_id"]:

            empleado_nuevo = (
                nombres_empleados.get(
                    datos_nuevos[
                        "empleado_usuario_id"
                    ],
                    "Desconocido"
                )
            )

        else:

            empleado_nuevo = (
                datos_nuevos[
                    "empleado_otro"
                ]
                or "—"
            )


        if empleado_anterior != empleado_nuevo:

            cambios.append(
                f"Asociado por: "
                f"{empleado_anterior} → "
                f"{empleado_nuevo}"
            )


        # --------------------------------
        # HISTORIAL
        # --------------------------------

        if cambios:

            registrar_historial_nuevo_asociado(
                conexion=conexion,
                asociado_id=id,
                accion="EDITADO",
                detalle="; ".join(
                    cambios
                ),
                datos_anteriores=
                    datos_anteriores,
                datos_nuevos=
                    datos_nuevos
            )


        conexion.commit()
        conexion.close()


        flash(
            "Asociado actualizado correctamente.",
            "exito"
        )

        return redirect(
            url_for(
                "nuevos_asociados"
            )
        )


    # --------------------------------
    # MOSTRAR FORMULARIO
    # --------------------------------

    conexion.close()


    return render_template(
        "editar_asociado.html",
        asociado=asociado,
        categorias=categorias,
        empleados=empleados
    )

@app.route(
    "/nuevos-asociados/<int:id>/historial"
)
@login_required
def historial_asociado(id):

    conexion = conectar()


    # --------------------------------
    # ASOCIADO
    # --------------------------------

    asociado = conexion.execute("""
        SELECT
            nuevos_asociados.*,

            categorias_socio.nombre
                AS categoria_nombre,

            COALESCE(
                usuarios_empleado.nombre,
                nuevos_asociados.empleado_otro
            )
                AS empleado_nombre,

            usuarios_carga.nombre
                AS usuario_carga_nombre

        FROM nuevos_asociados

        INNER JOIN categorias_socio
            ON nuevos_asociados.categoria_socio_id
            = categorias_socio.id

        LEFT JOIN usuarios AS usuarios_empleado
            ON nuevos_asociados.empleado_usuario_id
            = usuarios_empleado.id

        INNER JOIN usuarios AS usuarios_carga
            ON nuevos_asociados.usuario_id
            = usuarios_carga.id

        WHERE nuevos_asociados.id = ?
    """, (
        id,
    )).fetchone()


    if asociado is None:

        conexion.close()

        return (
            "Asociado no encontrado",
            404
        )


    # --------------------------------
    # HISTORIAL
    # --------------------------------

    historial = conexion.execute("""
        SELECT
            historial_nuevos_asociados.*,
            usuarios.nombre
                AS usuario_nombre

        FROM historial_nuevos_asociados

        INNER JOIN usuarios
            ON historial_nuevos_asociados.usuario_id
            = usuarios.id

        WHERE historial_nuevos_asociados.asociado_id = ?

        ORDER BY
            historial_nuevos_asociados.fecha_hora DESC,
            historial_nuevos_asociados.id DESC
    """, (
        id,
    )).fetchall()


    conexion.close()


    return render_template(
        "historial_asociado.html",
        asociado=asociado,
        historial=historial
    )

@app.route(
    "/nuevos-asociados/exportar"
)
@login_required
def exportar_nuevos_asociados():

    conexion = conectar()


    # --------------------------------
    # FILTROS
    # --------------------------------

    fecha_desde = request.args.get(
        "fecha_desde",
        ""
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        ""
    )

    categoria_socio_id = request.args.get(
        "categoria_socio_id",
        ""
    )

    estado = request.args.get(
        "estado",
        "ACTIVO"
    )

    busqueda = request.args.get(
        "busqueda",
        ""
    ).strip()


    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "nuevos_asociados.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "nuevos_asociados.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if categoria_socio_id:

        condiciones.append(
            "nuevos_asociados.categoria_socio_id = ?"
        )

        parametros.append(
            categoria_socio_id
        )


    if estado:

        condiciones.append(
            "nuevos_asociados.estado = ?"
        )

        parametros.append(
            estado
        )


    if busqueda:

        condiciones.append("""
            (
                nuevos_asociados.nombre LIKE ?
                OR nuevos_asociados.dni LIKE ?
                OR categorias_socio.nombre LIKE ?
                OR usuarios_empleado.nombre LIKE ?
                OR nuevos_asociados.empleado_otro LIKE ?
            )
        """)

        busqueda_sql = (
            f"%{busqueda}%"
        )

        parametros.extend([
            busqueda_sql,
            busqueda_sql,
            busqueda_sql,
            busqueda_sql,
            busqueda_sql
        ])


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(
                condiciones
            )
        )


    # --------------------------------
    # CONSULTA
    # --------------------------------

    asociados = conexion.execute(f"""
        SELECT
            nuevos_asociados.fecha,
            nuevos_asociados.hora,
            nuevos_asociados.nombre,
            nuevos_asociados.dni,

            categorias_socio.nombre
                AS categoria_nombre,

            COALESCE(
                usuarios_empleado.nombre,
                nuevos_asociados.empleado_otro
            )
                AS empleado_nombre,

            usuarios_carga.nombre
                AS usuario_carga_nombre,

            nuevos_asociados.creado_en,
            nuevos_asociados.estado

        FROM nuevos_asociados

        INNER JOIN categorias_socio
            ON nuevos_asociados.categoria_socio_id
            = categorias_socio.id

        LEFT JOIN usuarios AS usuarios_empleado
            ON nuevos_asociados.empleado_usuario_id
            = usuarios_empleado.id

        INNER JOIN usuarios AS usuarios_carga
            ON nuevos_asociados.usuario_id
            = usuarios_carga.id

        {where_sql}

        ORDER BY
            nuevos_asociados.fecha ASC,
            nuevos_asociados.hora ASC,
            nuevos_asociados.id ASC
    """, parametros).fetchall()


    conexion.close()


    # --------------------------------
    # CREAR EXCEL
    # --------------------------------

    libro = Workbook()

    hoja = libro.active

    hoja.title = (
        "Nuevos asociados"
    )


    encabezados = [
        "Fecha",
        "Hora",
        "Nombre",
        "DNI",
        "Categoría",
        "Asociado por",
        "Cargado por",
        "Cargado el",
        "Estado"
    ]


    hoja.append(
        encabezados
    )


    # --------------------------------
    # ENCABEZADOS EN NEGRITA
    # --------------------------------

    for celda in hoja[1]:

        celda.font = Font(
            bold=True
        )


    # --------------------------------
    # DATOS
    # --------------------------------

    for asociado in asociados:

        try:

            fecha_excel = datetime.strptime(
                asociado["fecha"],
                "%Y-%m-%d"
            ).date()

        except (
            ValueError,
            TypeError
        ):

            fecha_excel = asociado[
                "fecha"
            ]


        try:

            hora_excel = datetime.strptime(
                asociado["hora"],
                "%H:%M"
            ).time()

        except (
            ValueError,
            TypeError
        ):

            hora_excel = asociado[
                "hora"
            ]


        try:

            creado_en_excel = datetime.strptime(
                asociado["creado_en"],
                "%Y-%m-%d %H:%M:%S"
            )

        except (
            ValueError,
            TypeError
        ):

            creado_en_excel = asociado[
                "creado_en"
            ]


        hoja.append([
            fecha_excel,
            hora_excel,
            asociado["nombre"],
            asociado["dni"],
            asociado["categoria_nombre"],
            asociado["empleado_nombre"],
            asociado["usuario_carga_nombre"],
            creado_en_excel,
            asociado["estado"]
        ])


    # --------------------------------
    # FORMATOS
    # --------------------------------

    for fila in range(
        2,
        hoja.max_row + 1
    ):

        hoja.cell(
            row=fila,
            column=1
        ).number_format = (
            "dd/mm/yyyy"
        )

        hoja.cell(
            row=fila,
            column=2
        ).number_format = (
            "hh:mm"
        )

        hoja.cell(
            row=fila,
            column=8
        ).number_format = (
            "dd/mm/yyyy hh:mm"
        )


    # --------------------------------
    # ANCHO DE COLUMNAS
    # --------------------------------

    anchos = {
        "A": 14,
        "B": 10,
        "C": 30,
        "D": 16,
        "E": 24,
        "F": 28,
        "G": 24,
        "H": 21,
        "I": 14
    }


    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    # --------------------------------
    # ARCHIVO EN MEMORIA
    # --------------------------------

    archivo = BytesIO()

    libro.save(
        archivo
    )

    archivo.seek(0)


    fecha_archivo = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).strftime(
        "%Y-%m-%d_%H-%M"
    )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=(
            f"nuevos_asociados_"
            f"{fecha_archivo}.xlsx"
        ),
        mimetype=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

if __name__ == "__main__":
    app.run(debug=True)