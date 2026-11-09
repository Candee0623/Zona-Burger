import requests
import re

# URL del endpoint de registro de compras
url = "https://zonaburger.com.ar/panel/stock/compras/registrar/"

# Tu cookie de sesión activa obtenida del navegador
session_id = "qememeek3zhvo1squqt0dd15e8k0s1z9"

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": f"sessionid={session_id}"
}

print("1. Obteniendo la página y el token CSRF fresco...")
response = session.get(url, headers=headers)

print("Código HTTP GET:", response.status_code)

# Extraemos el token CSRF del formulario HTML
match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', response.text)
if match:
    csrf_token = match.group(1)
    print(f"Token CSRF extraído con éxito: {csrf_token[:10]}...")
else:
    # Si no lo encuentra, usamos el de las cookies
    csrf_token = session.cookies.get('csrftoken', '')
    print("Aviso: Token CSRF tomado de la cookie.")

# Preparamos las cabeceras completas con el token CSRF
headers["Referer"] = url
headers["X-CSRFToken"] = csrf_token

# Aseguramos que la cookie de csrf esté en la sesión
if csrf_token:
    session.cookies.set('csrftoken', csrf_token)

# Datos de la prueba STK-022 (Insumo inexistente: 99999)
payload = {
    "csrfmiddlewaretoken": csrf_token,
    "idinsumo": 99999,
    "cantidad": 5,
    "preciototal": 1000,
    "lote": "LOTE-TEST-01"
}

print("\n2. Enviando la petición POST con el insumo inválido (STK-022)...")
post_response = session.post(url, data=payload, headers=headers)

print("Código HTTP POST:", post_response.status_code)
print("\n--- RESPUESTA DEL SERVIDOR ---")
print(post_response.text[:1000]) # Mostramos los primeros 1000 caracteres para ver el mensaje de error