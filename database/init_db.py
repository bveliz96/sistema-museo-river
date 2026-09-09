from database.database import conectar


def inicializar_base_datos():

    conexion = conectar()

    try:

        conexion.execute(
            "PRAGMA journal_mode = WAL"
        )

        # --------------------------------
        # USUARIOS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                usuario TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'OPERADOR',
                estado TEXT NOT NULL DEFAULT 'ACTIVO'
            )
        """)


        # --------------------------------
        # EMPRESAS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'ACTIVA'
            )
        """)


        # --------------------------------
        # TIPOS DE VISITA
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS tipos_visita (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'ACTIVO'
            )
        """)

        # Tipos iniciales
        tipos_visita_iniciales = (
            "FULL",
            "EXPRESS",
            "MUSEO"
        )

        for nombre in tipos_visita_iniciales:

            conexion.execute("""
                INSERT OR IGNORE INTO tipos_visita (
                    nombre,
                    estado
                )
                VALUES (?, 'ACTIVO')
            """, (nombre,))


        # --------------------------------
        # TIPOS DE PROTOCOLO
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS tipos_protocolo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'ACTIVO'
            )
        """)

        # --------------------------------
        # CATEGORÍAS DE SOCIO
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS categorias_socio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'ACTIVO'
            )
        """)


        # --------------------------------
        # NUEVOS ASOCIADOS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS nuevos_asociados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,

                nombre TEXT NOT NULL,
                dni TEXT NOT NULL,

                categoria_socio_id INTEGER NOT NULL,

                empleado_usuario_id INTEGER,
                empleado_otro TEXT,

                creado_en TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                FOREIGN KEY (categoria_socio_id)
                    REFERENCES categorias_socio(id),

                FOREIGN KEY (empleado_usuario_id)
                    REFERENCES usuarios(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id),

                CHECK (
                    (
                        empleado_usuario_id IS NOT NULL
                        AND empleado_otro IS NULL
                    )
                    OR
                    (
                        empleado_usuario_id IS NULL
                        AND empleado_otro IS NOT NULL
                    )
                )
            )
        """)


        # --------------------------------
        # HISTORIAL DE NUEVOS ASOCIADOS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_nuevos_asociados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                asociado_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,

                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,

                datos_anteriores TEXT,
                datos_nuevos TEXT,

                fecha_hora TEXT NOT NULL,

                FOREIGN KEY (asociado_id)
                    REFERENCES nuevos_asociados(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # --------------------------------
        # RESERVAS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,

                empresa_id INTEGER NOT NULL,
                tipo_visita_id INTEGER NOT NULL,

                nombre_reserva TEXT NOT NULL,

                mayores INTEGER NOT NULL,
                menores INTEGER NOT NULL,

                nacionalidad TEXT NOT NULL,

                voucher TEXT,
                guia TEXT,
                notas TEXT,

                estado TEXT NOT NULL DEFAULT 'ACTIVA',

                creado_en TEXT NOT NULL,

                FOREIGN KEY (empresa_id)
                    REFERENCES empresas(id),

                FOREIGN KEY (tipo_visita_id)
                    REFERENCES tipos_visita(id)
            )
        """)


        # --------------------------------
        # HISTORIAL DE RESERVAS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                reserva_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,

                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,

                datos_anteriores TEXT,
                datos_nuevos TEXT,

                fecha_hora TEXT NOT NULL,

                FOREIGN KEY (reserva_id)
                    REFERENCES reservas(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # --------------------------------
        # HISTORIAL DE PROTOCOLOS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_protocolos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                protocolo_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,

                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,

                datos_anteriores TEXT,
                datos_nuevos TEXT,

                fecha_hora TEXT NOT NULL,

                FOREIGN KEY (protocolo_id)
                    REFERENCES protocolos(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # --------------------------------
        # PROTOCOLOS
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS protocolos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,

                tipo_protocolo_id INTEGER NOT NULL,
                tipo_visita_id INTEGER NOT NULL,

                cantidad INTEGER NOT NULL,

                descripcion TEXT,

                creado_en TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                FOREIGN KEY (tipo_protocolo_id)
                    REFERENCES tipos_protocolo(id),

                FOREIGN KEY (tipo_visita_id)
                    REFERENCES tipos_visita(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # --------------------------------
        # ÍNDICES NUEVOS ASOCIADOS
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_nuevos_asociados_fecha
            ON nuevos_asociados(fecha)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_nuevos_asociados_categoria
            ON nuevos_asociados(categoria_socio_id)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_nuevos_asociados_estado
            ON nuevos_asociados(estado)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_nuevos_asociados
            ON historial_nuevos_asociados(asociado_id)
        """)
        
        # --------------------------------
        # ÍNDICES RESERVAS
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_reservas_fecha
            ON reservas(fecha)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_reservas_empresa
            ON reservas(empresa_id)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_reservas_tipo_visita
            ON reservas(tipo_visita_id)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_reservas_estado
            ON reservas(estado)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_protocolo
            ON historial_protocolos(protocolo_id)
        """)


        # --------------------------------
        # ÍNDICES HISTORIAL
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_reserva
            ON historial_reservas(reserva_id)
        """)

        # --------------------------------
        # INMERSIVO
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS inmersivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,

                tipo_visita_id INTEGER NOT NULL,

                cantidad INTEGER NOT NULL,

                medio_pago TEXT,

                marca TEXT,

                creado_en TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                FOREIGN KEY (tipo_visita_id)
                    REFERENCES tipos_visita(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id),

                CHECK (
                    medio_pago IS NULL
                    OR medio_pago IN (
                        'EFECTIVO',
                        'TARJETA'
                    )
                ),

                CHECK (
                    marca IS NULL
                    OR marca IN (
                        'ONLINE',
                        'DIFERENCIA'
                    )
                ),

                CHECK (
                    (
                        marca = 'ONLINE'
                        AND medio_pago IS NULL
                    )
                    OR
                    (
                        (
                            marca IS NULL
                            OR marca = 'DIFERENCIA'
                        )
                        AND medio_pago IN (
                            'EFECTIVO',
                            'TARJETA'
                        )
                    )
                )
            )
        """)
        # --------------------------------
        # ÍNDICES INMERSIVO
        # --------------------------------
        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_inmersivo_fecha
            ON inmersivo(fecha)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_inmersivo_tipo_visita
            ON inmersivo(tipo_visita_id)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_inmersivo_medio_pago
            ON inmersivo(medio_pago)
        """)

        # --------------------------------
        # ÍNDICES PROTOCOLOS
        # --------------------------------
        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_protocolos_fecha
            ON protocolos(fecha)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_protocolos_tipo
            ON protocolos(tipo_protocolo_id)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_protocolos_visita
            ON protocolos(tipo_visita_id)
        """)


        # --------------------------------
        # HISTORIAL DE INMERSIVO
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_inmersivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                inmersivo_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,

                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,

                datos_anteriores TEXT,
                datos_nuevos TEXT,

                fecha_hora TEXT NOT NULL,

                FOREIGN KEY (inmersivo_id)
                    REFERENCES inmersivo(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # --------------------------------
        # ÍNDICES HISTORIAL INMERSIVO
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_inmersivo
            ON historial_inmersivo(inmersivo_id)
        """)
        conexion.commit()

        print(
            "Base de datos inicializada correctamente."
        )

    except Exception:

        conexion.rollback()
        raise

    finally:

        conexion.close()


if __name__ == "__main__":
    inicializar_base_datos()