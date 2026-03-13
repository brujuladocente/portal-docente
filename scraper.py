"""
Lógica para buscar ofertas en el portal ABC, extraer la tabla y aplicar los filtros comerciales.
"""
from playwright.sync_api import Page
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
                
                with page.context.expect_page(timeout=10000) as nueva_pagina_info:
                    btn_postularse.click(force=True)
                
                nueva_pagina = nueva_pagina_info.value
                nueva_pagina.wait_for_load_state("networkidle")
                nueva_pagina.wait_for_timeout(5000)
                
                url_nueva = nueva_pagina.url
                print(f"[ESTADOS] URL de la nueva pestaña: {url_nueva}")
                
                print("[ESTADOS] Cerrando pestaña original (dashboard)...")
                page.close()
                
                if "postulacionAPD" in url_nueva or "ofertas" in url_nueva:
                    print("[ESTADOS] ✓ Nueva pestaña es la vista de postulaciones. Continuando en ella.")
                    return nueva_pagina
                else:
                    print(f"[ESTADOS] ⚠ URL inesperada en nueva pestaña: {url_nueva}")
                    intentos += 1
                    page = nueva_pagina
                    continue
                    
            except Exception as e:
                print(f"[ESTADOS] No se abrió nueva pestaña (quizás misma pestaña): {type(e).__name__}. Verificando URL actual...")
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
            page.close()
            return nueva_pagina
        except Exception:
            btn.click(force=True)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            print(f"[NAV] Misma pestaña redirigida a: {page.url}")
            return page
    except Exception as e:
        print(f"[NAV] Error en reseteo seguro: {e}")
        return page

def extraer_todas_paginas(page: Page) -> list:
    ofertas_extraidas = []
    pagina_actual = 1
    intentos_sin_avance = 0
    MAX_INTENTOS_SIN_AVANCE = 3

    while True:
        print(f"\n[SCRAPER] --- Extrayendo Página {pagina_actual} ---")
        try:
            snapshot_antes = page.locator(".card").first.text_content() if page.locator(".card").count() > 0 else ""
        except Exception:
            snapshot_antes = ""

        tarjetas = page.locator(".card").all()
        print(f"[SCRAPER] Total bruto de tarjetas extraídas en página {pagina_actual}: {len(tarjetas)}")

        for i, t in enumerate(tarjetas):
            try:
                texto_tarjeta = t.text_content()
                if not texto_tarjeta:
                    continue
                    
                texto_upper = texto_tarjeta.upper()

                # Buscar código en paréntesis ej (FIA)
                match_codigo = re.search(r'\(([A-Z0-9\/\+\-]+)\)', texto_upper)
                codigo_area = match_codigo.group(1).strip() if match_codigo else "DESCONOCIDO"

                # IGE
                match_ige = re.search(r'#(?:IGE)?\s*(\d+)', texto_upper)
                if not match_ige:
                    match_ige = re.search(r'IGE\s*:\s*(\d+)', texto_upper)
                ige = match_ige.group(1) if match_ige else "SinIGE"

                # Distrito: Extraer de "DISTRITO: <valor>" para evitar domicilios
                match_distrito = re.search(r'DISTRITO\s*:\s*([^\n]+)', texto_upper)
                distrito_tarjeta = match_distrito.group(1).strip() if match_distrito else "DESCONOCIDO"

                lineas = [line.strip() for line in texto_tarjeta.split('\n') if line.strip()]

                escuela_linea = next((l for l in lineas if 'ESCUELA' in l.upper()), "")
                escuela = escuela_linea.split(':', 1)[-1].strip() if escuela_linea else "Ver en Portal"

                nivel_linea = next((l for l in lineas if 'NIVEL' in l.upper()), "")
                nivel = nivel_linea.split(':', 1)[-1].strip() if nivel_linea else "Ver en Portal"

                # Horarios
                DIAS = ['LUNES', 'MARTES', 'MIÉRCOLES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'SABADO']
                lineas_horario = [
                    l for l in lineas
                    if any(dia in l.upper() for dia in DIAS)
                ]
                horarios = " | ".join(lineas_horario) if lineas_horario else "Ver en Portal"

                # Observaciones
                match_obs = re.search(r'observaciones\s*:?\s*([^\n]+)', texto_tarjeta, re.IGNORECASE)
                observaciones = match_obs.group(1).strip() if match_obs and match_obs.group(1).strip() else "-"

                if not observaciones or "POSTULARSE" in observaciones.upper():
                    observaciones = "-"

                print(f"  -> [EXTRACCIÓN] Código: {codigo_area} | IGE: {ige} | Distrito: {distrito_tarjeta} | Nivel: {nivel} (Pág: {pagina_actual})")

                ofertas_extraidas.append({
                    "id": f"IGE_{ige}_{distrito_tarjeta.replace(' ', '_')}",
                    "ige": ige,
                    "codigo_area": codigo_area,
                    "distrito": distrito_tarjeta,
                    "nivel": nivel,
                    "escuela": escuela,
                    "horarios": horarios,
                    "observaciones": observaciones,
                    "texto_completo": texto_tarjeta
                })
            except Exception as loop_e:
                print(f"  -> [ERROR] Fallo al procesar la tarjeta índice {i} ({loop_e}). Saltando...")
                continue

        # PAGINACIÓN
        try:
            contenedor_siguiente = page.locator('li.page-item.der').first
            btn_siguiente = page.locator('li.page-item.der a[aria-label="Next"]').first

            if not contenedor_siguiente.is_visible() or not btn_siguiente.is_visible():
                print(f"[SCRAPER] No se detectó paginación o botón Siguiente en la página {pagina_actual}. Fin de extracciones.")
                break

            class_attribute = contenedor_siguiente.get_attribute("class") or ""
            if "disabled" in class_attribute:
                print(f"[SCRAPER] Botón 'Siguiente' está deshabilitado en página {pagina_actual}. Llegamos al final.")
                break

            print(f"[SCRAPER] Botón 'Siguiente' habilitado. Navegando a la página {pagina_actual + 1}...")
            btn_siguiente.click(force=True)
            pagina_actual += 1

            page.wait_for_timeout(3000)
            try:
                page.wait_for_selector(".card", timeout=10000)
            except Exception:
                pass

            # Guardia de movimiento
            try:
                snapshot_despues = page.locator(".card").first.text_content() if page.locator(".card").count() > 0 else ""
            except Exception:
                snapshot_despues = ""

            if snapshot_despues and snapshot_despues == snapshot_antes:
                intentos_sin_avance += 1
                print(f"[SCRAPER] ⚠ La página NO cambió tras clic en Siguiente (intento {intentos_sin_avance}/{MAX_INTENTOS_SIN_AVANCE}).")
                if intentos_sin_avance >= MAX_INTENTOS_SIN_AVANCE:
                    print(f"[SCRAPER] ✋ {MAX_INTENTOS_SIN_AVANCE} intentos sin avance. Forzando salida.")
                    break
            else:
                intentos_sin_avance = 0

        except Exception as eval_err:
            print(f"[SCRAPER] Error evaluando botón 'Siguiente': {eval_err}. Asumiendo fin del escaneo por esta tanda.")
            break

    return ofertas_extraidas


def scrape_ofertas(page: Page, distritos: list):
    ofertas_encontradas = []
    
    page_activa = gestionar_estado_sesion(page)
    if page_activa is None:
        print("Abortando extracción de ofertas por fallo en la sesión/navegación.")
        return []
    
    page = page_activa
    print(f"[SCRAPER] URL activa para scraping: {page.url}")

    try:
        page.wait_for_selector("text='Para Desempe'", timeout=5000)
        print("[SCRAPER] ✓ Título de la sección de postulaciones confirmado.")
    except Exception:
        print("[SCRAPER] Advertencia: título de la sección no detectado (continuando de todas formas).")

    modo_barrido_total = False
    fallos_filtro = 0

    for distrito in distritos:
        if modo_barrido_total:
            # Si estamos en barrido total, no iteramos por distritos, rompemos el ciclo
            break

        print(f"\n--- Procesando Distrito: {distrito} ---")
        exito_filtro = False
        
        try:
            print("[SCRAPER] Abriendo modal de Distrito...")
            boton_distrito = page.locator("div.filtro", has_text="Distrito").locator("button")
            boton_distrito.scroll_into_view_if_needed()
            boton_distrito.click(force=True)
            
            page.wait_for_selector("input[role='combobox']", state="visible", timeout=10000)
            print(f"[SCRAPER] Limpiando input y tipeando '{distrito}'...")
            page.locator("input[role='combobox']").clear()
            page.type("input[role='combobox']", distrito, delay=150)
            page.wait_for_timeout(1500)
            
            # Chequear preventivamente si dice "No items found"
            dropdown_panel = page.locator("ng-dropdown-panel")
            if dropdown_panel.is_visible():
                panel_texto = dropdown_panel.inner_text().lower()
                if "no items found" in panel_texto or "no se encontraron" in panel_texto:
                    raise Exception("Dropdown muestra 'No items found'")
            
            print(f"[SCRAPER] Esperando opción '{distrito}'...")
            opcion = page.locator("span.ng-option-label", has_text=distrito)
            opcion.wait_for(state="visible", timeout=6000)
            page.screenshot(path="debug_filtro.png")
            opcion.first.click()
            page.wait_for_timeout(1500)
            
            print("[SCRAPER] Presionando Buscar en el modal...")
            btn_buscar = page.locator(".modal-footer button", has_text=re.compile(r"Buscar", re.IGNORECASE))
            btn_buscar.wait_for(state="visible", timeout=10000)
            btn_buscar.click(force=True)
            # --- PROTECCIÓN CONTRA RACE CONDITION ---
            
            # 1. Esperar obligatoriamente la desaparición de spinners/loaders antes de chequear el DOM
            try:
                print(f"[SCRAPER] Esperando que desaparezcan indicadores de carga para {distrito}...")
                page.locator(".spinner-border, .loader, [role='status'], text='Cargando'").locator("visible=true").first.wait_for(state="hidden", timeout=15000)
            except Exception:
                pass
                
            # 2. Verificación por Contenido (Esperar por tarjetas o el mensaje de '0 registros')
            print(f"[SCRAPER] Esperando resolución del DOM (tarjetas o mensaje de cero)...")
            try:
                page.wait_for_function(
                    "() => document.querySelectorAll('.card').length > 0 || document.body.innerText.toLowerCase().includes('0 registros encontrados') || document.body.innerText.toLowerCase().includes('no se encontraron resultados')",
                    timeout=10000
                )
            except Exception:
                print("[SCRAPER] ⏱ Timeout de 10s esperando un estado definitivo en el DOM. Podría estar lento...")

            page.wait_for_load_state("networkidle", timeout=5000)
            
            # --- VALIDACIÓN DEL FILTRO DE DISTRITO ---
            if page.locator(".card").count() > 0:
                try:
                    primera_tarjeta_texto = page.locator(".card").first.text_content().upper()
                    match_distrito_check = re.search(r'DISTRITO\s*:\s*([^\n]+)', primera_tarjeta_texto)
                    if match_distrito_check:
                        distrito_leido = match_distrito_check.group(1).strip().upper()
                        # Normalizar comparaciones sencillas (quitar acentos básicos)
                        import unicodedata
                        def unidecode_str(s):
                            return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                        
                        dist_leido_norm = unidecode_str(distrito_leido)
                        dist_buscado_norm = unidecode_str(distrito.upper())
                        
                        if dist_buscado_norm not in dist_leido_norm and dist_leido_norm not in dist_buscado_norm:
                            print(f"[SCRAPER] ❌ ERROR DE FILTRO EN PORTAL: Buscábamos '{distrito}', pero vimos tarjetas de '{distrito_leido}'.")
                            raise Exception("Portal ignoró el filtro de búsqueda de distrito")
                        else:
                            print(f"[SCRAPER] ✓ Validación de filtro correcta (Tarjeta indica '{distrito_leido}')")
                except Exception as e_val:
                    if "Portal ignoró" in str(e_val):
                        raise e_val
                    print(f"[SCRAPER] Advertencia durante validación cruzada del filtro: {e_val}")
                    
            exito_filtro = True

        except Exception as e:
            print(f"[SCRAPER] ⚠ Falla al administrar el modal de distritos {distrito}: {e}")
            exito_filtro = False

        if not exito_filtro:
            fallos_filtro += 1
            print(f"[SCRAPER] ⚠ Detectado fallo en carga de {distrito} (Intento {fallos_filtro}/2). Refrescando vista pacientemente...")
            # Refrescar la vista a ver si soluciona el problema de Angular
            page = _navegar_a_ofertas(page)
            
            if fallos_filtro >= 2:
                print("⚠️ Carga de distritos fallida reiteradamente. Iniciando escaneo manual de páginas para garantizar resultados")
                modo_barrido_total = True
                break
            continue

        # --- GUARDIA MEJORADA CON PRIORIDAD Y RETARDO EXTENDIDO ---
        try:
            texto_pagina = page.inner_text("body").lower()
            hay_cero = "0 registros encontrados" in texto_pagina or "no se encontraron resultados" in texto_pagina
            hay_tarjetas = page.locator(".card").count() > 0

            # 3. Prioridad a las Ofertas
            if hay_tarjetas:
                print(f"[SCRAPER] ✓ Se detectaron tarjetas de oferta en {distrito}.")
            elif hay_cero:
                # 4. Aumentar Doble Chequeo a 5s
                print(f"[SCRAPER] ⚠ Detectado '0 registros' sin tarjetas. Esperando 5s térmicos para confirmación (Doble Chequeo)...")
                page.wait_for_timeout(5000)
                
                texto_pagina_2 = page.inner_text("body").lower()
                hay_tarjetas_2 = page.locator(".card").count() > 0
                hay_cero_2 = "0 registros encontrados" in texto_pagina_2 or "no se encontraron resultados" in texto_pagina_2

                if hay_tarjetas_2:
                    print(f"[SCRAPER] 🟢 Falso positivo evitado (Doble Chequeo). Las tarjetas de {distrito} terminaron de cargar en el fondo.")
                elif hay_cero_2:
                    print(f"[SCRAPER] 🛑 Confirmado: Distrito {distrito} tiene 0 registros reales (comprobado). Saltando al siguiente.")
                    page = _navegar_a_ofertas(page)
                    continue
                else:
                    print(f"[SCRAPER] 🟢 Estado incierto pero asumimos que carga ofertas ocultas.")
        except Exception as e:
            print(f"[SCRAPER] Error durante la guardia de 0 registros: {e}")

        print(f"[SCRAPER] ✓ Distrito {distrito} procesado. Iniciando extracción de datos...")
        ofertas_distrito = extraer_todas_paginas(page)
        ofertas_encontradas.extend(ofertas_distrito)
        
        # Reset para el siguiente distrito
        page = _navegar_a_ofertas(page)

    if modo_barrido_total:
        print("\n[BARRIDO TOTAL] Extrayendo TODAS las ofertas sin aplicar filtros en portal...")
        ofertas_barrido = extraer_todas_paginas(page)
        
        # Merge para evitar duplicados en caso de que algún distrito haya sido exitoso antes de fallar
        ids_existentes = {o['id'] for o in ofertas_encontradas}
        for o in ofertas_barrido:
            if o['id'] not in ids_existentes:
                ofertas_encontradas.append(o)

    print(f"[SCRAPER] Fin total. Extracciones útiles enviadas a orquestador: {len(ofertas_encontradas)}")
    return ofertas_encontradas
