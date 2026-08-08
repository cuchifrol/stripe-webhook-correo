# mbp_user_manager.py

import os
import secrets
import string
import redis
from datetime import datetime
from werkzeug.security import generate_password_hash


def get_webhook_redis_client():
    """
    Establece la conexión con la base de datos de Redis en el Webhook.
    """
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("REDIS_USER")
    if not redis_url:
        raise ValueError("No se configuró la variable de entorno para conectar a Redis.")
    return redis.from_url(redis_url, decode_responses=True)


def registrar_cliente_con_password(email: str, curso: str) -> str:
    """
    Si el cliente ya existe en Redis:
        - Mantiene su usuario y contraseña.
        - Añade el nuevo curso al campo 'curso', separado por ';'.

    Si el cliente no existe:
        - Genera una contraseña nueva.
        - Guarda el usuario en Redis.
        - Retorna la contraseña plana para enviarla por correo.
    """

    email_normalizado = email.lower().strip()
    curso_normalizado = curso.strip()
    key = f"cliente_mbp:{email_normalizado}"

    try:
        # Conectar con Redis
        r = get_webhook_redis_client()

        # ---------------------------------------------------------
        # 1. COMPROBAR SI EL CLIENTE YA EXISTE
        # ---------------------------------------------------------
        if r.exists(key):

            datos_existentes = r.hgetall(key)

            curso_actual = datos_existentes.get("curso", "")

            # Convertimos "MBP;TIMON" en una lista
            cursos = [c.strip() for c in curso_actual.split(";") if c.strip()]

            # Añadir el nuevo curso solamente si todavía no lo tiene
            if curso_normalizado not in cursos:
                cursos.append(curso_normalizado)

                nuevo_curso = ";".join(cursos)

                r.hset(key, "curso", nuevo_curso)

                print(
                    f"Cliente existente: {email_normalizado}. "
                    f"Curso añadido: {curso_normalizado}. "
                    f"Cursos actuales: {nuevo_curso}"
                )
            else:

                print(
                    f"Cliente existente: {email_normalizado}. "
                    f"Ya tiene el curso {curso_normalizado}."
                )

            # IMPORTANTE:
            # No generamos una nueva contraseña.
            # Devolvemos None porque el usuario ya tiene contraseña.
            return None,1

        # ---------------------------------------------------------
        # 2. SI NO EXISTE, CREAR CLIENTE NUEVO
        # ---------------------------------------------------------

        # Generar contraseña en texto plano
        caracteres = string.ascii_letters + string.digits
        password_plana = ''.join(
            secrets.choice(caracteres) for _ in range(8)
        )

        # Encriptar contraseña (hash)
        password_hash = generate_password_hash(password_plana)

        # Preparar la estructura
        fecha_creacion = datetime.now().isoformat()

        datos_usuario = {
            "email": email_normalizado,
            "curso": curso_normalizado,
            "status": "activo",
            "created_at": fecha_creacion,
            "login_count": "0",
            "password_hash": password_hash
        }

        # Guardar en Redis
        r.hset(key, mapping=datos_usuario)

        print(
            f"Nuevo cliente creado: {email_normalizado}. "
            f"Curso: {curso_normalizado}"
        )

        # Retornar contraseña en texto plano, portal_cliente=0 pues no existía
        return password_plana, 0

    except Exception as e:
        print(f"Error al escribir el cliente en Redis: {e}")
        #portal cliente=1 pues ya existía
        return None, 0