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
    print("PID     PPID    USER        EST  THR   RSS(KB)   COMANDO")
    print("-" * 95)

    for proc in resumen[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['ppid']:<7} "
            f"{proc['usuario']:<10} "
            f"{proc['estado']:<4} "
            f"{proc['threads']:<5} "
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
    print("PID     NOMBRE              VmSize(KB)  VmRSS(KB)   VmData(KB)  VmHWM(KB)   VmSwap(KB)")
    print("-" * 105)

    for proc in memoria[:20]:
        print(
            f"{proc['pid']:<7} "
            f"{proc['nombre']:<18} "
            f"{proc['vmsize_kb']:<11} "
            f"{proc['vmrss_kb']:<11} "
            f"{proc['vmdata_kb']:<11} "
            f"{proc['vmhwm_kb']:<10} "
            f"{proc['vmswap_kb']:<10}"
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

    print("CPU acumulada:")
    print(f"  User:   {cpu.get('user_pct', 0)} %")
    print(f"  System: {cpu.get('system_pct', 0)} %")
    print(f"  Idle:   {cpu.get('idle_pct', 0)} %")
    print(f"  IOWait: {cpu.get('iowait_pct', 0)} %")
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


def mostrar_display(snapshot, lock, vista_actual):
    """
    Muestra la vista seleccionada.
    """
    with lock:
        copia = dict(snapshot)

    limpiar_pantalla()
    mostrar_cabecera(vista_actual)
    mostrar_estado_analizadores(copia)

    if vista_actual == "1":
        mostrar_vista_resumen(copia)
    elif vista_actual == "2":
        mostrar_vista_memoria(copia)
    elif vista_actual == "3":
        mostrar_vista_fds(copia)
    elif vista_actual == "4":
        mostrar_vista_threads(copia)
    elif vista_actual == "5":
        mostrar_vista_senales(copia)
    elif vista_actual == "6":
        mostrar_vista_scheduling(copia)
    elif vista_actual == "7":
        mostrar_vista_sistema(copia)
    else:
        print("Vista desconocida.")

    print()
    print(f"Actualizado: {time.strftime('%H:%M:%S')}")