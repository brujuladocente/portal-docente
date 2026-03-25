import requests
import json
import sys

# ==============================================================================
# INSTRUCCIONES:
# Pegá acá la URL de tu Google Apps Script (La que termina en /exec)
# Ejemplo: "https://script.google.com/macros/s/AKfy.../exec"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwYNGUE5U2oEPtFOSN73CdasMFk6TMrQH0TFgVTntY8nAEvvXYOmdPQMuNpYbi5nQDUNw/exec"

# Poné un ID de pago real de Mercado Pago que figure en tu cuenta como "Aprobado"
# O dejá este de prueba (probablemente falle el Access Token si no es tuyo)
PAYMENT_ID_DE_PRUEBA = "1234567890" 
# ==============================================================================

def test_webhook():
    if WEBHOOK_URL == "URL_DE_TU_APPS_SCRIPT_AQUI":
        print("❌ ERROR: Tenés que pegar tu URL del Apps Script en la variable WEBHOOK_URL dentro de test_webhook.py")
        sys.exit(1)

    print(f"🚀 Simulando notificación de Mercado Pago hacia:\n{WEBHOOK_URL}")
    print(f"📦 Enviando ID de pago: {PAYMENT_ID_DE_PRUEBA}...")

    # Payload que envía Mercado Pago (Notificación IPN estándar)
    payload = {
        "action": "payment.created",
        "api_version": "v1",
        "data": {
            "id": PAYMENT_ID_DE_PRUEBA
        },
        "date_created": "2026-03-25T00:00:00Z",
        "id": 11223344,
        "live_mode": True,
        "type": "payment",
        "user_id": "123456"
    }

    try:
        # Hacemos el POST de prueba
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        print(f"\n📡 Código de respuesta HTTP: {response.status_code}")
        
        # Google Web Apps devuelve 200 siempre si el script corre y termina bien o si devuelve .createTextOutput
        # Si devuelve HTML gigante con error de Google, el script falló antes de ejecutar nuestro código.
        if response.status_code == 200:
            content = response.text
            if "<html" in content.lower():
                print("❌ ERROR DE PERMISOS DE GOOGLE:")
                print("Google bloqueó la petición con una página HTML de error (Suele ser la página de login).")
                print("-> Solución: Volvé a 'Implementar > Nueva Implementación' en Apps Script.")
                print("-> Asegurate de poner 'Quién tiene acceso: Cualquier persona (Everyone)'.")
            else:
                print("✅ Google Apps Script respondió:")
                print(f"Respuesta del script: {content}")
                print("Si dice 'OK', el script de Google se ejecutó sin colgarse.")
                print("Si aún no se actualiza tu Sheet, verificá el Menú 'Ejecuciones' o 'Executions' en Apps Script para ver si falló internamente (ej: Token de MP inválido).")
        else:
            print("❌ Google Apps Script devolvió un error HTTP:")
            print(response.text)

    except Exception as e:
        print(f"❌ Error al intentar conectar: {e}")

if __name__ == "__main__":
    test_webhook()
