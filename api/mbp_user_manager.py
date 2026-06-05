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
    Genera una contraseña aleatoria, calcula su hash, guarda el usuario en Redis
    y retorna la contraseña plana para ser enviada por correo.
    """
    email_normalizado = email.lower().strip()
    key = f"cliente_mbp:{email_normalizado}"
    
    # 1. Generar la contraseña en texto plano
    caracteres = string.ascii_letters + string.digits
    password_plana = ''.join(secrets.choice(caracteres) for _ in range(8))
    
    # 2. Encriptar la contraseña (hash)
    password_hash = generate_password_hash(password_plana)
    
    # 3. Preparar la estructura
    fecha_creacion = datetime.now().isoformat()
    datos_usuario = {
        "email": email_normalizado,
        "curso": curso,
        "status": "activo",
        "created_at": fecha_creacion,
        "login_count": "0",
        "password_hash": password_hash
    }
    
    try:
        # 4. Guardar en Redis
        r = get_webhook_redis_client()
        r.hset(key, mapping=datos_usuario)
        
        # 5. Retornar la contraseña en texto plano
        return password_plana
    except Exception as e:
        print(f"Error al escribir el nuevo cliente en Redis: {e}")
        return None