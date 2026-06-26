import json
import os
import signal
import time
from pathlib import Path


def convertir_a_serializable(objeto):
    """
    Convierte estructuras compartidas por multiprocessing en objetos normales
    para poder guardarlas como JSON.
    """
    if isinstance(objeto, dict):
        return {
            str(clave): convertir_a_serializable(valor)
            for clave, valor in objeto.items()
        }

    if isinstance(objeto, list):
        return [convertir_a_serializable(item) for item in objeto]

    if isinstance(objeto, tuple):
        return [convertir_a_serializable(item) for item in objeto]

    return objeto


def guardar_dump_json(snapshot, lock, carpeta="dumps"):
    """
    Guarda una copia del snapshot global en un archivo JSON.

    Esto se usa cuando el programa recibe SIGUSR1.
    """
    Path(carpeta).mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    ruta = Path(carpeta) / f"snapshot_{timestamp}.json"

    with lock:
        copia = convertir_a_serializable(dict(snapshot))

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(copia, archivo, indent=4, ensure_ascii=False)

    return str(ruta)


def configurar_manejadores_senales(stop_event, control):
    """
    Configura los manejadores de señales del proceso principal.

    Señales implementadas:
    - SIGINT:  salida ordenada, equivale a Ctrl+C
    - SIGTERM: salida ordenada
    - SIGHUP:  marca solicitud de recarga de configuración
    - SIGUSR1: solicita dump JSON del snapshot
    - SIGUSR2: alterna modo verbose
    - SIGWINCH: repinta pantalla al redimensionar terminal
    """

    def manejar_salida(signum, frame):
        control["ultima_senal"] = signal.Signals(signum).name
        control["mensaje"] = "Solicitud de salida recibida"
        stop_event.set()

    def manejar_sighup(signum, frame):
        control["ultima_senal"] = "SIGHUP"
        control["mensaje"] = "Solicitud de recarga de configuracion"
        control["recargar_config"] = True

    def manejar_sigusr1(signum, frame):
        control["ultima_senal"] = "SIGUSR1"
        control["mensaje"] = "Solicitud de dump JSON"
        control["dump_json"] = True

    def manejar_sigusr2(signum, frame):
        verbose_actual = bool(control.get("verbose", False))
        control["verbose"] = not verbose_actual
        control["ultima_senal"] = "SIGUSR2"
        control["mensaje"] = f"Modo verbose: {control['verbose']}"

    def manejar_sigwinch(signum, frame):
        control["ultima_senal"] = "SIGWINCH"
        control["mensaje"] = "Terminal redimensionada"
        control["repintar"] = True

    signal.signal(signal.SIGINT, manejar_salida)
    signal.signal(signal.SIGTERM, manejar_salida)
    signal.signal(signal.SIGHUP, manejar_sighup)
    signal.signal(signal.SIGUSR1, manejar_sigusr1)
    signal.signal(signal.SIGUSR2, manejar_sigusr2)

    if hasattr(signal, "SIGWINCH"):
        signal.signal(signal.SIGWINCH, manejar_sigwinch)


def procesar_acciones_senales(snapshot, lock, control, config=None):
    """
    Procesa acciones pedidas por señales.

    La idea es que el handler de la señal sea liviano.
    Por eso el handler solo marca flags, y esta funcion hace el trabajo pesado.
    """
    if control.get("dump_json", False):
        ruta = guardar_dump_json(snapshot, lock)
        control["dump_json"] = False
        control["mensaje"] = f"Dump JSON guardado en {ruta}"

    if control.get("recargar_config", False):
        if config is not None:
            from configuracion import cargar_configuracion

            nueva_config = cargar_configuracion()
            config.clear()
            config.update(nueva_config)

        control["recargar_config"] = False
        control["mensaje"] = "Configuracion recargada desde config.json"

    if control.get("repintar", False):
        # El display ya se repinta en cada iteracion.
        # Esta bandera queda para registrar que SIGWINCH fue recibido.
        control["repintar"] = False


def enviar_senal_a_proceso_actual(nombre_senal):
    """
    Funcion auxiliar para pruebas.

    Permite enviar señales al proceso actual desde codigo si hiciera falta.
    """
    pid = os.getpid()
    senal = getattr(signal, nombre_senal)
    os.kill(pid, senal)