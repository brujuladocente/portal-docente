# -*- coding: utf-8 -*-
"""
Formateo y envío de correos electrónicos vía Gmail (smtplib y email.mime).
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

LINK_BAJA = "https://docs.google.com/forms/d/e/1FAIpQLSdn6pJoHFKmBdUKqyyLGYsbf7MBx5lqP-Q6EMXWMZSUiEhH8w/viewform?usp=sharing&ouid=106040616818185769622"

def enviar_correo(ofertas, destinatario, nombre="Colega"):
    """
    Envía un resumen de las ofertas filtradas por correo usando HTML simple al destinatario especificado.
    """
    if not ofertas:
        return

    remitente = os.environ.get("EMAIL_REMITENTE")
    password = os.environ.get("EMAIL_PASSWORD")

    if not remitente or not password:
        print("INFO: No configuró credenciales de correo (EMAIL_REMITENTE / EMAIL_PASSWORD). Saltando envío de email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Alerta Lector ABC: {len(ofertas)} nuevas ofertas docentes en tus distritos"
    msg['From'] = remitente
    msg['To'] = destinatario

    html = f"""
    <div style="font-family: Arial, sans-serif; color: #222;">
      <p>Hola, <strong>{nombre}</strong>! Encontramos estas ofertas para vos:</p>
    </div>
    """
    
    for o in ofertas:
        html += f"""
        <div style="font-family: Arial, sans-serif; border-left: 4px solid #800080; padding: 12px 16px; margin-bottom: 14px; background: #f9f9f9;">
          <h3 style="color: #800080; margin: 0 0 6px 0;">{o.get('encabezado', 'N/A').strip()}</h3>
          <p style="margin: 3px 0; color: #333;">
            <b>Nivel:</b> {o.get('nivel', 'Desconocido').strip()} &nbsp;|&nbsp;
            <b>Escuela:</b> {o.get('escuela', 'Desconocido').strip()}
          </p>
          <p style="margin: 3px 0; color: #333;"><b>Horarios:</b> {o.get('horarios', 'Ver en Portal').strip()}</p>
          <p style="margin: 3px 0; color: #555;"><b>Observaciones:</b> {o.get('observaciones', '-').strip()}</p>
          <p style="margin: 3px 0; color: #333;"><b>Nro. IGE:</b> {o.get('ige', 'Desconocido').strip()}</p>
        </div>
        """
    
    html += "<p>Ingresa a <a href='https://misservicios.abc.gob.ar/actos.publicos.digitales/'>Actos Públicos Digitales</a> para ver detalles completos y postularte.</p>"
    html += f"""
    <hr style="border: none; border-top: 1px solid #ddd; margin: 24px 0;">
    <p style="font-size: 13px; color: #555;">
      ¿Ya conseguiste tus horas? Si no querés recibir más alertas, podés darte de baja acá: 
      <a href="{LINK_BAJA}" style="color: #6c3483; text-decoration: underline;">Solicitar baja</a>
    </p>
    <p style="font-size: 11px; color: #999; margin-top: 10px;">
      <b>Bot Automático Lector ABC</b> | Automate & Professionalize
    </p>
    """

    parte_html = MIMEText(html, 'html')
    msg.attach(parte_html)

    try:
        # Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        print(f"Correo de notificación enviado con éxito a {destinatario}: {len(ofertas)} ofertas notificadas.")
    except Exception as e:
        print(f"Error crítico al enviar el correo a {destinatario}: {e}")
