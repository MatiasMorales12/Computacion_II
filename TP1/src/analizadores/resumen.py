import os
import time

from procfs import listar_resumenes


def leer_intervalo_compartido(intervalo, valor_por_defecto=2.0):
    """
    Lee un intervalo desde multiprocessing.Value.

    Si no recibe un Value, usa el valor por defecto.
    """
    if intervalo is None:
        return valor_por_defecto

    try:
        with intervalo.get_lock():
            return float(intervalo.value)
    except AttributeError:
        return float(intervalo)


def obtener_limite_resumen(config):
    """
    Obtiene el limite de procesos para la vista resumen desde config.json.
    """
    try:
        return int(config.get("limite_resumen", 20))
    except (TypeError, ValueError):
        return 20


def calcular_cpu_delta(procesos_actuales, ticks_anteriores, delta_tiempo, clock_ticks):
    """
    Calcula CPU% por proceso usando delta entre dos lecturas.

    Formula:
    delta_ticks = ticks_actuales - ticks_anteriores
    CPU% = delta_ticks / (delta_tiempo * clock_ticks) * 100

    Es un porcentaje respecto de una CPU logica.
    """
    for proc in procesos_actuales:
        pid = proc.get("pid")
        ticks_actuales = int(proc.get("cpu_ticks", 0))

        cpu_pct = 0.0

        if (
            pid in ticks_anteriores
            and delta_tiempo is not None
            and delta_tiempo > 0
            and clock_ticks > 0
        ):
            delta_ticks = max(0, ticks_actuales - ticks_anteriores[pid])
            cpu_pct = (delta_ticks / (delta_tiempo * clock_ticks)) * 100

        proc["cpu_pct"] = round(cpu_pct, 2)

    return procesos_actuales


def analizador_resumen(snapshot, lock, stop_event, config, intervalo=None):
    """
    Proceso analizador de resumen.

    Lee periodicamente /proc, calcula resumenes de procesos y agrega CPU%
    por delta comparando la lectura actual contra la lectura anterior.
    """
    clock_ticks = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK"))

    ticks_anteriores = {}
    tiempo_anterior = None

    while not stop_event.is_set():
        ahora = time.time()
        limite = obtener_limite_resumen(config)

        # Se leen todos los procesos para poder calcular CPU% por delta
        # y luego ordenar por mayor consumo antes de aplicar el limite visual.
        datos = listar_resumenes(limite=None)

        delta_tiempo = None
        if tiempo_anterior is not None:
            delta_tiempo = ahora - tiempo_anterior

        datos = calcular_cpu_delta(datos, ticks_anteriores, delta_tiempo, clock_ticks)

        ticks_anteriores = {
            proc["pid"]: int(proc.get("cpu_ticks", 0))
            for proc in datos
            if "pid" in proc
        }

        datos.sort(
            key=lambda proc: (
                float(proc.get("cpu_pct", 0.0)),
                int(proc.get("rss_kb", 0))
            ),
            reverse=True
        )

        datos = datos[:limite]
        tiempo_anterior = ahora

        with lock:
            snapshot["resumen"] = {
                "timestamp": ahora,
                "datos": datos,
                "delta_tiempo": delta_tiempo,
            }

        stop_event.wait(leer_intervalo_compartido(intervalo, 2.0))
