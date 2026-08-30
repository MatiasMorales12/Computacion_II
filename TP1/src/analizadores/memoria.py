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

        stop_event.wait(leer_intervalo_compartido(intervalo))