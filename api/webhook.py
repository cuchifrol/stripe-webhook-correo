# --- 1. IMPORTACIONES NECESARIAS ---
# Todas estas son librerías estándar de Python, no necesitan instalación.
from http.server import BaseHTTPRequestHandler
import json
import os  # La herramienta CLAVE para leer nuestras Variables de Entorno (secretos).
import smtplib, ssl  # Las herramientas para enviar correos usando SMTP.
from email.message import EmailMessage  # Una clase para construir correos con formato.


# --- 2. EL MANEJADOR DEL WEBHOOK (Nuestra clase principal) ---
# Vercel buscará y ejecutará esta clase cuando reciba una petición.
class handler(BaseHTTPRequestHandler):

    # Esta función se ejecuta específicamente cuando la petición es de tipo POST (que es lo que hace Stripe).
    def do_POST(self):
        # --- 3. LEER Y DECODIFICAR LOS DATOS DE STRIPE ---
        content_length = int(self.headers['Content-Length'])
        post_data_bytes = self.rfile.read(content_length)
        evento_stripe = json.loads(post_data_bytes)

        # Imprimimos en los logs de Vercel para saber que hemos recibido algo.
        print(f"¡Webhook recibido! Procesando evento tipo: {evento_stripe.get('type')}")

        # --- 4. VERIFICAR QUE ES EL EVENTO QUE NOS INTERESA ---
        # Solo queremos actuar cuando un pago se ha completado con éxito.
        if evento_stripe.get('type') == 'payment_intent.succeeded':
            print("-> Evento 'payment_intent.succeeded' detectado. Procediendo a enviar correo.")

            try:
                # Intentamos extraer el email del cliente. La información puede venir en varios campos.
                # Esta es la ruta típica donde Stripe lo coloca.
                email_cliente = evento_stripe['data']['object']['receipt_email']
                # También extraemos el monto y la moneda para personalizar el correo.
                monto = evento_stripe['data']['object']['amount'] / 100  # Stripe lo envía en céntimos
                moneda = evento_stripe['data']['object']['currency'].upper()

                if email_cliente:
                    print(f"-> Correo del cliente encontrado: {email_cliente}")
                    # Si encontramos un email, llamamos a nuestra función para enviarlo.
                    self.enviar_correo_confirmacion(email_cliente, monto, moneda)
                else:
                    print("-> ADVERTENCIA: No se encontró un 'receipt_email' en el evento de Stripe.")

            except KeyError:
                print(
                    "-> ERROR: No se pudo encontrar el email o el monto en los datos del evento. La estructura puede haber cambiado.")

        # --- 5. RESPONDER A STRIPE QUE TODO HA IDO BIEN ---
        # Esto es muy importante. Le decimos a Stripe "Recibido, gracias" para que no lo siga reintentando.
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Webhook procesado y finalizado.")
        return

    # --- FUNCIÓN AUXILIAR PARA ENVIAR EL CORREO ---
    def enviar_correo_confirmacion(self, destinatario, monto, moneda):
        print("-> Iniciando la función para enviar correo...")

        # --- 6. LEER NUESTROS SECRETOS DE LAS VARIABLES DE ENTORNO ---
        # `os.environ.get()` le pide a Vercel el valor de la variable.
        # El código NUNCA ve la contraseña real, solo la referencia a ella.
        remitente = os.environ.get('CORREO_USER')
        password = os.environ.get('CORREO_PASS')
        servidor_smtp = os.environ.get('SMTP_SERVER')
        puerto_smtp = int(os.environ.get('SMTP_PORT'))  # El puerto debe ser un número entero (int)

        # Verificación: Nos aseguramos de que todas las variables fueron encontradas.
        if not all([remitente, password, servidor_smtp, puerto_smtp]):
            print(
                "-> ERROR FATAL: Faltan una o más variables de entorno para el correo. Revisa la configuración en Vercel.")
            return  # Salimos de la función si faltan datos.

        # --- 7. CONSTRUIR EL MENSAJE DEL CORREO ---
        asunto = "¡Gracias por tu compra en Mi Tienda!"
        cuerpo_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; }}
                .container {{ padding: 20px; border: 1px solid #ddd; border-radius: 5px; max-width: 600px; margin: auto; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Confirmación de tu pago</h1>
                <p>Hola,</p>
                <p>Hemos recibido tu pago de <strong>{monto:.2f} {moneda}</strong> correctamente. ¡Muchas gracias por tu confianza!</p>
                <p>Si tienes cualquier duda, responde a este correo.</p>
                <p>Saludos,<br>El equipo de Mi Tienda</p>
            </div>
        </body>
        </html>
        """

        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = destinatario
        # Es buena práctica tener una versión de texto simple para clientes de correo antiguos.
        msg.set_content(f"Hemos recibido tu pago de {monto:.2f} {moneda} correctamente. ¡Muchas gracias!")
        # Añadimos la versión HTML que es la que se verá normalmente.
        msg.add_alternative(cuerpo_html, subtype='html')

        # --- 8. CONECTAR Y ENVIAR EL CORREO DE FORMA SEGURA ---
        try:
            print(f"-> Intentando conectar con {servidor_smtp} en el puerto {puerto_smtp}...")
            # Creamos un contexto seguro SSL para encriptar la conexión.
            contexto_seguro = ssl.create_default_context()

            # Usamos "with" para asegurar que la conexión se cierra automáticamente.
            with smtplib.SMTP_SSL(servidor_smtp, puerto_smtp, context=contexto_seguro) as server:
                print("-> Conexión establecida. Intentando iniciar sesión...")
                server.login(remitente, password)
                print("-> Sesión iniciada. Enviando correo...")
                server.send_message(msg)
                print(f"-> ¡ÉXITO! Correo de confirmación enviado a {destinatario}.")

        except Exception as e:
            # Capturamos cualquier error (contraseña incorrecta, servidor no responde, etc.)
            # para poder verlo en los logs de Vercel y saber qué ha pasado.
            print(f"-> HA OCURRIDO UN ERROR INESPERADO AL ENVIAR EL CORREO: {e}")