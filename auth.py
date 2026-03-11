"""
Flujo de inicio de sesión en el portal ABC usando Playwright.
"""
import os
import re
from playwright.sync_api import Page, TimeoutError

def login_abc(page: Page):
    """
    Inyecta las credenciales en el formulario de login y presiona entrar.
    Asume que el scraper ya determinó que estamos en el ESTADO A (Pantalla de login).
    """
    usuario = os.environ.get("ABC_USUARIO")
    clave = os.environ.get("ABC_CLAVE")
    
    if not usuario or not clave:
        raise ValueError("Credenciales no configuradas en el entorno (.env)")

    print("\n[LOGIN] Iniciando inyección de credenciales...")
        
    print("[LOGIN] Buscando formulario de credenciales...")
    try:
        # 1. Campo CUIL - Iteramos tipos básicos genéricos
        print("[LOGIN] Esperando campo CUIL (text/number/email)...")
        cuil_selector = 'input[type="text"], input[type="number"], input[type="email"]'
        page.wait_for_selector(cuil_selector, timeout=15000, state="visible")
        
        textbox_cuil = page.locator(cuil_selector).locator("visible=true").first
        
        print("[LOGIN] Forzando clic en CUIL...")
        textbox_cuil.click(force=True)
        print("[LOGIN] Tipeando CUIL...")
        textbox_cuil.fill(usuario)
        
        # 2. Campo Contraseña
        print("[LOGIN] Esperando campo Contraseña (password)...")
        pass_selector = 'input[type="password"]'
        page.wait_for_selector(pass_selector, timeout=5000, state="visible")
        
        textbox_pass = page.locator(pass_selector).locator("visible=true").first
        print("[LOGIN] Forzando clic en Contraseña...")
        textbox_pass.click(force=True)
        print("[LOGIN] Tipeando Contraseña...")
        textbox_pass.fill(clave)
        
        # 3. Botón ENTRAR usando ENTER sobre el input de pass
        print("[LOGIN] Presionando Enter para enviar el formulario...")
        textbox_pass.press('Enter')
        
    except Exception as e:
        print("\n[ERROR CRÍTICO LOGIN] Falló la interacción con el formulario de inicio de sesión.")
        print(f"[TRACE] Detalle técnico: {type(e).__name__} - {e}")
        
        try:
            # Intento de extraer el HTML de los inputs para debug
            html_inputs = page.evaluate("() => Array.from(document.querySelectorAll('input')).map(el => el.outerHTML)")
            print("\n[DEBUG] HTML de los inputs encontrados en la página:")
            for html in html_inputs:
                print(f"  {html}")
        except Exception as eval_err:
            print(f"[DEBUG] No se pudo extraer el HTML: {eval_err}")
            
        print("\n-> Revisa en la pantalla abierta el selector exacto y pásamelo.\n")
        raise


