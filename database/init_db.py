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
                rol TEXT NOT NULL DEFAULT 'CAJERO',
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

                circuito_recepcion TEXT,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                CHECK (
                    circuito_recepcion IS NULL
                    OR circuito_recepcion IN (
                        'ESTADIO',
                        'TRIBUNA',
                        'MUSEO'
                    )
                )
            )
        """)


        # --------------------------------
        # TOURS RECEPCION
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS tours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,
                hora TEXT,

                circuito TEXT NOT NULL,

                capacidad INTEGER DEFAULT 100,

                estado TEXT NOT NULL DEFAULT 'ABIERTO',

                creado_en TEXT NOT NULL,
                cerrado_en TEXT,

                CHECK (
                    circuito IN (
                        'ESTADIO',
                        'TRIBUNA',
                        'MUSEO'
                    )
                ),

                CHECK (
                    estado IN (
                        'ABIERTO',
                        'CERRADO'
                    )
                ),

                CHECK (
                    capacidad IS NULL
                    OR capacidad > 0
                )
            )
        """)

        # --------------------------------
        # CIRCUITOS DE RECEPCION
        # --------------------------------

        conexion.execute("""
            UPDATE tipos_visita
            SET circuito_recepcion = 'ESTADIO'
            WHERE nombre IN (
                'ESTADIO',
                'FULL'
            )
        """)


        conexion.execute("""
            UPDATE tipos_visita
            SET circuito_recepcion = 'TRIBUNA'
            WHERE nombre IN (
                'EXPRESS',
                'TRIBUNA'
            )
        """)


        conexion.execute("""
            UPDATE tipos_visita
            SET circuito_recepcion = 'MUSEO'
            WHERE nombre = 'MUSEO'
        """)
        # --------------------------------
        # INGRESOS RECEPCION
        # --------------------------------

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ingresos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                tour_id INTEGER NOT NULL,
                tipo_visita_id INTEGER NOT NULL,

                cantidad INTEGER NOT NULL,

                origen_movimiento TEXT NOT NULL
                    DEFAULT 'INGRESO',

                creado_en TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,

                FOREIGN KEY (tour_id)
                    REFERENCES tours(id),

                FOREIGN KEY (tipo_visita_id)
                    REFERENCES tipos_visita(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id),

                CHECK (
                    cantidad != 0
                ),

                CHECK (
                    origen_movimiento IN (
                        'INGRESO',
                        'GRUPO',
                        'PROTOCOLO',
                        'DIFERENCIA'
                    )
                )
            )
        """)

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

                recepcion_estado TEXT NOT NULL DEFAULT 'PENDIENTE',
                destino TEXT,

                confirmado_en TEXT,
                confirmado_por INTEGER,

                FOREIGN KEY (tipo_protocolo_id)
                    REFERENCES tipos_protocolo(id),

                FOREIGN KEY (tipo_visita_id)
                    REFERENCES tipos_visita(id),

                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id),

                FOREIGN KEY (confirmado_por)
                    REFERENCES usuarios(id),

                CHECK (
                    recepcion_estado IN (
                        'PENDIENTE',
                        'CONFIRMADO'
                    )
                ),

                CHECK (
                    destino IS NULL
                    OR destino IN (
                        'NORMAL',
                        'PRIVADA'
                    )
                )
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
        # ==========================================
        # GRUPOS - RECEPCIÓN
        # ==========================================

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,

                cantidad INTEGER NOT NULL,

                tipo_visita_id INTEGER NOT NULL,

                destino TEXT NOT NULL,

                tour_id INTEGER,

                creado_en TEXT NOT NULL,

                usuario_id INTEGER NOT NULL,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                FOREIGN KEY (
                    tipo_visita_id
                )
                REFERENCES tipos_visita(id),

                FOREIGN KEY (
                    tour_id
                )
                REFERENCES tours(id),

                FOREIGN KEY (
                    usuario_id
                )
                REFERENCES usuarios(id),

                CHECK (
                    cantidad > 0
                ),

                CHECK (
                    destino IN (
                        'NORMAL',
                        'PRIVADA'
                    )
                ),

                CHECK (
                    estado IN (
                        'ACTIVO',
                        'ANULADO'
                    )
                ),

                CHECK (
                    (
                        destino = 'NORMAL'
                        AND tour_id IS NOT NULL
                    )
                    OR
                    (
                        destino = 'PRIVADA'
                        AND tour_id IS NULL
                    )
                )
            )
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_grupos_fecha
            ON grupos(fecha)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_grupos_tipo_visita
            ON grupos(tipo_visita_id)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_grupos_tour
            ON grupos(tour_id)
        """)

        # --------------------------------
        # ÍNDICES TOURS RECEPCION
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_tours_fecha
            ON tours(fecha)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_tours_circuito
            ON tours(circuito)
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_tours_estado
            ON tours(estado)
        """)


        # --------------------------------
        # ÍNDICES INGRESOS RECEPCION
        # --------------------------------

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ingresos_tour
            ON ingresos(tour_id)
        """)
        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ingresos_tipo_visita
            ON ingresos(tipo_visita_id)
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

        # ==========================================
        # HISTORIAL DE RECEPCIÓN
        # ==========================================

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_recepcion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,

                creado_en TEXT NOT NULL,

                origen TEXT NOT NULL,

                referencia_id INTEGER NOT NULL,

                tipo_visita_id INTEGER NOT NULL,

                cantidad INTEGER NOT NULL,

                destino TEXT NOT NULL,

                tour_id INTEGER,

                usuario_id INTEGER NOT NULL,

                estado TEXT NOT NULL DEFAULT 'ACTIVO',

                anulado_en TEXT,

                anulado_por INTEGER,

                FOREIGN KEY (
                    tipo_visita_id
                )
                REFERENCES tipos_visita(id),

                FOREIGN KEY (
                    tour_id
                )
                REFERENCES tours(id),

                FOREIGN KEY (
                    usuario_id
                )
                REFERENCES usuarios(id),

                FOREIGN KEY (
                    anulado_por
                )
                REFERENCES usuarios(id),

                CHECK (
                    origen IN (
                        'INGRESO',
                        'GRUPO',
                        'PROTOCOLO',
                        'DIFERENCIA'
                    )
                ),

                CHECK (
                    destino IN (
                        'NORMAL',
                        'PRIVADA'
                    )
                ),

                CHECK (
                    estado IN (
                        'ACTIVO',
                        'ANULADO'
                    )
                ),

                CHECK (
                    cantidad > 0
                )
            )
        """)

        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_recepcion_fecha
            ON historial_recepcion(fecha)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_recepcion_origen
            ON historial_recepcion(origen)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_historial_recepcion_tour
            ON historial_recepcion(tour_id)
        """)


        # ==========================================
        # ALERTAS AUTOMÁTICAS
        # ==========================================

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                tipo TEXT NOT NULL,

                tour_id INTEGER,
                protocolo_id INTEGER,

                destinatario_rol TEXT NOT NULL,

                mensaje TEXT NOT NULL,

                creado_en TEXT NOT NULL,

                FOREIGN KEY (
                    tour_id
                )
                REFERENCES tours(id),

                FOREIGN KEY (
                    protocolo_id
                )
                REFERENCES protocolos(id),

                CHECK (
                    tipo IN (
                        'FALTAN_20',
                        'FALTAN_15',
                        'TOUR_CERRADO',
                        'NUEVO_PROTOCOLO'
                    )
                ),

                CHECK (
                    destinatario_rol IN (
                        'CAJERO',
                        'RECEPCION'
                    )
                ),

                CHECK (
                    (
                        tipo = 'NUEVO_PROTOCOLO'
                        AND protocolo_id IS NOT NULL
                    )
                    OR
                    (
                        tipo != 'NUEVO_PROTOCOLO'
                        AND tour_id IS NOT NULL
                    )
                )
            )
        """)


        conexion.execute("""
            CREATE TABLE IF NOT EXISTS alertas_leidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                alerta_id INTEGER NOT NULL,

                usuario_id INTEGER NOT NULL,

                leida_en TEXT NOT NULL,

                FOREIGN KEY (
                    alerta_id
                )
                REFERENCES alertas(id),

                FOREIGN KEY (
                    usuario_id
                )
                REFERENCES usuarios(id),

                UNIQUE (
                    alerta_id,
                    usuario_id
                )
            )
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_alertas_destinatario
            ON alertas(destinatario_rol)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_alertas_leidas_usuario
            ON alertas_leidas(usuario_id)
        """)

        conexion.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_alerta_tour_tipo
            ON alertas (
                tour_id,
                tipo
            )
            WHERE tour_id IS NOT NULL
        """)


        conexion.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_alerta_protocolo_tipo
            ON alertas (
                protocolo_id,
                tipo
            )
            WHERE protocolo_id IS NOT NULL
        """)

        # ==========================================
        # DIFERENCIAS
        # ==========================================

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS diferencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                fecha TEXT NOT NULL,

                tipo_visita_origen_id INTEGER NOT NULL,
                tipo_visita_destino_id INTEGER NOT NULL,

                cantidad INTEGER NOT NULL,

                descripcion TEXT,

                creado_en TEXT NOT NULL,

                usuario_id INTEGER NOT NULL,

                recepcion_estado TEXT NOT NULL
                    DEFAULT 'PENDIENTE',

                tour_origen_id INTEGER,
                tour_destino_id INTEGER,

                confirmado_en TEXT,
                confirmado_por INTEGER,

                estado TEXT NOT NULL
                    DEFAULT 'ACTIVO',

                FOREIGN KEY (
                    tipo_visita_origen_id
                )
                REFERENCES tipos_visita(id),

                FOREIGN KEY (
                    tipo_visita_destino_id
                )
                REFERENCES tipos_visita(id),

                FOREIGN KEY (
                    usuario_id
                )
                REFERENCES usuarios(id),

                FOREIGN KEY (
                    tour_origen_id
                )
                REFERENCES tours(id),

                FOREIGN KEY (
                    tour_destino_id
                )
                REFERENCES tours(id),

                FOREIGN KEY (
                    confirmado_por
                )
                REFERENCES usuarios(id),

                CHECK (
                    cantidad > 0
                ),

                CHECK (
                    tipo_visita_origen_id
                    !=
                    tipo_visita_destino_id
                ),

                CHECK (
                    recepcion_estado IN (
                        'PENDIENTE',
                        'CONFIRMADA'
                    )
                ),

                CHECK (
                    estado IN (
                        'ACTIVO',
                        'ANULADO'
                    )
                )
            )
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_diferencias_fecha
            ON diferencias(fecha)
        """)


        conexion.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_diferencias_estado_recepcion
            ON diferencias(
                recepcion_estado
            )
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