import time

from procfs import sistema_global


def analizador_sistema(snapshot, lock, stop_event, intervalo=2.0):
    """
    Proceso analizador de sistema global.

    Lee datos generales del sistema:
    CPU, memoria, load average, procesos y uptime.
    """
    while not stop_event.is_set():
        datos = sistema_global()

        with lock:
            snapshot["sistema"] = {
                "timestamp": time.time(),
                "datos": datos,
            }

        stop_event.wait(intervalo)