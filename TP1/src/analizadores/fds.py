def leer_intervalo_compartido(intervalo, valor_por_defecto=2.0):
    """
    Lee un intervalo que puede venir como float o como multiprocessing.Value.
    """
    try:
        with intervalo.get_lock():
            return float(intervalo.value)
    except AttributeError:
        return float(intervalo)
    except (TypeError, ValueError):
        return valor_por_defecto


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

        stop_event.wait(leer_intervalo_compartido(intervalo))