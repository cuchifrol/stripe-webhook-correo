# Reemplaza todo el archivo api/webhook.py
from flask import Flask, request, Response
import json
import os
import smtplib, ssl
from email.message import EmailMessage
import stripe
from pathlib import Path

# Creamos la aplicación Flask
app = Flask(__name__)


# Movemos la función de enviar correo fuera para que sea independiente
def enviar_correo_confirmacion(destinatario, monto, moneda, nombre_cliente, direccion_envio, nombre_producto):
    print("-> Iniciando envío de correo con plantilla HTML...")

    remitente = os.environ.get('CORREO_USER')
    password = os.environ.get('CORREO_PASS')
    servidor_smtp = os.environ.get('SMTP_SERVER')
    puerto_smtp = int(os.environ.get('SMTP_PORT'))

    if not all([remitente, password, servidor_smtp, puerto_smtp]):
        print("-> ERROR FATAL: Faltan variables de entorno del correo.")
        return

    # --- ¡AQUÍ ESTÁ LA SOLUCIÓN! CONSTRUIMOS LA RUTA CORRECTA ---
    try:
        # 1. Obtenemos la ruta de la carpeta donde está este script (api/)
        script_dir = Path(__file__).parent
        # 2. Subimos un nivel para llegar a la raíz del proyecto
        base_dir = script_dir.parent
        # 3. Unimos la ruta raíz con el nombre del archivo de la plantilla
        template_path = base_dir / 'correo_template.html'

        print(f"-> Intentando leer la plantilla desde la ruta: {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            cuerpo_html = f.read()
    except FileNotFoundError:
        print(f"-> ERROR FATAL: No se encontró el archivo de plantilla en la ruta esperada: {template_path}")
        return
    except Exception as e:
        print(f"-> ERROR LEYENDO EL ARCHIVO DE PLANTILLA: {e}")
        return

    # --- El resto del código para reemplazar variables y enviar es el mismo ---
    monto_formateado = f"{monto:.2f} {moneda}"
    nombre_formateado = nombre_cliente.title() if nombre_cliente else " "

    if direccion_envio and direccion_envio.address:
        addr = direccion_envio.address
        direccion_formateada = f"{addr.line1}<br>{f'{addr.line2}<br>' if addr.line2 else ''}{addr.postal_code} {addr.city}, {addr.state}<br>{addr.country}".strip()
    else:
        direccion_formateada = "No se ha especificado una dirección de envío."

    cuerpo_html = cuerpo_html.replace('{{NOMBRE_CLIENTE}}', nombre_formateado)
    cuerpo_html = cuerpo_html.replace('{{MONTO_PAGO}}', monto_formateado)
    cuerpo_html = cuerpo_html.replace('{{DIRECCION_ENTREGA}}', direccion_formateada)
    cuerpo_html = cuerpo_html.replace('{{NOMBRE_PRODUCTO}}', nombre_producto)  # <-- ¡AÑADE ESTA LÍNEA!

    asunto = f"Tu pedido en micosmeticanatural.com ha sido confirmado."
    msg = EmailMessage()
    msg['Subject'] = asunto
    nombre_a_mostrar = os.environ.get('NOMBRE_CORREO')  # <-- CAMBIA ESTO POR TU NOMBRE O EL DE TU NEGOCIO
    msg['From'] = f"{nombre_a_mostrar} <{remitente}>"
    msg['To'] = destinatario
    msg['Cc'] = remitente
    
    msg.set_content(
        "Hemos recibido tu pago correctamente. Este correo se visualiza mejor en un cliente de correo moderno.")
    msg.add_alternative(cuerpo_html, subtype='html')

    try:
        contexto_seguro = ssl.create_default_context()
        with smtplib.SMTP_SSL(servidor_smtp, puerto_smtp, context=contexto_seguro) as server:
            server.login(remitente, password)
            server.send_message(msg)
            print(f"-> Correo con plantilla enviado exitosamente a {destinatario}.")
    except Exception as e:
        print(f"-> ERROR AL ENVIAR CORREO CON PLANTILLA: {e}")


# Esta es nuestra ruta de webhook, que ahora usa Flask
@app.route('/api/webhook', methods=['POST'])
def stripe_webhook():
    # --- 1. CONFIGURACIÓN INICIAL ---
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
#coment to test
    # --- 2. VERIFICACIÓN DE LA FIRMA (Máxima Seguridad) ---
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        print(f"Webhook verificado y recibido: {event.get('type')}")
    except ValueError as e:
        # Cuerpo del payload inválido
        print(f"ERROR: Payload inválido. {e}")
        return Response(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Firma inválida
        print(f"ERROR: Fallo en la verificación de la firma. {e}")
        return Response(status=400)

    # --- 3. MANEJAR EL EVENTO 'checkout.session.completed' ---
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        try:
            # Obtenemos los datos del cliente de la sesión
            email_cliente = session.get('customer_details', {}).get('email')
            nombre_cliente = session.get('customer_details', {}).get('name')
            direccion_envio = session.get('shipping_details')

            # Obtenemos los datos del pago
            monto = session.get('amount_total', 0) / 100
            moneda = session.get('currency', 'usd').upper()

            if not email_cliente:
                raise ValueError("No se encontró email en los detalles de la sesión.")

            # Obtenemos el nombre del producto de los Line Items
            line_items = stripe.checkout.Session.list_line_items(session['id'], limit=5)
            nombres_productos = [item.description for item in line_items.data]
            nombre_producto = ", ".join(nombres_productos) if nombres_productos else "Tu Compra"

            print(f"-> Sesión procesada. Producto: {nombre_producto}, Cliente: {email_cliente}")

            # Llamamos a nuestra función de envío de correo
            # (Hay que definirla fuera o dentro de esta función)
            enviar_correo_confirmacion(email_cliente, monto, moneda, nombre_cliente, direccion_envio, nombre_producto)
            #enviar_correo_confirmacion(os.environ.get('CORREO_USER'), monto, moneda, nombre_cliente, direccion_envio, nombre_producto)
        except Exception as e:
            print(f"-> ERROR al procesar la sesión de checkout: {e}")
            return Response(status=500)

    return Response(status=200)

