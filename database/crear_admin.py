import getpass
import sqlite3

from werkzeug.security import generate_password_hash


DATABASE = "database/database.db"


nombre = input("Nombre completo: ").strip()
usuario = input("Nombre de usuario: ").strip()
password = getpass.getpass("Contraseña: ")
confirmacion = getpass.getpass("Repetir contraseña: ")


if not nombre or not usuario or not password:
    print("Todos los datos son obligatorios.")
    raise SystemExit(1)


if password != confirmacion:
    print("Las contraseñas no coinciden.")
    raise SystemExit(1)


password_hash = generate_password_hash(password)

conexion = sqlite3.connect(DATABASE)

try:
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
        usuario,
        password_hash,
        "ADMIN",
        "ACTIVO"
    ))

    conexion.commit()

except sqlite3.IntegrityError:
    print("Ese nombre de usuario ya existe.")

else:
    print("Administrador creado correctamente.")

finally:
    conexion.close()