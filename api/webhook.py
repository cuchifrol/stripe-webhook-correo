from http.server import BaseHTTPRequestHandler
import json


# Vercel espera una clase llamada 'handler' que herede de BaseHTTPRequestHandler
class handler(BaseHTTPRequestHandler):

    # Esta función se ejecutará cuando Stripe envíe una petición POST
    def do_POST(self):

        # 1. Leemos los datos que envía Stripe
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # 2. Nuestro "Hola Mundo": Imprimimos un mensaje y los datos en los logs del servidor.
        #    Esto nos permitirá verificar que la conexión funciona.
        print("¡Hola Mundo! Se ha recibido una llamada desde el Webhook de Stripe.")
        print("-------------------- INICIO DE DATOS --------------------")
        try:
            # Intentamos formatear los datos como un diccionario para que se lean mejor
            datos_diccionario = json.loads(post_data)
            print(json.dumps(datos_diccionario, indent=4))
        except:
            # Si no se puede, simplemente imprimimos el texto bruto
            print(post_data.decode('utf-8'))
        print("--------------------- FIN DE DATOS ----------------------")

        # 3. Respondemos a Stripe con un código "200 OK" para decirle que
        #    hemos recibido su notificación correctamente.
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Hola Stripe. Webhook recibido. Gracias.")

        return