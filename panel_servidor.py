import json
import os
import socket
import subprocess
import sys
import webbrowser
import time
from pathlib import Path
from datetime import datetime
from rutas_sistema import (
    ARCHIVO_DATABASE,
    ARCHIVO_LOG_SERVIDOR,
    CARPETA_BACKUPS,
    CARPETA_LOGS,
    crear_carpetas_sistema
)

from database.backup_db import crear_backup

import tkinter as tk
from tkinter import messagebox, ttk


PUERTO_PREDETERMINADO = 8080


def obtener_carpeta_programa():

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


BASE_PROYECTO = obtener_carpeta_programa()

CARPETA_CONFIGURACION = (
    Path(
        os.environ.get(
            "APPDATA",
            BASE_PROYECTO
        )
    )
    / "SistemaMuseoRiver"
)

ARCHIVO_CONFIGURACION_PANEL = (
    CARPETA_CONFIGURACION
    / "panel_servidor.json"
)


class PanelServidor:

    def __init__(self, ventana):

        self.ventana = ventana

        self.proceso_servidor = None
        self.archivo_log_servidor = None
        self.puerto_en_ejecucion = None
        self.cerrando = False
        crear_carpetas_sistema()
        configuracion = self.cargar_configuracion()

        self.puerto_var = tk.StringVar(
            value=str(
                configuracion.get(
                    "puerto",
                    PUERTO_PREDETERMINADO
                )
            )
        )

        self.abrir_navegador_var = tk.BooleanVar(
            value=configuracion.get(
                "abrir_navegador",
                True
            )
        )

        self.inicio_automatico_var = tk.BooleanVar(
            value=configuracion.get(
                "inicio_automatico",
                False
            )
        )

        self.direccion_local_var = tk.StringVar()
        self.direccion_red_var = tk.StringVar()

        self.ultimo_backup_var = tk.StringVar(value="Último backup: ninguno")

        self.ventana.title(
            "Servidor - Sistema Museo River"
        )

        self.ventana.geometry("800x800")
        self.ventana.resizable(False, False)

        self.crear_interfaz()
        self.actualizar_ultimo_backup()
        self.actualizar_direcciones()
        self.actualizar_estado()
        self.vigilar_servidor()

        self.puerto_var.trace_add(
            "write",
            lambda *_: self.actualizar_direcciones()
        )

        self.ventana.protocol(
            "WM_DELETE_WINDOW",
            self.cerrar_aplicacion
        )

        if self.inicio_automatico_var.get():

            self.ventana.after(
                500,
                self.iniciar_servidor
            )

    def crear_interfaz(self):

        contenedor = ttk.Frame(
            self.ventana,
            padding=25
        )

        contenedor.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            contenedor,
            text="Sistema Museo River",
            font=("Arial", 20, "bold")
        ).pack(pady=(0, 5))

        ttk.Label(
            contenedor,
            text="Panel de administración del servidor",
            font=("Arial", 10)
        ).pack(pady=(0, 20))

        self.etiqueta_estado = ttk.Label(
            contenedor,
            text="● Servidor apagado",
            font=("Arial", 14, "bold"),
            foreground="#b0000a"
        )

        self.etiqueta_estado.pack(
            pady=(0, 15)
        )

        bloque_configuracion = ttk.LabelFrame(
            contenedor,
            text="Configuración",
            padding=15
        )

        bloque_configuracion.pack(
            fill="x",
            pady=(0, 15)
        )

        fila_puerto = ttk.Frame(
            bloque_configuracion
        )

        fila_puerto.pack(
            fill="x",
            pady=(0, 10)
        )

        ttk.Label(
            fila_puerto,
            text="Puerto:"
        ).pack(side="left")

        self.campo_puerto = ttk.Spinbox(
            fila_puerto,
            from_=1024,
            to=65535,
            textvariable=self.puerto_var,
            width=10
        )

        self.campo_puerto.pack(
            side="left",
            padx=(10, 0)
        )

        ttk.Label(
            fila_puerto,
            text="Ejemplo: 8080, 5000 u 8000",
            foreground="#666666"
        ).pack(
            side="left",
            padx=(12, 0)
        )

        ttk.Checkbutton(
            bloque_configuracion,
            text="Abrir el navegador al iniciar el servidor",
            variable=self.abrir_navegador_var
        ).pack(
            anchor="w",
            pady=3
        )

        ttk.Checkbutton(
            bloque_configuracion,
            text="Iniciar el servidor al abrir este panel",
            variable=self.inicio_automatico_var
        ).pack(
            anchor="w",
            pady=3
        )

        bloque_direcciones = ttk.LabelFrame(
            contenedor,
            text="Direcciones del sistema",
            padding=15
        )

        bloque_direcciones.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            bloque_direcciones,
            textvariable=self.direccion_local_var
        ).pack(
            anchor="w",
            pady=3
        )

        ttk.Label(
            bloque_direcciones,
            textvariable=self.direccion_red_var
        ).pack(
            anchor="w",
            pady=3
        )

        botones_red = ttk.Frame(
            bloque_direcciones
        )

        botones_red.pack(
            fill="x",
            pady=(12, 0)
        )

        botones_red.columnconfigure(
            0,
            weight=1
        )

        botones_red.columnconfigure(
            1,
            weight=1
        )


        ttk.Button(
            botones_red,
            text="Ver configuración de red",
            command=self.mostrar_configuracion_red
        ).grid(
            row=0,
            column=0,
            padx=(0, 5),
            sticky="ew"
        )


        ttk.Button(
            botones_red,
            text="Abrir configuración del router",
            command=self.abrir_router
        ).grid(
            row=0,
            column=1,
            padx=(5, 0),
            sticky="ew"
        )

        botones_principales = ttk.Frame(
            contenedor
        )

        botones_principales.pack(
            pady=(5, 8)
        )

        self.boton_iniciar = ttk.Button(
            botones_principales,
            text="Iniciar servidor",
            command=self.iniciar_servidor
        )

        self.boton_iniciar.grid(
            row=0,
            column=0,
            padx=5,
            pady=5
        )

        self.boton_detener = ttk.Button(
            botones_principales,
            text="Detener servidor",
            command=self.detener_servidor
        )

        self.boton_detener.grid(
            row=0,
            column=1,
            padx=5,
            pady=5
        )

        self.boton_abrir = ttk.Button(
            botones_principales,
            text="Abrir sistema",
            command=self.abrir_sistema
        )

        self.boton_abrir.grid(
            row=1,
            column=0,
            padx=5,
            pady=5,
            sticky="ew"
        )

        self.boton_copiar = ttk.Button(
            botones_principales,
            text="Copiar dirección de red",
            command=self.copiar_direccion_red
        )

        self.boton_copiar.grid(
            row=1,
            column=1,
            padx=5,
            pady=5,
            sticky="ew"
        )

        ttk.Button(
            botones_principales,
            text="Abrir registros",
            command=self.abrir_carpeta_logs
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            padx=5,
            pady=5,
            sticky="ew"
        )
        bloque_backups = ttk.LabelFrame(
            contenedor,
            text="Backups de la base de datos",
            padding=15
        )

        bloque_backups.pack(
            fill="x",
            pady=(10, 10)
        )

        botones_backups = ttk.Frame(
            bloque_backups
        )

        botones_backups.pack(
            fill="x"
        )

        botones_backups.columnconfigure(
            0,
            weight=1
        )

        botones_backups.columnconfigure(
            1,
            weight=1
        )

        ttk.Button(
            botones_backups,
            text="Crear backup ahora",
            command=self.crear_backup_manual,
            padding=(12, 9)
        ).grid(
            row=0,
            column=0,
            padx=(0, 5),
            sticky="ew"
        )

        ttk.Button(
            botones_backups,
            text="Abrir carpeta de backups",
            command=self.abrir_carpeta_backups,
            padding=(12, 9)
        ).grid(
            row=0,
            column=1,
            padx=(5, 0),
            sticky="ew"
        )

        ttk.Label(
            bloque_backups,
            textvariable=self.ultimo_backup_var,
            foreground="#666666"
        ).pack(
            anchor="w",
            pady=(10, 0)
        )

    def cargar_configuracion(self):

        configuracion_default = {
            "puerto": PUERTO_PREDETERMINADO,
            "abrir_navegador": True,
            "inicio_automatico": False
        }

        if not ARCHIVO_CONFIGURACION_PANEL.exists():
            return configuracion_default

        try:

            with open(
                ARCHIVO_CONFIGURACION_PANEL,
                "r",
                encoding="utf-8"
            ) as archivo:

                configuracion_guardada = json.load(
                    archivo
                )

            configuracion_default.update(
                configuracion_guardada
            )

        except (
            OSError,
            json.JSONDecodeError
        ):
            pass

        return configuracion_default

    def guardar_configuracion(self):

        puerto = self.obtener_puerto(
            mostrar_error=False
        )

        if puerto is None:
            puerto = PUERTO_PREDETERMINADO

        configuracion = {
            "puerto": puerto,
            "abrir_navegador": (
                self.abrir_navegador_var.get()
            ),
            "inicio_automatico": (
                self.inicio_automatico_var.get()
            )
        }

        try:

            ARCHIVO_CONFIGURACION_PANEL.parent.mkdir(
                parents=True,
                exist_ok=True
                )

            with open(
                ARCHIVO_CONFIGURACION_PANEL,
                "w",
                encoding="utf-8"
            ) as archivo:

                json.dump(
                    configuracion,
                    archivo,
                    indent=4,
                    ensure_ascii=False
                )

        except OSError:
            pass

    def obtener_puerto(
        self,
        mostrar_error=True
    ):

        try:
            puerto = int(
                self.puerto_var.get().strip()
            )

        except ValueError:

            if mostrar_error:
                messagebox.showerror(
                    "Puerto inválido",
                    "El puerto debe ser un número."
                )

            return None

        if puerto < 1024 or puerto > 65535:

            if mostrar_error:
                messagebox.showerror(
                    "Puerto inválido",
                    (
                        "El puerto debe estar "
                        "entre 1024 y 65535."
                    )
                )

            return None

        return puerto

    def obtener_ip_local(self):

        socket_temporal = None

        try:

            socket_temporal = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            socket_temporal.connect(
                ("8.8.8.8", 80)
            )

            return socket_temporal.getsockname()[0]

        except OSError:
            return "IP-DEL-SERVIDOR"

        finally:

            if socket_temporal is not None:
                socket_temporal.close()

    def obtener_configuracion_red(self):

        if os.name != "nt":

            return {
                "interfaz": "No disponible",
                "ip": self.obtener_ip_local(),
                "gateway": None,
                "mac": "No disponible"
            }


        comando = r"""
    $config = Get-NetIPConfiguration |
        Where-Object {
            $_.IPv4DefaultGateway -ne $null -and
            $_.NetAdapter.Status -eq 'Up'
        } |
        Select-Object -First 1

    if ($null -eq $config) {
        exit 1
    }

    $adaptador = Get-NetAdapter `
        -InterfaceIndex $config.InterfaceIndex

    [PSCustomObject]@{
        interfaz = $config.InterfaceAlias
        ip = $config.IPv4Address.IPAddress
        gateway = $config.IPv4DefaultGateway.NextHop
        mac = $adaptador.MacAddress
    } |
    ConvertTo-Json -Compress
    """


        try:

            opciones = {}

            if os.name == "nt":

                opciones[
                    "creationflags"
                ] = subprocess.CREATE_NO_WINDOW


            resultado = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    comando
                ],
                capture_output=True,
                text=True,
                timeout=5,
                **opciones
            )


            if (
                resultado.returncode != 0
                or not resultado.stdout.strip()
            ):

                raise RuntimeError(
                    "No se pudo obtener "
                    "la configuración de red."
                )


            datos = json.loads(
                resultado.stdout
            )


            return {
                "interfaz": datos.get(
                    "interfaz",
                    "No disponible"
                ),

                "ip": datos.get(
                    "ip",
                    self.obtener_ip_local()
                ),

                "gateway": datos.get(
                    "gateway"
                ),

                "mac": datos.get(
                    "mac",
                    "No disponible"
                )
            }


        except (
            subprocess.SubprocessError,
            json.JSONDecodeError,
            OSError,
            RuntimeError
        ):

            return {
                "interfaz": "No disponible",
                "ip": self.obtener_ip_local(),
                "gateway": None,
                "mac": "No disponible"
            }

    def mostrar_configuracion_red(self):

        datos = (
            self.obtener_configuracion_red()
        )


        puerto = (
            self.puerto_en_ejecucion
            if self.servidor_activo()
            else self.obtener_puerto(
                mostrar_error=False
            )
        )


        gateway = (
            datos["gateway"]
            or "No disponible"
        )


        mensaje = (
            f"Adaptador:\n"
            f"{datos['interfaz']}\n\n"

            f"IP del servidor:\n"
            f"{datos['ip']}\n\n"

            f"Puerta de enlace / Router:\n"
            f"{gateway}\n\n"

            f"Dirección MAC:\n"
            f"{datos['mac']}\n\n"

            f"Puerto del sistema:\n"
            f"{puerto or 'No disponible'}"
        )


        messagebox.showinfo(
            "Configuración de red",
            mensaje
        )

    def abrir_router(self):

        datos = (
            self.obtener_configuracion_red()
        )


        gateway = datos["gateway"]


        if not gateway:

            messagebox.showwarning(
                "Router no encontrado",
                (
                    "No se pudo detectar "
                    "la dirección del router."
                )
            )

            return


        webbrowser.open(
            f"http://{gateway}"
        )

    def actualizar_direcciones(self):

        puerto = self.obtener_puerto(
            mostrar_error=False
        )

        if puerto is None:

            self.direccion_local_var.set(
                "En esta PC: puerto inválido"
            )

            self.direccion_red_var.set(
                "Desde la red: puerto inválido"
            )

            return

        ip_local = self.obtener_ip_local()

        self.direccion_local_var.set(
            f"En esta PC: http://127.0.0.1:{puerto}"
        )

        self.direccion_red_var.set(
            f"Desde la red: http://{ip_local}:{puerto}"
        )

    def puerto_disponible(self, puerto):

        socket_prueba = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        try:

            socket_prueba.bind(
                ("0.0.0.0", puerto)
            )

            return True

        except OSError:
            return False

        finally:
            socket_prueba.close()

    def obtener_comando_servidor(
        self,
        puerto
    ):

        if not getattr(sys, "frozen", False):

            return [
                sys.executable,
                str(
                    BASE_PROYECTO
                    / "servidor.py"
                ),
                "--port",
                str(puerto)
            ]

        ejecutable_servidor = (
            BASE_PROYECTO
            / "servidor.exe"
        )

        return [
            str(ejecutable_servidor),
            "--port",
            str(puerto)
        ]

    def iniciar_servidor(self):

        if self.servidor_activo():

            messagebox.showinfo(
                "Servidor",
                "El servidor ya está funcionando."
            )

            return

        puerto = self.obtener_puerto()

        if puerto is None:
            return

        if not self.puerto_disponible(puerto):

            messagebox.showerror(
                "Puerto ocupado",
                (
                    f"El puerto {puerto} ya está siendo "
                    "utilizado por otro programa.\n\n"
                    "Elegí otro puerto."
                )
            )

            return

        try:

            CARPETA_LOGS.mkdir(
                parents=True,
                exist_ok=True
            )

            self.archivo_log_servidor = open(
                ARCHIVO_LOG_SERVIDOR,
                "a",
                encoding="utf-8"
            )

            opciones_proceso = {
                "cwd": BASE_PROYECTO,
                "stdout": self.archivo_log_servidor,
                "stderr": subprocess.STDOUT
            }

            if os.name == "nt":

                opciones_proceso[
                    "creationflags"
                ] = subprocess.CREATE_NO_WINDOW

            self.proceso_servidor = subprocess.Popen(
                self.obtener_comando_servidor(
                    puerto
                ),
                **opciones_proceso
            )

            self.puerto_en_ejecucion = puerto

            self.guardar_configuracion()
            self.actualizar_estado()

            self.ventana.after(
                900,
                self.comprobar_inicio
            )

        except Exception as error:

            self.proceso_servidor = None
            self.puerto_en_ejecucion = None

            self.cerrar_log()

            messagebox.showerror(
                "Error",
                (
                    "No se pudo iniciar el servidor."
                    "\n\n"
                    f"{error}"
                )
            )

            self.actualizar_estado()

    def comprobar_inicio(self):

        if not self.servidor_activo():

            self.cerrar_log()

            messagebox.showerror(
                "Error",
                (
                    "El servidor no pudo iniciarse.\n"
                    "Revisá logs/servidor.log."
                )
            )

            self.proceso_servidor = None
            self.puerto_en_ejecucion = None

            self.actualizar_estado()

            return

        self.actualizar_estado()


        # --------------------------------
        # ACTUALIZAR ÚLTIMO BACKUP
        # --------------------------------

        self.actualizar_ultimo_backup()


        # Lo volvemos a comprobar unos
        # segundos después por si el backup
        # todavía estaba terminando.

        self.ventana.after(
            2000,
            self.actualizar_ultimo_backup
        )


        if self.abrir_navegador_var.get():
            self.abrir_sistema()

    def detener_servidor(self):

        if not self.servidor_activo():

            messagebox.showinfo(
                "Servidor",
                "El servidor ya está apagado."
            )

            return

        confirmado = messagebox.askyesno(
            "Detener servidor",
            (
                "¿Seguro que querés detener el servidor?"
                "\n\n"
                "Las demás computadoras perderán "
                "el acceso al sistema."
            )
        )

        if not confirmado:
            return

        self.finalizar_proceso_servidor()
        self.actualizar_estado()

    def finalizar_proceso_servidor(self):

        if not self.servidor_activo():
            return

        proceso = self.proceso_servidor

        try:

            # --------------------------------
            # WINDOWS
            # --------------------------------

            if os.name == "nt":

                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(proceso.pid),
                        "/T",
                        "/F"
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False
                )

            # --------------------------------
            # OTROS SISTEMAS
            # --------------------------------

            else:

                proceso.terminate()

                try:

                    proceso.wait(
                        timeout=5
                    )

                except subprocess.TimeoutExpired:

                    proceso.kill()
                    proceso.wait()


            # --------------------------------
            # ESPERAR LIBERACIÓN DEL PUERTO
            # --------------------------------

            if self.puerto_en_ejecucion is not None:

                for _ in range(20):

                    if self.puerto_disponible(
                        self.puerto_en_ejecucion
                    ):
                        break

                    time.sleep(0.1)


        except OSError:

            pass


        finally:

            self.proceso_servidor = None
            self.puerto_en_ejecucion = None

            self.cerrar_log()

    def abrir_sistema(self):

        if not self.servidor_activo():

            messagebox.showwarning(
                "Servidor apagado",
                "Primero iniciá el servidor."
            )

            return

        webbrowser.open(
            (
                "http://127.0.0.1:"
                f"{self.puerto_en_ejecucion}"
            )
        )

    def copiar_direccion_red(self):

        puerto = (
            self.puerto_en_ejecucion
            if self.servidor_activo()
            else self.obtener_puerto(
                mostrar_error=False
            )
        )

        if puerto is None:
            return

        direccion = (
            f"http://{self.obtener_ip_local()}:{puerto}"
        )

        self.ventana.clipboard_clear()
        self.ventana.clipboard_append(
            direccion
        )

        messagebox.showinfo(
            "Dirección copiada",
            (
                "La dirección fue copiada:"
                "\n\n"
                f"{direccion}"
            )
        )

    def abrir_carpeta_logs(self):

        CARPETA_LOGS.mkdir(
            parents=True,
            exist_ok=True
        )

        try:
            os.startfile(CARPETA_LOGS)

        except OSError as error:

            messagebox.showerror(
                "Error",
                (
                    "No se pudo abrir la carpeta."
                    "\n\n"
                    f"{error}"
                )
            )

    def crear_backup_manual(self):

        if not ARCHIVO_DATABASE.exists():

            messagebox.showerror(
                "Base de datos no encontrada",
                (
                    "No se encontró la base de datos:"
                    "\n\n"
                    f"{ARCHIVO_DATABASE}"
                )
            )

            return

        try:

            archivo_creado = crear_backup()

            self.actualizar_ultimo_backup()

            messagebox.showinfo(
                "Backup creado",
                (
                    "El backup se creó correctamente."
                    "\n\n"
                    f"{archivo_creado}"
                )
            )

        except Exception as error:

            messagebox.showerror(
                "Error al crear backup",
                (
                    "No se pudo crear el backup."
                    "\n\n"
                    f"{error}"
                )
            )


    def abrir_carpeta_backups(self):

        try:

            CARPETA_BACKUPS.mkdir(
                parents=True,
                exist_ok=True
            )

            os.startfile(
                str(CARPETA_BACKUPS)
            )

        except OSError as error:

            messagebox.showerror(
                "Error",
                (
                    "No se pudo abrir la carpeta "
                    "de backups."
                    "\n\n"
                    f"{error}"
                )
            )


    def actualizar_ultimo_backup(self):

        try:

            CARPETA_BACKUPS.mkdir(
                parents=True,
                exist_ok=True
            )

            archivos = list(
                CARPETA_BACKUPS.glob(
                    "database_*.db"
                )
            )

            if not archivos:

                self.ultimo_backup_var.set(
                    "Último backup: ninguno"
                )

                return

            ultimo_backup = max(
                archivos,
                key=lambda archivo: archivo.stat().st_mtime
            )

            fecha_modificacion = datetime.fromtimestamp(
                ultimo_backup.stat().st_mtime
            ).strftime(
                "%d/%m/%Y %H:%M"
            )

            self.ultimo_backup_var.set(
                (
                    "Último backup: "
                    f"{fecha_modificacion} — "
                    f"{ultimo_backup.name}"
                )
            )

        except OSError:

            self.ultimo_backup_var.set(
                "Último backup: no disponible"
            )

    def servidor_activo(self):

        return (
            self.proceso_servidor is not None
            and self.proceso_servidor.poll()
            is None
        )

    def vigilar_servidor(self):

        if self.cerrando:
            return

        if (
            self.proceso_servidor is not None
            and not self.servidor_activo()
        ):

            self.proceso_servidor = None
            self.puerto_en_ejecucion = None

            self.cerrar_log()
            self.actualizar_estado()

            messagebox.showerror(
                "Servidor detenido",
                (
                    "El servidor se cerró inesperadamente."
                    "\n\n"
                    "Revisá la carpeta de registros."
                )
            )

        self.ventana.after(
            1000,
            self.vigilar_servidor
        )

    def actualizar_estado(self):

        if self.servidor_activo():

            self.etiqueta_estado.config(
                text=(
                    "● Servidor encendido "
                    f"en puerto {self.puerto_en_ejecucion}"
                ),
                foreground="#198754"
            )

            self.boton_iniciar.config(
                state="disabled"
            )

            self.boton_detener.config(
                state="normal"
            )

            self.boton_abrir.config(
                state="normal"
            )

            self.campo_puerto.config(
                state="disabled"
            )

        else:

            self.etiqueta_estado.config(
                text="● Servidor apagado",
                foreground="#b0000a"
            )

            self.boton_iniciar.config(
                state="normal"
            )

            self.boton_detener.config(
                state="disabled"
            )

            self.boton_abrir.config(
                state="disabled"
            )

            self.campo_puerto.config(
                state="normal"
            )

    def cerrar_log(self):

        if self.archivo_log_servidor is None:
            return

        try:
            self.archivo_log_servidor.close()

        except OSError:
            pass

        self.archivo_log_servidor = None

    def cerrar_aplicacion(self):

        if self.servidor_activo():

            confirmado = messagebox.askyesno(
                "Cerrar panel",
                (
                    "El servidor sigue encendido."
                    "\n\n"
                    "¿Querés detenerlo y cerrar?"
                )
            )

            if not confirmado:
                return

        self.cerrando = True

        self.finalizar_proceso_servidor()
        self.guardar_configuracion()
        self.cerrar_log()

        self.ventana.destroy()


def iniciar_panel():

    ventana = tk.Tk()

    PanelServidor(ventana)

    ventana.mainloop()


if __name__ == "__main__":
    iniciar_panel()