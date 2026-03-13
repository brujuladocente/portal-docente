"""
Orquestador principal del bot para el Lector ABC con Schedule y Memoria Individual.
"""
import os
import sys
import time
import json
import schedule
from dotenv import load_dotenv
from scraper import scrape_ofertas
from database_google import obtener_usuarios_desde_sheets, normalizar_texto
from notifier import enviar_correo
from playwright.sync_api import sync_playwright

HISTORIAL_FILE = "ofertas_enviadas.json"

def cargar_historial():
    """Carga el historial desde JSON. Si no es un diccionario o falla, hace reset a {}."""
    if not os.path.exists(HISTORIAL_FILE):
        return {}
    try:
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"ATENCIÓN: Formato de {HISTORIAL_FILE} inválido. Haciendo auto-reset.")
                return {}
            return data
    except (json.JSONDecodeError, Exception) as e:
        print(f"INFO: Error al cargar historial ({e}). Creando uno nuevo.")
        return {}

def guardar_historial(historial):
    """Guarda el historial en el archivo JSON."""
    try:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, indent=2)
    except Exception as e:
        print(f"Error al guardar historial: {e}")

def job():
    print("\n" + "="*60)
    print("Iniciando ejecución programada del bot Lector ABC (Memoria Individual)...")
    print("="*60)
    
    print("Obteniendo usuarios desde la base de datos (Google Sheets)...")
    usuarios = obtener_usuarios_desde_sheets()
    if not usuarios:
        print("No se pudieron obtener usuarios o la lista está vacía. Saliendo del job.")
        return

    # Cargar historial multiusuario
    historial = cargar_historial()

    # 1. Generar lista única de todos los distritos de usuarios activos
    distritos_unicos = set()
    for u in usuarios:
        for d in u.get("distritos", []):
            distritos_unicos.add(d.upper())
    distritos_unicos = list(distritos_unicos)

    if not distritos_unicos:
        print("No hay distritos configurados en los usuarios. Saliendo del job.")
        return

    print(f"Distritos a buscar (Lista Única): {distritos_unicos}")

    with sync_playwright() as p:
        es_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        browser = p.chromium.launch(headless=es_github_actions)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Scrapear (Lista Maestra de ofertas actuales en el portal)
            lista_maestra = scrape_ofertas(page, distritos_unicos)
            print(f"Total de ofertas extraídas en Lista Maestra: {len(lista_maestra)}")

            if not lista_maestra:
                print("No se encontraron ofertas en los distritos seleccionados. Fin del ciclo.")
                return

            any_new_match = False

            # Match y Notificación por usuario individual
            for usuario in usuarios:
                mail_destino = usuario.get("email")
                nombre_usuario = usuario.get("nombre", "Colega")
                distritos_usuario = [d.upper() for d in usuario.get("distritos", [])]
                materias_usuario = [m.upper().strip() for m in usuario.get("materias", [])]
                
                # Obtener historial específico de este usuario
                usuario_sent_ids = historial.get(mail_destino, [])
                
                print(f"\n--- Evaluando ofertas para: {nombre_usuario} ({mail_destino}) ---")
                
                ofertas_match = []
                for oferta in lista_maestra:
                    oferta_id = oferta["id"]
                    oferta_distrito = normalizar_texto(oferta["distrito"])
                    oferta_codigo = oferta["codigo_area"].upper().strip()
                    
                    # 1. Filtro por Distrito y Materia
                    if oferta_distrito in distritos_usuario and oferta_codigo in materias_usuario:
                        # 2. Filtro por Memoria Individual (que no haya sido enviada ANTES a este mail)
                        if oferta_id not in usuario_sent_ids:
                            ofertas_match.append(oferta)

                if ofertas_match:
                    print(f"¡Match! {len(ofertas_match)} nuevas ofertas para {nombre_usuario}.")
                    enviar_correo(ofertas_match, mail_destino, nombre_usuario)
                    
                    # Actualizar historial del usuario
                    usuario_sent_ids.extend([o["id"] for o in ofertas_match])
                    historial[mail_destino] = usuario_sent_ids
                    any_new_match = True
                else:
                    print(f"Sin novedades para {nombre_usuario} (0 matches o ya enviadas).")

            if any_new_match:
                print("\nActualizando archivo de historial...")
                guardar_historial(historial)
            else:
                print("\nNo hubo nuevas ofertas para notificar a ningún usuario.")
                
        except Exception as e:
            import traceback
            print(f"Ocurrió un error en el flujo de ejecución:")
            traceback.print_exc()
        finally:
            print("Cerrando navegador...")
            browser.close()

def main():
    try:
        load_dotenv()
    except Exception:
        pass

    if not os.environ.get("ABC_USUARIO") or not os.environ.get("ABC_CLAVE"):
        print("ERROR: Faltan credenciales ABC_USUARIO y ABC_CLAVE.")
        sys.exit(1)

    es_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    
    if es_github_actions:
        print("Entorno: GitHub Actions. Ejecutando ciclo único...")
        job()
        sys.exit(0)

    # Entorno Local: Programación
    schedule.every().day.at("08:00").do(job)
    schedule.every().day.at("13:00").do(job)
    schedule.every().day.at("18:00").do(job)

    print("Bot Lector ABC en línea (Modo Local).")
    print("Ejecuciones: 08:00, 13:00 y 18:00 horas.")
    print("Ejecutando prueba inicial...")
    job() 
    
    print("\nEsperando próximas ejecuciones. (Ctrl+C para salir)")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
