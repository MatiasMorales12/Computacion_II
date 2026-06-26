"""
Funciones auxiliares para leer informacion del filesystem /proc.

En Linux, /proc es un filesystem virtual que expone informacion del kernel.
Cada proceso tiene una carpeta con su PID, por ejemplo:

/proc/1
/proc/1234
/proc/5678

La idea del TP es leer esos archivos directamente, sin usar psutil.
"""

import os
import pwd
from pathlib import Path


PROC_PATH = Path("/proc")


def listar_pids():
    """
    Devuelve una lista de PIDs existentes en /proc.

    En /proc hay muchas carpetas, pero las carpetas que tienen nombre numerico
    representan procesos.
    """
    pids = []

    for entrada in PROC_PATH.iterdir():
        if entrada.is_dir() and entrada.name.isdigit():
            pids.append(int(entrada.name))

    return sorted(pids)


def leer_archivo_texto(ruta):
    """
    Lee un archivo de texto y devuelve su contenido.

    Algunos procesos pueden terminar mientras los estamos leyendo.
    Por eso capturamos errores y devolvemos None.
    """
    try:
        return Path(ruta).read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None


def leer_status(pid):
    """
    Lee /proc/<pid>/status y lo convierte en un diccionario.

    Ejemplo de linea:
    Name:   bash
    State:  S (sleeping)
    PPid:   1234
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "status")

    if contenido is None:
        return {}

    datos = {}

    for linea in contenido.splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()

    return datos


def leer_cmdline(pid):
    """
    Lee /proc/<pid>/cmdline.

    Este archivo guarda los argumentos separados por caracteres nulos.
    Por eso reemplazamos '\\0' por espacios.
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "cmdline")

    if not contenido:
        return ""

    comando = contenido.replace("\x00", " ").strip()
    return comando


def leer_comm(pid):
    """
    Lee /proc/<pid>/comm.

    Es el nombre corto del comando/proceso.
    Lo usamos cuando cmdline esta vacio.
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "comm")

    if not contenido:
        return ""

    return contenido.strip()


def leer_stat(pid):
    """
    Lee /proc/<pid>/stat y extrae campos importantes.

    Ojo: el campo 2, comm, viene entre parentesis y puede tener espacios.
    Por eso no conviene hacer split directo de toda la linea.
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "stat")

    if contenido is None:
        return {}

    try:
        cierre_parentesis = contenido.rfind(")")
        antes = contenido[:cierre_parentesis + 1]
        despues = contenido[cierre_parentesis + 2:].split()

        pid_str, comm = antes.split(" ", 1)
        comm = comm.strip("()")

        # Despues del parentesis, el primer campo es el estado.
        # Segun proc(5):
        # campo 1 = pid
        # campo 2 = comm
        # campo 3 = state
        # campo 4 = ppid
        state = despues[0]
        ppid = int(despues[1])
        utime = int(despues[11])
        stime = int(despues[12])
        priority = int(despues[15])
        nice = int(despues[16])
        num_threads = int(despues[17])

        return {
            "pid": int(pid_str),
            "comm": comm,
            "state": state,
            "ppid": ppid,
            "utime": utime,
            "stime": stime,
            "priority": priority,
            "nice": nice,
            "num_threads": num_threads,
        }

    except (ValueError, IndexError):
        return {}


def obtener_usuario(uid_texto):
    """
    Convierte el UID numerico en nombre de usuario.

    Ejemplo:
    1000 -> mati
    """
    try:
        uid = int(uid_texto.split()[0])
        return pwd.getpwuid(uid).pw_name
    except (ValueError, KeyError, IndexError):
        return "?"


def obtener_rss_kb(status):
    """
    Obtiene la memoria residente VmRSS desde /proc/<pid>/status.

    Si no existe, devuelve 0.
    """
    vmrss = status.get("VmRSS", "0 kB")

    try:
        return int(vmrss.split()[0])
    except (ValueError, IndexError):
        return 0


def resumen_proceso(pid):
    """
    Construye un resumen basico de un proceso.

    Esta funcion junta informacion de:
    - /proc/<pid>/status
    - /proc/<pid>/stat
    - /proc/<pid>/cmdline
    - /proc/<pid>/comm
    """
    status = leer_status(pid)
    stat = leer_stat(pid)

    if not status or not stat:
        return None

    uid = status.get("Uid", "?")
    gid = status.get("Gid", "?")

    comando = leer_cmdline(pid)

    if not comando:
        comando = leer_comm(pid)

    return {
        "pid": pid,
        "ppid": stat.get("ppid"),
        "usuario": obtener_usuario(uid),
        "uid": uid.split()[0] if uid != "?" else "?",
        "gid": gid.split()[0] if gid != "?" else "?",
        "estado": stat.get("state", "?"),
        "threads": int(status.get("Threads", stat.get("num_threads", 0))),
        "rss_kb": obtener_rss_kb(status),
        "nice": stat.get("nice"),
        "priority": stat.get("priority"),
        "comando": comando,
    }


def listar_resumenes(limite=None):
    """
    Devuelve una lista con resumenes de procesos.

    El parametro limite sirve para probar sin imprimir cientos de procesos.
    """
    procesos = []

    for pid in listar_pids():
        resumen = resumen_proceso(pid)

        if resumen is not None:
            procesos.append(resumen)

        if limite is not None and len(procesos) >= limite:
            break

    return procesos



def obtener_valor_kb(status, clave):
    """
    Obtiene un valor de memoria desde /proc/<pid>/status.

    Ejemplo:
    status["VmRSS"] puede venir como "13872 kB".
    Esta funcion devuelve solamente el numero: 13872.
    """
    valor = status.get(clave, "0 kB")

    try:
        return int(valor.split()[0])
    except (ValueError, IndexError):
        return 0


def memoria_proceso(pid):
    """
    Obtiene informacion de memoria de un proceso leyendo /proc/<pid>/status.
    """
    status = leer_status(pid)

    if not status:
        return None

    return {
        "pid": pid,
        "nombre": status.get("Name", "?"),
        "vmsize_kb": obtener_valor_kb(status, "VmSize"),
        "vmrss_kb": obtener_valor_kb(status, "VmRSS"),
        "vmdata_kb": obtener_valor_kb(status, "VmData"),
        "vmstk_kb": obtener_valor_kb(status, "VmStk"),
        "vmexe_kb": obtener_valor_kb(status, "VmExe"),
        "vmlib_kb": obtener_valor_kb(status, "VmLib"),
        "vmhwm_kb": obtener_valor_kb(status, "VmHWM"),
        "vmswap_kb": obtener_valor_kb(status, "VmSwap"),
    }


def listar_memoria(limite=None):
    """
    Devuelve una lista con informacion de memoria de varios procesos.
    """
    procesos = []

    for pid in listar_pids():
        info = memoria_proceso(pid)

        if info is not None:
            procesos.append(info)

        if limite is not None and len(procesos) >= limite:
            break

    return procesos

def clasificar_fd(destino):
    """
    Clasifica un file descriptor segun el destino del symlink.

    En /proc/<pid>/fd cada FD es un enlace simbolico.
    Ejemplos:
    - socket:[12345]
    - pipe:[12345]
    - /dev/pts/0
    - /home/mati/archivo.txt
    """
    if destino.startswith("socket:"):
        return "socket"

    if destino.startswith("pipe:"):
        return "pipe"

    if destino.startswith("/dev/pts") or destino.startswith("/dev/tty"):
        return "tty"

    if destino.startswith("anon_inode:"):
        return "anon_inode"

    if destino.startswith("/"):
        return "file"

    return "otro"


def fds_proceso(pid, limite_fds=10):
    """
    Lista los file descriptors abiertos de un proceso.

    Lee:
    /proc/<pid>/fd/

    Y para cada FD usa os.readlink para saber a donde apunta.
    """
    ruta_fd = PROC_PATH / str(pid) / "fd"
    resultado = []

    try:
        fds = sorted(os.listdir(ruta_fd), key=lambda x: int(x))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None

    for fd in fds[:limite_fds]:
        ruta = ruta_fd / fd

        try:
            destino = os.readlink(ruta)
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            destino = "?"

        resultado.append(
            {
                "fd": int(fd),
                "tipo": clasificar_fd(destino),
                "destino": destino,
            }
        )

    return {
        "pid": pid,
        "nombre": leer_comm(pid),
        "cantidad_fds": len(fds),
        "fds": resultado,
    }


def listar_fds(limite_procesos=10, limite_fds=5):
    """
    Devuelve informacion de file descriptors de varios procesos.
    """
    procesos = []

    for pid in listar_pids():
        info = fds_proceso(pid, limite_fds=limite_fds)

        if info is not None:
            procesos.append(info)

        if len(procesos) >= limite_procesos:
            break

    return procesos

def leer_status_thread(pid, tid):
    """
    Lee /proc/<pid>/task/<tid>/status.

    Cada thread de Linux aparece dentro de /proc/<pid>/task/
    como una entrada con su propio TID.
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "task" / str(tid) / "status")

    if contenido is None:
        return {}

    datos = {}

    for linea in contenido.splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()

    return datos


def leer_comm_thread(pid, tid):
    """
    Lee el nombre corto de un thread desde /proc/<pid>/task/<tid>/comm.
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "task" / str(tid) / "comm")

    if not contenido:
        return ""

    return contenido.strip()


def leer_stat_thread(pid, tid):
    """
    Lee /proc/<pid>/task/<tid>/stat.

    El formato es parecido a /proc/<pid>/stat.
    Extraemos:
    - estado
    - utime
    - stime
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "task" / str(tid) / "stat")

    if contenido is None:
        return {}

    try:
        cierre_parentesis = contenido.rfind(")")
        despues = contenido[cierre_parentesis + 2:].split()

        estado = despues[0]
        utime = int(despues[11])
        stime = int(despues[12])

        return {
            "estado": estado,
            "utime": utime,
            "stime": stime,
            "cpu_ticks": utime + stime,
        }

    except (ValueError, IndexError):
        return {}


def threads_proceso(pid, limite_threads=10):
    """
    Lista los threads de un proceso.

    Fuente:
    /proc/<pid>/task/
    """
    ruta_task = PROC_PATH / str(pid) / "task"
    resultado = []

    try:
        tids = sorted(os.listdir(ruta_task), key=lambda x: int(x))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None

    for tid in tids[:limite_threads]:
        status = leer_status_thread(pid, tid)
        stat = leer_stat_thread(pid, tid)

        if not status or not stat:
            continue

        voluntarios = status.get("voluntary_ctxt_switches", "0")
        involuntarios = status.get("nonvoluntary_ctxt_switches", "0")

        resultado.append(
            {
                "tid": int(tid),
                "nombre": leer_comm_thread(pid, tid),
                "estado": stat.get("estado", "?"),
                "cpu_ticks": stat.get("cpu_ticks", 0),
                "ctx_voluntarios": voluntarios,
                "ctx_involuntarios": involuntarios,
            }
        )

    return {
        "pid": pid,
        "nombre": leer_comm(pid),
        "cantidad_threads": len(tids),
        "threads": resultado,
    }


def listar_threads(limite_procesos=10, limite_threads=5):
    """
    Devuelve informacion de threads de varios procesos.
    """
    procesos = []

    for pid in listar_pids():
        info = threads_proceso(pid, limite_threads=limite_threads)

        if info is not None:
            procesos.append(info)

        if len(procesos) >= limite_procesos:
            break

    return procesos

def nombre_politica_scheduling(policy_num):
    """
    Convierte el numero de politica de scheduling en un nombre legible.

    Valores comunes en Linux:
    0 = SCHED_OTHER
    1 = SCHED_FIFO
    2 = SCHED_RR
    3 = SCHED_BATCH
    5 = SCHED_IDLE
    6 = SCHED_DEADLINE
    """
    politicas = {
        0: "OTHER",
        1: "FIFO",
        2: "RR",
        3: "BATCH",
        5: "IDLE",
        6: "DEADLINE",
    }

    return politicas.get(policy_num, f"DESCONOCIDA({policy_num})")


def leer_scheduling_stat(pid):
    """
    Lee datos de scheduling desde /proc/<pid>/stat.

    Extraemos:
    - priority
    - nice
    - num_threads
    - utime
    - stime
    - rt_priority
    - policy
    - session id
    - process group id
    """
    contenido = leer_archivo_texto(PROC_PATH / str(pid) / "stat")

    if contenido is None:
        return {}

    try:
        cierre_parentesis = contenido.rfind(")")
        antes = contenido[:cierre_parentesis + 1]
        despues = contenido[cierre_parentesis + 2:].split()

        pid_str, comm = antes.split(" ", 1)
        comm = comm.strip("()")

        # Despues del campo comm:
        # indice 0 -> campo 3: state
        # indice 1 -> campo 4: ppid
        # indice 2 -> campo 5: pgrp
        # indice 3 -> campo 6: session
        # indice 11 -> campo 14: utime
        # indice 12 -> campo 15: stime
        # indice 15 -> campo 18: priority
        # indice 16 -> campo 19: nice
        # indice 17 -> campo 20: num_threads
        # indice 37 -> campo 40: rt_priority
        # indice 38 -> campo 41: policy
        return {
            "pid": int(pid_str),
            "nombre": comm,
            "estado": despues[0],
            "ppid": int(despues[1]),
            "pgid": int(despues[2]),
            "sid": int(despues[3]),
            "utime": int(despues[11]),
            "stime": int(despues[12]),
            "priority": int(despues[15]),
            "nice": int(despues[16]),
            "num_threads": int(despues[17]),
            "rt_priority": int(despues[37]),
            "policy_num": int(despues[38]),
            "policy": nombre_politica_scheduling(int(despues[38])),
        }

    except (ValueError, IndexError):
        return {}


def scheduling_proceso(pid):
    """
    Obtiene informacion de scheduling de un proceso.

    Combina:
    - /proc/<pid>/stat
    - /proc/<pid>/status
    """
    stat = leer_scheduling_stat(pid)
    status = leer_status(pid)

    if not stat or not status:
        return None

    return {
        "pid": pid,
        "nombre": stat.get("nombre", leer_comm(pid)),
        "estado": stat.get("estado", "?"),
        "nice": stat.get("nice", 0),
        "priority": stat.get("priority", 0),
        "policy": stat.get("policy", "?"),
        "rt_priority": stat.get("rt_priority", 0),
        "cpu_affinity": status.get("Cpus_allowed_list", "?"),
        "ctx_voluntarios": status.get("voluntary_ctxt_switches", "0"),
        "ctx_involuntarios": status.get("nonvoluntary_ctxt_switches", "0"),
        "utime": stat.get("utime", 0),
        "stime": stat.get("stime", 0),
        "pgid": stat.get("pgid", "?"),
        "sid": stat.get("sid", "?"),
    }


def listar_scheduling(limite=None):
    """
    Devuelve informacion de scheduling de varios procesos.
    """
    procesos = []

    for pid in listar_pids():
        info = scheduling_proceso(pid)

        if info is not None:
            procesos.append(info)

        if limite is not None and len(procesos) >= limite:
            break

    return procesos

def nombre_senal(numero):
    """
    Devuelve el nombre legible de una señal.

    Ejemplo:
    2  -> SIGINT
    9  -> SIGKILL
    15 -> SIGTERM
    """
    try:
        import signal
        return signal.Signals(numero).name
    except ValueError:
        return f"SIG{numero}"


def decodificar_mascara_senales(valor_hex):
    """
    Decodifica una mascara hexadecimal de señales.

    En /proc/<pid>/status las señales aparecen como mascaras hexadecimales.
    Cada bit representa una señal.

    Ejemplo:
    SigIgn: 0000000000001000

    El bit 0 representa la señal 1, el bit 1 representa la señal 2, etc.
    """
    if not valor_hex:
        return []

    try:
        mascara = int(valor_hex, 16)
    except ValueError:
        return []

    senales = []

    for numero in range(1, 65):
        bit = 1 << (numero - 1)

        if mascara & bit:
            senales.append(nombre_senal(numero))

    return senales


def senales_proceso(pid):
    """
    Obtiene informacion de señales de un proceso.

    Fuente:
    /proc/<pid>/status

    Campos:
    - SigBlk: señales bloqueadas
    - SigIgn: señales ignoradas
    - SigCgt: señales capturadas con handler propio
    - SigPnd: señales pendientes del proceso
    - ShdPnd: señales pendientes compartidas del grupo
    """
    status = leer_status(pid)

    if not status:
        return None

    sigblk_raw = status.get("SigBlk", "0")
    sigign_raw = status.get("SigIgn", "0")
    sigcgt_raw = status.get("SigCgt", "0")
    sigpnd_raw = status.get("SigPnd", "0")
    shdpnd_raw = status.get("ShdPnd", "0")

    return {
        "pid": pid,
        "nombre": status.get("Name", leer_comm(pid)),
        "sigblk_raw": sigblk_raw,
        "sigign_raw": sigign_raw,
        "sigcgt_raw": sigcgt_raw,
        "sigpnd_raw": sigpnd_raw,
        "shdpnd_raw": shdpnd_raw,
        "sigblk": decodificar_mascara_senales(sigblk_raw),
        "sigign": decodificar_mascara_senales(sigign_raw),
        "sigcgt": decodificar_mascara_senales(sigcgt_raw),
        "sigpnd": decodificar_mascara_senales(sigpnd_raw),
        "shdpnd": decodificar_mascara_senales(shdpnd_raw),
    }


def listar_senales(limite=None):
    """
    Devuelve informacion de señales de varios procesos.
    """
    procesos = []

    for pid in listar_pids():
        info = senales_proceso(pid)

        if info is not None:
            procesos.append(info)

        if limite is not None and len(procesos) >= limite:
            break

    return procesos

def leer_meminfo():
    """
    Lee /proc/meminfo y devuelve sus valores en un diccionario.

    Ejemplo de linea:
    MemTotal:       16277052 kB
    """
    contenido = leer_archivo_texto(PROC_PATH / "meminfo")

    if contenido is None:
        return {}

    datos = {}

    for linea in contenido.splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            partes = valor.strip().split()

            try:
                datos[clave] = int(partes[0])
            except (ValueError, IndexError):
                datos[clave] = 0

    return datos


def leer_loadavg():
    """
    Lee /proc/loadavg.

    Los primeros tres valores son la carga promedio:
    - 1 minuto
    - 5 minutos
    - 15 minutos
    """
    contenido = leer_archivo_texto(PROC_PATH / "loadavg")

    if not contenido:
        return {}

    partes = contenido.split()

    return {
        "load_1": partes[0],
        "load_5": partes[1],
        "load_15": partes[2],
        "procesos": partes[3],
        "ultimo_pid": partes[4],
    }


def leer_uptime():
    """
    Lee /proc/uptime.

    Primer valor: segundos desde que arrancó el sistema.
    Segundo valor: tiempo idle acumulado.
    """
    contenido = leer_archivo_texto(PROC_PATH / "uptime")

    if not contenido:
        return {}

    partes = contenido.split()

    try:
        return {
            "uptime_segundos": float(partes[0]),
            "idle_segundos": float(partes[1]),
        }
    except (ValueError, IndexError):
        return {}


def leer_cpu_global():
    """
    Lee la primera linea de /proc/stat.

    Ejemplo:
    cpu  123 456 789 ...

    De aca sacamos tiempos acumulados de CPU.
    Por ahora mostramos porcentajes aproximados sobre el total acumulado.
    """
    contenido = leer_archivo_texto(PROC_PATH / "stat")

    if contenido is None:
        return {}

    for linea in contenido.splitlines():
        if linea.startswith("cpu "):
            partes = linea.split()

            try:
                user = int(partes[1])
                nice = int(partes[2])
                system = int(partes[3])
                idle = int(partes[4])
                iowait = int(partes[5])
                irq = int(partes[6])
                softirq = int(partes[7])
            except (ValueError, IndexError):
                return {}

            total = user + nice + system + idle + iowait + irq + softirq

            if total == 0:
                total = 1

            return {
                "user_pct": round((user / total) * 100, 2),
                "system_pct": round((system / total) * 100, 2),
                "idle_pct": round((idle / total) * 100, 2),
                "iowait_pct": round((iowait / total) * 100, 2),
            }

    return {}


def contar_procesos_por_estado():
    """
    Recorre /proc y cuenta procesos por estado.

    Estados tipicos:
    R = running
    S = sleeping
    D = uninterruptible sleep
    T = stopped
    Z = zombie
    I = idle kernel thread
    """
    conteo = {}
    total_threads = 0

    for pid in listar_pids():
        stat = leer_stat(pid)
        status = leer_status(pid)

        if not stat:
            continue

        estado = stat.get("state", "?")
        conteo[estado] = conteo.get(estado, 0) + 1

        try:
            total_threads += int(status.get("Threads", 0))
        except ValueError:
            pass

    return {
        "por_estado": conteo,
        "procesos_totales": sum(conteo.values()),
        "threads_totales": total_threads,
        "zombies": conteo.get("Z", 0),
    }


def sistema_global():
    """
    Junta informacion global del sistema leyendo varios archivos de /proc.
    """
    meminfo = leer_meminfo()
    loadavg = leer_loadavg()
    uptime = leer_uptime()
    cpu = leer_cpu_global()
    procesos = contar_procesos_por_estado()

    return {
        "cpu": cpu,
        "loadavg": loadavg,
        "memoria": {
            "mem_total_kb": meminfo.get("MemTotal", 0),
            "mem_free_kb": meminfo.get("MemFree", 0),
            "buffers_kb": meminfo.get("Buffers", 0),
            "cached_kb": meminfo.get("Cached", 0),
            "swap_total_kb": meminfo.get("SwapTotal", 0),
            "swap_free_kb": meminfo.get("SwapFree", 0),
        },
        "uptime": uptime,
        "procesos": procesos,
    }