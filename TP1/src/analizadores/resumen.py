import time

from procfs import listar_resumenes


def analizador_resumen(snapshot, lock, stop_event, config, intervalo=2.0):
    """
    Proceso analizador de resumen.
    """
    while not stop_event.is_set():
        limite = int(config.get("limite_resumen", 20))
        datos = listar_resumenes(limite=limite)

        with lock:
            snapshot["resumen"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)