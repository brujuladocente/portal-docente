"""
Orquestador principal del bot para el Lector ABC Cosechador Masivo.
Maneja cronogramas separados para la Cosecha Portuaria y la Emisión de Alertas.
"""
import os
import sys
import time
import json
import schedule
from dotenv import load_dotenv

from scraper import scrape_ofertas
from database_google import obtener_usuarios_desde_sheets
from notifier import enviar_correo, enviar_correo_vencimiento
from database_manager import sincronizar_ofertas, obtener_ofertas_por_filtros
from playwright.sync_api import sync_playwright

HISTORIAL_FILE = "ofertas_enviadas.json"
VENCIMIENTOS_FILE = "vencimientos.json"

def cargar_json_local(ruta):
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def guardar_json_local(ruta, data):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error al guardar {ruta}: {e}")

cargar_historial = lambda: cargar_json_local(HISTORIAL_FILE)
guardar_historial = lambda h: guardar_json_local(HISTORIAL_FILE, h)

cargar_vencimientos = lambda: cargar_json_local(VENCIMIENTOS_FILE)
guardar_vencimientos = lambda v: guardar_json_local(VENCIMIENTOS_FILE, v)

def tarea_cosecha():
    """Ejecuta el Scraper en Barrido Total y sincroniza la DB local."""
    print("\n" + "="*60)
    print("Iniciando Cosecha de Ofertas (Barrido Total APD)...")
    print("="*60)
    
    with sync_playwright() as p:
        es_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        browser = p.chromium.launch(headless=es_github_actions)
        context = browser.new_context()
        page = context.new_page()

        try:
            lista_maestra = scrape_ofertas(page)
            if lista_maestra:
                print(f"Extracción finalizada. Sincronizando {len(lista_maestra)} ofertas con la base local...")
                sincronizar_ofertas(lista_maestra)
            else:
                print("No se extrajeron ofertas en esta sesión.")
        except Exception as e:
            import traceback
            print("Ocurrió un error crítico durante la cosecha:")
            traceback.print_exc()
        finally:
            print("Cerrando navegador y contextos de cosecha para evitar procesos zombies...")
            context.close()
            browser.close()

def procesar_vencimientos(usuarios_vencidos):
    """Verifica y envía correos de cortesía a los usuarios que pasaron al plan gratis."""
    if not usuarios_vencidos:
        return
        
    vencimientos = cargar_vencimientos()
    hubo_cambios = False
    
    for u in usuarios_vencidos:
        email = u.get("email")
        nombre = u.get("nombre", "Colega")
        if email and email not in vencimientos:
            print(f"[*] Notificando caída a Plan Gratis para: {email}")
            exito = enviar_correo_vencimiento(email, nombre)
            if exito:
                vencimientos[email] = {"fecha_aviso": time.strftime("%Y-%m-%d %H:%M:%S")}
                hubo_cambios = True

    if hubo_cambios:
        guardar_vencimientos(vencimientos)

def tarea_notificacion():
    """Lee la DB Local usando los índices invertidos y avisa a los usuarios anotados."""
    print("\n" + "="*60)
    print("Iniciando Emisión de Alertas a Usuarios Registrados...")
    print("="*60)
    
    # 1. Traer lista de usuarios activos de Google Sheets
    print("Obteniendo usuarios suscritos y verificando estado Freemium...")
    res = obtener_usuarios_desde_sheets()
    if isinstance(res, tuple) and len(res) == 2:
        usuarios, usuarios_vencidos = res
    else:
        usuarios = res
        usuarios_vencidos = []
        
    # Procesar cortesía de vencidos
    procesar_vencimientos(usuarios_vencidos)

    if not usuarios:
        print("No hay usuarios activos validos para notificar. Saliendo.")
        return

    # 2. Cargar ofertas enviadas históricamente
    historial = cargar_historial()
    any_new_match = False

    # 3. Cruzar datos locales
    for usuario in usuarios:
        mail_destino = usuario.get("email")
        nombre_usuario = usuario.get("nombre", "Colega")
        distritos_usuario = usuario.get("distritos", [])
        materias_usuario = usuario.get("materias", [])
        
        usuario_sent_ids = historial.get(mail_destino, [])
        
        print(f"\n--- Evaluando {nombre_usuario} ({mail_destino}) ---")
        print(f"  Filtros -> Distritos: {distritos_usuario} | Materias: {materias_usuario}")
        
        # Consultar la DB Local Instantánea (usa los índices)
        matches_db = obtener_ofertas_por_filtros(distritos_usuario, materias_usuario)
        ofertas_a_enviar = []
        
        for oferta in matches_db:
            if oferta["id"] not in usuario_sent_ids:
                ofertas_a_enviar.append(oferta)
                
        if ofertas_a_enviar:
            print(f"¡Match! {len(ofertas_a_enviar)} nuevas ofertas a enviar.")
            enviar_correo(ofertas_a_enviar, mail_destino, nombre_usuario)
            
            # Registrar e Historial
            usuario_sent_ids.extend([o["id"] for o in ofertas_a_enviar])
            historial[mail_destino] = usuario_sent_ids
            any_new_match = True
        else:
            print("Sin novedades no notificadas.")

    if any_new_match:
        guardar_historial(historial)
    else:
        print("\nEmisión finalizada. No hubo correos nuevos que enviar.")

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
        print("Entorno: GitHub Actions detectado.")
        tipo_tarea = os.environ.get("TIPO_TAREA", "AUTO")
        
        if tipo_tarea == "COSECHA":
            tarea_cosecha()
        elif tipo_tarea == "NOTIFICACION":
            tarea_notificacion()
        elif tipo_tarea == "COMPLETO":
            print("Ejecutando ciclo completo (Cosecha seguida de Notificación)...")
            tarea_cosecha()
            tarea_notificacion()
        else:
            # Modo AUTO por defecto: Cosecha siempre, Notifica solo en horarios clave
            from datetime import datetime, timedelta
            
            # Obtener hora actual en UTC y convertir a ART (UTC-3)
            ahora_utc = datetime.utcnow()
            ahora_art = ahora_utc - timedelta(hours=3)
            
            print(f"Hora detectada (ART): {ahora_art.strftime('%H:%M')} hs.")
            
            # 1) Ejecutar siempre la cosecha
            tarea_cosecha()
            
            # 2) Evaluar si la hora coincide con el ciclo de notificación (y si es de Lunes a Viernes)
            horarios_notificacion = [8, 10, 14, 18]
            es_dia_habil = ahora_art.weekday() < 5  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
            
            if ahora_art.hour in horarios_notificacion and es_dia_habil:
                print("Hora y día hábiles coincidentes. Ejecutando alertas...")
                tarea_notificacion()
            else:
                if not es_dia_habil:
                    print(f"Es fin de semana (día {ahora_art.weekday()}). Saltando fase de alertas.")
                else:
                    print(f"La hora actual ({ahora_art.hour} hs) no corresponde al envío de notificaciones. Saltando fase de alertas.")
                
        sys.exit(0)

    # Entorno Local: Programación de Tareas
    
    # 1. Horarios de Cosecha Masiva (Cada 1 Hora exacta, de 08:00 a 21:00)
    horarios_cosecha = [
        "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", 
        "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"
    ]
    for hc in horarios_cosecha:
        schedule.every().day.at(hc).do(tarea_cosecha)
        
    # 2. Horarios de Notificación (Rondas de emails)
    horarios_notificacion = ["08:30", "11:00", "14:00", "19:00"]
    for hn in horarios_notificacion:
        schedule.every().day.at(hn).do(tarea_notificacion)

    print("Bot Lector ABC - Cosechador Masivo Local.")
    print(f"Cosecha programada: {', '.join(horarios_cosecha)}")
    print(f"Notificación programada: {', '.join(horarios_notificacion)}")
    
    # Prueba inicial al levantar
    print("\n[Inicialización] Ejecutando ronda cero de cosecha y notificación...")
    tarea_cosecha()
    tarea_notificacion()
    
    print("\nEsperando próximas ejecuciones. (Ctrl+C para salir)")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
