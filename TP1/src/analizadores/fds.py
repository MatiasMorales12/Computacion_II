import time

from procfs import listar_fds


def analizador_fds(snapshot, lock, stop_event, config, intervalo=3.0):
    """
    Analizador de file descriptors.
    """
    while not stop_event.is_set():
        limite_procesos = int(config.get("limite_fds_procesos", 10))
        limite_fds = int(config.get("limite_fds", 5))

        datos = listar_fds(
            limite_procesos=limite_procesos,
            limite_fds=limite_fds,
        )

        with lock:
            snapshot["fds"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)