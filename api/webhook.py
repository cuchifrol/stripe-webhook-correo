from http.server import BaseHTTPRequestHandler
import json
import os
import smtplib, ssl
from email.message import EmailMessage
import stripe  # <-- ¡NUESTRA PRIMERA LIBRERÍA EXTERNA!


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
                        self.enviar_correo_confirmacion(email_cliente, monto, moneda)
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

    def enviar_correo_confirmacion(self, destinatario, monto, moneda):
        # (Esta función se queda exactamente igual que antes)
        print("-> Iniciando envío de correo...")
        remitente = os.environ.get('CORREO_USER')
        password = os.environ.get('CORREO_PASS')
        servidor_smtp = os.environ.get('SMTP_SERVER')
        puerto_smtp = int(os.environ.get('SMTP_PORT'))

        if not all([remitente, password, servidor_smtp, puerto_smtp]):
            print("-> ERROR FATAL: Faltan variables de entorno del correo.")
            return

        asunto = "¡Gracias por tu compra!"
        cuerpo_html = f"""
        <html><body><h1>Confirmación de tu pago</h1><p>Hemos recibido tu pago de <strong>{monto:.2f} {moneda}</strong>. ¡Gracias!</p></body></html>
        """
        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = destinatario
        msg.set_content(f"Hemos recibido tu pago de {monto:.2f} {moneda}. ¡Gracias!")
        msg.add_alternative(cuerpo_html, subtype='html')

        try:
            contexto_seguro = ssl.create_default_context()
            with smtplib.SMTP_SSL(servidor_smtp, puerto_smtp, context=contexto_seguro) as server:
                server.login(remitente, password)
                server.send_message(msg)
                print(f"-> Correo de confirmación enviado a {destinatario}.")
        except Exception as e:
            print(f"-> ERROR AL ENVIAR CORREO: {e}")