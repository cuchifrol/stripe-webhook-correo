from http.server import BaseHTTPRequestHandler
import json
import os
import smtplib, ssl
from email.message import EmailMessage
import stripe  # <-- ¡NUESTRA PRIMERA LIBRERÍA EXTERNA!
from pathlib import Path # <-- ¡AÑADE ESTA LÍNEA!

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # --- 1. CONFIGURAR LA LIBRERÍA DE STRIPE ---
        # Le decimos a la librería que use nuestra clave secreta.
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

        # --- 2. LEER LOS DATOS DEL WEBHOOK ---
        content_length = int(self.headers['Content-Length'])
        evento_stripe = json.loads(self.rfile.read(content_length))

        print(f"Webhook recibido: {evento_stripe.get('type')}")

        if evento_stripe.get('type') == 'payment_intent.succeeded':
            print("-> Evento de pago exitoso detectado.")

            try:
                datos_pago = evento_stripe['data']['object']
                id_del_cargo = datos_pago.get('latest_charge')

                if id_del_cargo:
                    # --- 3. EL TRUCO: USAR EL ID PARA PEDIR EL OBJETO DEL CARGO COMPLETO ---
                    print(f"-> Obteniendo detalles completos del cargo: {id_del_cargo}")
                    cargo_completo = stripe.Charge.retrieve(id_del_cargo)

                    # Ahora, en `cargo_completo` SÍ tenemos los detalles de facturación.
                    email_cliente = cargo_completo.billing_details.email

                    if email_cliente:
                        print(f"-> ¡ÉXITO! Correo encontrado en los detalles del cargo: {email_cliente}")
                        monto = datos_pago['amount'] / 100
                        moneda = datos_pago['currency'].upper()

                        # --- EXTRACCIÓN DE NUEVOS DATOS ---
                        nombre_cliente = cargo_completo.billing_details.name
                        direccion_envio = cargo_completo.shipping

                        nombre_producto = cargo_completo.description or datos_pago.get('description') or "Tu Compra"
                        print(f"-> Nombre del producto encontrado: {nombre_producto}")

                        self.enviar_correo_confirmacion(email_cliente, monto, moneda, nombre_cliente, direccion_envio,
                                                        nombre_producto)


                    else:
                        print("-> ADVERTENCIA: Se recuperó el cargo pero no contenía un email en billing_details.")
                else:
                    print("-> ADVERTENCIA: El evento no contenía un 'latest_charge' ID.")

            except Exception as e:
                print(f"-> ERROR PROCESANDO EL EVENTO: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Webhook procesado.")
        return

    def enviar_correo_confirmacion(self, destinatario, monto, moneda, nombre_cliente, direccion_envio, nombre_producto):
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
        cuerpo_html = cuerpo_html.replace('{{NOMBRE_PRODUCTO}}', nombre_producto) # <-- ¡AÑADE ESTA LÍNEA!

        asunto = f"Tu pedido en micosmeticanatural.com se ha sido confirmado ({monto_formateado})"
        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = destinatario
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