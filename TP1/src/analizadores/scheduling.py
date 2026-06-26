import time

from procfs import listar_scheduling


def analizador_scheduling(snapshot, lock, stop_event, config, intervalo=2.0):
    """
    Analizador de scheduling.
    """
    while not stop_event.is_set():
        limite = int(config.get("limite_scheduling", 20))
        datos = listar_scheduling(limite=limite)

        with lock:
            snapshot["scheduling"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)