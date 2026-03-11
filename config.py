"""
Configuración centralizada y definición de constantes/filtros para el scraper de Lector ABC.
"""
import os
from dotenv import load_dotenv

# Filtro 1: Distritos permitidos en el formato exacto del dropdown
DISTRITOS = [
    "LANUS",
    "L DE ZAMORA",
    "AVELLANEDA"
]

# Filtro 2: Códigos de Nomenclador (Incumbencias - Lista unificada y estricta)
TODOS_LOS_CODIGOS = {
    "/PR", "+3P", "FIA", "CFF", "CCD", "YCS",
    "PIC", "PEE", "ECS", "FCT", "PRA", "PRT"
}
