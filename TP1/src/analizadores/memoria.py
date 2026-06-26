import time

from procfs import listar_memoria


def analizador_memoria(snapshot, lock, stop_event, config, intervalo=2.0):
    """
    Analizador de memoria.
    """
    while not stop_event.is_set():
        limite = int(config.get("limite_memoria", 20))
        datos = listar_memoria(limite=limite)

        with lock:
            snapshot["memoria"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)