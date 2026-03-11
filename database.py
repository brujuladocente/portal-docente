"""
Manejo de estado local (SQLite) para registrar ofertas enviadas y evitar duplicados.
"""
import sqlite3
import os

DB_PATH = "ofertas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Guardaremos un ID único para cada oferta enviada (ej. ID de oferta de la plataforma)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ofertas_enviadas (
            id TEXT PRIMARY KEY,
            fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def es_oferta_nueva(oferta_id):
    """
    Retorna True si la oferta no está en la base de datos (es nueva).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM ofertas_enviadas WHERE id = ?', (oferta_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is None

def registrar_oferta(oferta_id):
    """
    Registra el ID de la oferta en la base de datos.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO ofertas_enviadas (id) VALUES (?)', (oferta_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Ya existe
    finally:
        conn.close()

