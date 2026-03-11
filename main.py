"""
Orquestador principal del bot para el Lector ABC con Schedule.
"""
import os
import sys
import time
import schedule
from dotenv import load_dotenv
from scraper import scrape_ofertas
from database import init_db, es_oferta_nueva, registrar_oferta
from notifier import enviar_correo
from playwright.sync_api import sync_playwright

def job():
    print("Iniciando ejecución programada del bot Lector ABC...")
    
    # Inicia Playwright en modo visual para desarrollo y testing local, y headless en la nube
    with sync_playwright() as p:
        es_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        browser = p.chromium.launch(headless=es_github_actions)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Scrapear
            ofertas = scrape_ofertas(page)
            
            # Filtrar solo las nuevas
            nuevas_ofertas = []
            for o in ofertas:
                if es_oferta_nueva(o["id"]):
                    nuevas_ofertas.append(o)
            
            print(f"Total ofertas compatibles detectadas: {len(ofertas)}")
            print(f"Nuevas ofertas para notificar: {len(nuevas_ofertas)}")
            
            if nuevas_ofertas:
                enviar_correo(nuevas_ofertas)
                for o in nuevas_ofertas:
                    registrar_oferta(o["id"])
            else:
                print("No hay ofertas nuevas o ya fueron notificadas.")
                
        except Exception as e:
            import traceback
            print(f"Ocurrió un error en el flujo de ejecución:")
            traceback.print_exc()
        finally:
            print("Cerrando navegador...")
            browser.close()

def main():
    # Solo intentamos cargar .env en local para evitar errores en GitHub Actions si no existe el archivo
    try:
        load_dotenv()
    except Exception:
        pass

    if not os.environ.get("ABC_USUARIO") or not os.environ.get("ABC_CLAVE"):
        print("IMPORTANTE: Por favor, asegúrate de tener completadas tus credenciales ABC_USUARIO y ABC_CLAVE como variables de entorno.")
        sys.exit(1)

    init_db()
    
    # Detección de entorno: Si se ejecuta en GitHub Actions, ejecuta una sola vez.
    es_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    
    if es_github_actions:
        print("Bot Lector ABC ejecutándose en la nube (GitHub Actions).")
        print("Ejecutando ciclo único...")
        job()
        print("Ciclo completado con éxito. Saliendo.")
        sys.exit(0)

    # Entorno Local: Scheduling tasks
    schedule.every().day.at("08:00").do(job)
    schedule.every().day.at("13:00").do(job)
    schedule.every().day.at("18:00").do(job)

    print("Bot Lector ABC en línea (Modo Local).")
    print("Tareas programadas para ejecutarse a las 08:00, 13:00 y 18:00 horas.")
    print("Ejecutando una vez el flujo para validar...")
    
    # Primera ejecución manual de prueba
    job() 
    
    print("Esperando próximas ejecuciones planificadas. (Ctrl+C para salir)")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
