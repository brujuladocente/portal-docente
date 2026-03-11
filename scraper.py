"""
Lógica para buscar ofertas en el portal ABC, extraer la tabla y aplicar los filtros comerciales.
"""
from playwright.sync_api import Page
from config import DISTRITOS, TODOS_LOS_CODIGOS
import re
from auth import login_abc

APD_URL = "https://misservicios.abc.gob.ar/actos.publicos.digitales/"

def limpiar_modales(page: Page):
    print("\n[MODAL] Revisando / Limpiando pop-ups modales activos...")
    try:
        # 1. Pulsación de Tecla (Escape)
        print("[MODAL] Intentando cerrar modales con la tecla Escape...")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        
        # 2. Clic fuera del modal (coordenada 0,0)
        print("[MODAL] Simulando clic en el fondo de la pantalla (0,0)...")
        page.mouse.click(0, 0)
        page.wait_for_timeout(500)

        # 3. Búsqueda flexible de la 'X'
        for iteracion in range(2):
            try:
                boton_cerrar = page.locator("button.close, [aria-label='Close'], button:has-text('×'), button.btn-close").locator("visible=true").first
                boton_cerrar.wait_for(timeout=2000)
                boton_cerrar.click(force=True)
                print(f"[MODAL] Pop-up modal (iter {iteracion+1}) cerrado con botón X.")
                page.wait_for_timeout(1000)
            except Exception:
                break
    except Exception as e:
        print(f"[MODAL] Error ignorado limpiando modales: {e}")
        
    print("[MODAL] Limpieza de modales completada u omitida.")

def gestionar_estado_sesion(page: Page):
    """
    State Machine dinámica para manejar las redirecciones del portal ABC.
    Retorna la Page activa (nueva pestaña si aplica) o None si falló críticamente.
    """
    print("\n[ESTADOS] Navegando a Actos Públicos Digitales (APD)...")
    page.goto("https://misservicios.abc.gob.ar/actos.publicos.digitales/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)
    
    intentos = 0
    max_intentos = 3
    
    while intentos < max_intentos:
        print(f"\n[ESTADOS] Evaluando Estado Actual del DOM (Intento {intentos + 1}/{max_intentos})...")
        
        # 1. ESTADO A: Pantalla de Login (mis.abc.gob.ar)
        es_login = page.locator("input[type='password'], input[type='email'], input[placeholder*='CUIL'], #Ecom_Password").locator("visible=true").count() > 0 or page.locator("text='CUIL o cuenta'").locator("visible=true").count() > 0
        
        # 2. ESTADO B/C: Pantalla APD Pública o Logueada
        es_apd_publico = page.locator("a, button", has_text=re.compile(r"Iniciar sesi.n", re.IGNORECASE)).locator("visible=true").count() > 0
        es_apd_logueado = page.locator("a, button", has_text=re.compile(r"Postularse", re.IGNORECASE)).locator("visible=true").count() > 0
        
        if es_login:
            print("[ESTADOS] -> Detectado ESTADO A (Pantalla de Login Centralizado).")
            print("[ESTADOS] Omitiendo limpieza de modales. Procediendo a inyectar credenciales...")
            login_abc(page)
            print("[ESTADOS] Credenciales inyectadas, esperando volver a APD...")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(4000)
            intentos += 1
            continue
            
        elif es_apd_publico:
            print("[ESTADOS] -> Detectado ESTADO B (APD Vista Pública).")
            limpiar_modales(page)
            print("[ESTADOS] Clickeando en 'Iniciar Sesión ABC'...")
            btn_iniciar_sesion = page.locator("a, button", has_text=re.compile(r"Iniciar sesi.n", re.IGNORECASE)).locator("visible=true").first
            btn_iniciar_sesion.click(force=True)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            intentos += 1
            continue
            
        elif es_apd_logueado:
            print("[ESTADOS] -> Detectado ESTADO C (APD Logueado).")
            limpiar_modales(page)
            
            print("[ESTADOS] Clickeando 'Postularse' (target=_blank → esperando nueva pestaña)...")
            try:
                btn_postularse = page.locator("a, button", has_text=re.compile(r"Postularse", re.IGNORECASE)).locator("visible=true").first
                
                # Capturar nueva pestaña ANTES del clic
                with page.context.expect_page(timeout=10000) as nueva_pagina_info:
                    btn_postularse.click(force=True)
                
                nueva_pagina = nueva_pagina_info.value
                nueva_pagina.wait_for_load_state("networkidle")
                nueva_pagina.wait_for_timeout(5000)
                
                url_nueva = nueva_pagina.url
                print(f"[ESTADOS] URL de la nueva pestaña: {url_nueva}")
                
                # Cerrar la pestaña original para no confundir al script
                print("[ESTADOS] Cerrando pestaña original (dashboard)...")
                page.close()
                
                if "postulacionAPD" in url_nueva or "ofertas" in url_nueva:
                    print("[ESTADOS] ✓ Nueva pestaña es la vista de postulaciones. Continuando en ella.")
                    return nueva_pagina
                else:
                    print(f"[ESTADOS] ⚠ URL inesperada en nueva pestaña: {url_nueva}")
                    intentos += 1
                    # Reasignamos page para el próximo ciclo
                    page = nueva_pagina
                    continue
                    
            except Exception as e:
                print(f"[ESTADOS] No se abrió nueva pestaña (quizás misma pestaña): {type(e).__name__}. Verificando URL actual...")
                # Fallback: clic normal si no hubo nueva pestaña
                try:
                    btn_postularse = page.locator("a, button", has_text=re.compile(r"Postularse", re.IGNORECASE)).locator("visible=true").first
                    btn_postularse.click(force=True)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
                    url_actual = page.url
                    print(f"[ESTADOS] URL tras clic simple: {url_actual}")
                    if "postulacionAPD" in url_actual or "ofertas" in url_actual:
                        print("[ESTADOS] ✓ Misma pestaña redirigida a postulaciones.")
                        return page
                except Exception as e2:
                    print(f"[ERROR] Fallo total al navegar a Postularse: {e2}")
                return None
                
        else:
            print("[ESTADOS] -> ESTADO DESCONOCIDO. Forzando recarga...")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            intentos += 1
            
    print("[ERROR CRÍTICO] No se logró llegar al ESTADO C tras múltiples intentos.")
    return None

def _navegar_a_ofertas(page: Page) -> Page:
    """
    Reseteo seguro entre distritos: vuelve al dashboard y reabre la sección
    de Postularse, manejando la nueva pestaña y cerrando la vieja.
    Retorna la Page activa (la de ofertas).
    """
    print("[NAV] Reseteando: volviendo al Dashboard APD...")
    try:
        page.goto(APD_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        limpiar_modales(page)
        
        btn = page.locator("a, button", has_text=re.compile(r"Postularse", re.IGNORECASE)).locator("visible=true").first
        
        try:
            with page.context.expect_page(timeout=8000) as nueva_pagina_info:
                btn.click(force=True)
            nueva_pagina = nueva_pagina_info.value
            nueva_pagina.wait_for_load_state("networkidle")
            nueva_pagina.wait_for_timeout(4000)
            print(f"[NAV] Nueva pestaña de ofertas: {nueva_pagina.url}")
            # Cerrar la pestaña del dashboard para no acumular ventanas
            page.close()
            return nueva_pagina
        except Exception:
            # Postularse no abrió nueva pestaña: misma pestaña redirigida
            btn.click(force=True)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            print(f"[NAV] Misma pestaña redirigida a: {page.url}")
            return page
    except Exception as e:
        print(f"[NAV] Error en reseteo seguro: {e}")
        return page

def scrape_ofertas(page: Page):
    ofertas_encontradas = []
    
    # 1. Máquina de Estados: retorna la Page activa (posiblemente una nueva pestaña)
    page_activa = gestionar_estado_sesion(page)
    
    if page_activa is None:
        print("Abortando extracción de ofertas por fallo en la sesión/navegación.")
        return []
    
    # Usar siempre la page activa de aquí en adelante
    page = page_activa
    print(f"[SCRAPER] URL activa para scraping: {page.url}")

    # Verificar que el título de la sección es el correcto
    try:
        page.wait_for_selector("text='Para Desempe'", timeout=5000)
        print("[SCRAPER] ✓ Título de la sección de postulaciones confirmado.")
    except Exception:
        print("[SCRAPER] Advertencia: título de la sección no detectado (continuando de todas formas).")

    # 3 y 4. Filtro por Distrito e Iteración (ya estamos en el panel de Postularse)
    for distrito in DISTRITOS:
        print(f"\n--- Procesando Distrito: {distrito} ---")
        try:
            # === ABRIR MODAL DE DISTRITO - Selector definitivo confirmado manualmente ===
            print("[SCRAPER] Abriendo modal de Distrito (selector: div.filtro > Distrito > button)...")
            boton_distrito = page.locator("div.filtro", has_text="Distrito").locator("button")
            boton_distrito.scroll_into_view_if_needed()
            boton_distrito.click(force=True)
            print("[SCRAPER] Clic en botón de Distrito ejecutado.")
            
            # Esperar al input del modal
            page.wait_for_selector("input[role='combobox']", state="visible", timeout=10000)
            print("[SCRAPER] ✓ Modal de Distrito abierto. Combobox detectado.")
            
            # Tipeo carácter a carácter para que Angular dispare los eventos
            print(f"[SCRAPER] Tipeando '{distrito}' con delay=150ms (page.type)...")
            page.type("input[role='combobox']", distrito, delay=150)
            page.wait_for_timeout(1500)
            
            # Espera y clic en la opción del dropdown ng-select
            print(f"[SCRAPER] Esperando span.ng-option-label con texto '{distrito}'...")
            opcion = page.locator("span.ng-option-label", has_text=distrito)
            opcion.wait_for(state="visible", timeout=10000)
            page.screenshot(path="debug_filtro.png")
            print("[SCRAPER] Screenshot guardado: debug_filtro.png")
            opcion.first.click()
            page.wait_for_timeout(1000)
            
            # Clic en Buscar dentro del footer del modal
            print("[SCRAPER] Presionando Buscar en el footer del modal...")
            btn_buscar = page.locator(".modal-footer button", has_text=re.compile(r"Buscar", re.IGNORECASE))
            btn_buscar.wait_for(state="visible", timeout=10000)
            btn_buscar.click(force=True)
            
            print("[SCRAPER] Esperando que los resultados se actualicen en pantalla...")
            page.wait_for_load_state("networkidle")
            try:
                page.wait_for_selector(".card", timeout=12000)
            except Exception:
                print(f"[SCRAPER] No se encontraron tarjetas (.card) para {distrito}.")
            page.wait_for_timeout(3000)
            
            match_count = 0
            pagina_actual = 1
            
            while True:
                print(f"\n[SCRAPER] --- Extrayendo Página {pagina_actual} de {distrito} ---")
                # --- PASO 6: Extracción de Tarjetas ---
                tarjetas = page.locator(".card").all()
                print(f"[SCRAPER] Total bruto de tarjetas extraídas en página {pagina_actual}: {len(tarjetas)}")
                
                for t in tarjetas:
                    texto_tarjeta = t.inner_text()
                    texto_upper = texto_tarjeta.upper()
                    
                    # Buscar código en paréntesis ej (FIA)
                    match_codigo = re.search(r'\(([A-Z0-9\/\+\-]+)\)', texto_upper)
                    codigo_area = match_codigo.group(1).strip() if match_codigo else "DESCONOCIDO"
                    
                    # 6. Actualización de Filtros (CRITICO - Lista Unificada)
                    if codigo_area not in TODOS_LOS_CODIGOS:
                        continue
                    
                    # --- Extracción de campos ---
                    match_ige = re.search(r'#(?:IGE)?\s*(\d+)', texto_upper)
                    if not match_ige:
                        match_ige = re.search(r'IGE\s*:\s*(\d+)', texto_upper)
                    ige = match_ige.group(1) if match_ige else "SinIGE"
                    
                    lineas = [line.strip() for line in texto_tarjeta.split('\n') if line.strip()]
                    
                    escuela_linea = next((l for l in lineas if 'ESCUELA' in l.upper()), "")
                    escuela = escuela_linea.split(':', 1)[-1].strip() if escuela_linea else "Ver en Portal"
                    
                    nivel_linea = next((l for l in lineas if 'NIVEL' in l.upper()), "")
                    nivel = nivel_linea.split(':', 1)[-1].strip() if nivel_linea else "Ver en Portal"
                    
                    # Horarios: capturar líneas que contengan un día de la semana
                    DIAS = ['LUNES', 'MARTES', 'MI\u00c9RCOLES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'S\u00c1BADO', 'SABADO']
                    lineas_horario = [
                        l for l in lineas
                        if any(dia in l.upper() for dia in DIAS)
                    ]
                    horarios = " | ".join(lineas_horario) if lineas_horario else "Ver en Portal"
                    
                    # Observaciones: texto tras la etiqueta 'Observaciones:'
                    match_obs = re.search(r'observaciones\s*:?\s*([^\n]+)', texto_tarjeta, re.IGNORECASE)
                    observaciones = match_obs.group(1).strip() if match_obs and match_obs.group(1).strip() else "-"
                    
                    if not observaciones or "POSTULARSE" in observaciones.upper():
                        observaciones = "-"
                    
                    match_count += 1
                    print(f"  -> [MATCH CR\u00cdTICO] C\u00f3digo: {codigo_area} | IGE: {ige} | Distrito: {distrito} | Nivel: {nivel} (Pág: {pagina_actual})")
                    
                    ofertas_encontradas.append({
                        "id": f"IGE_{ige}_{distrito}",
                        "ige": ige,
                        "codigo_area": codigo_area,
                        "distrito": distrito,
                        "nivel": nivel,
                        "escuela": escuela,
                        "horarios": horarios,
                        "observaciones": observaciones,
                        "texto_completo": texto_tarjeta
                    })
                
                # PAGINACIÓN: Verificar si hay botón 'Siguiente' disponible
                try:
                    contenedor_siguiente = page.locator('li.page-item.der').first
                    btn_siguiente = page.locator('li.page-item.der a[aria-label="Next"]').first
                    
                    # Comprobamos si el componente de paginación existe en el DOM
                    if not contenedor_siguiente.is_visible() or not btn_siguiente.is_visible():
                        print(f"[SCRAPER] No se detectó paginación o botón Siguiente en la página {pagina_actual}. Fin del distrito.")
                        break
                    
                    # Comprobamos la clase disabled en el contenedor li
                    class_attribute = contenedor_siguiente.get_attribute("class") or ""
                    if "disabled" in class_attribute:
                        print(f"[SCRAPER] Botón 'Siguiente' está deshabilitado en página {pagina_actual}. Llegamos al final.")
                        break
                    
                    print(f"[SCRAPER] Botón 'Siguiente' habilitado. Navegando a la página {pagina_actual + 1}...")
                    btn_siguiente.click(force=True)
                    pagina_actual += 1
                    
                    # Espera Activa Post-Clic a que la tabla/tarjetas se refresquen
                    page.wait_for_timeout(3000)
                    try:
                        # Pequeña validación adicional para asegurar carga de DOM (Angular no refresca la URL)
                        page.wait_for_selector(".card", timeout=10000)
                    except Exception:
                        pass
                        
                except Exception as eval_err:
                    print(f"[SCRAPER] Error evaluando botón 'Siguiente': {eval_err}. Asumiendo fin de distrito.")
                    break
            
            print(f"[SCRAPER] Fin ciclo {distrito} - Extracciones útiles para enviar: {match_count}")
            
            # --- RESETEO SEGURO entre distritos: volver al dashboard y reabrir Postularse ---
            page = _navegar_a_ofertas(page)

        except Exception as e:
            print(f"[SCRAPER] Error procesando distrito {distrito}: {e}")
            page = _navegar_a_ofertas(page)
            continue

    return ofertas_encontradas
