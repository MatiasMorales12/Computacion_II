import multiprocessing as mp
import os
import select
import sys
import termios
import time
import tty

from analizadores.resumen import analizador_resumen
from analizadores.memoria import analizador_memoria
from analizadores.fds import analizador_fds
from analizadores.threads import analizador_threads
from analizadores.senales import analizador_senales
from analizadores.scheduling import analizador_scheduling
from analizadores.sistema import analizador_sistema

from display import mostrar_display
from senales import configurar_manejadores_senales, procesar_acciones_senales
from configuracion import cargar_configuracion

ANALIZADOR_POR_VISTA = {
    "1": "resumen",
    "2": "memoria",
    "3": "fds",
    "4": "threads",
    "5": "senales",
    "6": "scheduling",
    "7": "sistema",
}

NOMBRE_VISTA = {
    "1": "Resumen",
    "2": "Memoria",
    "3": "FDs",
    "4": "Threads",
    "5": "Señales",
    "6": "Scheduling",
    "7": "Sistema",
}


def crear_intervalos_compartidos(config):
    """
    Crea un multiprocessing.Value por analizador.

    Cada Value guarda el intervalo de refresco propio de ese analizador.
    Esto permite modificarlo en caliente desde la TUI con + y -.
    """
    base = float(config.get("refresh_interval", 2.0))

    return {
        "resumen": mp.Value("d", base),
        "memoria": mp.Value("d", base),
        "fds": mp.Value("d", base),
        "threads": mp.Value("d", base),
        "senales": mp.Value("d", base),
        "scheduling": mp.Value("d", base),
        "sistema": mp.Value("d", base),
    }


def obtener_intervalo_vista(intervalos, vista_actual):
    """
    Devuelve el intervalo actual asociado a la vista seleccionada.
    """
    clave = ANALIZADOR_POR_VISTA.get(vista_actual, "resumen")
    intervalo = intervalos[clave]

    with intervalo.get_lock():
        return float(intervalo.value)


def ajustar_intervalo_vista(intervalos, vista_actual, delta):
    """
    Ajusta en caliente el intervalo del analizador de la vista activa.

    Se limita el mínimo a 0.2 segundos para evitar refrescos excesivos.
    """
    clave = ANALIZADOR_POR_VISTA.get(vista_actual, "resumen")
    intervalo = intervalos[clave]

    with intervalo.get_lock():
        nuevo = max(0.2, round(float(intervalo.value) + delta, 2))
        intervalo.value = nuevo

    return clave, nuevo


def iniciar_procesos(snapshot, lock, stop_event, config, intervalos):
    """
    Crea e inicia los procesos analizadores.

    Cada analizador corre como un proceso separado.
    Todos escriben sus resultados en el snapshot compartido.
    """
    procesos = [
        mp.Process(
            target=analizador_resumen,
            args=(snapshot, lock, stop_event, config, intervalos["resumen"]),
            name="analizador_resumen",
        ),
        mp.Process(
            target=analizador_memoria,
            args=(snapshot, lock, stop_event, config, intervalos["memoria"]),
            name="analizador_memoria",
        ),
        mp.Process(
            target=analizador_fds,
            args=(snapshot, lock, stop_event, config, intervalos["fds"]),
            name="analizador_fds",
        ),
        mp.Process(
            target=analizador_threads,
            args=(snapshot, lock, stop_event, config, intervalos["threads"]),
            name="analizador_threads",
        ),
        mp.Process(
            target=analizador_senales,
            args=(snapshot, lock, stop_event, config, intervalos["senales"]),
            name="analizador_senales",
        ),
        mp.Process(
            target=analizador_scheduling,
            args=(snapshot, lock, stop_event, config, intervalos["scheduling"]),
            name="analizador_scheduling",
        ),
        mp.Process(
            target=analizador_sistema,
            args=(snapshot, lock, stop_event, config, intervalos["sistema"]),
            name="analizador_sistema",
        ),
    ]

    for proceso in procesos:
        proceso.start()

    return procesos


def detener_procesos(procesos, stop_event):
    """
    Detiene los procesos hijos de forma ordenada.
    """
    stop_event.set()

    for proceso in procesos:
        proceso.join(timeout=2)

    for proceso in procesos:
        if proceso.is_alive():
            proceso.terminate()
            proceso.join()


def leer_tecla_no_bloqueante():
    """
    Lee una tecla sin frenar el programa.

    Tambien interpreta teclas especiales:
    - flecha arriba
    - flecha abajo
    - Enter
    - Escape
    """
    if not sys.stdin.isatty():
        return None

    disponibles, _, _ = select.select([sys.stdin], [], [], 0)

    if not disponibles:
        return None

    tecla = sys.stdin.read(1)

    if tecla == "\x1b":
        secuencia = ""

        for _ in range(2):
            disponibles, _, _ = select.select([sys.stdin], [], [], 0.01)
            if disponibles:
                secuencia += sys.stdin.read(1)

        if secuencia == "[A":
            return "UP"
        if secuencia == "[B":
            return "DOWN"

        return "ESC"

    if tecla in ["\n", "\r"]:
        return "ENTER"

    return tecla


def mostrar_estado_senales(control):
    """
    Muestra informacion de la ultima señal recibida.
    """
    ultima = control.get("ultima_senal", "-")
    mensaje = control.get("mensaje", "")
    verbose = control.get("verbose", False)

    print()
    print(f"PID principal para pruebas con kill: {os.getpid()}")
    print(f"Ultima señal: {ultima}")

    if mensaje:
        print(f"Mensaje: {mensaje}")

    print(f"Verbose: {verbose}")
    print(f"Analizador activo: {control.get('analizador_actual', '-')}")
    print(f"Intervalo activo: {control.get('intervalo_actual', '-')} s")
    print()
    print("Teclas: 1-7 o r/m/f/t/s/p/g cambiar vista | + acelerar | - desacelerar | q salir")
    print("Extras: ↑/↓ seleccion | Enter pin | / filtro | u actualizar | c limpiar | h/? ayuda")
    print("Señales: SIGINT/SIGTERM salir | SIGHUP recargar | SIGUSR1 dump | SIGUSR2 verbose | SIGWINCH repintar")


def ejecutar_monitor(snapshot, lock, stop_event, control, config, intervalos):
    """
    Loop principal del monitor.

    Teclas:
    1 = Resumen
    2 = Memoria
    3 = FDs
    4 = Threads
    5 = Señales
    6 = Scheduling
    7 = Sistema
    q = Salir
    """
    vista_actual = "1"

    fd = sys.stdin.fileno()
    configuracion_original = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)

        while not stop_event.is_set():
            procesar_acciones_senales(snapshot, lock, control, config)

            tecla = leer_tecla_no_bloqueante()

            vista_por_letra = {
                "r": "1",
                "m": "2",
                "f": "3",
                "t": "4",
                "s": "5",
                "p": "6",
                "g": "7",
            }

            if control.get("modo_busqueda"):
                if tecla == "ENTER":
                    control["modo_busqueda"] = False
                    control["seleccion"] = 0
                    control["mensaje"] = f"Filtro aplicado: {control.get('filtro', '') or '(sin filtro)'}"

                elif tecla == "ESC":
                    control["modo_busqueda"] = False
                    control["filtro"] = ""
                    control["seleccion"] = 0
                    control["mensaje"] = "Busqueda cancelada"

                elif tecla in ["\x7f", "\b"]:
                    control["filtro"] = control.get("filtro", "")[:-1]
                    control["seleccion"] = 0

                elif tecla is not None and len(tecla) == 1 and tecla.isprintable():
                    control["filtro"] = control.get("filtro", "") + tecla
                    control["seleccion"] = 0

            elif tecla in ["1", "2", "3", "4", "5", "6", "7"]:
                vista_actual = tecla
                control["seleccion"] = 0
                control["mensaje"] = f"Vista cambiada a {NOMBRE_VISTA.get(vista_actual, vista_actual)}"

            elif tecla is not None and tecla.lower() in vista_por_letra:
                vista_actual = vista_por_letra[tecla.lower()]
                control["seleccion"] = 0
                control["mensaje"] = f"Vista cambiada a {NOMBRE_VISTA.get(vista_actual, vista_actual)}"

            elif tecla == "UP":
                control["seleccion"] = max(0, int(control.get("seleccion", 0)) - 1)

            elif tecla == "DOWN":
                control["seleccion"] = int(control.get("seleccion", 0)) + 1

            elif tecla == "ENTER":
                pid = control.get("pid_seleccionado")

                if pid is None:
                    control["mensaje"] = "No hay proceso seleccionado para fijar"
                elif control.get("pid_pineado") == pid:
                    control["pid_pineado"] = None
                    control["mensaje"] = f"PID {pid} desfijado"
                else:
                    control["pid_pineado"] = pid
                    control["mensaje"] = f"PID {pid} fijado en panel de detalle"

            elif tecla == "/":
                control["modo_busqueda"] = True
                control["filtro"] = ""
                control["seleccion"] = 0
                control["mensaje"] = "Modo busqueda activo"

            elif tecla in ["u", "U"]:
                control["mensaje"] = "Actualizacion manual solicitada"

            elif tecla in ["c", "C"]:
                control["filtro"] = ""
                control["pid_pineado"] = None
                control["pid_seleccionado"] = None
                control["seleccion"] = 0
                control["mensaje"] = "Filtro, seleccion y pin limpiados"

            elif tecla in ["h", "H", "?"]:
                control["mostrar_ayuda"] = not control.get("mostrar_ayuda", False)
                control["mensaje"] = "Ayuda visible" if control["mostrar_ayuda"] else "Ayuda oculta"

            elif tecla in ["+", "="]:
                clave, nuevo = ajustar_intervalo_vista(intervalos, vista_actual, -0.2)
                control["analizador_actual"] = clave
                control["intervalo_actual"] = nuevo
                control["mensaje"] = f"Intervalo de {clave} ajustado a {nuevo} s"

            elif tecla in ["-", "_"]:
                clave, nuevo = ajustar_intervalo_vista(intervalos, vista_actual, 0.2)
                control["analizador_actual"] = clave
                control["intervalo_actual"] = nuevo
                control["mensaje"] = f"Intervalo de {clave} ajustado a {nuevo} s"

            elif tecla in ["q", "Q"]:
                break

            mostrar_display(snapshot, lock, vista_actual, control)
            mostrar_estado_senales(control)

            time.sleep(float(config.get("refresh_interval", 0.5)))

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, configuracion_original)


def main():
    """
    Entry point del monitor.

    Crea:
    - Manager.dict para snapshot compartido
    - Lock para evitar escrituras simultaneas
    - Event para avisar a los hijos que deben terminar
    - 7 procesos analizadores
    - Display interactivo con vistas
    - Manejadores de señales
    """
    with mp.Manager() as manager:
        snapshot = manager.dict()
        lock = manager.RLock()
        stop_event = mp.Event()
        config = manager.dict(cargar_configuracion())

        control = {
            "ultima_senal": "-",
            "mensaje": "",
            "dump_json": False,
            "recargar_config": False,
            "verbose": False,
            "repintar": False,
            "seleccion": 0,
            "pid_seleccionado": None,
            "pid_pineado": None,
            "filtro": "",
            "modo_busqueda": False,
            "mostrar_ayuda": False,
        }

        intervalos = crear_intervalos_compartidos(config)

        procesos = iniciar_procesos(snapshot, lock, stop_event, config, intervalos)

        # Configuramos señales solo en el proceso principal.
        configurar_manejadores_senales(stop_event, control)

        # Damos tiempo para que los analizadores carguen el primer snapshot.
        time.sleep(2)

        try:
            ejecutar_monitor(snapshot, lock, stop_event, control, config, intervalos)

        finally:
            detener_procesos(procesos, stop_event)
            print("Monitor finalizado correctamente.")


if __name__ == "__main__":
    main()