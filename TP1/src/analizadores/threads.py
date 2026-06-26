import time

from procfs import listar_threads


def analizador_threads(snapshot, lock, stop_event, config, intervalo=2.0):
    """
    Analizador de threads.
    """
    while not stop_event.is_set():
        limite_procesos = int(config.get("limite_threads_procesos", 10))
        limite_threads = int(config.get("limite_threads", 5))

        datos = listar_threads(
            limite_procesos=limite_procesos,
            limite_threads=limite_threads,
        )

        with lock:
            snapshot["threads"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)