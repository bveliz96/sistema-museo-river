import json
import os
from tkinter.font import Font
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
    flash,
    abort
)

from flask_wtf.csrf import CSRFProtect

from database.database import conectar

from openpyxl import Workbook

from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment
)

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


def cajero_required(funcion):

    @wraps(funcion)
    def funcion_protegida(*args, **kwargs):

        usuario = obtener_usuario_actual()

        if usuario is None:
            return redirect(url_for("login"))

        if usuario["rol"] not in ("CAJERO", "ADMIN"):
            abort(403)

        return funcion(*args, **kwargs)

    return funcion_protegida

def recepcion_required(funcion):

    @wraps(funcion)
    def funcion_protegida(*args, **kwargs):

        usuario = obtener_usuario_actual()

        if usuario is None:
            return redirect(url_for("login"))

        if usuario["rol"] not in ("RECEPCION", "ADMIN"):
            abort(403)

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

def crear_alerta(
    conexion,
    tipo,
    tour_id,
    destinatario_rol,
    mensaje,
    creado_en
):

    conexion.execute("""
        INSERT OR IGNORE INTO alertas (
            tipo,
            tour_id,
            destinatario_rol,
            mensaje,
            creado_en
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        tipo,
        tour_id,
        destinatario_rol,
        mensaje,
        creado_en
    ))

def crear_alerta_protocolo(
    conexion,
    protocolo_id,
    mensaje,
    creado_en
):

    conexion.execute("""
        INSERT OR IGNORE INTO alertas (
            tipo,
            protocolo_id,
            destinatario_rol,
            mensaje,
            creado_en
        )
        VALUES (
            'NUEVO_PROTOCOLO',
            ?,
            'RECEPCION',
            ?,
            ?
        )
    """, (
        protocolo_id,
        mensaje,
        creado_en
    ))

def verificar_alertas_capacidad(
    conexion,
    tour_id,
    creado_en
):

    tour = conexion.execute("""
        SELECT
            tours.id,
            tours.hora,
            tours.circuito,
            tours.capacidad,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS total

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id =
               tours.id

        WHERE tours.id = ?

        GROUP BY
            tours.id,
            tours.hora,
            tours.circuito,
            tours.capacidad
    """, (
        tour_id,
    )).fetchone()


    if tour is None:
        return


    if tour["capacidad"] is None:
        return


    disponibles = (
        tour["capacidad"]
        - tour["total"]
    )


    # ====================================
    # ALERTA 10 LUGARES
    # ====================================

    if disponibles <= 10:

        if disponibles > 0:

            mensaje = (
                f"Tour {tour['circuito']} "
                f"{tour['hora']}: "
                f"quedan {disponibles} lugares."
            )

        else:

            mensaje = (
                f"Tour {tour['circuito']} "
                f"{tour['hora']}: "
                f"capacidad alcanzada o excedida."
            )


        crear_alerta(
            conexion,
            "FALTAN_15",
            tour_id,
            "CAJERO",
            mensaje,
            creado_en
        )


    # ====================================
    # ALERTA 20 LUGARES
    # ====================================

    elif disponibles <= 20:

        mensaje = (
            f"Tour {tour['circuito']} "
            f"{tour['hora']}: "
            f"quedan {disponibles} lugares."
        )


        crear_alerta(
            conexion,
            "FALTAN_20",
            tour_id,
            "CAJERO",
            mensaje,
            creado_en
        )

@app.route("/protocolos")
@cajero_required
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
@cajero_required
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

    hoy = ahora.date().isoformat()


    fecha_predeterminada = (
        request.form.get("fecha")
        or hoy
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
            request.form.get(
                "descripcion",
                ""
            )
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
            SELECT
                id,
                nombre
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
            SELECT
                id,
                nombre
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

        cursor = conexion.execute("""
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


        # --------------------------------
        # HISTORIAL DEL PROTOCOLO
        # --------------------------------

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


        # --------------------------------
        # ALERTA A RECEPCIÓN
        # --------------------------------

        # Solo avisamos si el protocolo
        # corresponde al día de hoy.

        if fecha == hoy:

            mensaje = (
                f"{tipo_protocolo['nombre']} · "
                f"{tipo_visita['nombre']} · "
                f"{cantidad} personas."
            )


            crear_alerta_protocolo(
                conexion=conexion,
                protocolo_id=protocolo_id,
                mensaje=mensaje,
                creado_en=creado_en
            )


        conexion.commit()
        conexion.close()


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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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




    return redirect(
        url_for("inmersivo")
    )


@app.route(
    "/inmersivo/<int:id>/reactivar",
    methods=["POST"]
)
@cajero_required
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
@cajero_required
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
@cajero_required
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

        elif rol not in ("ADMIN", "CAJERO","RECEPCION"):
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

        elif rol not in ("ADMIN", "CAJERO", "RECEPCION"):

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

    usuario = obtener_usuario_actual()

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )


    hoy = ahora.date().isoformat()


    hora_actual = ahora.strftime(
        "%H:%M"
    )

    # ====================================
    # INICIO DE RECEPCIÓN
    # ====================================

    if usuario["rol"] == "RECEPCION":

        conexion = conectar()


        # --------------------------------
        # PRÓXIMO TOUR
        # --------------------------------

        proximo_tour = conexion.execute("""
            SELECT
                tours.id,
                tours.hora,
                tours.circuito,

                COALESCE(
                    SUM(ingresos.cantidad),
                    0
                ) AS total

            FROM tours

            LEFT JOIN ingresos
                ON ingresos.tour_id =
                   tours.id

            WHERE tours.fecha = ?
            AND tours.estado = 'ABIERTO'
            AND tours.hora IS NOT NULL
            AND tours.hora >= ?

            GROUP BY
                tours.id,
                tours.hora,
                tours.circuito

            ORDER BY tours.hora ASC

            LIMIT 1
        """, (
            hoy,
            hora_actual
        )).fetchone()


        # --------------------------------
        # TOTAL PERSONAS DEL DÍA
        # --------------------------------

        total_personas_hoy = conexion.execute("""
            SELECT
                COALESCE(
                    SUM(cantidad),
                    0
                )
            FROM historial_recepcion
            WHERE fecha = ?
            AND estado = 'ACTIVO'
        """, (
            hoy,
        )).fetchone()[0]


        # --------------------------------
        # PROTOCOLOS PENDIENTES
        # --------------------------------

        protocolos_pendientes = conexion.execute("""
            SELECT
                COUNT(*) AS cantidad,

                COALESCE(
                    SUM(cantidad),
                    0
                ) AS personas

            FROM protocolos

            WHERE fecha = ?
            AND estado = 'ACTIVO'
            AND recepcion_estado = 'PENDIENTE'
        """, (
            hoy,
        )).fetchone()


        # --------------------------------
        # TOURS ABIERTOS
        # --------------------------------

        tours_abiertos_db = conexion.execute("""
            SELECT
                circuito,
                COUNT(*) AS cantidad

            FROM tours

            WHERE fecha = ?
            AND estado = 'ABIERTO'

            GROUP BY circuito
        """, (
            hoy,
        )).fetchall()


        tours_por_circuito = {
            "ESTADIO": 0,
            "TRIBUNA": 0,
            "MUSEO": 0
        }


        for fila in tours_abiertos_db:

            tours_por_circuito[
                fila["circuito"]
            ] = fila["cantidad"]


        total_tours_abiertos = sum(
            tours_por_circuito.values()
        )

        # ====================================
        # TOTALES FINALES DE HOY
        # ====================================

        filas_totales_hoy = conexion.execute("""
            SELECT
                tipos_visita.id,
                tipos_visita.nombre,

                COALESCE(
                    SUM(ingresos.cantidad),
                    0
                ) AS cantidad

            FROM tours

            JOIN ingresos
                ON ingresos.tour_id =
                tours.id

            JOIN tipos_visita
                ON tipos_visita.id =
                ingresos.tipo_visita_id

            WHERE tours.fecha = ?

            AND tours.estado = 'CERRADO'

            GROUP BY
                tipos_visita.id,
                tipos_visita.nombre

            ORDER BY
                tipos_visita.nombre
        """, (
            hoy,
        )).fetchall()


        totales_finales_hoy = []


        for fila in filas_totales_hoy:

            totales_finales_hoy.append({
                "nombre": fila["nombre"],
                "cantidad": fila["cantidad"]
            })


        total_final_hoy = sum(
            fila["cantidad"]
            for fila in filas_totales_hoy
        )


        conexion.close()


        return render_template(
            "recepcion/inicio.html",

            proximo_tour=
                proximo_tour,

            total_personas_hoy=
                total_personas_hoy,

            protocolos_pendientes=
                protocolos_pendientes,

            tours_por_circuito=
                tours_por_circuito,

            total_tours_abiertos=
                total_tours_abiertos,
            totales_finales_hoy=
                totales_finales_hoy,
            total_final_hoy=
                total_final_hoy
        )


    # ====================================
    # INICIO DE CAJA / ADMIN
    # ====================================

    conexion = conectar()

    hoy = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
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
    # PRÓXIMO TOUR DE ESTADIO
    # --------------------------------

    proximo_estadio = conexion.execute("""
        SELECT
            tours.id,
            tours.hora,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS total

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id = tours.id

        WHERE tours.fecha = ?
        AND tours.circuito = 'ESTADIO'
        AND tours.estado = 'ABIERTO'
        AND tours.hora >= ?

        GROUP BY
            tours.id,
            tours.hora

        ORDER BY tours.hora ASC

        LIMIT 1
    """, (
        hoy,
        hora_actual
    )).fetchone()


    # --------------------------------
    # PRÓXIMO TOUR DE TRIBUNA
    # --------------------------------

    proxima_tribuna = conexion.execute("""
        SELECT
            tours.id,
            tours.hora,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS total

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id = tours.id

        WHERE tours.fecha = ?
        AND tours.circuito = 'TRIBUNA'
        AND tours.estado = 'ABIERTO'
        AND tours.hora >= ?

        GROUP BY
            tours.id,
            tours.hora

        ORDER BY tours.hora ASC

        LIMIT 1
    """, (
        hoy,
        hora_actual
    )).fetchone()

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

        proximo_estadio=
            proximo_estadio,

        proxima_tribuna=
            proxima_tribuna,

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



            return redirect(url_for("empresas"))

    conexion.close()

    return render_template(
        "editar_empresa.html",
        empresa=empresa,
        nombre_formulario=nombre_formulario,
        error=error
    )

@app.route("/reservas")
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
def herramientas():

    return render_template(
        "herramientas.html"
    )


@app.route("/herramientas/calculadora")
@cajero_required
def calculadora():

    return render_template(
        "calculadora.html"
    )


@app.route("/herramientas/contador-billetes")
@cajero_required
def contador_billetes():

    return render_template(
        "contador_billetes.html"
    )

@app.route("/herramientas/cierre-cajas")
@cajero_required
def cierre_cajas():

    return render_template(
        "cierre_cajas.html"
    )

@app.route("/administracion")
@cajero_required
@admin_required
def administracion():

    return render_template(
        "administracion.html"
    )

@app.route("/administracion/tipos-visita")
@cajero_required
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
@admin_required
def nuevo_tipo_visita():

    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        circuito_recepcion = request.form.get(
            "circuito_recepcion",
            ""
        ).strip().upper()


        if not nombre:

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for("nuevo_tipo_visita")
            )


        # Si no selecciona circuito,
        # queda sin configurar

        if not circuito_recepcion:
            circuito_recepcion = None


        circuitos_validos = (
            "ESTADIO",
            "TRIBUNA",
            "MUSEO"
        )


        if (
            circuito_recepcion is not None
            and circuito_recepcion
            not in circuitos_validos
        ):

            flash(
                "El circuito de recepción no es válido.",
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
                circuito_recepcion,
                estado
            )
            VALUES (?, ?, 'ACTIVO')
        """, (
            nombre,
            circuito_recepcion
        ))


        conexion.commit()
        conexion.close()





        return redirect(
            url_for("tipos_visita")
        )


    return render_template(
        "nuevo_tipo_visita.html"
    )


@app.route(
    "/administracion/tipos-visita/<int:tipo_id>/editar",
    methods=["GET", "POST"]
)
@admin_required
def editar_tipo_visita(tipo_id):

    conexion = conectar()

    tipo = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion,
            estado
        FROM tipos_visita
        WHERE id = ?
    """, (
        tipo_id,
    )).fetchone()


    if tipo is None:

        conexion.close()
        abort(404)


    if request.method == "POST":

        nombre = texto_mayusculas(
            request.form.get("nombre", "")
        )

        circuito_recepcion = request.form.get(
            "circuito_recepcion",
            ""
        ).strip().upper()

        estado = request.form.get(
            "estado",
            "ACTIVO"
        ).strip().upper()


        if not nombre:

            conexion.close()

            flash(
                "El nombre es obligatorio.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_visita",
                    tipo_id=tipo_id
                )
            )


        if not circuito_recepcion:
            circuito_recepcion = None


        circuitos_validos = (
            "ESTADIO",
            "TRIBUNA",
            "MUSEO"
        )


        if (
            circuito_recepcion is not None
            and circuito_recepcion
            not in circuitos_validos
        ):

            conexion.close()

            flash(
                "El circuito de recepción no es válido.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_visita",
                    tipo_id=tipo_id
                )
            )


        if estado not in (
            "ACTIVO",
            "INACTIVO"
        ):

            conexion.close()

            flash(
                "El estado seleccionado no es válido.",
                "error"
            )

            return redirect(
                url_for(
                    "editar_tipo_visita",
                    tipo_id=tipo_id
                )
            )


        existente = conexion.execute("""
            SELECT id
            FROM tipos_visita
            WHERE LOWER(nombre) = LOWER(?)
            AND id != ?
        """, (
            nombre,
            tipo_id
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
                    tipo_id=tipo_id
                )
            )


        conexion.execute("""
            UPDATE tipos_visita
            SET
                nombre = ?,
                circuito_recepcion = ?,
                estado = ?
            WHERE id = ?
        """, (
            nombre,
            circuito_recepcion,
            estado,
            tipo_id
        ))


        conexion.commit()
        conexion.close()





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
@cajero_required
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



    return redirect(
        url_for("tipos_visita")
    )


@app.route(
    "/administracion/tipos-visita/<int:id>/activar",
    methods=["POST"]
)
@cajero_required
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



    return redirect(
        url_for("tipos_visita")
    )

@app.route("/administracion/tipos-protocolo")
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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



    return redirect(
        url_for("tipos_protocolo")
    )


@app.route(
    "/administracion/tipos-protocolo/<int:id>/activar",
    methods=["POST"]
)
@cajero_required
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



    return redirect(
        url_for("tipos_protocolo")
    )

@app.route(
    "/protocolos/<int:id>/editar",
    methods=["GET", "POST"]
)
@cajero_required
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
@cajero_required
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




    return redirect(
        url_for("protocolos")
    )


@app.route(
    "/protocolos/<int:id>/reactivar",
    methods=["POST"]
)
@cajero_required
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




    return redirect(
        url_for("protocolos")
    )

@app.route(
    "/protocolos/<int:id>/historial"
)
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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


    return redirect(
        url_for("categorias_socio")
    )


@app.post(
    "/administracion/categorias-socio/<int:id>/activar"
)
@cajero_required
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
@cajero_required
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
@cajero_required
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
@cajero_required
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




    return redirect(
        url_for("nuevos_asociados")
    )

@app.post(
    "/nuevos-asociados/<int:id>/reactivar"
)
@cajero_required
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




    return redirect(
        url_for("nuevos_asociados")
    )

@app.route(
    "/nuevos-asociados/<int:id>/editar",
    methods=["GET", "POST"]
)
@cajero_required
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
@cajero_required
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
@cajero_required
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


@app.route("/recepcion/ingresos")
@recepcion_required
def ingresos():

    conexion = conectar()

    hoy = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    ).date().isoformat()


    tours = {}


    for circuito in (
        "ESTADIO",
        "TRIBUNA",
        "MUSEO"
    ):

        # --------------------------------
        # TOURS ABIERTOS
        # --------------------------------

        tours_abiertos = conexion.execute("""
            SELECT
                tours.id,
                tours.fecha,
                tours.hora,
                tours.circuito,
                tours.capacidad,
                tours.estado,

                COALESCE(
                    SUM(ingresos.cantidad),
                    0
                ) AS total

            FROM tours

            LEFT JOIN ingresos
                ON ingresos.tour_id = tours.id

            WHERE tours.fecha = ?
            AND tours.circuito = ?
            AND tours.estado = 'ABIERTO'

            GROUP BY
                tours.id,
                tours.fecha,
                tours.hora,
                tours.circuito,
                tours.capacidad,
                tours.estado

            ORDER BY tours.hora
        """, (
            hoy,
            circuito
        )).fetchall()


        # --------------------------------
        # ULTIMO TOUR CERRADO
        # --------------------------------

        ultimo_cerrado = conexion.execute("""
            SELECT
                tours.id,
                tours.fecha,
                tours.hora,
                tours.circuito,
                tours.estado,

                COALESCE(
                    SUM(ingresos.cantidad),
                    0
                ) AS total

            FROM tours

            LEFT JOIN ingresos
                ON ingresos.tour_id = tours.id

            WHERE tours.fecha = ?
            AND tours.circuito = ?
            AND tours.estado = 'CERRADO'

            GROUP BY
                tours.id,
                tours.fecha,
                tours.hora,
                tours.circuito,
                tours.estado,
                tours.cerrado_en

            ORDER BY tours.cerrado_en DESC

            LIMIT 1
        """, (
            hoy,
            circuito
        )).fetchone()


        # --------------------------------
        # TIPOS DE VISITA
        # --------------------------------

        tipos_visita = conexion.execute("""
            SELECT
                id,
                nombre
            FROM tipos_visita
            WHERE estado = 'ACTIVO'
            AND circuito_recepcion = ?
            ORDER BY nombre
        """, (
            circuito,
        )).fetchall()


        # --------------------------------
        # DATOS DEL CIRCUITO
        # --------------------------------

        tours[circuito] = {
            "abiertos": tours_abiertos,
            "ultimo_cerrado": ultimo_cerrado,
            "tipos_visita": tipos_visita
        }


    conexion.close()


    return render_template(
        "recepcion/ingresos.html",
        tours=tours
    )

@app.route(
    "/recepcion/tours/abrir",
    methods=["POST"]
)
@recepcion_required
def abrir_tour():

    circuito = request.form.get(
        "circuito",
        ""
    ).strip().upper()

    hora_ingresada = request.form.get(
        "hora",
        ""
    ).strip()

    capacidad = request.form.get(
        "capacidad",
        type=int
    )


    circuitos_validos = (
        "ESTADIO",
        "TRIBUNA",
        "MUSEO"
    )


    # -----------------------------
    # VALIDAR CIRCUITO
    # -----------------------------

    if circuito not in circuitos_validos:
        abort(400)


    # -----------------------------
    # VALIDAR HORARIO
    # -----------------------------

    if circuito == "MUSEO":

        hora = None

    else:

        if (
            len(hora_ingresada) != 4
            or not hora_ingresada.isdigit()
        ):

            flash(
                "Ingresá el horario con 4 números. Ejemplo: 1100.",
                "error"
            )

            return redirect(
                url_for("ingresos")
            )


        horas = int(
            hora_ingresada[:2]
        )

        minutos = int(
            hora_ingresada[2:]
        )


        if (
            horas > 23
            or minutos > 59
        ):

            flash(
                "El horario ingresado no es válido.",
                "error"
            )

            return redirect(
                url_for("ingresos")
            )


        hora = (
            f"{horas:02d}:"
            f"{minutos:02d}"
        )


    # -----------------------------
    # FECHA Y HORA DE CREACIÓN
    # -----------------------------

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    creado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()

    # -----------------------------
    # VERIFICAR CAPACIDAD
    # -----------------------------

    if circuito == "MUSEO":

        capacidad = None

    else:

        if capacidad is None:
            capacidad = 100

        if capacidad <= 0:

            flash(
                "La capacidad debe ser mayor a 0.",
                "error"
            )

            return redirect(
                url_for("ingresos")
            )

    # -----------------------------
    # VERIFICAR TOUR EXISTENTE
    # -----------------------------

    if circuito == "MUSEO":

        tour_existente = conexion.execute("""
            SELECT id
            FROM tours
            WHERE fecha = ?
            AND circuito = 'MUSEO'
            AND estado = 'ABIERTO'
            LIMIT 1
        """, (
            hoy,
        )).fetchone()

    else:

        tour_existente = conexion.execute("""
            SELECT id
            FROM tours
            WHERE fecha = ?
            AND circuito = ?
            AND hora = ?
            AND estado = 'ABIERTO'
            LIMIT 1
        """, (
            hoy,
            circuito,
            hora
        )).fetchone()


    if tour_existente:

        conexion.close()

        if circuito == "MUSEO":

            flash(
                "El Museo ya está abierto.",
                "error"
            )

        else:

            flash(
                "Ya existe un tour de ese circuito "
                "con ese horario.",
                "error"
            )

        return redirect(
            url_for("ingresos")
        )


    # -----------------------------
    # CREAR TOUR
    # -----------------------------

    conexion.execute("""
        INSERT INTO tours (
            fecha,
            hora,
            circuito,
            capacidad,
            estado,
            creado_en
        )
        VALUES (?, ?, ?, ?, 'ABIERTO', ?)
    """, (
        hoy,
        hora,
        circuito,
        capacidad,
        creado_en
    ))


    conexion.commit()
    conexion.close()


    return redirect(
        url_for("ingresos")
    )

@app.route(
    "/recepcion/tours/<int:tour_id>/ingreso",
    methods=["POST"]
)
@recepcion_required
def registrar_ingreso_tour(tour_id):

    usuario = obtener_usuario_actual()


    cantidad = request.form.get(
        "cantidad",
        type=int
    )


    tipo_visita_id = request.form.get(
        "tipo_visita_id",
        type=int
    )


    # --------------------------------
    # VALIDAR CANTIDAD
    # --------------------------------

    if cantidad is None or cantidad <= 0:

        return {
            "ok": False,
            "error": "La cantidad debe ser mayor a 0."
        }, 400


    # --------------------------------
    # VALIDAR TIPO DE VISITA
    # --------------------------------

    if tipo_visita_id is None:

        return {
            "ok": False,
            "error": "Debe seleccionar un tipo de visita."
        }, 400


    conexion = conectar()


    # --------------------------------
    # OBTENER TOUR
    # --------------------------------

    tour = conexion.execute("""
        SELECT
            id,
            circuito,
            estado
        FROM tours
        WHERE id = ?
    """, (
        tour_id,
    )).fetchone()


    if tour is None:

        conexion.close()

        return {
            "ok": False,
            "error": "El tour no existe."
        }, 404


    if tour["estado"] != "ABIERTO":

        conexion.close()

        return {
            "ok": False,
            "error": "El tour ya está cerrado."
        }, 400


    # --------------------------------
    # OBTENER TIPO DE VISITA
    # --------------------------------

    tipo_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion,
            estado
        FROM tipos_visita
        WHERE id = ?
    """, (
        tipo_visita_id,
    )).fetchone()


    if tipo_visita is None:

        conexion.close()

        return {
            "ok": False,
            "error": "El tipo de visita no existe."
        }, 404


    if tipo_visita["estado"] != "ACTIVO":

        conexion.close()

        return {
            "ok": False,
            "error": "Ese tipo de visita está inactivo."
        }, 400


    # --------------------------------
    # VALIDAR CIRCUITO
    # --------------------------------

    if tipo_visita["circuito_recepcion"] is None:

        conexion.close()

        return {
            "ok": False,
            "error": (
                "Ese tipo de visita no tiene "
                "un circuito de recepción configurado."
            )
        }, 400


    if (
        tipo_visita["circuito_recepcion"]
        != tour["circuito"]
    ):

        conexion.close()

        return {
            "ok": False,
            "error": (
                "Ese tipo de visita no corresponde "
                "a este tour."
            )
        }, 400


    # --------------------------------
    # FECHA Y HORA
    # --------------------------------

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )


    fecha = ahora.date().isoformat()


    creado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    # --------------------------------
    # REGISTRAR INGRESO
    # --------------------------------

    cursor = conexion.execute("""
        INSERT INTO ingresos (
            tour_id,
            tipo_visita_id,
            cantidad,
            creado_en,
            usuario_id
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        tour_id,
        tipo_visita_id,
        cantidad,
        creado_en,
        usuario["id"]
    ))


    ingreso_id = cursor.lastrowid


    # --------------------------------
    # HISTORIAL DE RECEPCIÓN
    # --------------------------------

    conexion.execute("""
        INSERT INTO historial_recepcion (
            fecha,
            creado_en,
            origen,
            referencia_id,
            tipo_visita_id,
            cantidad,
            destino,
            tour_id,
            usuario_id,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')
    """, (
        fecha,
        creado_en,
        "INGRESO",
        ingreso_id,
        tipo_visita_id,
        cantidad,
        "NORMAL",
        tour_id,
        usuario["id"]
    ))

    verificar_alertas_capacidad(
        conexion,
        tour_id,
        creado_en
    )


    conexion.commit()


    # --------------------------------
    # TOTAL DEL TOUR
    # --------------------------------

    total = conexion.execute("""
        SELECT
            COALESCE(
                SUM(cantidad),
                0
            ) AS total
        FROM ingresos
        WHERE tour_id = ?
    """, (
        tour_id,
    )).fetchone()["total"]


    conexion.close()


    return {
        "ok": True,
        "total": total,
        "tipo_visita": tipo_visita["nombre"]
    }

@app.route(
    "/recepcion/tours/<int:tour_id>/cerrar",
    methods=["POST"]
)
@recepcion_required
def cerrar_tour(tour_id):

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    cerrado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()


    tour = conexion.execute("""
        SELECT
            id,
            circuito,
            hora,
            estado
        FROM tours
        WHERE id = ?
    """, (
        tour_id,
    )).fetchone()


    if tour is None:

        conexion.close()
        abort(404)


    if tour["estado"] != "ABIERTO":

        conexion.close()

        flash(
            "Ese tour ya está cerrado.",
            "error"
        )

        return redirect(
            url_for("ingresos")
        )


    conexion.execute("""
        UPDATE tours
        SET
            estado = 'CERRADO',
            cerrado_en = ?
        WHERE id = ?
    """, (
        cerrado_en,
        tour_id
    ))

    if tour["hora"]:

        mensaje = (
            f"Tour {tour['circuito']} "
            f"{tour['hora']} cerrado."
        )

    else:

        mensaje = (
            f"{tour['circuito']} cerrado."
        )


    crear_alerta(
        conexion,
        "TOUR_CERRADO",
        tour_id,
        "CAJERO",
        mensaje,
        cerrado_en
    )


    conexion.commit()
    conexion.close()




    return redirect(
        url_for("ingresos")
    )


@app.route(
    "/recepcion/tours/<int:tour_id>/reabrir",
    methods=["POST"]
)
@recepcion_required
def reabrir_tour(tour_id):

    conexion = conectar()


    tour = conexion.execute("""
        SELECT
            id,
            fecha,
            hora,
            circuito,
            estado
        FROM tours
        WHERE id = ?
    """, (
        tour_id,
    )).fetchone()


    if tour is None:

        conexion.close()
        abort(404)


    if tour["estado"] != "CERRADO":

        conexion.close()

        flash(
            "Ese tour no está cerrado.",
            "error"
        )

        return redirect(
            url_for("ingresos")
        )

    conexion.execute("""
        UPDATE tours
        SET
            estado = 'ABIERTO',
            cerrado_en = NULL
        WHERE id = ?
    """, (
        tour_id,
    ))


    conexion.commit()
    conexion.close()





    return redirect(
        url_for("ingresos")
    )

@app.route(
    "/recepcion/tours/<int:tour_id>/deshacer",
    methods=["POST"]
)
@recepcion_required
def deshacer_ultimo_ingreso(tour_id):

    usuario = obtener_usuario_actual()

    conexion = conectar()

    tour = conexion.execute("""
        SELECT
            id,
            estado
        FROM tours
        WHERE id = ?
    """, (
        tour_id,
    )).fetchone()


    if tour is None:

        conexion.close()

        return {
            "ok": False,
            "error": "El tour no existe."
        }, 404


    if tour["estado"] != "ABIERTO":

        conexion.close()

        return {
            "ok": False,
            "error": "El tour está cerrado."
        }, 400


    ultimo_ingreso = conexion.execute("""
        SELECT
            ingresos.id,
            ingresos.cantidad,

            tipos_visita.nombre
                AS tipo_visita

        FROM ingresos

        JOIN tipos_visita
            ON tipos_visita.id =
            ingresos.tipo_visita_id

        WHERE ingresos.tour_id = ?
        AND ingresos.usuario_id = ?

        ORDER BY ingresos.id DESC

        LIMIT 1
    """, (
        tour_id,
        usuario["id"]
    )).fetchone()


    if ultimo_ingreso is None:

        conexion.close()

        return {
            "ok": False,
            "error": "No hay cargas para deshacer."
        }, 400


    conexion.execute("""
        DELETE FROM ingresos
        WHERE id = ?
    """, (
        ultimo_ingreso["id"],
    ))


    conexion.commit()


    total = conexion.execute("""
        SELECT
            COALESCE(
                SUM(cantidad),
                0
            ) AS total
        FROM ingresos
        WHERE tour_id = ?
    """, (
        tour_id,
    )).fetchone()["total"]


    conexion.close()


    return {
        "ok": True,
        "total": total,
        "cantidad_eliminada": ultimo_ingreso["cantidad"],
        "tipo_visita_eliminado": ultimo_ingreso["tipo_visita"]
    }


@app.route("/recepcion/protocolos")
@recepcion_required
def recepcion_protocolos():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    conexion = conectar()


    protocolos_db = conexion.execute("""
        SELECT
            protocolos.id,
            protocolos.cantidad,
            protocolos.descripcion,
            protocolos.tipo_visita_id,

            tipos_protocolo.nombre
                AS tipo_protocolo,

            tipos_visita.nombre
                AS tipo_visita,

            tipos_visita.circuito_recepcion
                AS circuito_recepcion

        FROM protocolos

        JOIN tipos_protocolo
            ON tipos_protocolo.id =
               protocolos.tipo_protocolo_id

        JOIN tipos_visita
            ON tipos_visita.id =
               protocolos.tipo_visita_id

        WHERE protocolos.fecha = ?
        AND protocolos.estado = 'ACTIVO'
        AND protocolos.recepcion_estado = 'PENDIENTE'

        ORDER BY protocolos.id
    """, (
        hoy,
    )).fetchall()


    protocolos = []


    for protocolo in protocolos_db:

        circuito = protocolo["circuito_recepcion"]

        tours_abiertos = []


        if circuito:

            tours_abiertos = conexion.execute("""
                SELECT
                    tours.id,
                    tours.hora,
                    tours.circuito,

                    COALESCE(
                        SUM(ingresos.cantidad),
                        0
                    ) AS total

                FROM tours

                LEFT JOIN ingresos
                    ON ingresos.tour_id =
                       tours.id

                WHERE tours.fecha = ?
                AND tours.circuito = ?
                AND tours.estado = 'ABIERTO'

                GROUP BY
                    tours.id,
                    tours.hora,
                    tours.circuito

                ORDER BY tours.hora
            """, (
                hoy,
                circuito
            )).fetchall()


        protocolos.append({

            "id":
                protocolo["id"],

            "cantidad":
                protocolo["cantidad"],

            "descripcion":
                protocolo["descripcion"],

            "tipo_protocolo":
                protocolo["tipo_protocolo"],

            "tipo_visita_id":
                protocolo["tipo_visita_id"],

            "tipo_visita":
                protocolo["tipo_visita"],

            "circuito":
                circuito,

            "tours_abiertos":
                tours_abiertos

        })


    conexion.close()


    return render_template(
        "recepcion/protocolos.html",
        protocolos=protocolos
    )

@app.route(
    "/recepcion/protocolos/<int:protocolo_id>/confirmar",
    methods=["POST"]
)
@recepcion_required
def confirmar_protocolo_recepcion(
    protocolo_id
):

    usuario = obtener_usuario_actual()


    destino = request.form.get(
        "destino",
        ""
    ).strip().upper()


    tour_id = request.form.get(
        "tour_id",
        type=int
    )


    if destino not in (
        "NORMAL",
        "PRIVADA"
    ):

        abort(400)


    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    confirmado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()


    # --------------------------------
    # OBTENER PROTOCOLO
    # --------------------------------

    protocolo = conexion.execute("""
        SELECT
            protocolos.id,
            protocolos.cantidad,
            protocolos.tipo_visita_id,
            protocolos.recepcion_estado,

            tipos_visita.nombre
                AS tipo_visita,

            tipos_visita.circuito_recepcion
                AS circuito_recepcion

        FROM protocolos

        JOIN tipos_visita
            ON tipos_visita.id =
               protocolos.tipo_visita_id

        WHERE protocolos.id = ?
        AND protocolos.estado = 'ACTIVO'
    """, (
        protocolo_id,
    )).fetchone()


    if protocolo is None:

        conexion.close()
        abort(404)


    if (
        protocolo["recepcion_estado"]
        != "PENDIENTE"
    ):

        conexion.close()

        flash(
            "Ese protocolo ya fue confirmado.",
            "error"
        )

        return redirect(
            url_for(
                "recepcion_protocolos"
            )
        )


    # ====================================
    # VISITA NORMAL
    # ====================================

    if destino == "NORMAL":

        circuito = protocolo[
            "circuito_recepcion"
        ]


        if circuito is None:

            conexion.close()

            flash(
                "Este tipo de visita no tiene "
                "un circuito de recepción configurado.",
                "error"
            )

            return redirect(
                url_for(
                    "recepcion_protocolos"
                )
            )


        if tour_id is None:

            conexion.close()

            flash(
                "Seleccioná el tour al que "
                "querés sumar el protocolo.",
                "error"
            )

            return redirect(
                url_for(
                    "recepcion_protocolos"
                )
            )


        # --------------------------------
        # VALIDAR TOUR
        # --------------------------------

        tour = conexion.execute("""
            SELECT
                id,
                fecha,
                circuito,
                estado
            FROM tours
            WHERE id = ?
        """, (
            tour_id,
        )).fetchone()


        if tour is None:

            conexion.close()

            flash(
                "El tour seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for(
                    "recepcion_protocolos"
                )
            )


        if (
            tour["fecha"] != hoy
            or tour["estado"] != "ABIERTO"
            or tour["circuito"] != circuito
        ):

            conexion.close()

            flash(
                "El tour seleccionado "
                "no es válido para este protocolo.",
                "error"
            )

            return redirect(
                url_for(
                    "recepcion_protocolos"
                )
            )


        # --------------------------------
        # SUMAR AL TOUR
        # --------------------------------

        conexion.execute("""
            INSERT INTO ingresos (
                tour_id,
                tipo_visita_id,
                cantidad,
                creado_en,
                usuario_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            tour_id,
            protocolo["tipo_visita_id"],
            protocolo["cantidad"],
            confirmado_en,
            usuario["id"]
        ))

        verificar_alertas_capacidad(
        conexion,
        tour_id,
        confirmado_en
    )


    # ====================================
    # VISITA PRIVADA
    # ====================================

    else:

        tour_id = None


    # ====================================
    # CONFIRMAR PROTOCOLO
    # ====================================

    conexion.execute("""
        UPDATE protocolos
        SET
            recepcion_estado = 'CONFIRMADO',
            destino = ?,
            confirmado_en = ?,
            confirmado_por = ?
        WHERE id = ?
    """, (
        destino,
        confirmado_en,
        usuario["id"],
        protocolo_id
    ))


    # ====================================
    # HISTORIAL DE RECEPCIÓN
    # ====================================

    conexion.execute("""
        INSERT INTO historial_recepcion (
            fecha,
            creado_en,
            origen,
            referencia_id,
            tipo_visita_id,
            cantidad,
            destino,
            tour_id,
            usuario_id,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')
    """, (
        hoy,
        confirmado_en,
        "PROTOCOLO",
        protocolo_id,
        protocolo["tipo_visita_id"],
        protocolo["cantidad"],
        destino,
        tour_id,
        usuario["id"]
    ))


    conexion.commit()
    conexion.close()





    return redirect(
        url_for(
            "recepcion_protocolos"
        )
    )

@app.route("/recepcion/grupos")
@recepcion_required
def recepcion_grupos():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    conexion = conectar()


    # --------------------------------
    # TIPOS DE VISITA ACTIVOS
    # --------------------------------

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion
        FROM tipos_visita
        WHERE estado = 'ACTIVO'
        ORDER BY nombre
    """).fetchall()


    # --------------------------------
    # TOURS ABIERTOS DEL DÍA
    # --------------------------------

    tours_abiertos = conexion.execute("""
        SELECT
            tours.id,
            tours.hora,
            tours.circuito,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS total

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id =
               tours.id

        WHERE tours.fecha = ?
        AND tours.estado = 'ABIERTO'

        GROUP BY
            tours.id,
            tours.hora,
            tours.circuito

        ORDER BY
            tours.circuito,
            tours.hora
    """, (
        hoy,
    )).fetchall()


    conexion.close()


    return render_template(
        "recepcion/grupos.html",
        tipos_visita=tipos_visita,
        tours_abiertos=tours_abiertos
    )

@app.route(
    "/recepcion/grupos/registrar",
    methods=["POST"]
)
@recepcion_required
def registrar_grupo():

    usuario = obtener_usuario_actual()


    cantidad = request.form.get(
        "cantidad",
        type=int
    )


    tipo_visita_id = request.form.get(
        "tipo_visita_id",
        type=int
    )


    destino = request.form.get(
        "destino",
        ""
    ).strip().upper()


    tour_id = request.form.get(
        "tour_id",
        type=int
    )


    # --------------------------------
    # VALIDACIONES BÁSICAS
    # --------------------------------

    if cantidad is None or cantidad <= 0:

        flash(
            "La cantidad debe ser mayor a 0.",
            "error"
        )

        return redirect(
            url_for("recepcion_grupos")
        )


    if tipo_visita_id is None:

        flash(
            "Debe seleccionar un tipo de visita.",
            "error"
        )

        return redirect(
            url_for("recepcion_grupos")
        )


    if destino not in (
        "NORMAL",
        "PRIVADA"
    ):

        flash(
            "Debe seleccionar cómo ingresa el grupo.",
            "error"
        )

        return redirect(
            url_for("recepcion_grupos")
        )


    # --------------------------------
    # FECHA Y HORA
    # --------------------------------

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )


    fecha = ahora.date().isoformat()


    creado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()


    # --------------------------------
    # TIPO DE VISITA
    # --------------------------------

    tipo_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion,
            estado
        FROM tipos_visita
        WHERE id = ?
    """, (
        tipo_visita_id,
    )).fetchone()


    if tipo_visita is None:

        conexion.close()

        flash(
            "El tipo de visita no existe.",
            "error"
        )

        return redirect(
            url_for("recepcion_grupos")
        )


    if tipo_visita["estado"] != "ACTIVO":

        conexion.close()

        flash(
            "Ese tipo de visita está inactivo.",
            "error"
        )

        return redirect(
            url_for("recepcion_grupos")
        )


    # ====================================
    # GRUPO NORMAL
    # ====================================

    if destino == "NORMAL":

        circuito = tipo_visita[
            "circuito_recepcion"
        ]


        if circuito is None:

            conexion.close()

            flash(
                "Ese tipo de visita no tiene "
                "un circuito de recepción configurado.",
                "error"
            )

            return redirect(
                url_for("recepcion_grupos")
            )


        if tour_id is None:

            conexion.close()

            flash(
                "Debe seleccionar un tour.",
                "error"
            )

            return redirect(
                url_for("recepcion_grupos")
            )


        # --------------------------------
        # VALIDAR TOUR
        # --------------------------------

        tour = conexion.execute("""
            SELECT
                id,
                fecha,
                circuito,
                estado
            FROM tours
            WHERE id = ?
        """, (
            tour_id,
        )).fetchone()


        if tour is None:

            conexion.close()

            flash(
                "El tour seleccionado no existe.",
                "error"
            )

            return redirect(
                url_for("recepcion_grupos")
            )


        if (
            tour["fecha"] != fecha
            or tour["estado"] != "ABIERTO"
            or tour["circuito"] != circuito
        ):

            conexion.close()

            flash(
                "El tour seleccionado no corresponde "
                "al tipo de visita.",
                "error"
            )

            return redirect(
                url_for("recepcion_grupos")
            )


        # --------------------------------
        # GUARDAR GRUPO
        # --------------------------------

        cursor = conexion.execute("""
            INSERT INTO grupos (
                fecha,
                cantidad,
                tipo_visita_id,
                destino,
                tour_id,
                creado_en,
                usuario_id,
                estado
            )
            VALUES (?, ?, ?, 'NORMAL', ?, ?, ?, 'ACTIVO')
        """, (
            fecha,
            cantidad,
            tipo_visita_id,
            tour_id,
            creado_en,
            usuario["id"]
        ))



        grupo_id = cursor.lastrowid


        # --------------------------------
        # SUMAR PERSONAS AL TOUR
        # --------------------------------

        conexion.execute("""
            INSERT INTO ingresos (
                tour_id,
                tipo_visita_id,
                cantidad,
                creado_en,
                usuario_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            tour_id,
            tipo_visita_id,
            cantidad,
            creado_en,
            usuario["id"]
        ))

        verificar_alertas_capacidad(
        conexion,
        tour_id,
        creado_en
    )


    # ====================================
    # GRUPO PRIVADO
    # ====================================

    else:

        cursor = conexion.execute("""
            INSERT INTO grupos (
                fecha,
                cantidad,
                tipo_visita_id,
                destino,
                tour_id,
                creado_en,
                usuario_id,
                estado
            )
            VALUES (?, ?, ?, 'PRIVADA', NULL, ?, ?, 'ACTIVO')
        """, (
            fecha,
            cantidad,
            tipo_visita_id,
            creado_en,
            usuario["id"]
        ))


        grupo_id = cursor.lastrowid


        # Las visitas privadas no pertenecen
        # a ningún tour normal.

        tour_id = None


    # ====================================
    # HISTORIAL DE RECEPCIÓN
    # ====================================

    conexion.execute("""
        INSERT INTO historial_recepcion (
            fecha,
            creado_en,
            origen,
            referencia_id,
            tipo_visita_id,
            cantidad,
            destino,
            tour_id,
            usuario_id,
            estado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')
    """, (
        fecha,
        creado_en,
        "GRUPO",
        grupo_id,
        tipo_visita_id,
        cantidad,
        destino,
        tour_id,
        usuario["id"]
    ))


    conexion.commit()
    conexion.close()




    return redirect(
        url_for("recepcion_grupos")
    )

@app.route("/recepcion/historial")
@recepcion_required
def historial_recepcion():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()


    # ====================================
    # FILTROS
    # ====================================

    fecha_desde = request.args.get(
        "fecha_desde",
        hoy
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        hoy
    )

    tour_id = request.args.get(
        "tour_id",
        ""
    )

    origen = request.args.get(
        "origen",
        ""
    ).strip().upper()

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    destino = request.args.get(
        "destino",
        ""
    ).strip().upper()

    usuario_id = request.args.get(
        "usuario_id",
        ""
    )

    estado = request.args.get(
        "estado",
        ""
    ).strip().upper()


    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "historial_recepcion.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "historial_recepcion.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )

    if tour_id:

        condiciones.append(
            "historial_recepcion.tour_id = ?"
        )

        parametros.append(
            tour_id
        )

    if origen:

        condiciones.append(
            "historial_recepcion.origen = ?"
        )

        parametros.append(
            origen
        )


    if tipo_visita_id:

        condiciones.append(
            "historial_recepcion.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if destino:

        condiciones.append(
            "historial_recepcion.destino = ?"
        )

        parametros.append(
            destino
        )


    if usuario_id:

        condiciones.append(
            "historial_recepcion.usuario_id = ?"
        )

        parametros.append(
            usuario_id
        )


    if estado:

        condiciones.append(
            "historial_recepcion.estado = ?"
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


    conexion = conectar()


    # ====================================
    # HISTORIAL
    # ====================================

    historial = conexion.execute(
        f"""
        SELECT
            historial_recepcion.id,
            historial_recepcion.fecha,
            historial_recepcion.creado_en,
            historial_recepcion.origen,
            historial_recepcion.referencia_id,
            historial_recepcion.cantidad,
            historial_recepcion.destino,
            historial_recepcion.estado,

            tipos_visita.nombre
                AS tipo_visita,

            tours.id
                AS tour_id,

            tours.hora
                AS tour_hora,

            tours.circuito
                AS tour_circuito,

            usuarios.nombre
                AS usuario_nombre,

            diferencia_origen.nombre
                AS diferencia_origen,

            diferencia_destino.nombre
                AS diferencia_destino

        FROM historial_recepcion

        JOIN tipos_visita
            ON tipos_visita.id =
            historial_recepcion.tipo_visita_id

        LEFT JOIN tours
            ON tours.id =
            historial_recepcion.tour_id

        JOIN usuarios
            ON usuarios.id =
            historial_recepcion.usuario_id

        LEFT JOIN diferencias
            ON historial_recepcion.origen =
            'DIFERENCIA'

            AND diferencias.id =
                historial_recepcion.referencia_id

        LEFT JOIN tipos_visita
            AS diferencia_origen

            ON diferencia_origen.id =
            diferencias.tipo_visita_origen_id

        LEFT JOIN tipos_visita
            AS diferencia_destino

            ON diferencia_destino.id =
            diferencias.tipo_visita_destino_id

        {where_sql}

        ORDER BY
            historial_recepcion.creado_en DESC,
            historial_recepcion.id DESC
        """,
        parametros
    ).fetchall()

    # ====================================
    # FINALES DE TOURS CERRADOS
    # ====================================

    filas_finales = conexion.execute("""
        SELECT
            tours.id AS tour_id,
            tours.fecha,
            tours.hora,
            tours.circuito,
            tours.capacidad,
            tours.cerrado_en,

            tipos_visita.id
                AS tipo_visita_id,

            tipos_visita.nombre
                AS tipo_visita,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS cantidad

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id =
            tours.id

        LEFT JOIN tipos_visita
            ON tipos_visita.id =
            ingresos.tipo_visita_id

        WHERE tours.estado = 'CERRADO'

        AND tours.fecha >= ?
        AND tours.fecha <= ?

        GROUP BY
            tours.id,
            tours.fecha,
            tours.hora,
            tours.circuito,
            tours.capacidad,
            tours.cerrado_en,
            tipos_visita.id,
            tipos_visita.nombre

        ORDER BY
            tours.fecha DESC,
            tours.hora DESC,
            tours.id DESC,
            tipos_visita.nombre
    """, (
        fecha_desde,
        fecha_hasta
    )).fetchall()


    finales_diccionario = {}


    for fila in filas_finales:

        tour_id_final = fila["tour_id"]


        if (
            tour_id_final
            not in finales_diccionario
        ):

            finales_diccionario[
                tour_id_final
            ] = {
                "id": tour_id_final,
                "fecha": fila["fecha"],
                "hora": fila["hora"],
                "circuito": fila["circuito"],
                "capacidad": fila["capacidad"],
                "cerrado_en": fila["cerrado_en"],
                "tipos": [],
                "total": 0
            }


        if fila["tipo_visita"]:

            cantidad_final = (
                fila["cantidad"] or 0
            )


            finales_diccionario[
                tour_id_final
            ]["tipos"].append({
                "nombre":
                    fila["tipo_visita"],

                "cantidad":
                    cantidad_final
            })


            finales_diccionario[
                tour_id_final
            ]["total"] += cantidad_final


    finales_tours = list(
        finales_diccionario.values()
    )

    # ====================================
    # TOTALES POR TIPO DE VISITA
    # ====================================

    totales_por_tipo = {}


    for fila in filas_finales:

        tipo = fila["tipo_visita"]


        if not tipo:
            continue


        if tipo not in totales_por_tipo:

            totales_por_tipo[tipo] = 0


        totales_por_tipo[tipo] += (
            fila["cantidad"] or 0
        )


    resumen_tipos = []


    for tipo, cantidad in sorted(
        totales_por_tipo.items()
    ):

        resumen_tipos.append({
            "nombre": tipo,
            "cantidad": cantidad
        })


    total_final_general = sum(
        item["cantidad"]
        for item in resumen_tipos
    )


    # ====================================
    # OPCIONES DE FILTROS
    # ====================================

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion
        FROM tipos_visita
        ORDER BY nombre
    """).fetchall()


    usuarios = conexion.execute("""
        SELECT
            id,
            nombre
        FROM usuarios
        ORDER BY nombre
    """).fetchall()


    tours_filtro = conexion.execute("""
        SELECT
            id,
            fecha,
            hora,
            circuito
        FROM tours
        WHERE fecha >= ?
        AND fecha <= ?
        ORDER BY
            fecha DESC,
            circuito,
            hora
    """, (
        fecha_desde,
        fecha_hasta
    )).fetchall()


    conexion.close()


    return render_template(
        "recepcion/historial.html",

        historial=historial,

        tipos_visita=tipos_visita,
        usuarios=usuarios,
        tours_filtro=tours_filtro,

        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        origen=origen,
        tipo_visita_id=tipo_visita_id,
        destino=destino,
        usuario_id=usuario_id,
        estado=estado,
        tour_id=tour_id,
        resumen_tipos=resumen_tipos,
        total_final_general=total_final_general,
        finales_tours=finales_tours
    )

@app.route("/recepcion/historial/exportar")
@recepcion_required
def exportar_historial_recepcion():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()


    # ====================================
    # FILTROS
    # ====================================

    fecha_desde = request.args.get(
        "fecha_desde",
        hoy
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        hoy
    )

    origen = request.args.get(
        "origen",
        ""
    ).strip().upper()

    tipo_visita_id = request.args.get(
        "tipo_visita_id",
        ""
    )

    destino = request.args.get(
        "destino",
        ""
    ).strip().upper()

    usuario_id = request.args.get(
        "usuario_id",
        ""
    )

    estado = request.args.get(
        "estado",
        ""
    ).strip().upper()

    tour_id = request.args.get(
        "tour_id",
        ""
    )


    # ====================================
    # ARMAR FILTROS SQL
    # ====================================

    condiciones = []
    parametros = []


    if fecha_desde:

        condiciones.append(
            "historial_recepcion.fecha >= ?"
        )

        parametros.append(
            fecha_desde
        )


    if fecha_hasta:

        condiciones.append(
            "historial_recepcion.fecha <= ?"
        )

        parametros.append(
            fecha_hasta
        )


    if origen:

        condiciones.append(
            "historial_recepcion.origen = ?"
        )

        parametros.append(
            origen
        )


    if tipo_visita_id:

        condiciones.append(
            "historial_recepcion.tipo_visita_id = ?"
        )

        parametros.append(
            tipo_visita_id
        )


    if destino:

        condiciones.append(
            "historial_recepcion.destino = ?"
        )

        parametros.append(
            destino
        )


    if usuario_id:

        condiciones.append(
            "historial_recepcion.usuario_id = ?"
        )

        parametros.append(
            usuario_id
        )


    if estado:

        condiciones.append(
            "historial_recepcion.estado = ?"
        )

        parametros.append(
            estado
        )


    if tour_id:

        condiciones.append(
            "historial_recepcion.tour_id = ?"
        )

        parametros.append(
            tour_id
        )


    where_sql = ""

    if condiciones:

        where_sql = (
            "WHERE "
            + " AND ".join(condiciones)
        )


    # ====================================
    # CONSULTAR DATOS
    # ====================================

    conexion = conectar()


    registros = conexion.execute(
        f"""
        SELECT
            historial_recepcion.fecha,
            historial_recepcion.creado_en,
            historial_recepcion.origen,
            historial_recepcion.cantidad,
            historial_recepcion.destino,
            historial_recepcion.estado,

            tipos_visita.nombre
                AS tipo_visita,

            tours.hora
                AS tour_hora,

            tours.circuito
                AS tour_circuito,

            usuarios.nombre
                AS usuario_nombre

        FROM historial_recepcion

        JOIN tipos_visita
            ON tipos_visita.id =
               historial_recepcion.tipo_visita_id

        LEFT JOIN tours
            ON tours.id =
               historial_recepcion.tour_id

        JOIN usuarios
            ON usuarios.id =
               historial_recepcion.usuario_id

        {where_sql}

        ORDER BY
            historial_recepcion.creado_en,
            historial_recepcion.id
        """,
        parametros
    ).fetchall()


    conexion.close()


    # ====================================
    # CREAR EXCEL
    # ====================================

    libro = Workbook()

    hoja = libro.active
    hoja.title = "Historial Recepción"


    encabezados = [
        "Fecha",
        "Hora",
        "Origen",
        "Cantidad",
        "Tipo de visita",
        "Destino",
        "Circuito",
        "Horario tour",
        "Usuario",
        "Estado"
    ]


    hoja.append(
        encabezados
    )


    # ====================================
    # ESTILO ENCABEZADO
    # ====================================

    relleno_rojo = PatternFill( 
        fill_type="solid",
        fgColor="E30613",
    )

    fuente_blanca = Font(
        color="FFFFFF",
        bold=True
    )


    for celda in hoja[1]:

        celda.fill = relleno_rojo
        celda.font = fuente_blanca

        celda.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )


    # ====================================
    # CARGAR REGISTROS
    # ====================================

    for registro in registros:

        fecha = registro["fecha"]

        hora = registro[
            "creado_en"
        ][11:16]


        if registro["tour_circuito"]:

            circuito = registro[
                "tour_circuito"
            ]

        else:

            circuito = "-"


        if registro["tour_hora"]:

            horario_tour = registro[
                "tour_hora"
            ]

        elif (
            registro["tour_circuito"]
            == "MUSEO"
        ):

            horario_tour = "MUSEO"

        else:

            horario_tour = "-"


        hoja.append([
            fecha,
            hora,
            registro["origen"],
            registro["cantidad"],
            registro["tipo_visita"],
            registro["destino"],
            circuito,
            horario_tour,
            registro["usuario_nombre"],
            registro["estado"]
        ])


    # ====================================
    # FORMATO
    # ====================================

    hoja.freeze_panes = "A2"


    if hoja.max_row > 1:

        hoja.auto_filter.ref = (
            f"A1:J{hoja.max_row}"
        )


    anchos = {
        "A": 14,
        "B": 10,
        "C": 16,
        "D": 12,
        "E": 22,
        "F": 14,
        "G": 16,
        "H": 16,
        "I": 22,
        "J": 14
    }


    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    for fila in hoja.iter_rows(
        min_row=2
    ):

        fila[3].alignment = Alignment(
            horizontal="center"
        )


    # ====================================
    # GUARDAR EN MEMORIA
    # ====================================

    archivo = BytesIO()

    libro.save(
        archivo
    )

    archivo.seek(0)


    # ====================================
    # NOMBRE ARCHIVO
    # ====================================

    if fecha_desde == fecha_hasta:

        nombre_archivo = (
            f"historial_recepcion_"
            f"{fecha_desde}.xlsx"
        )

    else:

        nombre_archivo = (
            f"historial_recepcion_"
            f"{fecha_desde}_a_"
            f"{fecha_hasta}.xlsx"
        )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


@app.route("/alertas/pendiente")
@login_required
def alerta_pendiente():

    usuario = obtener_usuario_actual()


    # Por ahora las alertas automáticas
    # están dirigidas a CAJERO.
    # RECEPCION queda preparado para usarlo
    # más adelante.

    if usuario["rol"] not in (
        "CAJERO",
        "RECEPCION"
    ):

        return {
            "ok": True,
            "alerta": None
        }


    conexion = conectar()


    alerta = conexion.execute("""
        SELECT
            alertas.id,
            alertas.tipo,
            alertas.mensaje,
            alertas.creado_en

        FROM alertas

        WHERE alertas.destinatario_rol = ?

        AND NOT EXISTS (

            SELECT 1

            FROM alertas_leidas

            WHERE alertas_leidas.alerta_id =
                  alertas.id

            AND alertas_leidas.usuario_id = ?

        )

        ORDER BY
            alertas.creado_en ASC,
            alertas.id ASC

        LIMIT 1
    """, (
        usuario["rol"],
        usuario["id"]
    )).fetchone()


    conexion.close()


    if alerta is None:

        return {
            "ok": True,
            "alerta": None
        }


    return {
        "ok": True,

        "alerta": {
            "id": alerta["id"],
            "tipo": alerta["tipo"],
            "mensaje": alerta["mensaje"],
            "creado_en": alerta["creado_en"]
        }
    }

@app.route(
    "/alertas/<int:alerta_id>/entendido",
    methods=["POST"]
)
@login_required
def alerta_entendida(alerta_id):

    usuario = obtener_usuario_actual()


    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    leida_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()


    alerta = conexion.execute("""
        SELECT
            id,
            destinatario_rol
        FROM alertas
        WHERE id = ?
    """, (
        alerta_id,
    )).fetchone()


    if alerta is None:

        conexion.close()

        return {
            "ok": False,
            "error": "La alerta no existe."
        }, 404


    if (
        alerta["destinatario_rol"]
        != usuario["rol"]
    ):

        conexion.close()

        return {
            "ok": False,
            "error": "La alerta no corresponde a este usuario."
        }, 403


    conexion.execute("""
        INSERT OR IGNORE INTO alertas_leidas (
            alerta_id,
            usuario_id,
            leida_en
        )
        VALUES (?, ?, ?)
    """, (
        alerta_id,
        usuario["id"],
        leida_en
    ))


    conexion.commit()
    conexion.close()


    return {
        "ok": True
    }


@app.route(
    "/diferencias",
    methods=["GET", "POST"]
)
@cajero_required
def diferencias():

    usuario = obtener_usuario_actual()

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    creado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conexion = conectar()


    # ====================================
    # TIPOS DISPONIBLES
    # ====================================

    tipos_visita = conexion.execute("""
        SELECT
            id,
            nombre,
            circuito_recepcion

        FROM tipos_visita

        WHERE estado = 'ACTIVO'

        AND circuito_recepcion
            IS NOT NULL

        ORDER BY nombre
    """).fetchall()


    # ====================================
    # GUARDAR DIFERENCIA
    # ====================================

    if request.method == "POST":

        tipo_origen_id = request.form.get(
            "tipo_visita_origen_id",
            ""
        )

        tipo_destino_id = request.form.get(
            "tipo_visita_destino_id",
            ""
        )

        cantidad_texto = request.form.get(
            "cantidad",
            ""
        ).strip()

        descripcion = texto_mayusculas(
            request.form.get(
                "descripcion",
                ""
            )
        )


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
                url_for("diferencias")
            )


        if (
            not tipo_origen_id
            or not tipo_destino_id
        ):

            conexion.close()

            flash(
                "Seleccioná el tipo de visita "
                "de origen y destino.",
                "error"
            )

            return redirect(
                url_for("diferencias")
            )


        if (
            tipo_origen_id
            == tipo_destino_id
        ):

            conexion.close()

            flash(
                "El tipo de origen y destino "
                "no pueden ser iguales.",
                "error"
            )

            return redirect(
                url_for("diferencias")
            )


        # --------------------------------
        # VALIDAR ORIGEN
        # --------------------------------

        tipo_origen = conexion.execute("""
            SELECT
                id,
                nombre,
                circuito_recepcion

            FROM tipos_visita

            WHERE id = ?

            AND estado = 'ACTIVO'

            AND circuito_recepcion
                IS NOT NULL
        """, (
            tipo_origen_id,
        )).fetchone()


        if tipo_origen is None:

            conexion.close()

            flash(
                "El tipo de visita de origen "
                "no es válido.",
                "error"
            )

            return redirect(
                url_for("diferencias")
            )


        # --------------------------------
        # VALIDAR DESTINO
        # --------------------------------

        tipo_destino = conexion.execute("""
            SELECT
                id,
                nombre,
                circuito_recepcion

            FROM tipos_visita

            WHERE id = ?

            AND estado = 'ACTIVO'

            AND circuito_recepcion
                IS NOT NULL
        """, (
            tipo_destino_id,
        )).fetchone()


        if tipo_destino is None:

            conexion.close()

            flash(
                "El tipo de visita de destino "
                "no es válido.",
                "error"
            )

            return redirect(
                url_for("diferencias")
            )


        # ====================================
        # INSERT
        # ====================================

        conexion.execute("""
            INSERT INTO diferencias (
                fecha,
                tipo_visita_origen_id,
                tipo_visita_destino_id,
                cantidad,
                descripcion,
                creado_en,
                usuario_id,
                recepcion_estado,
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
                'PENDIENTE',
                'ACTIVO'
            )
        """, (
            hoy,
            tipo_origen_id,
            tipo_destino_id,
            cantidad,
            descripcion,
            creado_en,
            usuario["id"]
        ))


        conexion.commit()
        conexion.close()


        return redirect(
            url_for("diferencias")
        )


    # ====================================
    # DIFERENCIAS DEL DÍA
    # ====================================

    registros = conexion.execute("""
        SELECT
            diferencias.id,
            diferencias.cantidad,
            diferencias.descripcion,
            diferencias.creado_en,
            diferencias.recepcion_estado,
            diferencias.estado,

            origen.nombre
                AS tipo_origen,

            destino.nombre
                AS tipo_destino,

            usuarios.nombre
                AS usuario_nombre

        FROM diferencias

        JOIN tipos_visita AS origen
            ON origen.id =
               diferencias.tipo_visita_origen_id

        JOIN tipos_visita AS destino
            ON destino.id =
               diferencias.tipo_visita_destino_id

        JOIN usuarios
            ON usuarios.id =
               diferencias.usuario_id

        WHERE diferencias.fecha = ?

        ORDER BY
            diferencias.creado_en DESC
    """, (
        hoy,
    )).fetchall()


    conexion.close()


    return render_template(
        "diferencias.html",
        tipos_visita=tipos_visita,
        diferencias=registros
    )


@app.route("/recepcion/diferencias")
@recepcion_required
def diferencias_recepcion():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()


    conexion = conectar()


    # ====================================
    # DIFERENCIAS PENDIENTES
    # ====================================

    pendientes = conexion.execute("""
        SELECT
            diferencias.id,
            diferencias.cantidad,
            diferencias.descripcion,
            diferencias.creado_en,

            diferencias.tipo_visita_origen_id,
            diferencias.tipo_visita_destino_id,

            origen.nombre
                AS tipo_origen,

            origen.circuito_recepcion
                AS circuito_origen,

            destino.nombre
                AS tipo_destino,

            destino.circuito_recepcion
                AS circuito_destino

        FROM diferencias

        JOIN tipos_visita AS origen
            ON origen.id =
               diferencias.tipo_visita_origen_id

        JOIN tipos_visita AS destino
            ON destino.id =
               diferencias.tipo_visita_destino_id

        WHERE diferencias.fecha = ?

        AND diferencias.estado = 'ACTIVO'

        AND diferencias.recepcion_estado =
            'PENDIENTE'

        ORDER BY diferencias.creado_en
    """, (
        hoy,
    )).fetchall()


    # ====================================
    # TOURS ABIERTOS
    # ====================================

    tours_abiertos = conexion.execute("""
        SELECT
            tours.id,
            tours.hora,
            tours.circuito,
            tours.capacidad,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS total

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id =
               tours.id

        WHERE tours.fecha = ?

        AND tours.estado = 'ABIERTO'

        GROUP BY
            tours.id,
            tours.hora,
            tours.circuito,
            tours.capacidad

        ORDER BY
            tours.circuito,
            tours.hora
    """, (
        hoy,
    )).fetchall()


    # ====================================
    # CONFIRMADAS HOY
    # ====================================

    confirmadas = conexion.execute("""
        SELECT
            diferencias.id,
            diferencias.cantidad,
            diferencias.confirmado_en,

            origen.nombre
                AS tipo_origen,

            destino.nombre
                AS tipo_destino,

            tour_origen.hora
                AS hora_origen,

            tour_origen.circuito
                AS circuito_origen,

            tour_destino.hora
                AS hora_destino,

            tour_destino.circuito
                AS circuito_destino

        FROM diferencias

        JOIN tipos_visita AS origen
            ON origen.id =
               diferencias.tipo_visita_origen_id

        JOIN tipos_visita AS destino
            ON destino.id =
               diferencias.tipo_visita_destino_id

        LEFT JOIN tours AS tour_origen
            ON tour_origen.id =
               diferencias.tour_origen_id

        LEFT JOIN tours AS tour_destino
            ON tour_destino.id =
               diferencias.tour_destino_id

        WHERE diferencias.fecha = ?

        AND diferencias.estado = 'ACTIVO'

        AND diferencias.recepcion_estado =
            'CONFIRMADA'

        ORDER BY
            diferencias.confirmado_en DESC
    """, (
        hoy,
    )).fetchall()


    conexion.close()


    return render_template(
        "recepcion/diferencias.html",
        pendientes=pendientes,
        confirmadas=confirmadas,
        tours_abiertos=tours_abiertos
    )

@app.route(
    "/recepcion/diferencias/<int:diferencia_id>/confirmar",
    methods=["POST"]
)
@recepcion_required
def confirmar_diferencia_recepcion(
    diferencia_id
):

    usuario = obtener_usuario_actual()

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()

    confirmado_en = ahora.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    tour_origen_id = request.form.get(
        "tour_origen_id",
        ""
    )

    tour_destino_id = request.form.get(
        "tour_destino_id",
        ""
    )


    conexion = conectar()


    # ====================================
    # DIFERENCIA
    # ====================================

    diferencia = conexion.execute("""
        SELECT
            diferencias.*,

            origen.circuito_recepcion
                AS circuito_origen,

            destino.circuito_recepcion
                AS circuito_destino

        FROM diferencias

        JOIN tipos_visita AS origen
            ON origen.id =
               diferencias.tipo_visita_origen_id

        JOIN tipos_visita AS destino
            ON destino.id =
               diferencias.tipo_visita_destino_id

        WHERE diferencias.id = ?

        AND diferencias.estado = 'ACTIVO'

        AND diferencias.recepcion_estado =
            'PENDIENTE'
    """, (
        diferencia_id,
    )).fetchone()


    if diferencia is None:

        conexion.close()

        flash(
            "La diferencia ya fue procesada "
            "o no existe.",
            "error"
        )

        return redirect(
            url_for(
                "diferencias_recepcion"
            )
        )


    # ====================================
    # VALIDAR TOURS
    # ====================================

    tour_origen = conexion.execute("""
        SELECT *
        FROM tours
        WHERE id = ?
        AND fecha = ?
        AND estado = 'ABIERTO'
    """, (
        tour_origen_id,
        hoy
    )).fetchone()


    tour_destino = conexion.execute("""
        SELECT *
        FROM tours
        WHERE id = ?
        AND fecha = ?
        AND estado = 'ABIERTO'
    """, (
        tour_destino_id,
        hoy
    )).fetchone()


    if (
        tour_origen is None
        or tour_destino is None
    ):

        conexion.close()

        flash(
            "Seleccioná tours abiertos válidos.",
            "error"
        )

        return redirect(
            url_for(
                "diferencias_recepcion"
            )
        )


    # ====================================
    # VALIDAR CIRCUITOS
    # ====================================

    if (
        tour_origen["circuito"]
        != diferencia["circuito_origen"]
    ):

        conexion.close()

        flash(
            "El tour de origen no corresponde "
            "a la visita original.",
            "error"
        )

        return redirect(
            url_for(
                "diferencias_recepcion"
            )
        )


    if (
        tour_destino["circuito"]
        != diferencia["circuito_destino"]
    ):

        conexion.close()

        flash(
            "El tour de destino no corresponde "
            "a la nueva visita.",
            "error"
        )

        return redirect(
            url_for(
                "diferencias_recepcion"
            )
        )


    cantidad = diferencia["cantidad"]


    # ====================================
    # COMPROBAR QUE HAYA PERSONAS
    # EN EL ORIGEN
    # ====================================

    disponible_origen = conexion.execute("""
        SELECT
            COALESCE(
                SUM(cantidad),
                0
            ) AS total

        FROM ingresos

        WHERE tour_id = ?

        AND tipo_visita_id = ?
    """, (
        tour_origen_id,
        diferencia[
            "tipo_visita_origen_id"
        ]
    )).fetchone()["total"]


    if disponible_origen < cantidad:

        conexion.close()

        flash(
            "El tour de origen no tiene "
            "suficientes personas de ese "
            "tipo de visita.",
            "error"
        )

        return redirect(
            url_for(
                "diferencias_recepcion"
            )
        )


    # ====================================
    # RESTAR DEL ORIGEN
    # ====================================

    conexion.execute("""
        INSERT INTO ingresos (
            tour_id,
            tipo_visita_id,
            cantidad,
            origen_movimiento,
            creado_en,
            usuario_id
        )
        VALUES (
            ?,
            ?,
            ?,
            'DIFERENCIA',
            ?,
            ?
        )
    """, (
        tour_origen_id,
        diferencia[
            "tipo_visita_origen_id"
        ],
        -cantidad,
        confirmado_en,
        usuario["id"]
    ))


    # ====================================
    # SUMAR AL DESTINO
    # ====================================

    conexion.execute("""
        INSERT INTO ingresos (
            tour_id,
            tipo_visita_id,
            cantidad,
            origen_movimiento,
            creado_en,
            usuario_id
        )
        VALUES (
            ?,
            ?,
            ?,
            'DIFERENCIA',
            ?,
            ?
        )
    """, (
        tour_destino_id,
        diferencia[
            "tipo_visita_destino_id"
        ],
        cantidad,
        confirmado_en,
        usuario["id"]
    ))


    # ====================================
    # CONFIRMAR DIFERENCIA
    # ====================================

    conexion.execute("""
        UPDATE diferencias

        SET
            recepcion_estado = 'CONFIRMADA',
            tour_origen_id = ?,
            tour_destino_id = ?,
            confirmado_en = ?,
            confirmado_por = ?

        WHERE id = ?
    """, (
        tour_origen_id,
        tour_destino_id,
        confirmado_en,
        usuario["id"],
        diferencia_id
    ))

    # ====================================
    # HISTORIAL DE RECEPCIÓN
    # ====================================

    conexion.execute("""
        INSERT INTO historial_recepcion (
            fecha,
            creado_en,
            origen,
            referencia_id,
            tipo_visita_id,
            cantidad,
            destino,
            tour_id,
            usuario_id,
            estado
        )
        VALUES (
            ?,
            ?,
            'DIFERENCIA',
            ?,
            ?,
            ?,
            'NORMAL',
            ?,
            ?,
            'ACTIVO'
        )
    """, (
        diferencia["fecha"],
        confirmado_en,
        diferencia_id,
        diferencia["tipo_visita_destino_id"],
        cantidad,
        tour_destino_id,
        usuario["id"]
    ))


    # ====================================
    # CAPACIDAD DEL DESTINO
    # ====================================

    verificar_alertas_capacidad(
        conexion,
        int(tour_destino_id),
        confirmado_en
    )


    conexion.commit()
    conexion.close()


    return redirect(
        url_for(
            "diferencias_recepcion"
        )
    )


@app.route(
    "/recepcion/historial/finales/exportar"
)
@recepcion_required
def exportar_finales_recepcion():

    ahora = datetime.now(
        ZoneInfo(
            "America/Argentina/Buenos_Aires"
        )
    )

    hoy = ahora.date().isoformat()


    fecha_desde = request.args.get(
        "fecha_desde",
        hoy
    )

    fecha_hasta = request.args.get(
        "fecha_hasta",
        hoy
    )


    conexion = conectar()


    registros = conexion.execute("""
        SELECT
            tours.id AS tour_id,
            tours.fecha,
            tours.hora,
            tours.circuito,
            tours.capacidad,
            tours.cerrado_en,

            tipos_visita.nombre
                AS tipo_visita,

            COALESCE(
                SUM(ingresos.cantidad),
                0
            ) AS cantidad

        FROM tours

        LEFT JOIN ingresos
            ON ingresos.tour_id =
               tours.id

        LEFT JOIN tipos_visita
            ON tipos_visita.id =
               ingresos.tipo_visita_id

        WHERE tours.estado = 'CERRADO'

        AND tours.fecha >= ?
        AND tours.fecha <= ?

        GROUP BY
            tours.id,
            tours.fecha,
            tours.hora,
            tours.circuito,
            tours.capacidad,
            tours.cerrado_en,
            tipos_visita.id,
            tipos_visita.nombre

        ORDER BY
            tours.fecha,
            tours.hora,
            tours.id,
            tipos_visita.nombre
    """, (
        fecha_desde,
        fecha_hasta
    )).fetchall()


    conexion.close()


    libro = Workbook()


    # ====================================
    # HOJA 1 - FINALES POR TOUR
    # ====================================

    hoja = libro.active

    hoja.title = "Finales por tour"


    encabezados = [
        "Fecha",
        "Circuito",
        "Horario",
        "Tipo de visita",
        "Cantidad",
        "Capacidad",
        "Cerrado"
    ]


    hoja.append(
        encabezados
    )


    relleno_rojo = PatternFill(
        fill_type="solid",
        fgColor="E30613"
    )


    fuente_blanca = Font(
        color="FFFFFF",
        bold=True
    )


    for celda in hoja[1]:

        celda.fill = relleno_rojo
        celda.font = fuente_blanca

        celda.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )


    for registro in registros:

        if not registro["tipo_visita"]:
            continue


        horario = (
            registro["hora"]
            if registro["hora"]
            else "MUSEO"
        )


        cerrado = (
            registro["cerrado_en"][11:16]
            if registro["cerrado_en"]
            else "-"
        )


        hoja.append([
            registro["fecha"],
            registro["circuito"],
            horario,
            registro["tipo_visita"],
            registro["cantidad"],
            registro["capacidad"] or "-",
            cerrado
        ])


    hoja.freeze_panes = "A2"

    hoja.auto_filter.ref = (
        f"A1:G{hoja.max_row}"
    )


    anchos = {
        "A": 14,
        "B": 16,
        "C": 12,
        "D": 24,
        "E": 12,
        "F": 12,
        "G": 12
    }


    for columna, ancho in anchos.items():

        hoja.column_dimensions[
            columna
        ].width = ancho


    # ====================================
    # HOJA 2 - RESUMEN DEL PERÍODO
    # ====================================

    resumen = libro.create_sheet(
        "Resumen"
    )


    resumen.append([
        "Tipo de visita",
        "Total final"
    ])


    for celda in resumen[1]:

        celda.fill = relleno_rojo
        celda.font = fuente_blanca


    totales = {}


    for registro in registros:

        tipo = registro[
            "tipo_visita"
        ]


        if not tipo:
            continue


        if tipo not in totales:
            totales[tipo] = 0


        totales[tipo] += (
            registro["cantidad"] or 0
        )


    total_general = 0


    for tipo, cantidad in sorted(
        totales.items()
    ):

        resumen.append([
            tipo,
            cantidad
        ])

        total_general += cantidad


    resumen.append([
        "TOTAL GENERAL",
        total_general
    ])


    resumen.column_dimensions[
        "A"
    ].width = 25

    resumen.column_dimensions[
        "B"
    ].width = 15


    archivo = BytesIO()

    libro.save(
        archivo
    )

    archivo.seek(0)


    if fecha_desde == fecha_hasta:

        nombre = (
            f"finales_recepcion_"
            f"{fecha_desde}.xlsx"
        )

    else:

        nombre = (
            f"finales_recepcion_"
            f"{fecha_desde}_a_"
            f"{fecha_hasta}.xlsx"
        )


    return send_file(
        archivo,
        as_attachment=True,
        download_name=nombre,
        mimetype=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

if __name__ == "__main__":
    app.run(debug=True)