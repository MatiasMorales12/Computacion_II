import time

from procfs import listar_senales


def analizador_senales(snapshot, lock, stop_event, config, intervalo=3.0):
    """
    Analizador de señales.
    """
    while not stop_event.is_set():
        limite = int(config.get("limite_senales", 20))
        datos = listar_senales(limite=limite)

        with lock:
            snapshot["senales"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)