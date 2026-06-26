import json
from pathlib import Path


CONFIG_DEFAULT = {
    "refresh_interval": 0.5,
    "limite_resumen": 20,
    "limite_memoria": 20,
    "limite_fds_procesos": 10,
    "limite_fds": 5,
    "limite_threads_procesos": 10,
    "limite_threads": 5,
    "limite_senales": 20,
    "limite_scheduling": 20,
}


def cargar_configuracion(ruta="config.json"):
    """
    Carga la configuracion desde config.json.

    Si el archivo no existe o tiene un error, usa valores por defecto.
    """
    config = CONFIG_DEFAULT.copy()
    ruta_config = Path(ruta)

    if not ruta_config.exists():
        return config

    try:
        with open(ruta_config, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        if isinstance(datos, dict):
            config.update(datos)

    except (json.JSONDecodeError, OSError):
        # Si el JSON esta mal escrito o no se puede leer,
        # seguimos con valores por defecto.
        pass

    return config