import time
from pathlib import Path

from procfs import sistema_global


PROC_STAT = Path("/proc/stat")


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
    except (AttributeError, TypeError, ValueError):
        return valor_por_defecto


def leer_cpu_stat_crudo():
    """
    Lee la primera linea de /proc/stat y devuelve los ticks acumulados.

    Formato:
    cpu user nice system idle iowait irq softirq steal guest guest_nice
    """
    try:
        with PROC_STAT.open("r", encoding="utf-8") as archivo:
            linea = archivo.readline().strip()
    except OSError:
        return None

    partes = linea.split()

    if not partes or partes[0] != "cpu":
        return None

    valores = []
    for valor in partes[1:]:
        try:
            valores.append(int(valor))
        except ValueError:
            valores.append(0)

    while len(valores) < 10:
        valores.append(0)

    return {
        "user": valores[0],
        "nice": valores[1],
        "system": valores[2],
        "idle": valores[3],
        "iowait": valores[4],
        "irq": valores[5],
        "softirq": valores[6],
        "steal": valores[7],
        "guest": valores[8],
        "guest_nice": valores[9],
    }


def calcular_cpu_global_delta(actual, anterior):
    """
    Calcula porcentajes globales de CPU usando delta entre dos lecturas.

    No usa valores acumulados directamente para porcentajes.
    Compara:
    lectura anterior de /proc/stat vs lectura actual de /proc/stat.
    """
    if not actual or not anterior:
        return {
            "uso_pct": 0.0,
            "user_pct": 0.0,
            "system_pct": 0.0,
            "idle_pct": 0.0,
            "iowait_pct": 0.0,
        }

    deltas = {}
    for clave, valor_actual in actual.items():
        valor_anterior = anterior.get(clave, 0)
        deltas[clave] = max(0, int(valor_actual) - int(valor_anterior))

    total = sum(deltas.values())

    if total <= 0:
        return {
            "uso_pct": 0.0,
            "user_pct": 0.0,
            "system_pct": 0.0,
            "idle_pct": 0.0,
            "iowait_pct": 0.0,
        }

    user = deltas["user"] + deltas["nice"]
    system = deltas["system"] + deltas["irq"] + deltas["softirq"]
    idle = deltas["idle"]
    iowait = deltas["iowait"]

    uso = total - idle - iowait

    return {
        "uso_pct": round((uso / total) * 100, 2),
        "user_pct": round((user / total) * 100, 2),
        "system_pct": round((system / total) * 100, 2),
        "idle_pct": round((idle / total) * 100, 2),
        "iowait_pct": round((iowait / total) * 100, 2),
    }


def analizador_sistema(snapshot, lock, stop_event, config=None, intervalo=None):
    """
    Proceso analizador de sistema global.

    Lee datos generales del sistema y calcula CPU global por delta
    comparando lecturas sucesivas de /proc/stat.
    """
    cpu_anterior = None

    while not stop_event.is_set():
        ahora = time.time()

        datos = sistema_global()

        cpu_actual = leer_cpu_stat_crudo()
        cpu_delta = calcular_cpu_global_delta(cpu_actual, cpu_anterior)

        datos["cpu"] = cpu_delta
        datos["cpu_raw"] = cpu_actual

        cpu_anterior = cpu_actual

        with lock:
            snapshot["sistema"] = {
                "timestamp": ahora,
                "datos": datos,
            }

        stop_event.wait(leer_intervalo_compartido(intervalo, 2.0))
