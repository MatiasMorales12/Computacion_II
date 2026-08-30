import time


def limpiar_pantalla():
    """
    Limpia la pantalla usando una secuencia ANSI.
    Funciona en terminales Linux.
    """
    print("\033c", end="")


def estado_modulo(snapshot, nombre):
    """
    Indica si una vista ya cargó datos en el snapshot.
    """
    paquete = snapshot.get(nombre, {})

    if paquete.get("datos") is not None:
        return "OK"

    return "..."


def mostrar_cabecera(vista_actual):
    """
    Muestra la cabecera general del monitor.
    """
    print("=== TP1 MONITOR DE PROCESOS ===")
    print()
    print("Vistas disponibles:")
    print("  1 Resumen | 2 Memoria | 3 FDs | 4 Threads | 5 Señales | 6 Scheduling | 7 Sistema | q Salir")
    print(f"Vista actual: {vista_actual}")
    print("-" * 110)


def mostrar_estado_analizadores(snapshot):
    """
    Muestra si cada analizador ya cargó datos.
    """
    print("Analizadores:")
    print(f"  Resumen:     {estado_modulo(snapshot, 'resumen')}")
    print(f"  Memoria:     {estado_modulo(snapshot, 'memoria')}")
    print(f"  FDs:         {estado_modulo(snapshot, 'fds')}")
    print(f"  Threads:     {estado_modulo(snapshot, 'threads')}")
    print(f"  Señales:     {estado_modulo(snapshot, 'senales')}")
    print(f"  Scheduling:  {estado_modulo(snapshot, 'scheduling')}")
    print(f"  Sistema:     {estado_modulo(snapshot, 'sistema')}")
    print()


def mostrar_vista_resumen(snapshot):
    """
    Vista 1: resumen general de procesos.
    """
    resumen = snapshot.get("resumen", {}).get("datos", [])

    print("=== VISTA 1: RESUMEN DE PROCESOS ===")
    print()
    print("PID     PPID    USER        EST  THR   CPU%    RSS(KB)   COMANDO")
    print("-" * 105)

    for proc in resumen[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['ppid']:<7} "
            f"{proc['usuario']:<10} "
            f"{proc['estado']:<4} "
            f"{proc['threads']:<5} "
            f"{float(proc.get('cpu_pct', 0.0)):<7.2f} "
            f"{proc['rss_kb']:<9} "
            f"{proc['comando'][:45]}"
        )


def mostrar_vista_memoria(snapshot):
    """
    Vista 2: informacion de memoria de procesos.
    """
    memoria = snapshot.get("memoria", {}).get("datos", [])

    print("=== VISTA 2: MEMORIA ===")
    print()
    print("PID     NOMBRE              VmRSS(KB)  TEXT     DATA     HEAP     STACK    SHARED   COMANDO/MAPS")
    print("-" * 115)

    for proc in memoria[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['nombre']:<18} "
            f"{proc['vmrss_kb']:<10} "
            f"{proc.get('map_text_kb', 0):<8} "
            f"{proc.get('map_data_kb', 0):<8} "
            f"{proc.get('map_heap_kb', 0):<8} "
            f"{proc.get('map_stack_kb', 0):<8} "
            f"{proc.get('map_shared_kb', 0):<8} "
            f"total_maps={proc.get('map_total_kb', 0)} KB"
        )


def mostrar_vista_fds(snapshot):
    """
    Vista 3: file descriptors abiertos por proceso.
    """
    procesos = snapshot.get("fds", {}).get("datos", [])

    print("=== VISTA 3: FILE DESCRIPTORS ===")
    print()

    for proc in procesos[:8]:
        print(f"PID {proc['pid']} - {proc['nombre']} - FDs abiertos: {proc['cantidad_fds']}")
        print("-" * 90)

        for fd in proc["fds"]:
            destino = fd["destino"][:60]
            print(f"  FD {fd['fd']:<3} Tipo: {fd['tipo']:<10} Destino: {destino}")

        print()


def mostrar_vista_threads(snapshot):
    """
    Vista 4: threads por proceso.
    """
    procesos = snapshot.get("threads", {}).get("datos", [])

    print("=== VISTA 4: THREADS ===")
    print()

    for proc in procesos[:8]:
        print(f"PID {proc['pid']} - {proc['nombre']} - Threads: {proc['cantidad_threads']}")
        print("-" * 100)

        for thread in proc["threads"]:
            print(
                f"  TID {thread['tid']:<7} "
                f"Nombre: {thread['nombre']:<22} "
                f"Estado: {thread['estado']:<3} "
                f"CPU ticks: {thread['cpu_ticks']:<8} "
                f"Ctx V/I: {thread['ctx_voluntarios']}/{thread['ctx_involuntarios']}"
            )

        print()


def texto_senales(senales, maximo=4):
    """
    Convierte una lista de señales en texto corto.
    """
    if not senales:
        return "-"

    texto = ",".join(senales[:maximo])

    if len(senales) > maximo:
        texto += ",..."

    return texto


def mostrar_vista_senales(snapshot):
    """
    Vista 5: señales bloqueadas, ignoradas y capturadas.
    """
    procesos = snapshot.get("senales", {}).get("datos", [])

    print("=== VISTA 5: SEÑALES ===")
    print()
    print("PID     NOMBRE              BLOQUEADAS           IGNORADAS            HANDLER")
    print("-" * 100)

    for proc in procesos[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['nombre']:<18} "
            f"{texto_senales(proc['sigblk']):<20} "
            f"{texto_senales(proc['sigign']):<20} "
            f"{texto_senales(proc['sigcgt']):<20}"
        )

    print()
    print("BLOQUEADAS = SigBlk | IGNORADAS = SigIgn | HANDLER = SigCgt")


def mostrar_vista_scheduling(snapshot):
    """
    Vista 6: scheduling de procesos.
    """
    procesos = snapshot.get("scheduling", {}).get("datos", [])

    print("=== VISTA 6: SCHEDULING ===")
    print()
    print("PID     NOMBRE              EST NICE PRI  POLICY   RT  CPU-AFF  CTX-V/I       PGID    SID")
    print("-" * 110)

    for proc in procesos[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['nombre']:<18} "
            f"{proc['estado']:<3} "
            f"{proc['nice']:<4} "
            f"{proc['priority']:<4} "
            f"{proc['policy']:<8} "
            f"{proc['rt_priority']:<3} "
            f"{proc['cpu_affinity']:<8} "
            f"{proc['ctx_voluntarios']}/{proc['ctx_involuntarios']:<10} "
            f"{proc['pgid']:<7} "
            f"{proc['sid']:<7}"
        )


def kb_a_mb(valor_kb):
    """
    Convierte KB a MB.
    """
    return round(valor_kb / 1024, 2)


def mostrar_vista_sistema(snapshot):
    """
    Vista 7: informacion global del sistema.
    """
    sistema = snapshot.get("sistema", {}).get("datos", {})

    print("=== VISTA 7: SISTEMA GLOBAL ===")
    print()

    if not sistema:
        print("Esperando datos del sistema...")
        return

    cpu = sistema.get("cpu", {})
    memoria = sistema.get("memoria", {})
    loadavg = sistema.get("loadavg", {})
    uptime = sistema.get("uptime", {})
    procesos = sistema.get("procesos", {})

    print("CPU global por delta (/proc/stat):")
    print(f"  Uso:    {float(cpu.get('uso_pct', 0)):.2f} %")
    print(f"  User:   {float(cpu.get('user_pct', 0)):.2f} %")
    print(f"  System: {float(cpu.get('system_pct', 0)):.2f} %")
    print(f"  Idle:   {float(cpu.get('idle_pct', 0)):.2f} %")
    print(f"  IOWait: {float(cpu.get('iowait_pct', 0)):.2f} %")
    print()

    print("Load average:")
    print(f"  1 min:  {loadavg.get('load_1', '?')}")
    print(f"  5 min:  {loadavg.get('load_5', '?')}")
    print(f"  15 min: {loadavg.get('load_15', '?')}")
    print()

    print("Memoria:")
    print(f"  Total:   {kb_a_mb(memoria.get('mem_total_kb', 0))} MB")
    print(f"  Libre:   {kb_a_mb(memoria.get('mem_free_kb', 0))} MB")
    print(f"  Buffers: {kb_a_mb(memoria.get('buffers_kb', 0))} MB")
    print(f"  Cached:  {kb_a_mb(memoria.get('cached_kb', 0))} MB")
    print(f"  Swap:    {kb_a_mb(memoria.get('swap_total_kb', 0))} MB")
    print()

    print("Procesos:")
    print(f"  Total procesos: {procesos.get('procesos_totales', 0)}")
    print(f"  Total threads:  {procesos.get('threads_totales', 0)}")
    print(f"  Zombies:        {procesos.get('zombies', 0)}")
    print(f"  Por estado:     {procesos.get('por_estado', {})}")
    print()

    print("Uptime:")
    print(f"  Segundos activo: {round(uptime.get('uptime_segundos', 0), 2)}")


def _texto_proceso(proc):
    """
    Convierte los datos principales de un proceso a texto para poder filtrar.
    """
    partes = []

    if isinstance(proc, dict):
        for valor in proc.values():
            if isinstance(valor, (str, int, float, bool)):
                partes.append(str(valor))

    return " ".join(partes).lower()


def _aplicar_filtro_snapshot(snapshot, control):
    """
    Aplica un filtro simple sobre las listas de procesos de cada vista.
    """
    filtro = str(control.get("filtro", "")).strip().lower() if control else ""

    if not filtro:
        return snapshot

    copia = dict(snapshot)

    for clave in ["resumen", "memoria", "fds", "threads", "scheduling"]:
        entrada = snapshot.get(clave, {})

        if not isinstance(entrada, dict):
            continue

        datos = entrada.get("datos", [])

        if not isinstance(datos, list):
            continue

        nueva_entrada = dict(entrada)
        nueva_entrada["datos"] = [
            proc for proc in datos
            if filtro in _texto_proceso(proc)
        ]
        copia[clave] = nueva_entrada

    return copia


def _procesos_de_vista(snapshot, vista_actual):
    """
    Devuelve la lista de procesos asociada a la vista activa.
    """
    clave_por_vista = {
        "1": "resumen",
        "2": "memoria",
        "3": "fds",
        "4": "threads",
        "6": "scheduling",
    }

    clave = clave_por_vista.get(vista_actual)

    if not clave:
        return []

    entrada = snapshot.get(clave, {})

    if not isinstance(entrada, dict):
        return []

    datos = entrada.get("datos", [])

    if not isinstance(datos, list):
        return []

    return datos


def _buscar_proceso_por_pid(snapshot, pid):
    """
    Busca un proceso por PID dentro de las vistas con datos por proceso.
    """
    if pid is None:
        return None

    for clave in ["resumen", "memoria", "fds", "threads", "scheduling"]:
        entrada = snapshot.get(clave, {})

        if not isinstance(entrada, dict):
            continue

        for proc in entrada.get("datos", []):
            if str(proc.get("pid")) == str(pid):
                return proc

    return None


def _mostrar_datos_proceso(proc):
    """
    Imprime un resumen compacto del proceso seleccionado o fijado.
    """
    if not proc:
        print("No hay datos del proceso seleccionado.")
        return

    pid = proc.get("pid", "-")
    nombre = proc.get("nombre", proc.get("comando", "-"))
    usuario = proc.get("usuario", "-")
    estado = proc.get("estado", "-")
    cpu = proc.get("cpu_pct", "-")
    rss = proc.get("rss_kb", proc.get("vmrss_kb", "-"))
    threads = proc.get("threads", proc.get("cantidad_threads", "-"))
    fds = proc.get("cantidad_fds", "-")

    print(
        f"PID {pid} | Nombre/Comando: {str(nombre)[:45]} | "
        f"Usuario: {usuario} | Estado: {estado}"
    )
    print(f"CPU%: {cpu} | RSS/VmRSS(KB): {rss} | Threads: {threads} | FDs: {fds}")


def mostrar_panel_detalle(snapshot, vista_actual, control):
    """
    Muestra seleccion, filtro, ayuda y proceso fijado.
    """
    if control is None:
        return

    procesos = _procesos_de_vista(snapshot, vista_actual)

    print()
    print("=== PANEL DE DETALLE ===")

    filtro = control.get("filtro", "")
    modo_busqueda = control.get("modo_busqueda", False)
    pid_pineado = control.get("pid_pineado")

    print(
        f"Filtro: {filtro or '-'} "
        f"{'(escribiendo...)' if modo_busqueda else ''} | "
        f"Pin: {pid_pineado or '-'}"
    )

    if procesos:
        seleccion = int(control.get("seleccion", 0))
        seleccion = max(0, min(seleccion, len(procesos) - 1))
        control["seleccion"] = seleccion

        seleccionado = procesos[seleccion]
        control["pid_seleccionado"] = seleccionado.get("pid")

        print(f"Seleccion visible: {seleccion + 1}/{len(procesos)}")
        print("Proceso seleccionado:")
        _mostrar_datos_proceso(seleccionado)
    else:
        control["pid_seleccionado"] = None
        print("Esta vista no tiene procesos seleccionables o el filtro no encontro resultados.")

    if pid_pineado is not None:
        print()
        print("Proceso fijado:")
        _mostrar_datos_proceso(_buscar_proceso_por_pid(snapshot, pid_pineado))

    if control.get("mostrar_ayuda", False):
        print()
        print("Ayuda:")
        print("  1-7 o r/m/f/t/s/p/g : cambiar de vista")
        print("  arriba/abajo        : mover seleccion")
        print("  Enter               : fijar/desfijar PID seleccionado")
        print("  /                   : buscar/filtrar por texto")
        print("  + / -               : acelerar/desacelerar analizador activo")
        print("  u                   : marcar actualizacion manual")
        print("  c                   : limpiar filtro, seleccion y pin")
        print("  h o ?               : mostrar/ocultar ayuda")
        print("  q                   : salir")


def mostrar_display(snapshot, lock, vista_actual, control=None):
    """
    Muestra la vista seleccionada.
    """
    with lock:
        copia = dict(snapshot)

    copia_filtrada = _aplicar_filtro_snapshot(copia, control or {})

    limpiar_pantalla()
    mostrar_cabecera(vista_actual)
    mostrar_estado_analizadores(copia)

    if vista_actual == "1":
        mostrar_vista_resumen(copia_filtrada)
    elif vista_actual == "2":
        mostrar_vista_memoria(copia_filtrada)
    elif vista_actual == "3":
        mostrar_vista_fds(copia_filtrada)
    elif vista_actual == "4":
        mostrar_vista_threads(copia_filtrada)
    elif vista_actual == "5":
        mostrar_vista_senales(copia_filtrada)
    elif vista_actual == "6":
        mostrar_vista_scheduling(copia_filtrada)
    elif vista_actual == "7":
        mostrar_vista_sistema(copia_filtrada)
    else:
        print("Vista desconocida.")

    mostrar_panel_detalle(copia_filtrada, vista_actual, control)

    print()
    print(f"Actualizado: {time.strftime('%H:%M:%S')}")