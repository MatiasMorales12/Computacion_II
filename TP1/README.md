# TP1 - Monitor de Procesos en Linux

Trabajo practico de Computacion II desarrollado en Python sobre GNU/Linux.

El objetivo del proyecto es implementar un monitor de procesos que obtiene informacion real del sistema leyendo directamente el filesystem `/proc`. El programa usa procesos paralelos, memoria compartida, señales del sistema operativo, configuracion dinamica, una TUI simple por terminal y ejecucion mediante Docker.

---

## Objetivos del proyecto

El monitor permite observar distintos aspectos del sistema Linux:

- Resumen de procesos.
- Uso de CPU por proceso.
- Uso de memoria por proceso.
- Segmentos de memoria a partir de `/proc/<pid>/maps`.
- File descriptors abiertos.
- Threads por proceso.
- Señales bloqueadas, ignoradas y capturadas.
- Informacion de scheduling.
- Informacion global del sistema.

Tambien implementa:

- Multiprocessing.
- Snapshot compartido entre procesos.
- Intervalos dinamicos usando memoria compartida.
- Manejo de señales.
- Recarga de configuracion en caliente.
- Ejecucion con Docker.
- Tests automatizados.

---

## Arquitectura general

El proyecto esta dividido en tres partes principales:

1. Una capa de lectura de `/proc`.
2. Una capa de analizadores.
3. Una capa de visualizacion por terminal.

La capa de lectura esta concentrada en `procfs.py`. Ahi estan las funciones que abren y parsean archivos como `/proc/<pid>/stat`, `/proc/<pid>/status`, `/proc/<pid>/fd`, `/proc/<pid>/task`, `/proc/<pid>/maps`, `/proc/stat`, `/proc/meminfo`, `/proc/loadavg` y `/proc/uptime`.

Los analizadores estan en `src/analizadores/`. Cada uno corre como un proceso separado y actualiza una parte del snapshot compartido.

La visualizacion esta en `display.py`, que toma el snapshot y muestra la vista seleccionada.

El archivo `main.py` coordina todo: crea los procesos, inicializa las estructuras compartidas, configura señales, lee teclas y detiene el monitor correctamente.

---

## Estructura del proyecto

```text
TP1/
├── src/
│   ├── analizadores/
│   │   ├── resumen.py
│   │   ├── memoria.py
│   │   ├── fds.py
│   │   ├── threads.py
│   │   ├── senales.py
│   │   ├── scheduling.py
│   │   └── sistema.py
│   ├── configuracion.py
│   ├── display.py
│   ├── main.py
│   ├── procfs.py
│   └── senales.py
├── tests/
│   └── test_procfs.py
├── config.json
├── docker-compose.yml
├── Dockerfile
├── dudas.md
├── README.md
└── requirements.txt